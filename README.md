Updated: 6 October 2026, 23:40 CEST

# Surface Pro 7 front camera on Ubuntu

## Quick install

For Ubuntu 24.04 x86_64 on a Microsoft Surface Pro 7, run:

~~~sh
curl -fsSL https://raw.githubusercontent.com/Eurobotics-Association/surface7-ubuntu-frontcamera/main/scripts/install-from-github.sh | bash -s -- --install
~~~

The GitHub installer checks the device, Ubuntu release, running kernel, matching headers, and required packages. It installs missing Ubuntu packages through APT and asks for sudo when needed. A fresh install builds/registers the camera modules with DKMS and deploys the on-demand GStreamer services. On an existing project-owned installation, it updates the services without rebuilding DKMS. It never reboots automatically.

## Current status

The experimental on-demand design is deployed. It keeps /dev/video83 discoverable using a low-activity relay with one initialization frame; it does not send black frames continuously. The physical camera pipeline starts when a client requests capture and stops after the client releases it.

Robert reports that WebcamTests.com eventually showed live video after three attempts: RGB 1280×720 at 29 FPS, labeled “Surface Pro 7 Front Camera.” The camera source started and stopped during the retries. After the successful session, closing the browser tab stopped the source and the white camera LED went out. This confirms one working browser session and idle release, while the repeated starts remain an open reliability issue.

The latest Cheese attempt did not discover the synthetic camera. Cheese is not accepted yet. Firefox has not been retested against the current on-demand deployment; previous attempts failed. Brave and Opera worked in earlier user tests, but must be retested on this deployment before they are called current passes. Image orientation has differed between clients, so no global rotation is applied. See the [handoff and acceptance record](docs/handoff-current.md), [detailed on-demand investigation](docs/on-demand-v4l2-prototype.md), and [test log](docs/testing.md).

## Install, update, and inspect

The command above supports both fresh installation and updating an existing project-owned install. From a checked-out repository, update only the on-demand services with:

~~~sh
./scripts/install.sh --deploy-services
~~~

Read-only checks:

~~~sh
./scripts/check-system.sh
./scripts/status.sh
systemctl status surface7-front-camera-idle-relay.service surface7-front-camera-on-demand.service
~~~

The installer checks required packages and kernel headers. It installs missing Ubuntu packages with APT and sudo when necessary. The old always-on unit and timer are disabled and removed during migration; the on-demand services are enabled at boot. The physical camera pipeline remains stopped while no client is capturing.

## Rollback

Restore the previous camera-service setup while keeping DKMS modules, firmware, and packages installed:

~~~sh
/usr/local/lib/surface7-ubuntu-frontcamera/scripts/rollback.sh --previous-deployment
~~~

Remove the project deployment and restore saved system files:

~~~sh
/usr/local/lib/surface7-ubuntu-frontcamera/scripts/rollback.sh
~~~

The previous-deployment rollback restores the prior service state; if that state used continuous capture, the camera LED may turn on again. Full rollback can restore older kernel-module files and may require a later manual reboot. Neither rollback mode reboots automatically. Backups are under /var/lib/surface7-ubuntu-frontcamera/backup.

## Scope

- Target: Microsoft Surface Pro 7 (not 7+) with Ubuntu 24.04 x86_64 and the currently running Ubuntu kernel.
- Camera capture uses GStreamer with the Surface-built libcamera plugin and libcamerasrc.
- No PipeWire camera source, SPA plugin, or WirePlumber camera rule is installed or configured.
- Packages come from Ubuntu APT repositories.
- upstream/surface-pro-7-camera/ is a pinned vendor source snapshot and remains unmodified.
- The front IR camera is outside this repository's scope. Surface 5 files and checkouts are not used or modified.
