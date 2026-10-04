#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
EXPECTED_UPSTREAM_SHA=e389583af1cf99a46e51377332b95236f153737e4685f8a171a4aabb2390ef6b
actual_sha="$(sha256sum "$ROOT/upstream/surface-pro-7-camera/install.sh" | awk '{print $1}')"
[[ "$actual_sha" == "$EXPECTED_UPSTREAM_SHA" ]] || {
    echo "Pinned upstream installer digest mismatch." >&2
    exit 1
}

while IFS= read -r -d '' file; do bash -n "$file"; done < <(find "$ROOT/scripts" -type f -name '*.sh' -print0)
bash -n "$ROOT/tests/static-validation.sh"
python3 -Werror::SyntaxWarning -m py_compile "$ROOT/scripts/prepare-upstream-installer.py"

tmp="$(mktemp -d -t surface7-static-check.XXXXXXXX)"
trap 'rm -rf "$tmp"' EXIT
cp -a "$ROOT/upstream/surface-pro-7-camera" "$tmp/upstream"
python3 "$ROOT/scripts/prepare-upstream-installer.py" "$tmp/upstream/install.sh"
adapted="$tmp/upstream/install.sh"

grep -Fq 'EXPECTED_KERNEL="6.19.8-surface-3"' "$adapted"
grep -Fq 'EXPECTED_UBUNTU="24.04"' "$adapted"
grep -Fq 'sudo apt-get install -y "linux-headers-$KVER"' "$adapted"
grep -Fq 'GSTREAMER_PLUGIN="/usr/local/lib/surface7-ubuntu-frontcamera/gstreamer-1.0/libgstlibcamera.so"' "$adapted"
grep -Fq 'gst-inspect-1.0 libcamerasrc' "$adapted"
grep -Fq 'v4l2sink device="$DEVICE"' "$ROOT/scripts/surface7-front-camera"
grep -Fq 'video_nr=83 card_label="Surface Pro 7 Front Camera" exclusive_caps=1' \
    "$tmp/upstream/config/modprobe.d/sp7-v4l2loopback.conf"
grep -Fq 'sudo install -D -m 0755' "$adapted"
grep -Fq 'record_unit_enablement_state surface7-front-camera.service' "$adapted"
grep -Fq 'record_unit_enablement_state sp7-camera-boot.service' "$adapted"

if grep -Eiq 'pipewiresrc|pipewire\.service|wireplumber\.service|libspa-libcamera|systemctl --user' "$adapted"; then
    echo "Adapted deployment still contains a desktop camera bridge path." >&2
    exit 1
fi
if grep -Eiq 'sudo dnf|kernel-surface-devel|rpm -' "$adapted"; then
    echo "Adapted deployment still contains a non-Ubuntu package operation." >&2
    exit 1
fi

bash -n "$adapted"
if cmp -s "$ROOT/upstream/surface-pro-7-camera/install.sh" "$adapted"; then
    echo "Adapter did not change the temporary installer." >&2
    exit 1
fi
[[ "$(sha256sum "$ROOT/upstream/surface-pro-7-camera/install.sh" | awk '{print $1}')" == "$EXPECTED_UPSTREAM_SHA" ]]

echo "PASS: pinned source, Ubuntu/GStreamer adapter, rollback hooks, and shell syntax"
