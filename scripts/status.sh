#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
set -u
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
source "$ROOT/config/ubuntu.env"

unit_status() {
    local unit="$1"
    local enabled active
    enabled="$(systemctl is-enabled "$unit" 2>/dev/null || true)"
    active="$(systemctl is-active "$unit" 2>/dev/null || true)"
    [[ -n "$enabled" ]] || enabled=not-found
    [[ -n "$active" ]] || active=inactive
    printf '  %-48s enabled=%-14s active=%s\n' "$unit" "$enabled" "$active"
}

printf 'Surface 7 front-camera status\n=============================\n'
printf 'Device: %s\n' "$(cat /sys/class/dmi/id/product_name 2>/dev/null || echo unknown)"
printf 'OS: %s\n' "$(. /etc/os-release; printf '%s' "${PRETTY_NAME:-unknown}")"
printf 'Kernel: %s (configured target %s)\n' "$(uname -r)" "$SURFACE7_TARGET_KERNEL"
printf 'IPU4P PCI device:\n'
lspci -nn 2>/dev/null | grep -i '8086:8a19' || true

printf '\nVideo/media nodes:\n'
found=0
for node in /dev/video* /dev/media*; do
    [[ -e "$node" ]] || continue
    printf '%s\n' "$node"
    found=1
done
[[ "$found" -eq 1 ]] || printf 'None found\n'

printf '\nCamera modules:\n'
for module in intel_ipu4p intel_ipu4p_isys intel_ipu4p_psys ov5693 ipu_bridge v4l2loopback; do
    if lsmod 2>/dev/null | awk '{print $1}' | grep -Fxq "$module"; then
        printf 'loaded  %s\n' "$module"
    else
        printf 'absent  %s\n' "$module"
    fi
done

firmware=/usr/lib/firmware/ipu4p_cpd.bin
if [[ -f "$firmware" ]]; then
    printf '\nFirmware: '
    sha256sum "$firmware"
else
    printf '\nFirmware: missing (%s)\n' "$firmware"
fi

printf '\nCamera systemd services:\n'
for unit in surface7-camera-init.service sp7-camera-boot.service surface7-front-camera.service \
    surface7-front-camera.timer surface7-front-camera-idle-relay.service \
    surface7-front-camera-on-demand.service; do
    unit_status "$unit"
done

if [[ -e /dev/video83 ]]; then
    printf '\nFront-camera V4L2 node: /dev/video83 present\n'
else
    printf '\nFront-camera V4L2 node: /dev/video83 absent (expected before explicit start)\n'
fi
printf 'GStreamer physical camera processes:\n'
pgrep -ax gst-launch-1.0 || printf '  none\n'

if command -v gst-inspect-1.0 >/dev/null 2>&1; then
    gst-inspect-1.0 libcamerasrc >/dev/null 2>&1 \
        && printf 'libcamerasrc: available\n' \
        || printf 'libcamerasrc: unavailable\n'
else
    printf 'libcamerasrc: gst-inspect-1.0 is not installed\n'
fi

printf '\nUse journalctl -b -u surface7-front-camera-on-demand.service for controller diagnostics.\n'

printf "Explicit-start gate: "
[[ -f /run/surface7-camera/requested ]] && echo armed || echo closed
printf "Failure latch: "
[[ -f /run/surface7-camera/failed ]] && echo set || echo clear
