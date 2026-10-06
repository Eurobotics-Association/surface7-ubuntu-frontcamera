#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 OUTPUT_PLUGIN_PATH" >&2
    exit 2
fi

output="$1"
if ! command -v pkg-config >/dev/null 2>&1 || \
   ! pkg-config --exists gstreamer-1.0; then
    echo "GStreamer development files are required (Ubuntu package: libgstreamer1.0-dev)." >&2
    exit 1
fi

mkdir -p "$(dirname -- "$output")"
cc -std=c11 -fPIC -shared -O2 -Wall -Wextra -Werror \
    -DPACKAGE=\"surface7-ubuntu-frontcamera\" \
    -DVERSION=\"0.1.0\" \
    $(pkg-config --cflags gstreamer-1.0) \
    "$ROOT/gstreamer/surface7-v4l2-device-provider.c" \
    -o "$output" \
    $(pkg-config --libs gstreamer-1.0)

printf 'Built GStreamer provider: %s\n' "$output"
