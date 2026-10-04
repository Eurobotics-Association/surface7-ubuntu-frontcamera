# Agent instructions for this repository

## GitHub workflow

- Use the GitHub plugin for all GitHub repository reads and writes.
- Do not use git push, gh, raw GitHub API requests, or another GitHub client.
- Confirm the destination is Eurobotics-Association/surface7-ubuntu-frontcamera.
- Keep the Surface 5 repository and any Surface 5 checkout unchanged.

## Platform and camera design

- Target Microsoft Surface Pro 7 (not 7+) on Ubuntu 24.04 x86_64 and the pinned linux-surface kernel.
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
- Keep camera support marked experimental until the target Surface 7 passes moving-frame tests.

## Source and validation

- Record source commits, firmware checksum, forum references, Ubuntu package names, and camera-test results in the documentation.
- Preserve upstream license notices and license files.
- Distinguish static checks, build results, camera enumeration, and moving-frame capture; never report one as another.
- Do not change Surface 5 files.
