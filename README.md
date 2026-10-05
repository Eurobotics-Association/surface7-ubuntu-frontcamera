# Surface Pro 7 front camera on Ubuntu

This repository adapts the Surface Pro 7 IPU4P camera stack for Ubuntu 24.04 and a GStreamer capture service for the front RGB camera. The GStreamer path has produced viewable frames and V4L2 loopback readback under temporary settings. Persistent deployment, ordinary-app access, moving-subject validation, and color tuning remain; support is experimental.

## Current target and status

The host is running Ubuntu's latest installed HWE generic kernel; the out-of-tree camera modules are registered with DKMS and installed for the current and a second installed Ubuntu kernel. The front OV5693 produced visible frames at 1296 × 972 with the matching simple-IPA tuning file. A temporary four-buffer loopback reload also allowed separate GStreamer readback from `/dev/video83` at 1280 × 720. The host was restored to its original two-buffer setting after testing; the tuning file and four-buffer option still need rollback-safe deployment. The image currently has a strong green cast and clipped highlights. The one-time `iommu=pt` diagnostic setting is not a proven fix and remains active only for the current boot. See the [DKMS and kernel plan](docs/dkms-plan.md), [test record](docs/testing.md), and [dated investigation log](docs/front-camera-investigation-2026-10-05.md).

## Camera path

~~~text
OV5693 front RGB sensor -> Intel IPU4P -> libcamera SimplePipeline / SoftISP
-> GStreamer libcamerasrc -> video conversion/scaling -> v4l2loopback /dev/video83
~~~

The design uses GStreamer and libcamera's `libcamerasrc`. It does not use a PipeWire camera source, SPA plugin, or WirePlumber camera rule. The system timer is intended to start the bridge after delayed IPU4 initialization; it is currently disabled during diagnosis. Treat the privacy indicator as active whenever a capture is running.

## Status and diagnostics

Use these read-only checks to inspect the host:

~~~sh
./scripts/check-system.sh
./scripts/status.sh
~~~

After an existing deployment, update only the systemd units with:

~~~sh
bash ./scripts/deploy-services.sh
~~~

This checks the ownership marker, backs up unit files and their original enabled states once, enables the 60-second boot timer, and disables direct boot activation. It leaves an already-running camera process alone; the change takes effect on the next boot. Use the normal rollback command to restore the saved service state.

For a fresh install directly from the public GitHub repository, run:

~~~sh
curl -fsSL https://raw.githubusercontent.com/Eurobotics-Association/surface7-ubuntu-frontcamera/main/scripts/install-from-github.sh | bash -s -- --install
~~~

This downloads the installer from `main`, checks/installs required Ubuntu packages, builds for the running Ubuntu kernel, and deploys the experimental camera stack. It asks for sudo when needed. Review the script and repository first; do not use this command to upgrade an existing deployment without first following the rollback instructions.

The deployed stack is still under validation. Do not treat a successful DKMS build, loaded modules, or `/dev/media0` alone as proof that the camera works. Acceptance requires moving, non-black frames from `/dev/video83`, ordinary video-application access, and persistence after reboot and a later kernel update.

## Rollback

~~~sh
./scripts/rollback.sh
~~~

Rollback verifies the ownership marker, stops and disables the camera services, restores saved files and modules, removes product-scoped files, and refreshes the module and dynamic linker databases. APT packages remain installed.

## Repository contents

- `upstream/surface-pro-7-camera/` — pinned vendor source, kept unchanged.
- `scripts/prepare-upstream-installer.py` — checksum-checked Ubuntu adaptations to a temporary copy.
- `scripts/install-build-deps.sh` — checks and installs Ubuntu build and GStreamer packages.
- `scripts/install.sh` — selects the running Ubuntu kernel; deployment and DKMS are installed, while camera capture remains under validation.
- `scripts/rollback.sh` — ownership-checked restoration of replaced system state.
- `docs/` — research, evidence, rollback behavior, and the proposed kernel/DKMS plan.

The front IR camera is outside this repository's scope. Surface 5 files are not used or modified.
