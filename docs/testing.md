# Testing and acceptance

## Current state

The intended host target is Surface Pro 7 on Ubuntu 24.04 x86_64 using the latest installed Ubuntu HWE kernel. Confirm the active/latest kernel and exact matching headers again before implementation. The exact host kernel version is kept out of this public repository.

The scripts in this repository are still pinned to `6.19.8-surface-3`. That kernel is legacy on this host and is slated for removal. Do not use the current install or build scripts until the approved kernel/DKMS plan is implemented. No camera installation is active now.

## Test history

- Ubuntu package preflight passed on the host. Required build and GStreamer packages were installed through Ubuntu APT; these packages remain installed after rollback.
- Static build-only validation succeeded for the legacy `6.19.8-surface-3` target. The IPU4P modules and GStreamer-enabled libcamera plugin built and staged. This proves only that the legacy target build completed; it does not validate the desired Ubuntu kernel or live camera.
- On the legacy target, a deployment attempt compiled the IPU4P modules and `v4l2loopback`, then installed the verified IPU4P firmware. Libcamera compilation was interrupted at 114/201 Ninja tasks after a thermal monitor warning at 87°C. The user has since clarified that work may continue below 95°C; future runs follow that limit. There was no compiler failure and no camera capture test.
- The first deployment was rolled back: the added kernel modules and firmware were removed/restored, and camera services are inactive. A later retry was stopped during its initial module build before deployment completed; its rollback confirmed no active camera services. Neither attempt established that the camera works.
- The machine was returned to its original Ubuntu HWE running kernel. The old `6.19.8-surface-3` kernel and header packages are being removed at the user's request.

The Surface thermal monitor reported 87°C during compilation. The user clarified that this is below the device's permitted test limit: continue work below 95°C and pause at or above 95°C. The user also reports that the fan may not engage when needed; record thermal observations and investigate that separately.

## Planned validation after approval

The proposed workflow is in [dkms-plan.md](dkms-plan.md). Once the plan is approved and implemented:

1. Run static validation and build the driver modules against the selected Ubuntu kernel headers.
2. Confirm DKMS status and module metadata for the target kernel before deployment.
3. Deploy with the ownership-checked rollback path, reboot only as required to load the selected kernel modules, and record the kernel version.
4. Check kernel logs, IPU4P/front-sensor enumeration, GStreamer `libcamerasrc`, and the V4L2 loopback device.
5. Capture moving, non-black frames from `/dev/video83`; verify with an application using V4L2 and repeat after reboot.
6. Record DKMS rebuild results for a later installed kernel before claiming automatic kernel-upgrade support.

Acceptance requires successful camera enumeration, moving-frame capture, application access, and persistence after reboot. A build result or detected video node alone is not camera acceptance.
