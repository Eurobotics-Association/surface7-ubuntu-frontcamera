# Surface Pro 7 front camera on Ubuntu

This repository adapts the pinned Surface Pro 7 IPU4P camera stack for Ubuntu 24.04 and provides a GStreamer capture service for the front RGB camera. It targets Microsoft Surface Pro 7 (not 7+) with the linux-surface 6.19.8-surface-3 kernel.

## Support status

The source stack and direct GStreamer capture design are based on Surface Pro 7 community reports. They do not validate this Ubuntu deployment, which remains experimental until the local camera produces non-black, changing frames and survives a reboot.

## Camera path

~~~text
OV5693 front RGB sensor -> Intel IPU4P -> libcamera SimplePipeline / SoftISP
-> GStreamer libcamerasrc -> video conversion/scaling -> v4l2loopback /dev/video83
~~~

The systemd bridge starts at boot and keeps the physical front camera active while the service runs. Stop it with sudo systemctl stop surface7-front-camera.service; start it again with sudo systemctl start surface7-front-camera.service. The camera's privacy indicator should be treated as active whenever the bridge is running.

## Prepare and install

Inspect the machine without changing it:

~~~sh
./scripts/check-system.sh --build-target
./scripts/status.sh
~~~

Build the pinned modules and GStreamer-enabled libcamera stack for the target kernel:

~~~sh
./scripts/install.sh --build-only
~~~

The installer checks for all required Ubuntu packages, GStreamer elements, and matching kernel headers. It uses APT to install missing packages and asks for sudo only when needed. Build-only does not install camera modules, firmware, libraries, or services into system locations.

After the build succeeds, boot 6.19.8-surface-3 and deploy:

~~~sh
./scripts/install.sh --install
~~~

The installer checks for the required packages again, backs up files it may replace, writes a project ownership marker, deploys the IPU4P stack and GStreamer bridge, and enables the services for the next boot. It does not reload camera modules or reboot. If deployment fails partway through, use the rollback script.

For a fresh machine using the published GitHub repository:

~~~sh
curl -fsSL https://raw.githubusercontent.com/Eurobotics-Association/surface7-ubuntu-frontcamera/main/scripts/install-from-github.sh | bash -s -- --install
~~~

Review the repository and script before running that command. Package installation and system deployment require sudo.

## Rollback

~~~sh
./scripts/rollback.sh
~~~

Rollback verifies the ownership marker, stops and disables the deployed services, restores saved files and modules, removes product-scoped files, and refreshes the module and dynamic linker databases. APT packages remain installed. Reboot after rollback to return to the previous camera module state.

## Repository contents

- upstream/surface-pro-7-camera/ — unchanged pinned vendor source.
- scripts/prepare-upstream-installer.py — checksum-checked Ubuntu changes applied only to a temporary copy.
- scripts/install-build-deps.sh — verifies and installs the Ubuntu build and GStreamer packages.
- scripts/install.sh — package preflight, build-only mode, and explicit deployment.
- scripts/rollback.sh — ownership-checked restoration of replaced system state.
- docs/ — research, pinned source details, test instructions, and rollback behavior.

The front IR camera is outside this repository's scope. Surface 5 files are not used or modified.
