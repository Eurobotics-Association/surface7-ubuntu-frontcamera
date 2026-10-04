# Surface Pro 7 front-camera research

Research reviewed before deployment planning, 4 October 2026.

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

The Surface 7 source release's installer targets a different Linux distribution, package manager, and kernel release. This repository changes those edges in a temporary source copy: package installation uses Ubuntu APT, the target is Ubuntu 24.04 with kernel 6.19.8-surface-3, and built libraries are installed in a project-specific directory. The vendor snapshot remains unchanged.

The supported project target is Surface Pro 7 on Ubuntu 24.04 with the matching pinned linux-surface kernel. Build, deployment, and camera tests are tracked separately in testing.md.
