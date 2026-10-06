#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
DEVICE="${SURFACE7_FRONT_CAMERA_DEVICE:-/dev/video83}"

if [[ $EUID -eq 0 ]]; then
    echo "Run Cheese as your desktop user, not with sudo." >&2
    exit 1
fi
if ! command -v cheese >/dev/null 2>&1; then
    echo "Cheese is not installed. This diagnostic does not install packages." >&2
    exit 1
fi
if [[ ! -c "$DEVICE" ]]; then
    echo "Camera loopback device is not present: $DEVICE" >&2
    exit 1
fi

tmp="$(mktemp -d -t surface7-cheese-provider.XXXXXXXX)"
cleanup() { rm -rf -- "$tmp"; }
trap cleanup EXIT
plugin_dir="$tmp/gstreamer-1.0"
mkdir -p "$plugin_dir"
bash "$ROOT/scripts/build-gstreamer-provider.sh" \
    "$plugin_dir/libgstsurface7v4l2camera.so"

plugin_path="$plugin_dir${GST_PLUGIN_PATH:+:$GST_PLUGIN_PATH}"
plugin_path_1_0="$plugin_dir${GST_PLUGIN_PATH_1_0:+:$GST_PLUGIN_PATH_1_0}"
echo "Launching Cheese with an isolated, temporary GStreamer provider."
echo "No system plugin, service, module, or package will be changed."
echo "Camera device: $DEVICE"
GST_PLUGIN_PATH="$plugin_path" \
GST_PLUGIN_PATH_1_0="$plugin_path_1_0" \
GST_REGISTRY="$tmp/registry.bin" \
SURFACE7_FRONT_CAMERA_DEVICE="$DEVICE" \
    cheese "$@"
