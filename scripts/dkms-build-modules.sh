#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
MODE=build
if [[ "${1:-}" == clean ]]; then
    MODE=clean
    shift
fi
KVER="${1:-}"
[[ "$KVER" =~ ^[A-Za-z0-9._+-]+$ ]] || {
    echo "Usage: $0 [clean] KERNEL_VERSION" >&2
    exit 2
}
KDIR="/lib/modules/$KVER/build"
[[ -f "$KDIR/Makefile" ]] || {
    echo "Matching kernel headers are missing: $KDIR" >&2
    exit 1
}
IPU4_M="$ROOT/ipu4-camera/linux-6.19.8/drivers/media/pci/intel"
KMOD_M="$ROOT/kernel-modules"
V4L2_SRC="$ROOT/v4l2loopback"

if [[ "$MODE" == clean ]]; then
    make -C "$KDIR" M="$KMOD_M" clean >/dev/null 2>&1 || true
    make -C "$KDIR" M="$IPU4_M" EXTERNAL_BUILD=1 srcpath="$IPU4_M" \
        CONFIG_VIDEO_INTEL_IPU=m CONFIG_VIDEO_INTEL_IPU4P=y \
        CONFIG_VIDEO_INTEL_IPU6= CONFIG_VIDEO_IPU3_CIO2= CONFIG_INTEL_VSC= \
        CONFIG_VIDEO_INTEL_IPU_FW_LIB=y clean >/dev/null 2>&1 || true
    make -C "$KDIR" M="$V4L2_SRC" clean >/dev/null 2>&1 || true
    find "$ROOT" -maxdepth 1 -type f -name '*.ko' -delete
    exit 0
fi

make -C "$KDIR" M="$KMOD_M" -j"${SURFACE7_BUILD_JOBS:-2}" modules
for module in ov8865 dw9719 ipu-bridge; do
    install -m 0644 "$KMOD_M/$module.ko" "$ROOT/$module.ko"
done
(
    cd "$ROOT/ipu4-camera"
    KDIR="$KDIR" KREL="$KVER" ./scripts/build-modules.sh -j1
)

ipu4_modules=(
    intel-ipu4p.ko
    intel-ipu4p-isys.ko
    intel-ipu4p-psys.ko
    intel-ipu4p-isys-csslib.ko
    intel-ipu4p-psys-csslib.ko
)
for module in "${ipu4_modules[@]}"; do
    path="$(find "$ROOT/ipu4-camera" -type f -name "$module" -print -quit)"
    [[ -n "$path" ]] || { echo "IPU4 build did not produce $module" >&2; exit 1; }
    install -m 0644 "$path" "$ROOT/$module"
done

make -C "$KDIR" M="$V4L2_SRC" KERNEL_DIR="$KDIR" KERNELRELEASE="$KVER" \
    -j"${SURFACE7_BUILD_JOBS:-2}" v4l2loopback.ko
install -m 0644 "$V4L2_SRC/v4l2loopback.ko" "$ROOT/v4l2loopback.ko"

for module in ov8865 dw9719 ipu-bridge "${ipu4_modules[@]}" v4l2loopback.ko; do
    module="${module%.ko}.ko"
    [[ -f "$ROOT/$module" ]] || { echo "Built module is missing: $module" >&2; exit 1; }
    vermagic="$(modinfo -F vermagic "$ROOT/$module")"
    [[ "${vermagic%% *}" == "$KVER" ]] || {
        echo "Wrong module vermagic for $module: $vermagic" >&2
        exit 1
    }
done
