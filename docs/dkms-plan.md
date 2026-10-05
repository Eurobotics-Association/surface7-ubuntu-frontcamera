# Proposed Ubuntu kernel and DKMS plan

Approved by Robert on 5 October 2026. Implementation and host validation are underway; this is not yet a deployment-ready release.

**Status: approved. Kernel selection and build-only validation passed. DKMS install/autoinstall passed for two installed kernels. The front camera now produces viewable frames and V4L2 loopback readback under temporary settings. Rollback-safe deployment, ordinary-application access, moving-subject validation, and image color tuning remain.**

## Goal

Run the Surface Pro 7 front camera on Ubuntu 24.04 using the latest installed Ubuntu HWE kernel and its matching headers. The obsolete custom kernel used in early experiments is not the target and has been removed from the host. Exact host-kernel inventory is kept out of this public repository.

Keep camera capture on the tested GStreamer/libcamera path:

~~~text
OV5693 -> IPU4P -> libcamera libcamerasrc -> GStreamer -> V4L2 loopback
~~~

Do not use a PipeWire camera source, SPA plugin, or WirePlumber camera rule.

## DKMS findings

DKMS can build and install an out-of-tree module for each installed kernel when matching headers are present. Its source and `dkms.conf` need to remain in `/usr/src`; `AUTOINSTALL="yes"` lets Ubuntu's DKMS integration attempt builds as new kernels are installed. Ubuntu also has a boot-time autoinstaller for kernels where an autoinstall module is still missing. `dkms status` and `dkms autoinstall -k <kernel-version>` provide verification and a targeted build action. DKMS still compiles the modules separately for each kernel. It does not solve source/API incompatibility, and a failed build must be visible rather than silently treated as camera support. [Ubuntu DKMS manual](https://manpages.ubuntu.com/manpages/noble/man8/dkms.8.html)

Expected side effects: kernel/header upgrades can take longer while DKMS compiles modules and may temporarily increase CPU use, fan activity, and temperature. Once modules are built and installed for a kernel, routine boots do not normally recompile them; the boot-time autoinstaller can add delay if a module is still missing for that kernel. If compilation fails for a new kernel, the system can still boot, but camera modules may be unavailable on that kernel until the source is fixed or a compatible kernel is selected. Continue work through 95°C; above 95°C pause for 3 minutes, then resume and continue monitoring.

The IPU4P drivers and `v4l2loopback` are packaged as nine DKMS-built modules. libcamera, its GStreamer plugin, and the GStreamer bridge remain userspace components outside DKMS. The source modules compiled against the current Ubuntu kernel in build-only mode; DKMS installed and autoinstalled them for two installed Ubuntu kernels.

References: [Ubuntu 24.04 DKMS manual](https://manpages.ubuntu.com/manpages/noble/man8/dkms.8.html), [DKMS upstream manual](https://github.com/dkms-project/dkms/blob/main/dkms.8.in), and [Surface Pro 7 IPU4 discussion](https://github.com/linux-surface/linux-surface/discussions/1353). Recent community camera work is promising, but its build on an older kernel branch does not prove compatibility with the host's current Ubuntu HWE kernel.

## Implementation sequence

1. **Clean and document the baseline.** Record that the obsolete custom-kernel and header packages were purged; retain build packages. Do not run broad `apt autoremove` cleanup.
2. **Confirm the target and build compatibility.** The current-running-kernel selection, matching headers, all IPU4P/kernel modules, `v4l2loopback`, patched libcamera, and GStreamer plugin passed build-only validation on 5 October 2026. No system files were deployed.
3. **Package kernel modules for DKMS.** The installer prepares a versioned `/usr/src/surface7-ubuntu-frontcamera-0.1.0` source tree, builds nine out-of-tree modules through DKMS, and sets `AUTOINSTALL="yes"`. DKMS install and autoinstall were verified for two installed Ubuntu kernels.
4. **Exercise automatic rebuild behavior.** Completed for another already-installed Ubuntu kernel with matching headers. Do not install a different kernel just to simulate this.
5. **Prove rollback-safe deployment and capture.** A temporary GStreamer/libcamera capture produced viewable 1296 × 972 frames after loading the OV5693 IPA tuning. A temporary `v4l2loopback` reload with `max_buffers=4` then passed synthetic and real camera producer/consumer readback. The original two-buffer setting was restored; the new tuning and module option still need to be deployed through the installer with rollback coverage. The image has a green cast and clipped highlights, and no ordinary camera application or moving subject has been tested.
6. **Repeat after deployment and reboot.** Validate the installed service, a separate V4L2 consumer, an ordinary camera application, and a moving subject. Confirm camera capture persists after reboot. Explain that DKMS compiles kernel modules for each new kernel while libcamera/GStreamer userspace normally remains installed; require a camera smoke test after kernel upgrades.

## Ventilation investigation (separate work)

Before or alongside camera work, collect read-only evidence about fan/thermal behavior: exact Surface model/CPU, current kernel, firmware version, `sensors`, thermal zones and trip points, `/sys/class/thermal/cooling_device*`, fan/EC telemetry if exposed, `thermald` and power-profile service status, and relevant kernel logs. Compare observed sensors and cooling devices to the upstream Surface Pro 7 thermal reports. Do not install another thermal tool, alter fan curves, write MSRs, or change firmware/kernel settings as part of this camera plan.

For compilation and camera tests, continue at readings up to and including 95°C. If any observed reading is above 95°C, pause heavy work for 3 minutes, then resume while continuing to monitor. Record temperature and fan observations with test outcomes.

## Review gates

- Complete the approved changes locally, validate each step, then publish the validated step to the repository's `main` branch through the GitHub plugin.
- Keep the work Ubuntu/APT-only and do not alter Surface 5.
- Mark support experimental until a live moving-frame test and post-reboot check pass on the target Ubuntu kernel.
