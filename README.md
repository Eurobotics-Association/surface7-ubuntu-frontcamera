Updated: 6 October 2026, 00:01 CEST

# Surface Pro 7 front camera on Ubuntu

## Quick install

For a fresh install on Ubuntu 24.04 x86_64 running on Microsoft Surface Pro 7, run:

~~~sh
curl -fsSL https://raw.githubusercontent.com/Eurobotics-Association/surface7-ubuntu-frontcamera/main/scripts/install-from-github.sh | bash -s -- --install
~~~

The installer checks and installs required Ubuntu packages through APT, builds the camera modules for the running kernel, and deploys the experimental GStreamer camera stack. It asks for sudo when needed. Review the repository and rollback instructions before installing; do not use this fresh-install command to upgrade an existing deployment.

This repository adapts the Surface Pro 7 IPU4P camera stack for Ubuntu 24.04 and a GStreamer capture service for the front RGB camera. The installed GStreamer path has produced viewable, visibly moving frames through `/dev/video83`, and the deployment's rollback path has been exercised. WebcamTests.com has shown live video in Brave and Opera at about 29 FPS and 1280 × 720 RGB. Firefox reports that the camera is in use or blocked, and Cheese currently reports no camera. These app-level failures remain unresolved. The bridge runs continuously, so the front-camera LED stays lit while the service is active even if no app is viewing its output. Support remains experimental while Firefox and Cheese compatibility, image quality, and reboot/kernel-upgrade persistence are checked.

## Current target and status

The host is running Ubuntu's latest installed HWE generic kernel; the out-of-tree camera modules are registered with DKMS for the running kernel and another installed kernel with matching headers. The rollback-safe installer is deployed, including the pinned OV5693 simple-IPA tuning file and persistent `max_buffers=4` loopback setting. The camera bridge runs continuously and keeps the front-camera LED lit even when no desktop app is open. User testing confirms browser capture in Brave and Opera at 29 FPS, RGB, 1280 × 720 (0.92 MP), but Firefox reports a generic in-use/blocked error and Cheese sees no camera. Current diagnostics show the default GStreamer device monitor omits `/dev/video83`, while `--include-hidden` exposes it, and a default MMAP reader fails to allocate buffers while `io-mode=rw` succeeds. A still JPEG captured through the read/write path contains visible scene pixels. Cheese discovery and Firefox WebRTC compatibility remain unresolved. The latest images were captured in low light, so normal-light image quality remains unassessed. No reboot was performed; boot-time and later kernel-upgrade behavior remain unverified. The one-time `iommu=pt` diagnostic setting is not a proven fix and remains active only for the current boot. See the [DKMS and kernel plan](docs/dkms-plan.md), [test record](docs/testing.md), and [dated investigation log](docs/front-camera-investigation-2026-10-05.md).

## Camera path

~~~text
OV5693 front RGB sensor -> Intel IPU4P -> libcamera SimplePipeline / SoftISP
-> GStreamer libcamerasrc -> video conversion/scaling -> v4l2loopback /dev/video83
~~~

The design uses GStreamer and libcamera's `libcamerasrc`. It does not use a PipeWire camera source, SPA plugin, or WirePlumber camera rule. The system timer is enabled to start the bridge after delayed IPU4 initialization; it has not been exercised across a reboot. Treat the privacy indicator as active whenever a capture is running.

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

The deployed stack is still under validation. Do not treat a successful DKMS build, loaded modules, or `/dev/media0` alone as proof that the camera works. Moving, non-black frames from `/dev/video83` are verified. Firefox and Cheese compatibility, image quality, and persistence after reboot and a later kernel update remain open acceptance items.

## Rollback

Installations made from this revision place a self-contained rollback helper in the product directory before deploying system files. This path works after the one-line GitHub installer has cleaned up its temporary checkout:

~~~sh
/usr/local/lib/surface7-ubuntu-frontcamera/scripts/rollback.sh
~~~

If you installed from a local clone, the checkout's copy also works:

~~~sh
./scripts/rollback.sh
~~~

Installations made before this helper was added should use the rollback script from their local repository checkout.

If deployment fails, the GitHub installer keeps its temporary source checkout and prints its rollback path. Rollback verifies the ownership marker, stops and disables the camera services, restores saved files and modules, removes product-scoped files, and refreshes the module and dynamic linker databases. APT packages remain installed.

## Repository contents

- `upstream/surface-pro-7-camera/` — pinned vendor source, kept unchanged.
- `scripts/prepare-upstream-installer.py` — checksum-checked Ubuntu adaptations to a temporary copy.
- `scripts/install-build-deps.sh` — checks and installs Ubuntu build and GStreamer packages.
- `scripts/install.sh` — checks required Ubuntu packages, selects the running Ubuntu kernel, and deploys the experimental stack through DKMS.
- `scripts/rollback.sh` — ownership-checked restoration of replaced system state.
- `docs/` — research, evidence, rollback behavior, and the proposed kernel/DKMS plan.

The front IR camera is outside this repository's scope. Surface 5 files are not used or modified.
