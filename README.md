# Surface Pro 7 front camera on Ubuntu

This repository adapts the Surface Pro 7 IPU4P camera stack for Ubuntu 24.04 and a GStreamer capture service for the front RGB camera. The camera path is experimental and has not passed live-frame acceptance on this Ubuntu installation.

## Current target and status

The deployment scripts still contain a legacy `6.19.8-surface-3` pin and must not be used until the approved kernel/DKMS plan is implemented. The target is the latest Ubuntu HWE kernel installed on the machine, detected at build time with matching headers. See [the DKMS and kernel plan](docs/dkms-plan.md) and [test record](docs/testing.md).

The last build-only validation passed against the legacy 6.19.8 headers. It did not test or validate the camera on the current Ubuntu HWE kernel. No live Surface 7 camera frames have been captured, so Ubuntu camera support remains unvalidated.

## Camera path

~~~text
OV5693 front RGB sensor -> Intel IPU4P -> libcamera SimplePipeline / SoftISP
-> GStreamer libcamerasrc -> video conversion/scaling -> v4l2loopback /dev/video83
~~~

The planned design uses GStreamer and libcamera's `libcamerasrc`. It does not use a PipeWire camera source, SPA plugin, or WirePlumber camera rule. When deployed, the system service keeps the physical front camera active; its privacy indicator should be treated as active while the bridge runs.

## Before deployment

Use read-only inspection while the revised installer is under review:

~~~sh
./scripts/check-system.sh
./scripts/status.sh
~~~

Do not run `install.sh --install` or `install.sh --build-only` yet: both still target the legacy kernel. Deployment instructions will be restored after the approved plan is implemented and the scripts select the current Ubuntu kernel and headers.

## Rollback

~~~sh
./scripts/rollback.sh
~~~

Rollback verifies the ownership marker, stops and disables the camera services, restores saved files and modules, removes product-scoped files, and refreshes the module and dynamic linker databases. APT packages remain installed.

## Repository contents

- `upstream/surface-pro-7-camera/` — pinned vendor source, kept unchanged.
- `scripts/prepare-upstream-installer.py` — checksum-checked Ubuntu adaptations to a temporary copy.
- `scripts/install-build-deps.sh` — checks and installs Ubuntu build and GStreamer packages.
- `scripts/install.sh` — currently legacy-pinned; do not use until revised.
- `scripts/rollback.sh` — ownership-checked restoration of replaced system state.
- `docs/` — research, evidence, rollback behavior, and the proposed kernel/DKMS plan.

The front IR camera is outside this repository's scope. Surface 5 files are not used or modified.
