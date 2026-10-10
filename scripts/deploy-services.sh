#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
if [[ ${1:-} == --plan ]]; then
    exec python3 "$ROOT/scripts/startup-policy.py" plan
fi
[[ $# -eq 0 ]] || { echo 'Usage: scripts/deploy-services.sh [--plan]' >&2; exit 2; }
[[ $EUID -ne 0 ]] || { echo 'Run as your desktop user; deployment asks sudo.' >&2; exit 1; }
# Preflight only: never install packages as a side effect of service deployment.
source /etc/os-release
[[ $ID == ubuntu && $VERSION_ID == 24.04 && $(uname -m) == x86_64 ]]
[[ $(cat /sys/class/dmi/id/product_name) == 'Surface Pro 7' ]]
[[ -f /lib/modules/$(uname -r)/build/Makefile ]] || { echo 'Matching running-kernel headers missing.' >&2; exit 1; }
for tool in cc python3 mkinitramfs lsinitramfs gst-inspect-1.0; do
    command -v "$tool" >/dev/null || { echo "Missing Ubuntu dependency: $tool (install separately after approval)" >&2; exit 1; }
done
[[ -f /usr/local/lib/surface7-ubuntu-frontcamera/gstreamer-1.0/libgstlibcamera.so ]]
gst-inspect-1.0 progressreport >/dev/null
staging="$(mktemp -d -t surface7-policy-build.XXXXXXXX)"
trap 'rm -rf -- "$staging"' EXIT
cc -O2 -Wall -Wextra -Werror -o "$staging/surface7-v4l2-client-watch" "$ROOT/prototypes/v4l2loopback-client-watch.c"
cc -O2 -Wall -Wextra -Werror -o "$staging/surface7-v4l2-idle-relay" "$ROOT/upstream/surface-pro-7-camera/src/sp7-camera-relay.c"
python3 "$ROOT/scripts/startup-policy.py" plan
sudo python3 "$ROOT/scripts/startup-policy.py" deploy --built "$staging"
