# Testing and acceptance

## Current evidence

The project target is Surface Pro 7 on Ubuntu 24.04 with the matching 6.19.8-surface-3 kernel. No build or live front-camera acceptance result has been recorded yet. Keep this status until a target Surface produces non-black, changing frames and passes a reboot check.

## Static validation

Run from the repository root:

~~~sh
./tests/static-validation.sh
~~~

This checks the pinned vendor installer digest, shell and Python syntax, and the adapter output. It does not write to system locations or prove that the camera works.

## Package and build validation

The installer checks its required APT package list, the GStreamer conversion and V4L2 elements, and matching kernel headers. It installs missing Ubuntu packages through APT, using sudo when needed.

~~~sh
./scripts/install.sh --build-only
~~~

Build-only targets /lib/modules/6.19.8-surface-3/build even when another kernel is running. It builds kernel modules, patched libcamera with its GStreamer plugin enabled, stages user-space files in a temporary directory, and verifies libcamerasrc with gst-inspect-1.0. It does not install camera modules, firmware, libraries, services, or configuration into system locations.

## Live camera acceptance

Boot 6.19.8-surface-3 before deployment. The install script installs the kernel modules and enables the GStreamer and IPU4P initialization services for boot. It does not reload camera modules or reboot.

~~~sh
./scripts/install.sh --install
sudo reboot
~~~

After boot, verify the device and services:

~~~sh
./scripts/status.sh
systemctl status sp7-camera-boot.service surface7-front-camera.service
v4l2-ctl --list-devices
gst-inspect-1.0 libcamerasrc
~~~

The front-camera bridge writes to /dev/video83. A V4L2 application should be able to open that device. For a simple stream check:

~~~sh
v4l2-ctl -d /dev/video83 --stream-mmap=3 --stream-count=90 --stream-to=/tmp/surface7-front-test.yuyv
~~~

Confirm that the camera shows the expected live view and that the saved frames change when the scene moves. Repeat after a second reboot. Check errors with:

~~~sh
journalctl -b -k
journalctl -b -u sp7-camera-boot.service -u surface7-front-camera.service
~~~

Acceptance requires:

1. IPU4P, front sensor, and GStreamer service start without unresolved symbols or firmware errors.
2. libcamerasrc enumerates the Surface Pro 7 front sensor.
3. /dev/video83 delivers non-black, changing frames.
4. An application using V4L2 can open the loopback camera and display a live image.
5. The behavior persists after reboot.

Save exact OS and kernel versions, command output, relevant logs, and moving-frame test result in a dated report before describing Ubuntu support as validated.

The GStreamer bridge is enabled as a system service and keeps the front camera active while running. Stop the service when the camera is not needed.
