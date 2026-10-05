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

deployment_kernel_marker="$SURFACE7_LIBDIR/deployment-kernel"
if sudo test -f "$deployment_kernel_marker"; then
    deployed_kernel="$(sudo cat "$deployment_kernel_marker")"
else
    echo "Refusing rollback: deployment kernel record is missing." >&2
    exit 1
fi
if [[ ! "$deployed_kernel" =~ ^[A-Za-z0-9._+-]+$ ]]; then
    echo "Refusing rollback: deployment kernel record is invalid." >&2
    exit 1
fi

dkms_package="surface7-ubuntu-frontcamera"
dkms_version="0.1.0"
dkms_source="/usr/src/${dkms_package}-${dkms_version}"
dkms_registration="/var/lib/dkms/${dkms_package}/${dkms_version}"
expected_source_marker="$(cat "$ROOT/config/ownership-marker")"
if sudo test -e "$dkms_source"; then
    source_marker="$dkms_source/.surface7-ubuntu-frontcamera-owned"
    if ! command -v dkms >/dev/null 2>&1; then
        echo "Refusing rollback: dkms is required to remove the registered modules safely." >&2
        exit 1
    fi

    if sudo test -f "$source_marker"; then
        if [[ "$(sudo cat "$source_marker")" != "$expected_source_marker" ]]; then
            echo "Refusing rollback: DKMS source ownership marker does not match this project." >&2
            exit 1
        fi
    elif sudo test -e "$dkms_registration"; then
        echo "Refusing rollback: unmarked DKMS source has a registered module; refusing to remove it." >&2
        exit 1
    fi

    if sudo test -e "$dkms_registration"; then
        sudo dkms remove -m "$dkms_package" -v "$dkms_version" --all
    fi
fi

backup="$SURFACE7_BACKUP_ROOT/$deployed_kernel"

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
timer_state="$(saved_unit_state surface7-front-camera.timer)"
sudo systemctl disable --now surface7-front-camera.timer 2>/dev/null || true
sudo systemctl disable --now surface7-front-camera.service 2>/dev/null || true
sudo systemctl disable --now sp7-camera-boot.service 2>/dev/null || true

system_files=(
    /usr/local/libexec/surface7-front-camera
    /usr/local/sbin/sp7-camera-boot
    /etc/default/surface7-front-camera
    /etc/systemd/system/surface7-front-camera.service
    /etc/systemd/system/surface7-front-camera.timer
    /etc/modprobe.d/ipu4p.conf
    /etc/modprobe.d/sp7-v4l2loopback.conf
    /etc/modules-load.d/sp7-v4l2loopback.conf
    /etc/systemd/system/sp7-camera-boot.service
    /etc/ld.so.conf.d/surface7-ubuntu-frontcamera.conf
    /usr/local/share/libcamera/ipa/simple/ov8865.yaml
    /usr/local/share/libcamera/ipa/simple/ov5693.yaml
)
for path in "${system_files[@]}"; do restore_or_remove "$path"; done

restore_or_remove /usr/lib/firmware/ipu4p_cpd.bin

# DKMS removes the project's modules. Restore only module files captured by its
# pre-install hook; an unrelated file without a saved copy is left untouched.
for kernel_path in /lib/modules/*; do
    [[ -d "$kernel_path" ]] || continue
    kernel_version="$(basename -- "$kernel_path")"
    backup="$SURFACE7_BACKUP_ROOT/$kernel_version"
    for module in ov8865.ko dw9719.ko ipu-bridge.ko intel-ipu4p.ko intel-ipu4p-isys.ko intel-ipu4p-psys.ko intel-ipu4p-isys-csslib.ko intel-ipu4p-psys-csslib.ko v4l2loopback.ko; do
        saved="$backup/lib/modules/$kernel_version/updates/dkms/$module"
        if sudo test -e "$saved" || sudo test -L "$saved"; then
            current="$kernel_path/updates/dkms/$module"
            if sudo test -e "$current" || sudo test -L "$current"; then
                if ! sudo cmp -s "$saved" "$current"; then
                    echo "Refusing rollback: module path changed after deployment: $current" >&2
                    exit 1
                fi
            else
                sudo mkdir -p "$kernel_path/updates/dkms"
                sudo cp -a "$saved" "$current"
            fi
        fi
    done
done

if sudo test -e "$dkms_source"; then
    sudo rm -rf -- "$dkms_source"
fi

sudo rm -rf -- "$SURFACE7_LIBDIR"
for kernel_path in /lib/modules/*; do
    [[ -d "$kernel_path" ]] || continue
    [[ -f "$kernel_path/modules.order" ]] || continue
    sudo depmod -a "$(basename -- "$kernel_path")"
done
sudo ldconfig
sudo systemctl daemon-reload
restore_unit_enablement surface7-front-camera.service "$front_state"
restore_unit_enablement sp7-camera-boot.service "$boot_state"
restore_unit_enablement surface7-front-camera.timer "$timer_state"
sudo systemctl daemon-reload

printf '\nRollback finished. Backups remain under %s\n' "$SURFACE7_BACKUP_ROOT"
printf 'APT packages remain installed. Reboot manually to restore the prior camera module state.\n'
