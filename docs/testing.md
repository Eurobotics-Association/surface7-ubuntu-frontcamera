# Testing and acceptance

## Current state

The Surface Pro 7 on Ubuntu 24.04 x86_64 has produced viewable front-camera images through the product libcamera/GStreamer stack. The capture needed the OV5693 simple-IPA tuning file supplied temporarily from `/tmp`, and the V4L2 loopback needed a temporary `max_buffers=4` module reload. Both direct PNG capture and camera-to-`/dev/video83`-to-GStreamer PNG readback succeeded at a 1296 × 972 source mode and 1280 × 720 loopback mode.

The temporary module setting was restored to the host's original `max_buffers=2`; no persistent deployment change was made. The camera service remains failed/stopped and its timer disabled. Image quality has a strong green cast and clipped highlights. A deliberately moving subject and a regular video application have not yet been tested. Support remains experimental. Exact host-kernel inventory is kept out of this public repository.

The temporary `iommu=pt` boot correlated with successful camera enumeration and frame delivery, but it is not proven to be the root cause. It remains active only for the current boot; the persistent GRUB custom entry was restored.

## Test history

- Ubuntu package preflight passed on the host. Required build and GStreamer packages were installed through Ubuntu APT; these packages remain installed.
- Static build-only validation succeeded for the obsolete custom-kernel target used in early experiments. The IPU4P modules and GStreamer-enabled libcamera plugin built and staged. This proves only that the legacy target build completed; it does not validate the desired Ubuntu kernel or live camera.
- On the legacy target, a deployment attempt compiled the IPU4P modules and `v4l2loopback`, then installed the verified IPU4P firmware. Libcamera compilation was interrupted at 114/201 Ninja tasks after a thermal warning. No camera capture test occurred in that attempt.
- The first deployment was rolled back. The machine was returned to Ubuntu's generic HWE kernel; the obsolete custom-kernel and header packages were purged at the user's request.
- On 5 October 2026, the running-kernel selection passed static validation and build-only checks on the Surface Pro 7. DKMS installed the camera modules for the running Ubuntu kernel and another installed Ubuntu kernel.
- The delayed IPU4 boot helper created the media graph. Earlier attempts showed CSE firmware-authentication/DMAR errors and no camera enumeration. In the temporary `iommu=pt` diagnostic boot, libcamera enumerated both sensors without reproducing the matching CSE/DMAR messages during the tested capture. This is a correlation, not a proven IOMMU fix.
- The first GStreamer RGB attempt failed because `ov5693.yaml` was absent and Software ISP disabled debayering. The pinned OV5693 tuning from ConsultingFuture4200/sp7-camera commit `9bb8ec8bed3ca02c774ef211332fcc8259232b90` was selected from `/tmp` using `LIBCAMERA_SIMPLE_TUNING_FILE`.
- A bounded direct GStreamer capture then produced viewable 1296 × 972 RGB PNG frames. The longer bounded capture delivered 90 buffers over about 8.9 seconds, with autofocus diagnostics active. The scene was visible, but the image had a strong green cast and clipped highlights. The scene was not deliberately moved.
- A default V4L2 loopback producer test failed with error `-5`. A synthetic GStreamer source reproduced it. GStreamer reported that its V4L2 sink needed at least three buffers, while the active loopback module allowed two; it failed allocating the next buffer.
- A temporary reload of only `v4l2loopback` with `max_buffers=4` passed a synthetic producer/consumer readback and a front-camera producer/consumer readback. The latter captured PNGs from `/dev/video83` at 1280 × 720. The module was restored to its original two-buffer setting immediately after testing.
- A 2560 × 1600 source attempt negotiated GStreamer caps but did not enable loopback capture during the bounded startup window; it produced no readback frame. That mode is unverified.
- Current host check after the tests found the loopback node present, no camera process holding it, service failed/stopped, timer disabled, and `max_buffers=2`. The OV5693 tuning file and four-buffer setting are not persistently deployed.
- Peak observed thermal-zone reading during these checks was 57°C. Continue through 95°C; above 95°C pause heavy work for 3 minutes and then resume while monitoring.

## Remaining validation

The repository installer now deploys the pinned OV5693 tuning file, sets `max_buffers=4`, preserves the tested 1296 × 972 source mode, and corrects camera-name escaping. The rollback path includes restoration/removal of the new IPA data file and existing modprobe configuration. These changes have not yet been deployed to the host.

After those changes are deployed, validate the service with a separate `v4l2src` consumer, capture a deliberately moving subject, and test an ordinary video application. Diagnose color balance and highlight clipping. Then verify operation after a normal reboot and a later Ubuntu kernel installation. Do not retry the earlier raw-buffer path as the next diagnostic; viewable pixels and V4L2 loopback readback are already proven under temporary settings.

Acceptance requires moving non-black frames from `/dev/video83`, access from an ordinary camera application, and persistence after reboot/kernel update. Build success, camera enumeration, an LED blink, or negotiated caps alone are not acceptance.
