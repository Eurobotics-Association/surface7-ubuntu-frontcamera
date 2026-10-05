# Surface Pro 7 front-camera research

Research reviewed before deployment planning, 4 October 2026.

Updated 5 October 2026 after the host target was corrected: the target is the latest Ubuntu HWE kernel installed on the Surface, with matching headers. The legacy `6.19.8-surface-3` target is not the user's requested target and is slated for removal. This public repository omits exact host-kernel inventory.

## Hardware and capture path

The [Linux Surface discussion #1353](https://github.com/linux-surface/linux-surface/discussions/1353) reports the Surface Pro 7 IPU4P stack working with the front OV5693 sensor and rear camera. It is useful evidence about the Surface 7 hardware and kernel drivers; its reported desktop camera bridge is not used here.

The more directly relevant capture reference is [sp7-ipu4-camera](https://github.com/georgemihaila/sp7-ipu4-camera). Its [front-camera notes](https://github.com/georgemihaila/sp7-ipu4-camera/blob/main/docs/front-camera.md) give a GStreamer pipeline using libcamera's libcamerasrc and v4l2sink for ACPI camera ID \_SB_.PCI0.I2C2.CAMF. The reference's README identifies its native camera bridge as unreliable for image capture and describes the GStreamer route through V4L2 loopback. This project adapts that direct GStreamer design and builds the needed libcamera plugin from pinned source.

The [official libcamera GStreamer documentation](https://docs.libcamera.org/master/getting-started.html) documents libcamerasrc as an optional GStreamer source plugin. The Ubuntu deployment uses APT packages for the build environment and builds the camera libraries from pinned source.

These reports establish a plausible Surface 7 implementation, not a validated Ubuntu result. The final Ubuntu-specific package and service configuration still requires local camera tests.

## Earlier Zorin OS report

The [Zorin forum thread about Surface Pro 7 cameras](https://forum.zorin.com/t/surface-pro-7-internal-camera-not-working-in-zorin-os-17-3-pro/49863) is from August 2025 and predates the later IPU4P work. It is historical context rather than the current hardware solution.

## Surface 5 repository review

The complete Eurobotics-Association/surface5-frontcamera repository was read before adapting this project, including its source, documentation, scripts, checks, and rollback instructions. Its camera details target different Surface hardware, so the Surface 7 implementation follows the Surface 7 IPU4P source and direct GStreamer capture reference. Process ideas carried forward include pinned source provenance, read-only preflight, build-only mode, bounded backups, rollback, and moving-frame acceptance checks. No Surface 5 files were changed.

## Ubuntu adaptation

The Surface 7 source release's installer targets a different Linux distribution, package manager, and kernel release. Existing local adaptations use Ubuntu APT and a project-specific library directory, but they are pinned to the now-obsolete `6.19.8-surface-3`. The next implementation must instead build against the selected Ubuntu kernel and matching headers. The vendor snapshot remains unchanged.

## Current-kernel compatibility

The target is Ubuntu 24.04 x86_64 with the latest installed Ubuntu HWE kernel. The [Linux Surface IPU4 discussion](https://github.com/linux-surface/linux-surface/discussions/1353) contains recent Surface Pro 7 reports of the IPU4P stack and OV5693 front camera working, including a driver patch series validated on Linux 6.19.8. Those reports make the driver path promising, but do not establish that the same source compiles or works against the host's current Ubuntu HWE kernel. That is the next compatibility check; no camera support claim is made yet.

## DKMS assessment

DKMS is a plausible way to keep the out-of-tree IPU4P and loopback kernel modules rebuilt when Ubuntu installs a new kernel. Its module source must remain under `/usr/src` with a valid `dkms.conf`; `AUTOINSTALL="yes"` enables automatic attempts, and `dkms autoinstall` installs modules built for other kernel revisions. A matching kernel headers package is still needed, and DKMS recompiles modules for each kernel version. It does not make an incompatible driver patch compatible with a new kernel or guarantee the build succeeds. See the [Ubuntu 24.04 DKMS manual](https://manpages.ubuntu.com/manpages/noble/man8/dkms.8.html) and [upstream DKMS manual](https://github.com/dkms-project/dkms/blob/main/dkms.8.in).

The plan is to prove the module sources against the host's current Ubuntu kernel first, then package those sources for DKMS only after a normal build and live camera test pass. The separately built libcamera/GStreamer userspace components are not DKMS modules; kernel upgrades do not normally require rebuilding them, though the camera path must be rechecked after kernel-driver changes.

## Surface Pro 7 ventilation context

The linux-surface project has a long-running [Surface Pro 7 thermal-throttling issue](https://github.com/linux-surface/linux-surface/issues/221) and a [thermald configuration discussion](https://github.com/linux-surface/linux-surface/discussions/558). These are historical reports, not a diagnosis of this unit's fan behavior. Investigate this separately using sensor/cooling-device reports, fan telemetry where available, and service/kernel logs before considering configuration changes. Keep this separate from camera driver deployment.
