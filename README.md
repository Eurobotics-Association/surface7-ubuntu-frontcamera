# Surface Pro 7 front camera on Ubuntu

This repository adapts the Surface Pro 7 IPU4P camera stack for Ubuntu 24.04 and a GStreamer capture service for the front RGB camera. The camera path is experimental and has not passed live-frame acceptance on this Ubuntu installation.

## Current target and status

The host is running Ubuntu's latest installed HWE generic kernel; the out-of-tree camera modules are registered with DKMS and installed for the current and a second installed Ubuntu kernel. The boot helper created the IPU4 media graph, but root-privileged GStreamer enumeration and capture attempts timed out without producing frames while the kernel reported CSE firmware-authentication errors. A 60-second systemd timer is now deployed for the next boot; its effect on camera capture remains untested. Camera support remains experimental. See the [DKMS and kernel plan](docs/dkms-plan.md) and [test record](docs/testing.md).

## Camera path

~~~text
OV5693 front RGB sensor -> Intel IPU4P -> libcamera SimplePipeline / SoftISP
-> GStreamer libcamerasrc -> video conversion/scaling -> v4l2loopback /dev/video83
~~~

The design uses GStreamer and libcamera's `libcamerasrc`. It does not use a PipeWire camera source, SPA plugin, or WirePlumber camera rule. The system timer starts the bridge after the delayed IPU4 initialization; its privacy indicator should be treated as active while the bridge runs.

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

The current deployed stack is still under live validation. Do not treat a successful DKMS build, loaded modules, or `/dev/media0` alone as proof that the camera works. A pass requires moving, non-black frames from `/dev/video83`.

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
