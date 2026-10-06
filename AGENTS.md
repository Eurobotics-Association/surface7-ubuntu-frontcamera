# Agent instructions for this repository

## GitHub workflow

- Use the GitHub plugin for all GitHub repository reads and writes.
- Do not use git push, gh, raw GitHub API requests, or another GitHub client.
- Confirm the destination is Eurobotics-Association/surface7-ubuntu-frontcamera.
- Keep the Surface 5 repository and any Surface 5 checkout unchanged.

## Platform and camera design

- Target Microsoft Surface Pro 7 (not 7+) on Ubuntu 24.04 x86_64 and the latest installed Ubuntu HWE kernel. Verify the running kernel and matching headers before each build; do not publish host-specific kernel inventory in this public repository.
- The obsolete custom kernel used in early experiments is legacy for this host and has been removed. Do not deploy against it or make it the project target.
- Robert approved the kernel/DKMS plan on 5 October 2026. Installer and DKMS changes may proceed, but camera support remains experimental until client capture and stop behavior are reliable across the required application matrix.
- Use Ubuntu packages through apt only. Do not use Fedora package managers, RPM packages, or Fedora-specific system paths.
- Camera capture must use GStreamer with libcamera's libcamerasrc into the V4L2 compatibility device.
- Do not build, install, enable, or configure a PipeWire camera source, SPA plugin, or WirePlumber camera rule.
- Leave the host's existing PipeWire audio and desktop services untouched.
- Keep upstream/surface-pro-7-camera byte-for-byte unchanged; apply audited adaptations only to a temporary copy.

## Installation and rollback

- Ask the user before installing packages or changing the host unless they explicitly authorize those actions in the current task.
- Before any system deployment or camera test, ensure scripts/rollback.sh can restore every file and module that deployment may replace.
- Back up existing files only once, under the product-specific backup directory, and refuse to overwrite unrelated files.
- Do not reboot or reload camera modules unless the user explicitly authorizes a hardware test that requires it.
- Before any reboot, broadcast a system-wide warning to all logged-in users at least 2 minutes in advance, then wait the full 2 minutes before rebooting. Never issue an immediate reboot while users may be working.
- Keep camera support marked experimental until the target Surface 7 passes moving-frame tests in the required clients and reliable idle release.
- The user reports that the Surface fan may not engage when needed. Investigate thermal sensors, cooling devices, fan reporting, and relevant Ubuntu/kernel services separately; start with read-only diagnostics and do not change fan controls or install thermal-management software without an approved plan.
- Thermal handling during compile/testing: continue at readings up to and including 95°C. If any observed reading is above 95°C, pause heavy work for 3 minutes, then resume while continuing to monitor. The user says the firmware will vent the heat; no permanent stop is required at that threshold.

## On-demand V4L2 camera behavior

- The old surface7-front-camera.service ran the physical GStreamer/libcamera capture continuously, which kept the front camera LED lit. Robert authorized stopping it; it is stopped and its timer disabled. Robert confirmed the LED went out. Do not re-enable that old service or timer as part of the current design.
- The pinned v4l2loopback v0.15.4 CLIENT_USAGE event payload is Boolean: 0 means capture idle and 1 means capture active. It is not an app identity or multi-client count. The watcher subscribes to that state; treat ENOENT from nonblocking event dequeue as an empty queue.
- The on-demand design reuses the pinned, unmodified sp7-camera-relay.c: it writes one initialization frame, then waits on the FIFO without repeating idle frames. The controller starts the existing GStreamer/libcamera pipeline on capture-active and stops it after the grace period.
- The design is installed on the Surface 7. Before future system deployments, confirm scripts/rollback.sh covers every replaced service, binary, config, and enablement state. Preserve the one-time previous-deployment snapshot.
- A bounded V4L2 read previously captured 30 frames through /dev/video83; a temporary image was upright (ceiling at top). This is lower-level frame evidence, not proof of app compatibility.
- Current acceptance checkpoint (6 October 2026): Robert reports WebcamTests.com eventually showed 1280×720 RGB at 29 FPS. He did not manually retry. The page's device entry changed after permission approval, asked for approval again, stopped/restarted the stream automatically, then changed its label to Surface Pro 7 Front Camera as stable frames appeared. Closing the tab stopped the source and white LED. Treat page/device identity churn and startup smoothness as unresolved; do not infer its cause without browser/device-enumeration evidence.
- Current Cheese result is failure: it did not discover the synthetic camera in the latest attempt. An isolated GStreamer provider preview worked in an earlier test, but do not treat that as a current Cheese pass or install the provider globally without separate validation and rollback coverage.
- Firefox is not retested on the current on-demand deployment; previous attempts failed. Brave and Opera were user-reported working on an earlier service version and require retesting on the current version.
- Orientation has varied by client. Do not apply a source-wide flip/rotation based on one app; record orientation separately for each client.
- Required application checks: Cheese, Firefox, Brave, Opera, and WebcamTests.com, one client at a time. Record device discovery, permission flow, moving frames, orientation, start/stop transitions, and LED state after closing the client. Teams and Google Meet have not been tested; treat their compatibility as unknown and test them after resolving basic device discovery and browser startup.
- The V4L2 node stays discoverable at idle. Do not replace it with an always-on black-frame source or a local network camera server without an approved design change.

## Source and validation

- Record source commits, firmware checksum, forum references, Ubuntu package names, and camera-test results in the documentation.
- Preserve upstream license notices and license files.
- Distinguish static checks, build results, camera enumeration, and moving-frame capture; never report one as another.
- Deployment scripts and documentation must not claim that systemd startup, a device node, an LED, negotiated caps, or one client's success proves the full application matrix.
- The README quick install is the supported public entry point. Keep install/update, rollback, known failures, and the exact current test matrix documented.
- Do not change Surface 5 files.
