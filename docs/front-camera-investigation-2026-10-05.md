# Surface Pro 7 front-camera investigation log — 5 October 2026

## Target and constraints

This investigation targets Microsoft Surface Pro 7 (not 7+) with Ubuntu 24.04 x86_64 and the latest installed Ubuntu HWE kernel. The selected capture design remains GStreamer with libcamera's `libcamerasrc`; PipeWire camera integration is out of scope. Exact host-kernel inventory and private image files are intentionally omitted from this public log. Camera support remains experimental until moving, non-black frames are verified in an application.

## What the latest diagnostic established

Earlier attempts on the deployed Ubuntu kernel showed IPU4 CSE firmware-authentication/DMAR errors and failed to enumerate the front camera. On 5 October, a one-time boot with `iommu=pt` changed the observed startup path:

- The front and rear cameras were enumerated by the product-specific libcamera 0.7.2 build.
- The relevant test boot logged CSE authentication completion and did not reproduce the earlier matching CSE boot-load, magic-number timeout, or DMAR DMA-read messages.
- A camera-name quoting error in the service configuration was identified: the direct test must preserve the leading backslash in the ACPI camera ID. With the corrected argument, GStreamer reached `PLAYING` and negotiated a front-camera Bayer stream (`bggr10le`, 1296 × 972 at 30 fps).
- A bounded GStreamer capture wrote raw buffers. The auto-exposure test set `ae-enable=true`, but the effective control value was not verified. Each saved buffer was 2,553,152 bytes.
- Interpreting the saved buffer as little-endian 16-bit words, frame 00 contained only 0 and 1023 values (1,312 zeros and 1,275,264 values at 1023); frame 01 contained only zero values. The row stride/padding has not been established, so these counts are preliminary buffer-level evidence. Neither file yielded a verified, viewable image.
- The privacy LED blinked during the explicit capture. On the user's alert, the producer was stopped, GStreamer capture processes were terminated, and the timer was disabled. A follow-up status check found no process holding the camera device nodes. The user later confirmed the LED had stopped blinking.

The result is **camera initialization and buffer arrival, but no demonstrated image flow**. `PLAYING`, an LED blink, camera enumeration, or a raw file is not proof of a working camera. The `iommu=pt` correlation is promising but does not prove that IOMMU configuration was the root cause or that it fixed DMA. It remains active for the current boot only; the persistent GRUB custom entry was restored, and the next normal reboot clears the setting. Do not repeat the boot-parameter experiment without a separate reason and approval.

## Approved next diagnostic

Robert approved a bounded direct-libcamera capture to determine whether meaningful sensor frames reach libcamera before GStreamer handles them. This is the next camera test; it has not yet been run.

1. Keep the camera service stopped and timer disabled until the controlled test is ready. Do not reboot or reload camera modules for this capture.
2. Read the installed product-specific libcamera capture tool's help first. Use the direct libcamera tool (for example, `cam` if the installed build supports bounded capture) so GStreamer and V4L2 loopback are not in the capture path. Limit the capture to a few frames and stop it explicitly afterward.
3. Record the camera ID, negotiated pixel format and dimensions, plane count, active row bytes, stride, bytes used, frame sequence and timestamp, requested and effective exposure/gain/AE controls, and per-frame pixel statistics after excluding row padding. Preserve relevant kernel logs around that single capture, especially CSE, DMA, and IOMMU messages.
4. Keep any captured image private on the host. Do not upload raw user imagery to this public repository; document only technical metadata and the pass/fail result.

## How to interpret that test

- **Direct libcamera produces valid, changing pixels:** the sensor/driver path is delivering frames. Diagnose the GStreamer caps, allocator/buffer layout, Bayer conversion, and V4L2 loopback path next.
- **Direct libcamera produces flat or invalid data after the buffer layout is verified:** investigate sensor mode/timing and exposure controls, IPU4P/CSE firmware initialization, and DMA/IOMMU behavior. Compare against the Surface 7 references and audit any kernel changes for the target Ubuntu HWE kernel before deploying them.
- **The buffer layout or controls cannot be verified:** stop short of attributing the failure to the sensor or GStreamer. First establish the actual format, stride, and whether the requested camera controls reached the device.

Do not retest a branch already ruled out by a recorded result. After valid direct frames, return to the approved GStreamer bridge and require moving, non-black frames from `/dev/video83`, application access, and a later kernel-upgrade check before calling the camera supported.
