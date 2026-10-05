#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Apply the audited Ubuntu/GStreamer adaptation to a temporary vendor copy."""

from __future__ import annotations

import hashlib
import pathlib
import sys

PINNED_SHA256 = "e389583af1cf99a46e51377332b95236f153737e4685f8a171a4aabb2390ef6b"
LIBDIR = "/usr/local/lib/surface7-ubuntu-frontcamera"
KERNEL = "${SURFACE7_TARGET_KERNEL:-$(uname -r)}"
NL = chr(10)
BS = chr(92)


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"Expected exactly one {label} anchor, found {count}")
    return source.replace(old, new, 1)


def backup_before_install(source: str, destination: str) -> str:
    candidates = []
    offset = 0
    while True:
        location = source.find(destination, offset)
        if location < 0:
            break
        start = source.rfind("sudo install", 0, location)
        if start >= 0:
            command = source[start:location]
            if len(command) < 300 and chr(10) + chr(10) not in command:
                candidates.append(start)
        offset = location + len(destination)
    if len(candidates) != 1:
        raise SystemExit(
            f"Expected one direct sudo install for {destination}, found {len(candidates)}"
        )
    start = candidates[0]
    return source[:start] + f"backup_system_file {destination}" + NL + source[start:]


def main() -> int:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} TEMP_UPSTREAM_INSTALLER", file=sys.stderr)
        return 2

    path = pathlib.Path(sys.argv[1]).resolve()
    source_bytes = path.read_bytes()
    actual = hashlib.sha256(source_bytes).hexdigest()
    if actual != PINNED_SHA256:
        raise SystemExit(
            f"Refusing unreviewed upstream installer: SHA256 {actual}, expected {PINNED_SHA256}"
        )
    source = source_bytes.decode("utf-8")

    source = replace_once(source, 'EXPECTED_KERNEL="6.19.8-3.surface.fc43.x86_64"',
                          f'EXPECTED_KERNEL="{KERNEL}"', "target kernel")
    source = replace_once(source, 'EXPECTED_FEDORA="43"', 'EXPECTED_UBUNTU="24.04"',
                          "target Ubuntu release")
    source = replace_once(
        source,
        "# Surface Pro 7 rear-camera installer\n#\n# v0.1 target:\n"
        "#   Microsoft Surface Pro 7 (without Plus)\n"
        "#   Fedora Workstation 43\n#   x86_64\n"
        "#   kernel 6.19.8-3.surface.fc43.x86_64",
        "# Surface Pro 7 front-camera installer\n#\n# Ubuntu 24.04, x86_64\n"
        "# currently running Ubuntu kernel with matching headers\n# GStreamer libcamerasrc to V4L2",
        "Ubuntu installer header",
    )
    source = replace_once(
        source,
        "# The default mode targets the exact configuration on which the rear OV8865\n"
        "# camera stack was validated. --allow-untested-distro permits deliberate\n"
        "# experiments on other distributions/kernel versions while retaining the\n"
        "# Surface Pro 7, x86_64, IPU4P, kernel-build-tree and Secure Boot checks.",
        "# The default mode targets Ubuntu 24.04 and the selected Ubuntu kernel.\n"
        "# --allow-untested-distro permits deliberate kernel experiments while retaining\n"
        "# the Surface Pro 7, x86_64, IPU4P, kernel-build-tree and Secure Boot checks.",
        "Ubuntu installer support comment",
    )
    source = replace_once(
        source,
        "      Permit deliberate testing outside the known-good Fedora 43/kernel\n"
        "      combination. Hardware and safety checks remain enforced.",
        "      Permit deliberate kernel testing outside the selected Ubuntu target.\n"
        "      Hardware and safety checks remain enforced.",
        "Ubuntu installer help text",
    )
    source = replace_once(source, 'KVER="$(uname -r)"',
                          'KVER="${SURFACE7_TARGET_KERNEL:-$(uname -r)}"',
                          "build-only target kernel override")

    boot_loader = path.parent / "scripts/sp7-camera-boot"
    boot_source = boot_loader.read_text(encoding="utf-8")
    surface_kernel_guard = (
        "# Nur auf einem linux-surface-Kernel tätig werden." + NL
        + "case \"$KREL\" in" + NL
        + "    *surface*)" + NL
        + "        ;;" + NL
        + "    *)" + NL
        + "        log \"Kein linux-surface-Kernel – Kamera-Loader wird übersprungen.\"" + NL
        + "        exit 0" + NL
        + "        ;;" + NL
        + "esac"
    )
    ubuntu_kernel_guard = (
        "# Ubuntu generic kernels are supported when this product's DKMS stack is installed." + NL
        + 'if [[ ! -e "/lib/modules/$KREL/updates/dkms/intel-ipu4p.ko" && ' + BS + NL
        + '      ! -e "/lib/modules/$KREL/updates/dkms/intel-ipu4p.ko.zst" ]]; then' + NL
        + '    log "Surface 7 IPU4P DKMS module is not installed for $KREL; skipping."' + NL
        + "    exit 0" + NL
        + "fi"
    )
    boot_source = replace_once(boot_source, surface_kernel_guard, ubuntu_kernel_guard,
                               "Ubuntu HWE DKMS boot-loader kernel guard")
    boot_loader.write_text(boot_source, encoding="utf-8")

    source = replace_once(
        source,
        'if [[ "${ID:-}" == "fedora" && "${VERSION_ID:-}" == "$EXPECTED_FEDORA" ]]; then',
        'if [[ "${ID:-}" == "ubuntu" && "${VERSION_ID:-}" == "$EXPECTED_UBUNTU" ]]; then',
        "Ubuntu distribution preflight",
    )
    source = replace_once(
        source,
        'echo "PASS: known-good distribution: Fedora $EXPECTED_FEDORA"',
        'echo "PASS: Ubuntu $EXPECTED_UBUNTU deployment target"',
        "distribution status text",
    )
    source = replace_once(
        source,
        'echo "WARNING: this is not the complete known-good Fedora/kernel combination."',
        'echo "WARNING: this is not the complete supported Ubuntu/kernel combination."',
        "Ubuntu experimental warning",
    )

    source = replace_once(
        source,
        'PIPEWIRE_COMMIT="255541eac34370e312f0c5c8c18e46dc1911352f"' + NL,
        "",
        "remove PipeWire source pin",
    )
    source = replace_once(
        source,
        'PIPEWIRE_REPO="$(repo_for_section PipeWire)"' + NL,
        "",
        "remove PipeWire source lookup",
    )
    source = replace_once(
        source,
        '[[ -n "$PIPEWIRE_REPO" ]] || die "PipeWire repository missing from source-bases.txt"' + NL,
        "",
        "remove PipeWire repository requirement",
    )

    start = source.index('    log "Installing Fedora build dependencies"')
    end = source.index(NL + "fi" + NL + NL + NL + 'if [[ ! -e "$KDIR/Makefile" ]]', start)
    apt_block = """    log "Verifying Ubuntu packages installed by scripts/install-build-deps.sh"

    for package in git git-lfs build-essential cmake meson ninja-build patch pkg-config \\
        python3-jinja2 python3-ply python3-yaml libyaml-dev libssl-dev libevent-dev \\
        libelf-dev libunwind-dev libsystemd-dev libglib2.0-dev libdrm-dev libjpeg-dev \\
        libtiff-dev libsdl2-dev libegl1-mesa-dev libgles2-mesa-dev libncurses-dev \\
        libx11-dev libxcb1-dev libcap-dev pciutils mokutil v4l-utils \\
        gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good \\
        libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev
    do
        status="$(dpkg-query -W -f='${db:Status-Status}' "$package" 2>/dev/null || true)"
        [[ "$status" == installed ]] || die "Required Ubuntu package is missing: $package"
    done
"""
    source = source[:start] + apt_block + source[end:]

    fedora_headers = (
        '    sudo dnf install -y ' + BS + NL
        + '        "kernel-surface-devel-$KVER" ' + BS + NL
        + '        || die "Matching kernel-surface-devel package could not be installed."'
    )
    ubuntu_headers = (
        "    sudo apt-get update" + NL
        + '    sudo apt-get install -y "linux-headers-$KVER" ' + BS + NL
        + '        || die "Matching Ubuntu kernel headers could not be installed."'
    )
    source = replace_once(source, fedora_headers, ubuntu_headers, "Ubuntu header package")

    kmod_start = source.index('make ' + BS + NL + '    -C "$KDIR" ' + BS + NL
                              + '    M="$KMOD_SRC"')
    kmod_end_marker = 'done' + NL + NL + '# -------------------------------------------------------------------------' + NL + '# IPU4P stack'
    kmod_end = source.index(kmod_end_marker, kmod_start) + len('done')
    kmod_block = source[kmod_start:kmod_end]
    source = (source[:kmod_start]
              + 'if [[ "$BUILD_ONLY" -eq 1 ]]; then' + NL
              + kmod_block + NL + 'fi'
              + source[kmod_end:])

    ipu_build_start = source.index('(' + NL + '    cd "$IPU4_SRC"')
    ipu_build_end_marker = "    printf 'PASS: %s\\n' \"$module\"" + NL + 'done'
    ipu_build_end = source.index(ipu_build_end_marker, ipu_build_start) + len(ipu_build_end_marker)
    ipu_build_block = source[ipu_build_start:ipu_build_end]
    source = (source[:ipu_build_start] + 'if [[ "$BUILD_ONLY" -eq 1 ]]; then' + NL
              + ipu_build_block + NL + 'fi' + source[ipu_build_end:])

    v4l2_start = source.index('make ' + BS + NL + '    -C "$V4L2_SRC"')
    v4l2_end_marker = '    || die "Unexpected v4l2loopback version: $V4L2_VERSION"'
    v4l2_end = source.index(v4l2_end_marker, v4l2_start) + len(v4l2_end_marker)
    v4l2_block = source[v4l2_start:v4l2_end]
    source = (source[:v4l2_start] + 'if [[ "$BUILD_ONLY" -eq 1 ]]; then' + NL
              + v4l2_block + NL + 'fi' + source[v4l2_end:])

    source = replace_once(
        source,
        "for gst_element in pipewiresrc videoconvert filesink; do",
        "for gst_element in videoconvert videoscale v4l2sink filesink; do",
        "use GStreamer V4L2 elements without PipeWire",
    )
    source = replace_once(
        source,
        "    -Dpipelines=simple" + NL,
        "    -Dpipelines=simple" + BS + NL + "    -Dgstreamer=enabled" + NL,
        "enable libcamera GStreamer plugin",
    )

    source = source.replace("/usr/local/lib64", LIBDIR)
    source = source.replace("--libdir=lib64", "--libdir=lib/surface7-ubuntu-frontcamera")
    source = source.replace("$(nproc)", "${SURFACE7_BUILD_JOBS:-2}")
    source = source.replace("/var/lib/sp7-camera/backup-v0.1",
                            "/var/lib/surface7-ubuntu-frontcamera/backup/$KVER")
    source = source.replace("/etc/ld.so.conf.d/sp7-camera.conf",
                            "/etc/ld.so.conf.d/surface7-ubuntu-frontcamera.conf")

    libcamera_patch_anchor = (
        'apply_patch ' + BS + NL
        + '    "$LIBCAMERA_SRC" ' + BS + NL
        + '    "$ROOT/patches/libcamera/0001-sp7-camera.patch"' + NL
    )
    enable_front_sensor = """# The pinned patch contains a temporary rear-only experiment guard.
# Remove only its exact OV5693 exclusion so libcamerasrc can enumerate the front sensor.
python3 - "$LIBCAMERA_SRC/src/libcamera/pipeline/simple/simple.cpp" <<'PY'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
source = path.read_text(encoding="utf-8")
begin = "\\t\\t/*\\n\\t\\t * Surface Pro 7 rear-only test."
end = "\\n\\t\\tstd::unique_ptr<SimpleCameraData> data ="
if source.count(begin) != 1 or source.count(end) != 1:
    raise SystemExit("Expected the pinned libcamera OV5693 skip block exactly once")
start = source.index(begin)
stop = source.index(end, start)
block = source[start:stop]
if 'sensor->name().find("ov5693")' not in block or "continue;" not in block:
    raise SystemExit("Refusing to remove an unexpected libcamera block")
path.write_text(source[:start] + source[stop:], encoding="utf-8")
PY
"""
    source = replace_once(
        source,
        libcamera_patch_anchor,
        libcamera_patch_anchor + enable_front_sensor,
        "enable Surface Pro 7 front OV5693 in libcamera",
    )

    ld_line = "    printf '%s" + BS + "n' '" + LIBDIR + "'"
    source = replace_once(
        source,
        ld_line,
        "    backup_system_file /etc/ld.so.conf.d/surface7-ubuntu-frontcamera.conf" + NL + ld_line,
        "dynamic linker configuration backup",
    )

    for destination in (
        "/usr/local/share/libcamera/ipa/simple/ov8865.yaml",
    ):
        source = backup_before_install(source, destination)

    source = replace_once(
        source,
        "else" + NL
        + '    sudo meson install ' + BS + NL
        + '        -C "$LIBCAMERA_BUILD"' + NL,
        "else" + NL
        + '    mkdir -p "$STAGE"' + NL
        + '    DESTDIR="$STAGE" meson install ' + BS + NL
        + '        -C "$LIBCAMERA_BUILD"' + NL + NL
        + '    staged_libdir="$STAGE' + LIBDIR + '"' + NL
        + '    [[ -d "$staged_libdir" ]] || die "Staged libcamera library directory is missing."' + NL
        + '    sudo install -d -m 0755 ' + LIBDIR + NL
        + '    sudo cp -a "$staged_libdir/." ' + LIBDIR + '/' + NL,
        "stage libcamera and install only the product library directory",
    )

    source = replace_once(
        source,
        'log "Installing verified IPU4P firmware"' + NL + NL + 'FW_SOURCE=',
        'log "Installing verified IPU4P firmware"' + NL + NL
        + "backup_system_file /usr/lib/firmware/ipu4p_cpd.bin" + NL + NL + "FW_SOURCE=",
        "firmware backup",
    )

    dkms_module_install = '''# Register and install kernel modules through Ubuntu DKMS.

log "Registering the verified modules with DKMS"
DKMS_PACKAGE="surface7-ubuntu-frontcamera"
DKMS_VERSION="0.1.0"
DKMS_SOURCE="/usr/src/${DKMS_PACKAGE}-${DKMS_VERSION}"
[[ "$(dpkg-query -W -f='${db:Status-Status}' dkms 2>/dev/null || true)" == installed ]] \\
    || die "Ubuntu package dkms is required."
if sudo test -e "$DKMS_SOURCE"; then
    die "DKMS source directory already exists: $DKMS_SOURCE. Roll back the owned deployment before retrying."
fi

# Strip build products so DKMS owns clean, reproducible sources for each kernel.
make -C "$KDIR" M="$KMOD_SRC" clean >/dev/null
make -C "$KDIR" M="$IPU4_SRC/linux-6.19.8/drivers/media/pci/intel" \\
    EXTERNAL_BUILD=1 srcpath="$IPU4_SRC/linux-6.19.8/drivers/media/pci/intel" \\
    CONFIG_VIDEO_INTEL_IPU=m CONFIG_VIDEO_INTEL_IPU4P=y \\
    CONFIG_VIDEO_INTEL_IPU6= CONFIG_VIDEO_IPU3_CIO2= CONFIG_INTEL_VSC= \\
    CONFIG_VIDEO_INTEL_IPU_FW_LIB=y clean >/dev/null
make -C "$KDIR" M="$V4L2_SRC" clean >/dev/null

sudo install -d -m 0755 "$DKMS_SOURCE/kernel-modules" "$DKMS_SOURCE/ipu4-camera" \\
    "$DKMS_SOURCE/v4l2loopback" "$DKMS_SOURCE/scripts"
sudo install -m 0644 "$ROOT/config/ownership-marker" \\
    "$DKMS_SOURCE/.surface7-ubuntu-frontcamera-owned"
for file in ov8865.c dw9719.c ipu-bridge.c Makefile; do
    sudo install -m 0644 "$KMOD_SRC/$file" "$DKMS_SOURCE/kernel-modules/$file"
done
sudo cp -a "$IPU4_SRC/." "$DKMS_SOURCE/ipu4-camera/"
sudo cp -a "$V4L2_SRC/." "$DKMS_SOURCE/v4l2loopback/"
sudo install -m 0644 "$ROOT/dkms.conf" "$DKMS_SOURCE/dkms.conf"
sudo install -m 0755 "$ROOT/scripts/dkms-build-modules.sh" \\
    "$DKMS_SOURCE/scripts/dkms-build-modules.sh"
sudo install -m 0755 "$ROOT/scripts/dkms-pre-install.sh" \\
    "$DKMS_SOURCE/scripts/dkms-pre-install.sh"

sudo dkms add -m "$DKMS_PACKAGE" -v "$DKMS_VERSION"
sudo dkms build -m "$DKMS_PACKAGE" -v "$DKMS_VERSION" -k "$KVER"
sudo dkms install -m "$DKMS_PACKAGE" -v "$DKMS_VERSION" -k "$KVER"
sudo depmod -a "$KVER"
sudo dkms status -m "$DKMS_PACKAGE" -v "$DKMS_VERSION"'''
    install_start = source.index("# Install kernel modules")
    install_end_marker = 'sudo depmod -a "$KVER"'
    install_end = source.index(install_end_marker, install_start) + len(install_end_marker)
    if source.count(install_end_marker) != 1:
        raise SystemExit("Expected exactly one direct module installation section")
    source = source[:install_start] + dkms_module_install + source[install_end:]

    root = path.parent
    loopback_config = root / "config/modprobe.d/sp7-v4l2loopback.conf"
    loopback_config.write_text(
        'options v4l2loopback video_nr=83 card_label="Surface Pro 7 Front Camera" exclusive_caps=1' + NL,
        encoding="utf-8",
    )

    start = source.index("# PipeWire libcamera SPA only")
    end = source.index("# V4L2 compatibility helpers", start)
    source = source[:start] + source[end:]

    start = source.index("# V4L2 compatibility helpers")
    end = source.index("# System configuration", start)
    runtime = r'''# GStreamer/libcamera front-camera deployment

GSTREAMER_PLUGIN="@LIBDIR@/gstreamer-1.0/libgstlibcamera.so"

record_unit_enablement_state() {
    local unit="$1"
    local state_file="$BACKUP_ROOT/systemd-state/$unit"
    local state
    if ! sudo test -e "$state_file"; then
        state="$(systemctl is-enabled "$unit" 2>/dev/null || true)"
        [[ -n "$state" ]] || state=disabled
        sudo mkdir -p "$(dirname "$state_file")"
        printf '%s\n' "$state" | sudo tee "$state_file" >/dev/null
    fi
}

if [[ "$BUILD_ONLY" -eq 1 ]]; then
    STAGED_PLUGIN="$STAGE$GSTREAMER_PLUGIN"
    [[ -f "$STAGED_PLUGIN" ]] || die "Staged libcamera GStreamer plugin is missing."

    GST_PLUGIN_PATH="$(dirname "$STAGED_PLUGIN")" \
    LD_LIBRARY_PATH="$STAGE@LIBDIR@:${LD_LIBRARY_PATH:-}" \
    GST_REGISTRY="$WORK/gstreamer-registry.bin" \
        gst-inspect-1.0 libcamerasrc >/dev/null \
        || die "Staged libcamerasrc plugin could not be loaded by GStreamer."

    log "BUILD-ONLY SUCCESS"
    echo "libcamera GStreamer plugin:"
    sha256sum "$STAGED_PLUGIN"
    echo
    echo "Kernel modules were built for $KVER."
    echo "Patched libcamera and libcamerasrc were built and staged."
    echo "No camera modules, firmware, libraries, services or configuration files were installed."
    exit 0
fi

backup_system_file /usr/local/libexec/surface7-front-camera
sudo install -D -m 0755 \
    "$ROOT/ubuntu-deployment/surface7-front-camera" \
    /usr/local/libexec/surface7-front-camera
backup_system_file /usr/local/sbin/sp7-camera-boot
sudo install -D -m 0755 \
    "$ROOT/scripts/sp7-camera-boot" \
    /usr/local/sbin/sp7-camera-boot

install_system_file \
    "$ROOT/ubuntu-deployment/front-camera.env" \
    /etc/default/surface7-front-camera \
    0644
record_unit_enablement_state surface7-front-camera.service
record_unit_enablement_state sp7-camera-boot.service
record_unit_enablement_state surface7-front-camera.timer
backup_system_file /etc/systemd/system/surface7-front-camera.timer
sudo install -D -m 0644 "$ROOT/ubuntu-deployment/sp7-camera-boot.service" /etc/systemd/system/sp7-camera-boot.service
sudo install -D -m 0644 "$ROOT/ubuntu-deployment/surface7-front-camera.timer" /etc/systemd/system/surface7-front-camera.timer
install_system_file \
    "$ROOT/ubuntu-deployment/surface7-front-camera.service" \
    /etc/systemd/system/surface7-front-camera.service \
    0644

sudo systemctl daemon-reload
sudo systemctl disable surface7-front-camera.service sp7-camera-boot.service 2>/dev/null || true
sudo systemctl enable surface7-front-camera.timer
[[ -f "$GSTREAMER_PLUGIN" ]] || die "Installed libcamera GStreamer plugin is missing."
GST_PLUGIN_PATH="$(dirname "$GSTREAMER_PLUGIN")" \
    gst-inspect-1.0 libcamerasrc >/dev/null \
    || die "Installed libcamerasrc plugin is unavailable."
gst-inspect-1.0 v4l2sink >/dev/null \
    || die "GStreamer v4l2sink is unavailable."

    '''
    runtime = runtime.replace("@LIBDIR@", LIBDIR)
    source = source[:start] + runtime + source[end:]

    source = replace_once(
        source,
        'install_system_file \\' + NL
        + '    "$ROOT/systemd/system/sp7-camera-boot.service"',
        'record_unit_enablement_state sp7-camera-boot.service' + NL
        + 'install_system_file \\' + NL
        + '    "$ROOT/systemd/system/sp7-camera-boot.service"',
        "preserve prior boot service enablement before replacing the unit",
    )
    source = replace_once(
        source,
        'sudo systemctl enable sp7-camera-boot.service',
        'sudo systemctl disable sp7-camera-boot.service 2>/dev/null || true',
        "prevent immediate camera boot service activation",
    )
    start = source.index("# Per-user WirePlumber and controller configuration")
    end = source.index("# Final static verification", start)
    source = source[:start] + """# Native camera applications use the documented V4L2 loopback device.

""" + source[end:]

    source = replace_once(
        source,
        'echo "PipeWire SPA:"' + NL + 'ls -l ' + LIBDIR
        + '/spa-0.2/libcamera/libspa-libcamera.so',
        'echo "libcamera GStreamer plugin:"' + NL + 'ls -l '
        + LIBDIR + '/gstreamer-1.0/libgstlibcamera.so',
        "final GStreamer plugin verification",
    )
    source = replace_once(
        source,
        'echo "User services:"' + NL + 'systemctl --user is-enabled sp7-camera-controller.service || true',
        'echo "GStreamer front-camera service:"' + NL
        + 'systemctl is-enabled surface7-front-camera.service || true',
        "final camera service status",
    )

    source = source.replace(
        "The camera stack has been installed for the current Surface Pro 7 system." + NL
        + "Fedora Workstation 43 with kernel 6.19.8-3.surface.fc43.x86_64 is the" + NL
        + "known-good configuration; installations made with --allow-untested-distro" + NL
        + "are experimental.",
        "The camera stack has been installed for Ubuntu 24.04 on Surface Pro 7." + NL
        + "The direct GStreamer front-camera path is experimental until moving-frame capture passes.",
    )
    source = source.replace(
        "  - GNOME Snapshot should expose Rear Standard and Rear HQ." + NL
        + "  - V4L2 applications should expose Rear Standard, Rear HQ and Rear Fast." + NL
        + "  - Only one physical rear-camera stream can own the sensor at a time.",
        "  - GStreamer libcamerasrc feeds the front RGB camera to /dev/video83." + NL
        + "  - V4L2 applications should expose the Surface Pro 7 front camera." + NL
        + "  - The enabled bridge keeps the front camera active until the service is stopped.",
    )
    source = source.replace(
        "Known v0.1 limitations:" + NL
        + "  - Snapshot and V4L2 applications must not use the physical camera concurrently." + NL
        + "  - Autofocus convergence is relatively slow." + NL
        + "  - Auto-exposure convergence is relatively slow." + NL
        + "  - Rear Fast can show a green cast in low light." + NL
        + "  - Signal may mirror its local self-preview.",
        "Known limitation: Ubuntu 24.04 has not yet passed live moving-frame acceptance.",
    )

    forbidden_camera_path = (
        "pipewiresrc",
        "pipewire.service",
        "wireplumber.service",
        "libspa-libcamera.so",
        "PIPEWIRE_REPO",
        "PIPEWIRE_COMMIT",
        "systemctl --user",
    )
    for token in forbidden_camera_path:
        if token.casefold() in source.casefold():
            raise SystemExit(f"Adapted installer still contains forbidden camera config: {token}")
    forbidden_os_path = ("sudo dnf", "kernel-surface-devel", "rpm -")
    for token in forbidden_os_path:
        if token in source:
            raise SystemExit(f"Adapted installer still contains Fedora package operation: {token}")

    path.write_text(source, encoding="utf-8")
    print(f"Prepared Ubuntu installer at {path}")
    print(f"Target kernel expression: {KERNEL}")
    print(f"Product library directory: {LIBDIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
