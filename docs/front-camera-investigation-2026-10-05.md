# Surface Pro 7 front-camera investigation log — 5 October 2026

## Scope and safety

This investigation targets Microsoft Surface Pro 7 (not 7+) with Ubuntu 24.04 x86_64 and the latest installed Ubuntu HWE kernel. The selected camera path is GStreamer with libcamera's `libcamerasrc`; PipeWire camera integration is out of scope. Exact host-kernel inventory and private image files are intentionally omitted. Surface 5 files were not changed.

No reboot was performed during these tests. The one-time `iommu=pt` diagnostic setting is active only for the current boot; its persistent GRUB entry was restored earlier. The user's thermal rule is to continue through 95°C and pause heavy work for 3 minutes only above 95°C. These tests stayed well below that threshold.

## What changed from the earlier diagnosis

Earlier raw-buffer attempts did not establish that image pixels were arriving. A later one-time `iommu=pt` boot allowed the product libcamera build to enumerate both sensors and removed the matching CSE/DMAR messages seen in earlier attempts. This is a useful correlation, not proof that IOMMU settings were the root cause.

The earlier bounded raw capture had negotiated `bggr10le` at 1296 × 972 and wrote 2,553,152-byte buffers. Preliminary word counts showed frame 00 contained mostly 0 and 1023 values and frame 01 contained only zeros; the row stride and active-pixel layout had not been established. Those raw files were not viewable images. The privacy LED blinking during camera startup was also not treated as image evidence. A camera-name quoting bug in the installed service was separately found: sourcing the old environment value left only one backslash, which GStreamer parsed away. The corrected service configuration now retains two backslashes until GStreamer parses the camera ID.

The first RGB capture then exposed a missing dependency in the userspace camera path: the installed libcamera data had no OV5693 tuning file. The logs said `ov5693.yaml` was missing, the simple IPA failed to initialize, and Software ISP disabled software debayering. The only installed simple tuning file was for OV8865.

The Ubuntu package's generic `/usr/bin/cam` is libcamera 0.2.0 and listed no cameras. It is not the product's libcamera 0.7.2 build and was not used as evidence against the working product build.

## OV5693 tuning provenance

The missing tuning file was obtained from [ConsultingFuture4200/sp7-camera](https://github.com/ConsultingFuture4200/sp7-camera/blob/9bb8ec8bed3ca02c774ef211332fcc8259232b90/ipa/simple/ov5693.yaml), commit `9bb8ec8bed3ca02c774ef211332fcc8259232b90`, Git blob `6c8e130ae23cb5428d3c71ea5b88d6f80a43b5b3`. It is marked CC0-1.0. Its SHA-256 is `73845d5ebaedc948ec0cca7b3d2f07ac8081c2f5c3e16c63905ce04532ba21ac`.

For the live tests, the file was kept under `/tmp` and selected with `LIBCAMERA_SIMPLE_TUNING_FILE`. Libcamera logged that it loaded this file; the simple IPA and software ISP then initialized. This proves the tuning file is needed for the demonstrated RGB path. It does not mean the file had already been installed persistently on the host.

## Captured frames

With the temporary tuning override, a bounded GStreamer capture negotiated front-camera output at 1296 × 972. The software ISP reported 2592 × 1944 BGGR10 input with stride 5184. It wrote viewable 8-bit RGB PNGs. A longer bounded run delivered 90 buffers over about 8.9 seconds and ended with EOS; live autofocus diagnostics advanced during the stream.

The pictures show the room and window, so the camera produced actual scene pixels. They have a pronounced green cast and the bright window is clipped. Automatic white balance/color quality still needs work. The scene was not deliberately moved during the capture, so this is not the final moving-subject acceptance test. The private images remain on the host and were not uploaded to GitHub.

## V4L2 loopback test and buffer finding

The first camera-to-loopback attempt used 2560 × 1600 and stopped with GStreamer error `-5`. A separate synthetic `videotestsrc` producer failed the same way, isolating the immediate failure from the camera sensor. GStreamer V4L2 diagnostics showed the sink requesting at least three buffers, then failing to allocate another buffer. The active `v4l2loopback` module allowed only two (`max_buffers=2`).

The loopback uses `exclusive_caps=1`. Before a producer is streaming it advertises output capability only; a capture application can open it after the producer starts. That explains why an early reader saw “not a capture device” while the producer was failing. GStreamer `io-mode=rw` kept the node output-only and did not solve the capture handoff.

A temporary reload of only `v4l2loopback` with `max_buffers=4` fixed the buffer shortage in a synthetic producer/consumer check. With the same temporary setting, a GStreamer/libcamera pipeline at 1296 × 972 fed YUY2 1280 × 720 into `/dev/video83`; a separate `v4l2src` consumer read it back and wrote PNG frames. Both producer and consumer completed cleanly. This establishes camera-to-V4L2-loopback readback under the temporary four-buffer setting.

The module was then restored to its original `max_buffers=2` configuration. The final check found `/dev/video83` present, no process holding it, and no camera producer running. The camera service remains failed/stopped and its timer remains disabled. No persistent host configuration was changed during these tests.

A follow-up attempt using the former 2560 × 1600 source mode negotiated caps but did not switch the loopback to capture capability within the bounded startup window, so no readback frame was obtained. That resolution remains unverified. The repository now defaults to the tested 1296 × 972 mode; this updated configuration has not yet been deployed to the host.

## Interpretation before persistent deployment (superseded below)

The target's front camera can now produce visible frames through libcamera's Software ISP, and GStreamer can deliver those frames through `/dev/video83` when the OV5693 tuning data is present and the loopback buffer limit is four. The remaining deployment gap is to make those two required settings part of the rollback-safe installer and then validate the installed service.

Do not repeat the earlier raw-buffer or single-frame `-5` experiments as if they were unresolved sensor failures. The evidence now points to a missing IPA tuning file for RGB conversion and a separate V4L2 loopback buffer limit. Keep support marked experimental: persistent deployment, deliberate moving-subject capture, an ordinary video application's access, improved color, and a later kernel-upgrade check remain outstanding.

## Plan before persistent deployment

1. Install the pinned CC0 OV5693 tuning file through the product installer and include it in rollback.
2. Set the loopback module's persistent `max_buffers=4` option in the existing product-specific modprobe configuration; retain `exclusive_caps=1`.
3. Preserve the tested 1296 × 972 source mode and correct the camera-name escaping in the service environment file.
4. Re-establish the elevated `surf7cam-test` tmux before host deployment. Test the deployed configuration and service with a separate V4L2 consumer; then test a deliberately moving subject and an ordinary video application.
5. Diagnose the green cast and clipped highlights before calling the camera supported.

Do not reboot for these checks. If a later step requires reboot, broadcast a global warning at least 2 minutes beforehand and wait the full 2 minutes.

## Post-deployment live test update — 5 October 2026

The rollback-safe deployment completed after the existing product installation was rolled back. It installed the pinned OV5693 tuning file and configured the V4L2 loopback for four buffers. The OV5693 tuning checksum was verified against the repository copy. DKMS installed the nine camera/loopback modules for the currently running Ubuntu kernel. A separate `dkms autoinstall` then built and installed them for another already-installed Ubuntu kernel with matching headers. No exact kernel versions are recorded here.

Only `v4l2loopback` was reloaded to apply its four-buffer setting; the IPU modules remained loaded. The camera service was started manually and stayed active. A separate `v4l2src` consumer read `/dev/video83` and saved five 1280 × 720 PNG frames. A three-second, 90-frame recording at 30 fps completed with EOS. Frames sampled near the beginning, middle, and end show the subject move across the scene. The camera is therefore delivering actual changing image frames through the deployed GStreamer/V4L2 path. The private images and recording remained in `/tmp` and were not committed or uploaded.

The latest preview was viewed in a very dark room lit only by a yellow LED, with the main room light off; the user said they could barely see the room themselves. Its darkness, noise, and tint are therefore a low-light test result, and image quality under normal lighting remains unassessed. Cheese was tested as the logged-in user with `/dev/video83` specified. Although its terminal logged “No device found” and GStreamer critical messages, the user saw a live preview and recognized their moving image; count this as a successful Cheese application test. A separate bounded `gst-device-monitor-1.0 Video/Source` probe listed no devices before timeout, while explicit `v4l2src device=/dev/video83` capture succeeds. Preserve the discrepancy between the visible app result and enumeration diagnostics for follow-up; the app test itself did work.

The delayed systemd timer is enabled, but no reboot or kernel upgrade test occurred. The service is running from the manual start. During the DKMS build, observed temperatures ranged from 46.4°C to 48.7°C, below the user's 95°C pause threshold. Reboot testing remains subject to a system-wide warning at least two minutes in advance and a full two-minute wait.

## Updated interpretation and next work

The image-flow problem has converged for direct capture: after rollback-safe installation, the camera now delivers visibly moving frames through libcamera, GStreamer, and `/dev/video83`. The unresolved items are Cheese/ordinary-application enumeration, color/noise quality, delayed startup after reboot, and persistence following a later Ubuntu kernel installation. The camera remains experimental until those integration and persistence checks pass.

Next, investigate the contradictory device-monitor logs only if they affect reliable startup, and continue with GStreamer image-quality work. Do not reboot unless explicitly authorized; before any approved reboot, broadcast to all logged-in users and wait at least two full minutes.
