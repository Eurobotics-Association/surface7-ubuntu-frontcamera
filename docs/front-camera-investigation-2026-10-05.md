# Surface Pro 7 front-camera investigation log — 5 October 2026

## Scope and safety

This investigation targets Microsoft Surface Pro 7 (not 7+) with Ubuntu 24.04 x86_64 and the latest installed Ubuntu HWE kernel. The selected camera path is GStreamer with libcamera's `libcamerasrc`; PipeWire camera integration is out of scope. Exact host-kernel inventory and private image files are intentionally omitted. Surface 5 files were not changed.

No reboot was performed during these tests. The one-time `iommu=pt` diagnostic setting is active only for the current boot; its persistent GRUB entry was restored earlier. The user's thermal rule is to continue through 95°C and pause heavy work for 3 minutes only above 95°C. These tests stayed well below that threshold.

## Browser and desktop application results — 5 October 2026

The user compared four applications against the installed feed. WebcamTests.com displayed live video in both Brave and Opera; the supplied Opera screenshot reports the device name `Surface Pro 7 Front Camera`, RGB, 1280 × 720, and 29 FPS. This confirms that the active GStreamer-to-V4L2 feed is usable from two Chromium-based browsers.

Firefox did not produce a usable preview. Its WebcamTests.com page showed a generic warning that the camera was in use or blocked, selected `videoinput#1`, and did not populate the camera information fields. This is a site-level message, not the exact Firefox WebRTC exception. The user also reports that Cheese currently finds no camera; that replaces the earlier one-time successful Cheese preview as the current result while preserving that earlier pass in the history. The test sequence does not establish whether the Brave or Opera stream had fully stopped before Firefox was tested, so exclusive-client contention still needs to be excluded.

Read-only checks found the Firefox Snap `camera` interface connected and `/dev/video83` tagged for Firefox access. Earlier checks also showed the service holding `/dev/video42` and producing into `/dev/video83`; the white LED is expected because the producer continuously opens the physical sensor, whether or not an application is consuming the virtual device. It is not evidence that Firefox successfully opened the camera. No Firefox preference, Snap connection, PipeWire service, camera service, module, or host setting was changed during this follow-up.

Mozilla Bugzilla [2007675](https://bugzilla.mozilla.org/show_bug.cgi?id=2007675) describes a similar Linux WebRTC report where Chromium finds a `v4l2loopback` device and Firefox does not; its reporter says the device appeared with `media.webrtc.camera.allow-pipewire` set to false. That issue was closed as a duplicate of [1946916](https://bugzilla.mozilla.org/show_bug.cgi?id=1946916), where a Mozilla engineer states Mozilla-distributed Firefox builds do not use PipeWire for cameras. The reports do not establish the cause on this Surface, and they should not be used to introduce the rejected PipeWire camera design.

The next low-risk diagnostic is sequential: stop the active camera stream in each other browser, then test Firefox alone on Mozilla's [WebRTC getUserMedia test page](https://mozilla.github.io/webrtc-landing/gum_test.html), recording the actual error and selected device. Leave the continuous bridge running; its LED will remain on during this check. If Firefox still fails, inspect its effective camera backend preference and WebRTC log before changing any browser or host setting. Separately, continue Cheese diagnosis through GStreamer device discovery and the observed `video_output` metadata mismatch. Do not reboot or reload camera modules for these application-level checks.

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

## Follow-up: continuous LED and Cheese enumeration — 5 October 2026

The existing `surf7cam-test` tmux pane was reused; no new tmux session was created. Read-only inspection showed `surface7-front-camera.service` active and running the product GStreamer command as PID 90319. That process continuously opens the physical libcamera sensor and writes to `/dev/video83`, even when no desktop application is consuming the loopback. This is why the white privacy LED remains on. It is expected from the current always-on bridge design, not evidence of a hidden Cheese connection. Stopping the service would release the sensor and turn the LED off, but would also stop populating the virtual camera. An on-demand producer design is a separate follow-up; do not stop the live service merely to clear the LED.

The current system service, DKMS module set, and `/dev/video83` were present on the running Ubuntu kernel. The producer owned the loopback node. The loopback has capture capability according to `v4l2-ctl`; the device also has the expected label, format, size, and user access. No reboot or module reload was performed.

GStreamer enumeration now explains part of the Cheese discrepancy: `gst-device-monitor-1.0 Video/Source` did not list the loopback node, but `gst-device-monitor-1.0 --include-hidden Video/Source` did. The hidden entry was `/dev/video83`, labeled `Surface Pro 7 Front Camera`, with YUY2 1280 × 720 at 30 fps. Its provider metadata described `device.capabilities=:video_output:` even though V4L2's active device caps report video capture. The local result establishes hidden/contradictory GStreamer metadata; it does not yet prove which provider implementation or metadata field causes Cheese to omit the camera. The GStreamer [device-provider API](https://gstreamer.freedesktop.org/documentation/gstreamer/gstdeviceprovider.html) is the discovery interface applications commonly use. The libcamera upstream discussion [patch 20002](https://patchwork.libcamera.org/patch/20002/) describes the libcamera provider hiding the V4L2 provider to avoid duplicate enumeration; this is a candidate explanation, not yet a confirmed local root cause.

Reader-mode checks separated buffer compatibility from image production. `v4l2-ctl` read five loopback frames successfully. A GStreamer `v4l2src` reader in its default MMAP mode failed with `Failed to allocate a buffer` / stream error `-5`. Setting `io-mode=rw` made the bounded GStreamer reader succeed. A one-frame 1280 × 720 JPEG was then captured through `v4l2src io-mode=rw`; it decoded and showed non-black scene pixels under the room's small light. The private image was inspected locally and was not committed. This confirms current still-frame delivery through the loopback read/write path, but it does not show that Cheese is using that mode or that Cheese can enumerate the hidden device.

Reproducible still-frame command used:

~~~sh
gst-launch-1.0 -e v4l2src device=/dev/video83 io-mode=rw num-buffers=1 \
  ! video/x-raw,format=YUY2,width=1280,height=720,framerate=30/1 \
  ! videoconvert ! jpegenc quality=90 \
  ! filesink location=/tmp/surface7-front-camera-still.jpg
~~~

The output image remained under `/tmp` on the host and was not uploaded. The frame was a low-light image-quality observation, not the moving-frame acceptance test.

The user reports that Cheese currently sees no camera. This supersedes the earlier single Cheese preview as the current acceptance state: the earlier preview proves that an app preview succeeded once, but Cheese discovery/capture is intermittent or state-dependent and is not considered resolved. Keep the distinct results separate: the producer is active, V4L2 readback works, GStreamer read/write capture works, default GStreamer device discovery does not expose the node, and current Cheese enumeration fails. Do not describe Cheese integration as consistently passing.

Next, investigate the provider-hide behavior and device-capability mismatch without changing PipeWire, reloading the IPU stack, or rebooting. Test candidate GStreamer/provider workarounds against device enumeration first, then run Cheese only when the user is available to observe the desktop. Preserve the active producer meanwhile. A future no-idle-LED design must start the producer only when a consumer needs the virtual camera and must keep first-frame latency acceptable; continuous service is the current tradeoff.

## Browser capture confirmation and next acceptance plan — 5 October 2026

The user tested `https://webcamtests.com/` and reported that it successfully opened `Surface Pro 7 Front Camera`. The complete result they provided is recorded below. These are website-reported values, not independently instrumented frame timing or image analysis. The result is strong evidence that a browser can discover and consume the current loopback stream. It does not prove Cheese works or that the bridge stops when unused.

| WebcamTests.com field | User-reported result |
| --- | --- |
| Webcam name | Surface Pro 7 Front Camera |
| Quality rating | 3792 |
| Built-in microphone / speaker | None / None |
| Frame rate | 29 FPS |
| Stream type / image mode | Video / RGB |
| Resolution / megapixels | 1280 × 720 / 0.92 MP |
| Video standard / aspect ratio | HD / 1.78 |
| PNG / JPEG file size | 1.69 MB / 1000.14 kB |
| Bitrate shown by site | 28.23 MB/s |
| Number of colors | 271107 |
| Average RGB color | Blank in the supplied result |
| Lightness / luminosity / brightness | 24.51% / 26.58% / 25.23% |
| Hue / saturation | 47° / 15.20% |

### Cheese acceptance

Do not treat the browser result as a Cheese test. Preserve three separate gates: default GStreamer device monitoring must expose the loopback as a capture source; a bounded `v4l2src` test using the mode Cheese selects must read frames; and Cheese itself must show live frames after selecting `Surface Pro 7 Front Camera`. Current evidence fails the first gate by default and fails the observed default-MMAP read, while explicit GStreamer read/write and the browser succeed. Investigate the local libcamera provider's V4L2-provider hiding and the `video_output` metadata discrepancy first. Any provider change must avoid making raw IPU subdevice nodes the default webcam. Then test Cheese in the user's desktop session; do not infer success from device enumeration alone.

### Idle LED acceptance

The LED cannot turn off while the current always-on `libcamerasrc` bridge is streaming from the sensor. A simple timer that stops the producer would likely make this `exclusive_caps=1` loopback advertise output-only and disappear from ordinary webcam discovery, so it could break Cheese and browser startup. The [upstream v4l2loopback documentation](https://github.com/v4l2loopback/v4l2loopback/blob/main/README.md#options) describes this output-only-before-producer / capture-only-after-producer behavior. The proposed reversible design is therefore conditional: first prove that `/dev/video83` can remain discoverable as a capture device with no sensor producer, possibly using its per-device format-retention controls; then add a small controller that starts the producer when a capture client begins streaming and stops it after a short idle grace period. Test first-client latency, reconnects, competing clients, suspend/resume, and rollback. Do not change `exclusive_caps`, unload/reload the module, or stop the current service until a reversible design and test window are ready.

No reboot is needed for either the successful browser test or the pending Cheese discovery work. A later reboot is a separate test of the already-enabled delayed boot timer, requiring the system-wide warning and full two-minute wait in `AGENTS.md`.

## Idle producer open-file check — 6 October 2026

A read-only check through the existing `surf7cam-test` tmux pane found `surface7-front-camera.service` active and the GStreamer producer holding `/dev/video42` and `/dev/video83`. `fuser -v` listed only that producer (PID 90319) on either device. Brave browser processes were present, but none held the physical or virtual camera node; no Firefox process was running at that observation. This confirms that the always-on producer, without an application reader, is sufficient to keep the physical sensor active and the white LED on. It does not establish the cause of Firefox's failed capture. No service, camera module, browser preference, or host setting was changed, and no reboot occurred.


The Firefox profile's read-only `permissions.sqlite` entry for `https://webcamtests.com` reports camera permission `1` (Allow). Its `prefs.js` and `user.js` contain no explicit `media.webrtc.camera.allow-pipewire` or `permissions.default.camera` overrides. The Firefox Snap [camera interface](https://snapcraft.io/docs/reference/interfaces/camera-interface/) was already connected and `/dev/video83` already carried the Firefox udev tag. This rules against an explicitly denied site permission or absent camera interface at the time of inspection, but it does not reveal Firefox's exact WebRTC exception or which device node its capture backend tried to open. No preference or permission was changed.
