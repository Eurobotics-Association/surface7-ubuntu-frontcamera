#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
set -u
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
source "$ROOT/config/ubuntu.env"
printf 'Surface 7 front-camera status\n=============================\n'
printf 'Device: %s\n' "$(cat /sys/class/dmi/id/product_name 2>/dev/null || echo unknown)"
printf 'OS: %s\n' "$(. /etc/os-release; printf '%s' "${PRETTY_NAME:-unknown}")"
printf 'Kernel: %s (target %s)\n' "$(uname -r)" "$SURFACE7_TARGET_KERNEL"
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
printf '\nSystem service:\n'
systemctl is-enabled sp7-camera-boot.service 2>/dev/null || true
systemctl is-active sp7-camera-boot.service 2>/dev/null || true
printf '\nGStreamer front-camera bridge:\n'
systemctl is-enabled surface7-front-camera.service 2>/dev/null || true
systemctl is-active surface7-front-camera.service 2>/dev/null || true
if [[ -e /dev/video83 ]]; then
    printf 'Front camera loopback: /dev/video83 present\n'
else
    printf 'Front camera loopback: /dev/video83 missing\n'
fi
if command -v gst-inspect-1.0 >/dev/null 2>&1; then
    gst-inspect-1.0 libcamerasrc >/dev/null 2>&1 \
        && printf 'libcamerasrc: available\n' \
        || printf 'libcamerasrc: unavailable\n'
else
    printf 'libcamerasrc: gst-inspect-1.0 is not installed\n'
fi
printf '\nUse journalctl -k -b and journalctl -b -u surface7-front-camera.service for diagnostics.\n'
