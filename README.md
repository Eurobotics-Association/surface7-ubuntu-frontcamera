Updated: 6 October 2026, 22:40 CEST

# Surface Pro 7 front camera on Ubuntu

## Quick install

For Ubuntu 24.04 x86_64 on a Microsoft Surface Pro 7, run:

~~~sh
curl -fsSL https://raw.githubusercontent.com/Eurobotics-Association/surface7-ubuntu-frontcamera/main/scripts/install-from-github.sh | bash -s -- --install
~~~

The installer checks the OS, running kernel, matching headers, and required packages; it installs missing Ubuntu packages through APT and asks for sudo when needed. A fresh installation builds/registers the kernel support with DKMS and deploys the on-demand GStreamer services. On an existing project-owned installation, the same command verifies ownership and the running-kernel record, then updates the service design without rebuilding DKMS. It does not reboot.

If the camera kernel modules were just installed and `/dev/video83` is not present yet, the services are enabled for the next boot but are not started. Reboot only when you are ready and follow the system-wide two-minute warning instruction in `AGENTS.md`.

## Camera and privacy behavior

The physical image path uses GStreamer with libcamera's `libcamerasrc`, then writes YUYV frames through a FIFO into v4l2loopback at `/dev/video83`. PipeWire camera sources, SPA plugins, and WirePlumber camera rules are not used.

The V4L2 device remains discoverable while idle. A small relay writes one initialization frame and then waits on the FIFO; it does not generate black frames repeatedly. When an application starts capture, the kernel's v4l2loopback `CLIENT_USAGE` event starts the physical GStreamer pipeline. After capture becomes idle for the two-second grace period, the pipeline stops. Only the relay and event watcher remain running while idle.

Robert confirmed that stopping the previous always-on service extinguished the white front-camera LED without a reboot. The new on-demand service transition is still experimental until its real capture/stop behavior and app matrix pass on the Surface.

## Current validation

Earlier tests produced a live 1280×720 RGB stream at about 29 FPS in the Codex in-app WebcamTests page. Cheese also displayed an upright preview using the isolated GStreamer provider; its launch emitted non-fatal GStreamer critical warnings. Browser orientation has varied between applications and must be checked again on the new service.

The agent has not verified the new on-demand relay/controller against Cheese, Firefox, Brave, Opera, or WebcamTests.com after deployment. See [the on-demand investigation and test record](docs/on-demand-v4l2-prototype.md) and [the general test log](docs/testing.md). Do not infer live capture from module load, device enumeration, or a successful build.

## Install, update, and inspect

The one-line command above supports fresh installation and updating an existing project-owned installation. From a checked-out repository, the service update can also be run with:

~~~sh
./scripts/install.sh --deploy-services
~~~

Inspect current services and devices with:

~~~sh
./scripts/check-system.sh
./scripts/status.sh
systemctl status surface7-front-camera-idle-relay.service surface7-front-camera-on-demand.service
~~~

The old always-on unit and its timer are removed during migration. The new services are enabled at boot; the physical camera pipeline remains stopped until a capture request arrives.

## Rollback

Restore the previous camera-service setup while keeping DKMS modules, firmware, and packages installed:

~~~sh
/usr/local/lib/surface7-ubuntu-frontcamera/scripts/rollback.sh --previous-deployment
~~~

Remove the project deployment and restore saved system files:

~~~sh
/usr/local/lib/surface7-ubuntu-frontcamera/scripts/rollback.sh
~~~

The rollback scripts stop camera services before restoring files. A full rollback can restore older kernel-module files and may require a later manual reboot; the script never reboots automatically. Backups are kept under `/var/lib/surface7-ubuntu-frontcamera/backup`.

## Project scope

- Target: Microsoft Surface Pro 7 (not 7+) with Ubuntu 24.04 x86_64 and the running Ubuntu HWE kernel.
- `upstream/surface-pro-7-camera/` is a pinned vendor source snapshot and remains unmodified.
- All packages are installed from Ubuntu APT repositories.
- The front IR camera is outside this repository's scope.
- Surface 5 files and checkouts are not used or modified.
