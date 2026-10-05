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
EXPECTED_OV5693_TUNING_SHA=73845d5ebaedc948ec0cca7b3d2f07ac8081c2f5c3e16c63905ce04532ba21ac
actual_tuning_sha="$(sha256sum "$ROOT/config/ipa/simple/ov5693.yaml" | awk '{print $1}')"
[[ "$actual_tuning_sha" == "$EXPECTED_OV5693_TUNING_SHA" ]] || {
    echo "Pinned OV5693 tuning digest mismatch." >&2
    exit 1
}

while IFS= read -r -d '' file; do bash -n "$file"; done < <(find "$ROOT/scripts" -type f -name '*.sh' -print0)
bash -n "$ROOT/tests/static-validation.sh"
python3 -Werror::SyntaxWarning -m py_compile "$ROOT/scripts/prepare-upstream-installer.py"

tmp="$(mktemp -d -t surface7-static-check.XXXXXXXX)"
trap 'rm -rf "$tmp"' EXIT
cp -a "$ROOT/upstream/surface-pro-7-camera" "$tmp/upstream"
mkdir -p "$tmp/upstream/scripts" "$tmp/upstream/ubuntu-deployment"
install -m 0644 "$ROOT/systemd/system/surface7-front-camera.service" \
    "$tmp/upstream/ubuntu-deployment/surface7-front-camera.service"
grep -Fq 'Restart=no' "$ROOT/systemd/system/surface7-front-camera.service"
install -m 0644 "$ROOT/systemd/system/surface7-front-camera.timer" \
    "$tmp/upstream/ubuntu-deployment/surface7-front-camera.timer"
install -m 0644 "$ROOT/systemd/system/sp7-camera-boot.service" \
    "$tmp/upstream/ubuntu-deployment/sp7-camera-boot.service"
install -m 0644 "$ROOT/config/front-camera.env" \
    "$tmp/upstream/ubuntu-deployment/front-camera.env"
install -m 0644 "$ROOT/config/ipa/simple/ov5693.yaml" \
    "$tmp/upstream/ubuntu-deployment/ov5693.yaml"
install -m 0755 "$ROOT/scripts/surface7-front-camera" \
    "$tmp/upstream/ubuntu-deployment/surface7-front-camera"
install -m 0755 "$ROOT/scripts/dkms-build-modules.sh" "$tmp/upstream/scripts/dkms-build-modules.sh"
install -m 0755 "$ROOT/scripts/dkms-pre-install.sh" "$tmp/upstream/scripts/dkms-pre-install.sh"
install -m 0644 "$ROOT/dkms/dkms.conf" "$tmp/upstream/dkms.conf"
python3 "$ROOT/scripts/prepare-upstream-installer.py" "$tmp/upstream/install.sh"
adapted="$tmp/upstream/install.sh"

grep -Fq 'options intel_ipu4p fw_version_check=0' \
    "$ROOT/upstream/surface-pro-7-camera/config/modprobe.d/ipu4p.conf"
if grep -Fq 'fw_version_check' "$tmp/upstream/config/modprobe.d/ipu4p.conf"; then
    echo "Temporary Ubuntu config still requests an unsupported IPU4P parameter." >&2
    exit 1
fi
grep -Fq 'sp7_full_fw_recycle_on_first_stream=Y' \
    "$tmp/upstream/config/modprobe.d/ipu4p.conf"
grep -Fq 'Restart=no' "$ROOT/systemd/system/surface7-front-camera.service"

grep -Fq 'EXPECTED_KERNEL="${SURFACE7_TARGET_KERNEL:-$(uname -r)}"' "$adapted"
grep -Fq 'EXPECTED_UBUNTU="24.04"' "$adapted"
grep -Fq 'sudo apt-get install -y "linux-headers-$KVER"' "$adapted"
grep -Fq 'GSTREAMER_PLUGIN="/usr/local/lib/surface7-ubuntu-frontcamera/gstreamer-1.0/libgstlibcamera.so"' "$adapted"
grep -Fq 'gst-inspect-1.0 libcamerasrc' "$adapted"
grep -Fq 'DESTDIR="$STAGE" meson install' "$adapted"
grep -Fq 'sudo cp -a "$staged_libdir/." /usr/local/lib/surface7-ubuntu-frontcamera/' "$adapted"
if grep -Fq 'sudo meson install' "$adapted"; then
    echo "Adapted deployment must stage libcamera before installing product-owned files." >&2
    exit 1
fi
grep -Fq 'v4l2sink device="$DEVICE"' "$ROOT/scripts/surface7-front-camera"
grep -Fq 'CAMERA_NAME="\\\\_SB_.PCI0.I2C2.CAMF"' "$ROOT/config/front-camera.env"
grep -Fq 'SOURCE_WIDTH=1296' "$ROOT/config/front-camera.env"
grep -Fq 'SOURCE_HEIGHT=972' "$ROOT/config/front-camera.env"
grep -Fq 'video_nr=83 card_label="Surface Pro 7 Front Camera" exclusive_caps=1 max_buffers=4' \
    "$tmp/upstream/config/modprobe.d/sp7-v4l2loopback.conf"
grep -Fq 'backup_system_file /usr/local/share/libcamera/ipa/simple/ov5693.yaml' "$adapted"
grep -Fq '/usr/local/share/libcamera/ipa/simple/ov5693.yaml' "$adapted"
grep -Fq '/usr/local/share/libcamera/ipa/simple/ov5693.yaml' "$ROOT/scripts/rollback.sh"
grep -Fq 'SPDX-License-Identifier: CC0-1.0' "$tmp/upstream/ubuntu-deployment/ov5693.yaml"
grep -Fq 'sudo install -D -m 0755' "$adapted"
grep -Fq 'record_unit_enablement_state surface7-front-camera.service' "$adapted"
grep -Fq 'record_unit_enablement_state sp7-camera-boot.service' "$adapted"
grep -Fq 'record_unit_enablement_state surface7-front-camera.timer' "$adapted"
grep -Fq 'OnBootSec=60s' "$tmp/upstream/ubuntu-deployment/surface7-front-camera.timer"
grep -Fq 'systemctl enable surface7-front-camera.timer' "$adapted"
if grep -Fq 'systemctl enable surface7-front-camera.service' "$adapted"; then
    echo "Front camera service must start via its delayed boot timer." >&2
    exit 1
fi
grep -Fq 'sudo dkms add -m "$DKMS_PACKAGE" -v "$DKMS_VERSION"' "$adapted"
grep -Fq 'sudo dkms build -m "$DKMS_PACKAGE" -v "$DKMS_VERSION" -k "$KVER"' "$adapted"
grep -Fq 'sudo dkms install -m "$DKMS_PACKAGE" -v "$DKMS_VERSION" -k "$KVER"' "$adapted"
grep -Fq 'sudo install -m 0644 "$ROOT/config/ownership-marker"' "$adapted"
grep -Fq 'AUTOINSTALL="yes"' "$tmp/upstream/dkms.conf"
grep -Fq 'PRE_INSTALL="scripts/dkms-pre-install.sh ${kernelver}"' "$tmp/upstream/dkms.conf"
grep -Fq '/updates/dkms/intel-ipu4p.ko.zst' "$tmp/upstream/scripts/sp7-camera-boot"
if grep -Fq 'Kein linux-surface-Kernel' "$tmp/upstream/scripts/sp7-camera-boot"; then
    echo "Ubuntu boot loader still skips non-surface kernel names." >&2
    exit 1
fi
grep -Fq 'BUILT_MODULE_NAME[8]="v4l2loopback"' "$tmp/upstream/dkms.conf"
grep -Fq 'install -m 0644 "$KMOD_M/$module.ko" "$ROOT/$module.ko"' \
    "$ROOT/scripts/dkms-build-modules.sh"
grep -Fq 'dkms remove -m "$dkms_package" -v "$dkms_version" --all' \
    "$ROOT/scripts/rollback.sh"
grep -Fq 'unmarked DKMS source has a registered module' "$ROOT/scripts/rollback.sh"
grep -Fq 'dkms_registration="/var/lib/dkms/${dkms_package}/${dkms_version}"' \
    "$ROOT/scripts/rollback.sh"
grep -Fq 'deployment-kernel' "$ROOT/scripts/install.sh"
grep -Fq 'sudo install -m 0755 "$ROOT/scripts/rollback.sh"' "$ROOT/scripts/install.sh"
grep -Fq 'sudo install -m 0644 "$ROOT/config/ubuntu.env"' "$ROOT/scripts/install.sh"
grep -Fq 'Rollback command: %s/scripts/rollback.sh' "$ROOT/scripts/install.sh"
grep -Fq 'persistent rollback helper' "$ROOT/scripts/install.sh"
grep -Fq 'KEEP_TMP=1' "$ROOT/scripts/install-from-github.sh"
grep -Fq 'source checkout retained at' "$ROOT/scripts/install-from-github.sh"
grep -Fq 'deployed_kernel="$(sudo cat "$deployment_kernel_marker")"' "$ROOT/scripts/rollback.sh"
grep -Fq 'backup_once "/etc/systemd/system/$unit"' "$ROOT/scripts/deploy-services.sh"
grep -Fq 'systemctl enable surface7-front-camera.timer' "$ROOT/scripts/deploy-services.sh"
if grep -Fq 'systemctl disable --now' "$ROOT/scripts/deploy-services.sh"; then
    echo "Service-only deployment must not stop currently running camera processes." >&2
    exit 1
fi

if grep -Eiq 'pipewiresrc|pipewire\.service|wireplumber\.service|libspa-libcamera|systemctl --user' "$adapted"; then
    echo "Adapted deployment still contains a desktop camera bridge path." >&2
    exit 1
fi
if grep -Eiq 'sudo dnf|kernel-surface-devel|rpm -' "$adapted"; then
    echo "Adapted deployment still contains a non-Ubuntu package operation." >&2
    exit 1
fi

bash -n "$adapted"
bash -n "$tmp/upstream/scripts/sp7-camera-boot"
if cmp -s "$ROOT/upstream/surface-pro-7-camera/install.sh" "$adapted"; then
    echo "Adapter did not change the temporary installer." >&2
    exit 1
fi
[[ "$(sha256sum "$ROOT/upstream/surface-pro-7-camera/install.sh" | awk '{print $1}')" == "$EXPECTED_UPSTREAM_SHA" ]]

echo "PASS: pinned source, Ubuntu/GStreamer adapter, rollback hooks, and shell syntax"
