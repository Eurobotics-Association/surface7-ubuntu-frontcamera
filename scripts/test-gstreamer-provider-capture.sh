#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
DEVICE="${SURFACE7_FRONT_CAMERA_DEVICE:-/dev/video83}"

if [[ $EUID -eq 0 ]]; then
    echo "Run this bounded capture test as your desktop user, not with sudo." >&2
    exit 1
fi
if [[ ! -c "$DEVICE" ]]; then
    echo "Camera loopback device is not present: $DEVICE" >&2
    exit 1
fi

tmp="$(mktemp -d -t surface7-provider-capture.XXXXXXXX)"
cleanup() { rm -rf -- "$tmp"; }
trap cleanup EXIT
plugin_dir="$tmp/gstreamer-1.0"
mkdir -p "$plugin_dir"
bash "$ROOT/scripts/build-gstreamer-provider.sh" \
    "$plugin_dir/libgstsurface7v4l2camera.so"
cc -std=c11 -O2 -Wall -Wextra -Werror \
    $(pkg-config --cflags gstreamer-1.0) \
    "$ROOT/tests/gstreamer-provider-capture.c" \
    -o "$tmp/gstreamer-provider-capture" \
    $(pkg-config --libs gstreamer-1.0)

plugin_path="$plugin_dir${GST_PLUGIN_PATH:+:$GST_PLUGIN_PATH}"
plugin_path_1_0="$plugin_dir${GST_PLUGIN_PATH_1_0:+:$GST_PLUGIN_PATH_1_0}"
echo "This is a bounded headless test: GStreamer must enumerate the labeled"
echo "loopback and read five frames through the device element Cheese would use."
echo "It does not install a plugin or alter services/modules."
GST_PLUGIN_PATH="$plugin_path" \
GST_PLUGIN_PATH_1_0="$plugin_path_1_0" \
GST_REGISTRY="$tmp/registry.bin" \
SURFACE7_FRONT_CAMERA_DEVICE="$DEVICE" \
    "$tmp/gstreamer-provider-capture"
