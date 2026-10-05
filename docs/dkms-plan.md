# Proposed Ubuntu kernel and DKMS plan

**Status: awaiting Robert's review. No installer or camera code changes are approved yet.**

## Goal

Run the Surface Pro 7 front camera on Ubuntu 24.04 using the latest installed Ubuntu HWE kernel and its matching headers. The legacy `6.19.8-surface-3` kernel is not the target and is slated for removal. Exact host-kernel inventory is kept out of this public repository.

Keep camera capture on the tested GStreamer/libcamera path:

~~~text
OV5693 -> IPU4P -> libcamera libcamerasrc -> GStreamer -> V4L2 loopback
~~~

Do not use a PipeWire camera source, SPA plugin, or WirePlumber camera rule.

## DKMS findings

DKMS can build and install an out-of-tree module for each installed kernel when matching headers are present. Its source and `dkms.conf` need to remain in `/usr/src`; `AUTOINSTALL="yes"` lets Ubuntu's DKMS integration attempt builds as new kernels are installed. `dkms status` and `dkms autoinstall -k <kernel-version>` provide verification and a targeted build action. DKMS still compiles the modules separately for each kernel. It does not solve source/API incompatibility, and a failed build must be visible rather than silently treated as camera support.

The IPU4P drivers and `v4l2loopback` are kernel modules and are candidates for DKMS. libcamera, its GStreamer plugin, and the GStreamer bridge are userspace components and should remain outside DKMS. Whether the full patched IPU4P source set can be expressed cleanly as one or more DKMS modules must be verified from the pinned source before implementation.

References: [Ubuntu 24.04 DKMS manual](https://manpages.ubuntu.com/manpages/noble/man8/dkms.8.html), [DKMS upstream manual](https://github.com/dkms-project/dkms/blob/main/dkms.8.in), and [Surface Pro 7 IPU4 discussion](https://github.com/linux-surface/linux-surface/discussions/1353). Recent community camera work is promising but its validated 6.19.8 build does not prove compatibility with the host's current Ubuntu HWE kernel.

## Proposed steps

1. **Clean and document the baseline.** Sync the local checkout to the repository's current `main`, record that the camera modules, firmware, and services were rolled back, and retain the build packages already installed. Remove only the exact legacy `6.19.8-surface-3` image and header packages after confirming the host is booted on its latest Ubuntu HWE kernel; do not run broad `apt autoremove` cleanup.
2. **Confirm the target.** Read the running kernel, latest installed Ubuntu HWE image, and exact matching header path. Build against the current selected Ubuntu HWE kernel without hard-coding a release as the permanent target. The build/deploy command should operate on an explicit validated kernel target and reject missing/mismatched headers.
3. **Prove a normal Ubuntu build.** Rebase or adapt the IPU4P patches to the current Ubuntu kernel sources/headers and compile the driver modules. If the existing out-of-tree build cannot work due to source/API changes, first assess the smallest compatible source patch. Build a custom Ubuntu kernel package only if the needed driver integration cannot be built and loaded as out-of-tree modules.
4. **Prove direct GStreamer capture.** Use rollback-safe deployment, load the modules on the target kernel, confirm firmware and front-sensor enumeration, then verify `libcamerasrc` and capture non-black changing frames through `/dev/video83`. Do not claim success from compilation or node enumeration alone.
5. **Package kernel modules for DKMS.** Keep the reviewed patched source and DKMS metadata in a stable `/usr/src/surface7-ipu4p-<version>` location. Use Ubuntu's DKMS hooks with `AUTOINSTALL="yes"`; specify module names, source files, build command, and install paths explicitly. Use `updates/dkms`, check module collisions and rollback behavior, and verify all modules are tracked with `dkms status`.
6. **Exercise automatic rebuild behavior.** First invoke `dkms autoinstall -k <selected-kernel-version>` and check the module files/status. Then test a second installed Ubuntu kernel with matching headers if one is available. Confirm that a new-kernel DKMS build is attempted during package installation and that a failed build is reported clearly. Do not install a different kernel just to simulate this unless separately authorized.
7. **Make install and rollback repeatable.** Installer checks/installs the Ubuntu DKMS and matching header packages, registers a versioned source tree, builds and loads the selected target modules, and installs userspace libraries/services with backups. Rollback unregisters the exact project DKMS versions, removes only owned module files, restores any pre-existing files and service state, and leaves unrelated kernels/modules untouched. Do not delete DKMS source/backups until rollback ownership is verified.
8. **Document upgrade behavior.** Explain that DKMS rebuilds modules for each new kernel (it does not eliminate per-kernel compilation), while libcamera/GStreamer userspace normally remains installed. Require a camera smoke test after kernel upgrades because a successful DKMS build is not proof of a working sensor pipeline.

## Ventilation investigation (separate work)

Before or alongside camera work, collect read-only evidence about fan/thermal behavior: exact Surface model/CPU, current kernel, firmware version, `sensors`, thermal zones and trip points, `/sys/class/thermal/cooling_device*`, fan/EC telemetry if exposed, `thermald` and power-profile service status, and relevant kernel logs. Compare observed sensors and cooling devices to the upstream Surface Pro 7 thermal reports. Do not install another thermal tool, alter fan curves, write MSRs, or change firmware/kernel settings as part of this camera plan.

For compilation and camera tests, follow the user's limit: continue below 95°C and pause at or above 95°C. Record temperature and fan observations with test outcomes.

## Review gates

- Robert reviews and approves this plan before any installer, kernel-module, DKMS, deployment, or camera-path code is changed.
- After approval, keep the work Ubuntu/APT-only and do not alter Surface 5.
- Mark support experimental until a live moving-frame test and post-reboot check pass on the target Ubuntu kernel.
