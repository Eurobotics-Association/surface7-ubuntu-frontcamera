#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
source "$ROOT/config/ubuntu.env"

if [[ $EUID -eq 0 ]]; then
    echo "Run as your desktop user; this script will ask sudo when required." >&2
    exit 1
fi

"$ROOT/scripts/install-build-deps.sh"

command -v cc >/dev/null 2>&1 || { echo "C compiler is missing; run scripts/install-build-deps.sh." >&2; exit 1; }
command -v gst-launch-1.0 >/dev/null 2>&1 || { echo "gst-launch-1.0 is missing; install the repository's Ubuntu packages first." >&2; exit 1; }
gst-inspect-1.0 libcamerasrc >/dev/null 2>&1 || { echo "GStreamer libcamerasrc is missing; the physical camera pipeline cannot start." >&2; exit 1; }
[[ -f "$ROOT/upstream/surface-pro-7-camera/src/sp7-camera-relay.c" ]] || { echo "Pinned idle-relay source is missing." >&2; exit 1; }
[[ "$(uname -r)" == "$SURFACE7_TARGET_KERNEL" ]] || {
    echo "Running kernel $(uname -r) differs from configured target $SURFACE7_TARGET_KERNEL." >&2
    exit 1
}

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
if [[ ! "$deployed_kernel" =~ ^[A-Za-z0-9._+-]+$ || "$deployed_kernel" != "$(uname -r)" ]]; then
    echo "Refusing service deployment: recorded deployment kernel is invalid or not running." >&2
    exit 1
fi

tmp="$(mktemp -d -t surface7-on-demand.XXXXXXXX)"
cleanup() { rm -rf -- "$tmp"; }
trap cleanup EXIT

cc -O2 -Wall -Wextra -Werror -o "$tmp/surface7-v4l2-client-watch" \
    "$ROOT/prototypes/v4l2loopback-client-watch.c"
cc -O2 -Wall -Wextra -Werror -o "$tmp/surface7-v4l2-idle-relay" \
    "$ROOT/upstream/surface-pro-7-camera/src/sp7-camera-relay.c"
python3 -c 'from pathlib import Path; compile(Path("'"$ROOT"'/prototypes/on-demand-gstreamer-controller.py").read_text(), "on-demand-gstreamer-controller.py", "exec")'

backup_root="$SURFACE7_BACKUP_ROOT/$deployed_kernel"
sudo install -d -m 0755 "$backup_root/systemd-state"
previous="$backup_root/pre-on-demand"
state_units=(
    surface7-front-camera.service
    surface7-front-camera.timer
    surface7-front-camera-idle-relay.service
    surface7-front-camera-on-demand.service
)
system_files=(
    /usr/local/libexec/surface7-front-camera
    /usr/local/libexec/surface7-v4l2-idle-relay
    /usr/local/libexec/surface7-v4l2-client-watch
    /usr/local/libexec/surface7-front-camera-controller.py
    /etc/default/surface7-front-camera
    /etc/systemd/system/surface7-front-camera.service
    /etc/systemd/system/surface7-front-camera.timer
    /etc/systemd/system/surface7-front-camera-idle-relay.service
    /etc/systemd/system/surface7-front-camera-on-demand.service
)

backup_once() {
    local path="$1"
    local saved="$backup_root$path"
    if sudo test -e "$saved" || sudo test -L "$saved"; then
        return
    fi
    if sudo test -e "$path" || sudo test -L "$path"; then
        sudo mkdir -p "$(dirname -- "$saved")"
        sudo cp -a "$path" "$saved"
    fi
}

snapshot_previous_deployment_once() {
    if sudo test -f "$previous/.complete"; then
        return
    fi
    sudo install -d -m 0755 "$previous/systemd-state" "$previous/systemd-active"
    for path in "${system_files[@]}"; do
        local saved="$previous$path"
        if sudo test -e "$path" || sudo test -L "$path"; then
            sudo mkdir -p "$(dirname -- "$saved")"
            sudo cp -a "$path" "$saved"
        fi
    done
    for unit in "${state_units[@]}"; do
        local enabled active
        enabled="$(systemctl is-enabled "$unit" 2>/dev/null || true)"
        [[ -n "$enabled" ]] || enabled=disabled
        active="$(systemctl is-active "$unit" 2>/dev/null || true)"
        [[ -n "$active" ]] || active=inactive
        printf '%s\n' "$enabled" | sudo tee "$previous/systemd-state/$unit" >/dev/null
        printf '%s\n' "$active" | sudo tee "$previous/systemd-active/$unit" >/dev/null
    done
    printf 'surface7-pre-on-demand-v1\n' | sudo tee "$previous/.complete" >/dev/null
}

snapshot_previous_deployment_once
for path in "${system_files[@]}"; do backup_once "$path"; done
for unit in "${state_units[@]}"; do
    state_file="$backup_root/systemd-state/$unit"
    if ! sudo test -e "$state_file"; then
        state="$(systemctl is-enabled "$unit" 2>/dev/null || true)"
        [[ -n "$state" ]] || state=disabled
        printf '%s\n' "$state" | sudo tee "$state_file" >/dev/null
    fi
done

restore_previous_and_exit() {
    local status="$1"
    echo "On-demand deployment failed; restoring the previous camera service snapshot." >&2
    sudo "$SURFACE7_LIBDIR/scripts/rollback.sh" --previous-deployment || {
        echo "Automatic restoration failed. Run: $SURFACE7_LIBDIR/scripts/rollback.sh --previous-deployment" >&2
    }
    exit "$status"
}

install_and_activate() {
    sudo install -d -m 0755 /usr/local/libexec /etc/systemd/system
    sudo install -m 0755 "$tmp/surface7-v4l2-client-watch" /usr/local/libexec/surface7-v4l2-client-watch
    sudo install -m 0755 "$tmp/surface7-v4l2-idle-relay" /usr/local/libexec/surface7-v4l2-idle-relay
    sudo install -m 0755 "$ROOT/prototypes/on-demand-gstreamer-controller.py" \
        /usr/local/libexec/surface7-front-camera-controller.py
    sudo install -m 0644 "$ROOT/config/front-camera.env" /etc/default/surface7-front-camera
    sudo install -m 0644 "$ROOT/systemd/system/surface7-front-camera-idle-relay.service" \
        /etc/systemd/system/surface7-front-camera-idle-relay.service
    sudo install -m 0644 "$ROOT/systemd/system/surface7-front-camera-on-demand.service" \
        /etc/systemd/system/surface7-front-camera-on-demand.service
    sudo install -m 0755 "$ROOT/scripts/rollback.sh" "$SURFACE7_LIBDIR/scripts/rollback.sh"

    sudo systemctl disable --now surface7-front-camera.timer 2>/dev/null || true
    sudo systemctl stop surface7-front-camera.service 2>/dev/null || true
    sudo rm -f /etc/systemd/system/surface7-front-camera.service \
        /etc/systemd/system/surface7-front-camera.timer
    sudo rm -f /usr/local/libexec/surface7-front-camera
    sudo systemctl daemon-reload

    sudo systemctl enable surface7-front-camera-idle-relay.service || return 1
    sudo systemctl enable surface7-front-camera-on-demand.service || return 1
    if [[ -e /dev/video83 ]]; then
        sudo systemctl start surface7-front-camera-idle-relay.service || return 1
        sudo systemctl start surface7-front-camera-on-demand.service || return 1
        sudo systemctl is-active --quiet surface7-front-camera-idle-relay.service || return 1
        sudo systemctl is-active --quiet surface7-front-camera-on-demand.service || return 1
    else
        echo "/dev/video83 is absent; on-demand services are enabled for next boot but were not started."
    fi
}

if install_and_activate; then
    :
else
    status=$?
    restore_previous_and_exit "$status"
fi

sleep 2
if pgrep -x 'gst-launch-1.0' >/dev/null 2>&1; then
    echo "A physical camera pipeline is active; check client usage before treating the camera as idle."
else
    echo "No libcamerasrc process is running while the V4L2 node is idle."
fi

printf '\nOn-demand GStreamer camera services are installed.\n'
printf 'Idle relay: one retained initialization frame; it does not generate a repeating idle video stream.\n'
printf 'Physical GStreamer capture starts on CLIENT_USAGE and stops after its grace period.\n'
printf 'Rollback to the prior service deployment: %s/scripts/rollback.sh --previous-deployment\n' "$SURFACE7_LIBDIR"
printf 'Full project removal and system restoration: %s/scripts/rollback.sh\n' "$SURFACE7_LIBDIR"
