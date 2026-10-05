#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
source "$ROOT/config/ubuntu.env"

if [[ $EUID -eq 0 ]]; then
    echo "Run as your desktop user; this script will ask sudo when required." >&2
    exit 1
fi

marker="$SURFACE7_LIBDIR/.surface7-ubuntu-frontcamera-owned"
expected_marker="$(cat "$ROOT/config/ownership-marker")"
sudo -v
if ! sudo test -f "$marker" || [[ "$(sudo cat "$marker")" != "$expected_marker" ]]; then
    echo "Refusing service deployment: this project does not own $SURFACE7_LIBDIR." >&2
    exit 1
fi

deployment_kernel_marker="$SURFACE7_LIBDIR/deployment-kernel"
if ! sudo test -f "$deployment_kernel_marker"; then
    echo "Refusing service deployment: deployed kernel record is missing." >&2
    exit 1
fi
deployed_kernel="$(sudo cat "$deployment_kernel_marker")"
if [[ ! "$deployed_kernel" =~ ^[A-Za-z0-9._+-]+$ ]]; then
    echo "Refusing service deployment: deployed kernel record is invalid." >&2
    exit 1
fi

backup="$SURFACE7_BACKUP_ROOT/$deployed_kernel"
backup_once() {
    local path="$1"
    local saved="$backup$path"
    if sudo test -e "$saved" || sudo test -L "$saved"; then
        return
    fi
    if sudo test -e "$path" || sudo test -L "$path"; then
        sudo mkdir -p "$(dirname -- "$saved")"
        sudo cp -a "$path" "$saved"
    fi
}

record_unit_state_once() {
    local unit="$1"
    local state_file="$backup/systemd-state/$unit"
    if sudo test -e "$state_file"; then
        return
    fi
    local state
    state="$(systemctl is-enabled "$unit" 2>/dev/null || true)"
    [[ -n "$state" ]] || state=disabled
    sudo mkdir -p "$(dirname -- "$state_file")"
    printf '%s\n' "$state" | sudo tee "$state_file" >/dev/null
}

units=(
    sp7-camera-boot.service
    surface7-front-camera.service
    surface7-front-camera.timer
)
for unit in "${units[@]}"; do
    record_unit_state_once "$unit"
    backup_once "/etc/systemd/system/$unit"
done

sudo install -D -m 0644 "$ROOT/systemd/system/sp7-camera-boot.service" \
    /etc/systemd/system/sp7-camera-boot.service
sudo install -D -m 0644 "$ROOT/systemd/system/surface7-front-camera.service" \
    /etc/systemd/system/surface7-front-camera.service
sudo install -D -m 0644 "$ROOT/systemd/system/surface7-front-camera.timer" \
    /etc/systemd/system/surface7-front-camera.timer

sudo systemctl daemon-reload
# Leave an already-running camera process alone. These changes take effect at
# the next boot; rollback can restore the recorded files and enablement states.
sudo systemctl disable surface7-front-camera.service sp7-camera-boot.service 2>/dev/null || true
sudo systemctl enable surface7-front-camera.timer

printf 'Installed delayed camera service units for the next boot.\n'
printf 'Timer delay: 60 seconds after boot.\n'
printf 'No reboot or camera module reload was performed.\n'
printf 'Rollback: %s/scripts/rollback.sh\n' "$ROOT"
