# Testing and acceptance

## Current state

The target is Surface Pro 7 on Ubuntu 24.04 x86_64 using the latest installed Ubuntu HWE kernel. The exact host kernel version is kept out of this public repository. The legacy `6.19.8-surface-3` packages have been removed.

The current kernel is Ubuntu's generic HWE kernel. DKMS reports the camera modules installed for the current kernel and another installed Ubuntu kernel. The deployed 60-second systemd timer ran after reboot; the boot helper loaded the module stack, pinned MMU1, and created `/dev/media0` plus 56 video nodes. This did not produce a working camera: kernel logs still show failed CSE firmware authentication, libcamera reports no camera, and no frames were captured. Camera support remains experimental.

## Test history

- Ubuntu package preflight passed on the host. Required build and GStreamer packages were installed through Ubuntu APT; these packages remain installed.
- Static build-only validation succeeded for the legacy `6.19.8-surface-3` target. The IPU4P modules and GStreamer-enabled libcamera plugin built and staged. This proves only that the legacy target build completed; it does not validate the desired Ubuntu kernel or live camera.
- On the legacy target, a deployment attempt compiled the IPU4P modules and `v4l2loopback`, then installed the verified IPU4P firmware. Libcamera compilation was interrupted at 114/201 Ninja tasks after a thermal monitor warning at 87°C. The user has since clarified that work continues through 95°C; above 95°C, pause heavy work for 3 minutes and then resume while monitoring. There was no compiler failure and no camera capture test.
- The first deployment was rolled back: the added kernel modules and firmware were removed/restored, and camera services are inactive. A later retry was stopped during its initial module build before deployment completed; its rollback confirmed no active camera services. Neither attempt established that the camera works.
- The machine was returned to Ubuntu's generic HWE kernel. The legacy `6.19.8-surface-3` kernel and header packages were purged at the user's request.
- On 5 October 2026, the dynamic running-kernel selection passed `tests/static-validation.sh` and `scripts/check-system.sh --build-target` on the Surface Pro 7 and Ubuntu 24.04.5 host. Matching headers for the current kernel were present.
- On 5 October 2026, the installer built the patched sensor/bridge and IPU4P modules, `v4l2loopback` 0.15.4, patched libcamera, and the GStreamer `libcamerasrc` plugin. DKMS installation completed for the running Ubuntu kernel; `dkms autoinstall` also completed for a second installed Ubuntu kernel. Representative modules resolved from each kernel's DKMS directory. A full rollback was exercised before the final deployment; the current installation remains available for further testing.
- After booting the latest installed Ubuntu HWE kernel, `sp7-camera-boot.service` reported `/dev/media0` and 56 video nodes, and `surface7-front-camera.service` started. The media graph includes the front `ov5693` sensor. This confirms kernel module load and media-node creation only.
- Unprivileged camera enumeration is inconclusive because physical IPU video nodes are root-only (`0600`). Root-privileged GStreamer enumeration and capture attempts using the deployed `libcamerasrc` plugin and product-specific libcamera 0.7.2 library timed out without producing frames. A direct read from `/dev/video83` failed because the loopback remained in video-output mode. No moving or non-black camera frames have been verified.
- The current boot log includes repeated IPU firmware-authentication/CSE boot-load errors after camera probing. `/etc/modprobe.d/ipu4p.conf` requests `fw_version_check=0`, but the loaded IPU4P module does not advertise that parameter and the kernel logs that it is ignored. This needs to be reconciled with the selected module source before further firmware conclusions.
- The GStreamer bridge was observed blocked in `ipu_buttress_authenticate` (uninterruptible D state) while the kernel logged `Expect magic number timeout 0xffffffeb`, `IPC response: 0x220`, and CSE boot-load failures. The IPU4 boot helper did complete successfully, reporting `/dev/media0` and 56 video nodes. This is not camera acceptance.
- After the delayed startup, GStreamer failed with `Could not find a camera named '_SB_.PCI0.I2C2.CAMF'` and `CameraManager::get() returned nullptr`. Systemd restarted the failed producer twice; the latest attempt again became stuck in the authentication path. Thus delaying startup alone did not solve the failure. The service restart policy should be disabled during further diagnosis to avoid repeated authentication attempts.
- The 60-second systemd timer was tested after reboot and fired as configured. It started the ordered boot helper, which pinned MMU1 before ISYS and created the media nodes. Unit files and original enablement states remain backed up under the product backup directory; rollback can restore them. No moving or non-black frames were captured.
- `modinfo` confirms `sp7_full_fw_recycle_on_first_stream` is supported by the installed ISYS module, but `fw_version_check=0` is not a parameter of the installed IPU4P module and is ignored. Resolve this source/config mismatch when comparing the running module to the known-working reference; do not treat the ignored option as a firmware fix.
- Peak observed package temperature in these checks was 72°C. Continue at readings through and including 95°C; above 95°C, pause heavy work for 3 minutes and then resume while monitoring.

## Remaining validation

The approved workflow is in [dkms-plan.md](dkms-plan.md). Remaining validation:

1. Prevent automatic GStreamer retries during diagnosis and preserve the current boot's kernel, module, and service logs.
2. Compare the exact IPU4P source and firmware handshake with the known-working Surface Pro 7 reference. The reference was validated on Arch/Linux 6.19.8; its kernel patches do not directly support this Ubuntu 7.x kernel.
3. Resolve CSE firmware authentication and make the product-specific `cam -l` enumerate the front sensor before retrying GStreamer.
4. Capture moving, non-black frames from `/dev/video83`, verify application access, and repeat after a later Ubuntu kernel installation.
5. Re-run rollback after the final driver changes.

Acceptance requires successful camera enumeration, moving-frame capture, application access, and persistence after reboot. A build result, loaded module, active service, or detected video node alone is not camera acceptance.
