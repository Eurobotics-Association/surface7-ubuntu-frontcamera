#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
source "$ROOT/config/ubuntu.env"

if [[ $EUID -eq 0 ]]; then
    echo "Run this helper as your desktop user; it uses sudo only if packages are missing." >&2
    exit 1
fi

source /etc/os-release
if [[ "${ID:-}" != "$SURFACE7_OS_ID" || "${VERSION_ID:-}" != "$SURFACE7_OS_VERSION" ]]; then
    echo "This package list is for Ubuntu 24.04." >&2
    exit 1
fi

required_packages=(
    git git-lfs build-essential cmake meson ninja-build patch pkg-config
    python3-jinja2 python3-ply python3-yaml libyaml-dev libssl-dev libevent-dev
    libelf-dev libunwind-dev libsystemd-dev libglib2.0-dev libdrm-dev
    libjpeg-dev libtiff-dev libsdl2-dev libegl1-mesa-dev libgles2-mesa-dev
    libncurses-dev libx11-dev libxcb1-dev libcap-dev pciutils mokutil v4l-utils
    gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good
    libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev
)

if [[ ! -f "/lib/modules/$SURFACE7_TARGET_KERNEL/build/Makefile" ]]; then
    required_packages+=("linux-headers-$SURFACE7_TARGET_KERNEL")
fi

missing_packages=()
for package in "${required_packages[@]}"; do
    if ! dpkg -s "$package" 2>/dev/null | grep -Fxq 'Status: install ok installed'; then
        missing_packages+=("$package")
    fi
done

if (("${#missing_packages[@]}" > 0)); then
    printf 'Installing missing Ubuntu packages: %s\n' "${missing_packages[*]}"
    sudo -v
    sudo apt-get update
    sudo apt-get install -y "${missing_packages[@]}"
else
    echo "All required Ubuntu build and GStreamer packages are already installed."
fi

for package in "${required_packages[@]}"; do
    dpkg -s "$package" 2>/dev/null | grep -Fxq 'Status: install ok installed' || {
        echo "Required Ubuntu package is still missing: $package" >&2
        exit 1
    }
done

[[ -f "/lib/modules/$SURFACE7_TARGET_KERNEL/build/Makefile" ]] || {
    echo "Matching target kernel headers are missing at /lib/modules/$SURFACE7_TARGET_KERNEL/build." >&2
    exit 1
}

for element in libcamerasrc videoconvert videoscale v4l2sink filesink; do
    if [[ "$element" == libcamerasrc ]]; then
        continue
    fi
    gst-inspect-1.0 "$element" >/dev/null 2>&1 || {
        echo "Required GStreamer element is not available after package setup: $element" >&2
        exit 1
    }
done

printf '\nUbuntu packages and build headers are ready for %s.\n' "$SURFACE7_TARGET_KERNEL"
