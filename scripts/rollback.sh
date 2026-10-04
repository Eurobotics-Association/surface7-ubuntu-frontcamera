#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
source "$ROOT/config/ubuntu.env"

[[ $EUID -ne 0 ]] || { echo "Run as your desktop user; rollback will ask sudo." >&2; exit 1; }
marker="$SURFACE7_LIBDIR/.surface7-ubuntu-frontcamera-owned"
expected_marker="$(cat "$ROOT/config/ownership-marker")"
sudo -v
if ! sudo test -f "$marker"; then
    echo "Refusing rollback: ownership marker is missing from $SURFACE7_LIBDIR." >&2
    exit 1
fi
actual_marker="$(sudo cat "$marker")"
if [[ "$actual_marker" != "$expected_marker" ]]; then
    echo "Refusing rollback: ownership marker does not match this repository." >&2
    exit 1
fi

backup="$SURFACE7_BACKUP_ROOT/$SURFACE7_TARGET_KERNEL"
module_dir="/lib/modules/$SURFACE7_TARGET_KERNEL/updates/extra"

restore_or_remove() {
    local path="$1"
    local saved="$backup$path"
    if sudo test -e "$saved" || sudo test -L "$saved"; then
        sudo mkdir -p "$(dirname -- "$path")"
        sudo cp -a "$saved" "$path"
        printf 'Restored %s\n' "$path"
    elif sudo test -e "$path" || sudo test -L "$path"; then
        sudo rm -f "$path"
        printf 'Removed %s\n' "$path"
    fi
}

saved_unit_state() {
    local unit="$1"
    local state_file="$backup/systemd-state/$unit"
    if sudo test -f "$state_file"; then
        sudo cat "$state_file"
    else
        printf 'disabled\n'
    fi
}

restore_unit_enablement() {
    local unit="$1"
    local state="$2"
    case "$state" in
        enabled) sudo systemctl enable "$unit" ;;
        enabled-runtime) sudo systemctl enable --runtime "$unit" ;;
        masked) sudo systemctl mask "$unit" ;;
        masked-runtime) sudo systemctl mask --runtime "$unit" ;;
        *) sudo systemctl disable "$unit" 2>/dev/null || true ;;
    esac
}

front_state="$(saved_unit_state surface7-front-camera.service)"
boot_state="$(saved_unit_state sp7-camera-boot.service)"
sudo systemctl disable --now surface7-front-camera.service 2>/dev/null || true
sudo systemctl disable --now sp7-camera-boot.service 2>/dev/null || true

system_files=(
    /usr/local/libexec/surface7-front-camera
    /usr/local/sbin/sp7-camera-boot
    /etc/default/surface7-front-camera
    /etc/systemd/system/surface7-front-camera.service
    /etc/modprobe.d/ipu4p.conf
    /etc/modprobe.d/sp7-v4l2loopback.conf
    /etc/modules-load.d/sp7-v4l2loopback.conf
    /etc/systemd/system/sp7-camera-boot.service
    /etc/ld.so.conf.d/surface7-ubuntu-frontcamera.conf
    /usr/local/share/libcamera/ipa/simple/ov8865.yaml
)
for path in "${system_files[@]}"; do restore_or_remove "$path"; done

for module in ov8865.ko dw9719.ko ipu-bridge.ko intel-ipu4p.ko intel-ipu4p-isys.ko intel-ipu4p-psys.ko intel-ipu4p-isys-csslib.ko intel-ipu4p-psys-csslib.ko v4l2loopback.ko; do
    restore_or_remove "$module_dir/$module"
done
restore_or_remove /usr/lib/firmware/ipu4p_cpd.bin

sudo rm -rf -- "$SURFACE7_LIBDIR"
sudo depmod -a "$SURFACE7_TARGET_KERNEL"
sudo ldconfig
sudo systemctl daemon-reload
restore_unit_enablement surface7-front-camera.service "$front_state"
restore_unit_enablement sp7-camera-boot.service "$boot_state"
sudo systemctl daemon-reload

printf '\nRollback finished. Backups remain at %s\n' "$backup"
printf 'APT packages remain installed. Reboot manually to restore the prior camera module state.\n'
