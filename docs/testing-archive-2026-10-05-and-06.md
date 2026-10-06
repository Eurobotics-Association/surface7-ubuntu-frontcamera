# Archived camera test notes (5–6 October 2026)

This document preserves the original exploratory test log for traceability.
Its status and app conclusions were superseded by the current concise summary in
[testing.md](testing.md) and the on-demand investigation in
[on-demand-v4l2-prototype.md](on-demand-v4l2-prototype.md). Historical host
states and early failure reports below should not be treated as the current
deployment.

---

# Testing and acceptance

## Current state

The deployed product libcamera/GStreamer stack on the Surface Pro 7 running Ubuntu 24.04 x86_64 produces viewable front-camera frames and V4L2 loopback readback. The rollback-safe installer placed the pinned OV5693 simple-IPA tuning file and persistent `max_buffers=4` setting. The tuning file's SHA-256 was verified as `73845d5ebaedc948ec0cca7b3d2f07ac8081c2f5c3e16c63905ce04532ba21ac`. The service is active after a manual start. A separate GStreamer `v4l2src` consumer read five PNG frames from `/dev/video83` at 1280 × 720, and a 90-frame, 30 fps recording visibly showed the subject move between sampled frames. The producer used the tested 1296 × 972 sensor mode.

An earlier Cheese launch showed the user a live camera preview, but the latest user report is that Cheese sees no camera; do not count Cheese integration as consistently passing. Follow-up checks found that the default GStreamer device monitor does not list `/dev/video83`, while `gst-device-monitor-1.0 --include-hidden Video/Source` does. The hidden entry is labeled `Surface Pro 7 Front Camera`, advertises YUY2 1280 × 720 at 30 fps, and has provider metadata `device.capabilities=:video_output:` despite V4L2 reporting active capture capability. A GStreamer `v4l2src` consumer using default MMAP failed with `Failed to allocate a buffer` / stream error `-5`; the same reader in `io-mode=rw` succeeded. A one-frame JPEG capture through the read/write mode decoded and contained visible scene pixels under the room's small light. The still image stayed private and was not committed. This verifies frame readback through the read/write path, not Cheese enumeration or its default MMAP compatibility. The stale device.capabilities=:video_output: property remains a metadata mismatch, but a process-local no-op interposition probe confirmed that provider hiding is why the default GStreamer monitor omits /dev/video83; a scoped provider test is recorded below. Support remains experimental. Exact host-kernel inventory is kept out of this public repository.

The DKMS modules are installed for the running Ubuntu kernel and were then built/installed successfully for another already-installed kernel with matching headers. Old kernel directories without matching headers were not built. The service timer is enabled but has not been tested across a reboot. No reboot was performed. The installed service is currently active, and the loopback module is loaded with `max_buffers=4`.

The user subsequently tested the virtual camera at WebcamTests.com. Their page reported `Surface Pro 7 Front Camera`, RGB, 1280 × 720 (0.92 MP), and 29 FPS, with no built-in microphone or speaker. This is user-reported browser validation of the active stream; it does not prove Cheese discovery or idle power behavior. The listed 24.51% lightness, 26.58% luminosity, and 25.23% brightness are consistent with the low-light room described above. The site's quality score and file/bitrate estimates are retained as its reported output, not as independent measurements.


The user has since compared applications on WebcamTests.com. Brave and Opera both displayed live front-camera video; the supplied Opera screenshot reports `Surface Pro 7 Front Camera`, RGB, 1280 × 720, and 29 FPS. Firefox did not start the camera and displayed the site's generic message that the webcam was in use or blocked; its selector showed `videoinput#1`, and no camera information or usable preview was produced. The page did not expose the underlying WebRTC error, so “busy” is the site's wording rather than a confirmed `NotReadableError`. The user reports that Cheese does not find a camera, superseding the earlier single successful preview as current status. The user did not report whether every other browser camera stream was stopped before the Firefox attempt; a single-client test remains necessary to rule out contention.

| Application | Result reported by user | What the evidence establishes |
| --- | --- | --- |
| Brave | Pass; live image and browser test stats were reported earlier | The loopback feed can work through a Chromium-based browser. |
| Opera | Pass; screenshot shows live image, 29 FPS, 1280 × 720 RGB | The feed also works through a second Chromium-based browser. |
| Firefox | Fail; generic in-use/blocked page message, no successful frame | Firefox compatibility or client contention remains unresolved; exact WebRTC error is unknown. |
| Cheese | Fail currently; user reports no camera | Cheese discovery/opening is unresolved despite one earlier preview. |

Read-only checks found Firefox's Snap `camera` interface connected and `/dev/video83` tagged for Firefox access. These make a missing basic Snap camera grant less likely, but do not rule out Firefox's own site permission, device selection, or WebRTC backend behavior. The continuous GStreamer service keeps the physical sensor open and feeds `/dev/video83`; its white privacy LED therefore remains on even when Firefox and Cheese fail. LED state does not identify which applications are reading the loopback.

Mozilla Bugzilla [2007675](https://bugzilla.mozilla.org/show_bug.cgi?id=2007675) documents a similar report: Chromium found a `v4l2loopback` camera while Firefox WebRTC did not. The reporter observed that disabling Firefox's `media.webrtc.camera.allow-pipewire` preference made the device appear, but the issue was closed as a duplicate of [1946916](https://bugzilla.mozilla.org/show_bug.cgi?id=1946916), whose discussion says Mozilla-distributed Firefox builds do not use PipeWire for camera capture. Treat this as an upstream lead, not a diagnosis or a reason to add a PipeWire camera path. No Firefox preferences, PipeWire services, or host settings were changed for this investigation.

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
- The last check before persistent deployment found the loopback node present, no camera process holding it, service failed/stopped, timer disabled, and `max_buffers=2`. This was superseded by the rollback-safe deployment below.
- Earlier temporary checks observed up to 57°C. During the later DKMS build, observed readings ranged from 46.4°C to 48.7°C. Continue through 95°C; above 95°C pause heavy work for 3 minutes and then resume while monitoring.
- After the deployment, rollback completed successfully before reinstall. The installer deployed the service, tuning data, module setting, and DKMS source for the running kernel. The V4L2 loopback module alone was reloaded to apply four buffers; the IPU stack was not reloaded and the machine was not rebooted.
- An independent GStreamer readback from `/dev/video83` produced five 1280 × 720 PNGs and reached EOS cleanly. A 3.1-second AVI containing 90 frames at 30 fps also reached EOS. Correctly extracted samples at approximately 0.3, 1.5, and 2.7 seconds show clear changes in subject position. These private images/video remain in `/tmp` and were not added to the repository.
- An earlier Cheese preview visibly showed the front camera, but the current user report says Cheese sees no camera. A normal GStreamer device-monitor probe omits `/dev/video83`; `--include-hidden` reveals it with output-class provider metadata even while V4L2 reports capture capability. Default-MMAP `v4l2src` failed buffer allocation; `io-mode=rw` succeeded and captured a private, non-black still JPEG. The discrepancy is now a concrete discovery/capture compatibility issue, not grounds to claim Cheese always passes or that image flow fails.
- The user tested WebcamTests.com and reported an RGB 1280 × 720 stream at 29 FPS (0.92 MP) from `Surface Pro 7 Front Camera`. This confirms a browser can consume the active virtual-camera feed. It does not clear the Cheese issue, test the camera after the producer stops, or verify automatic boot startup.
- The always-running `surface7-front-camera.service` owns the physical camera and keeps streaming into `/dev/video83` when no desktop app is open; this accounts for the white front-camera LED. The live producer and LED were left alone during these checks. Maximum observed CPU temperature in the pane was 64°C, below the user's 95°C pause threshold.
- On 6 October 2026, a read-only check in the existing `surf7cam-test` tmux pane found the camera service active. `fuser -v /dev/video42 /dev/video83` listed only the GStreamer producer (PID 90319) as holding either node. Brave processes were running, but none held those camera nodes; no Firefox process was running. This confirms the producer alone can keep the LED on when no browser is consuming `/dev/video83`. No service, module, device, or browser setting was changed.
- A read-only Firefox profile check on 6 October found `https://webcamtests.com` has a saved camera permission of Allow (`permission=1`). The profile's `prefs.js` and `user.js` contain no explicit `media.webrtc.camera.allow-pipewire` or `permissions.default.camera` override. Together with the connected Firefox Snap camera interface, which [grants webcam access when connected](https://snapcraft.io/docs/reference/interfaces/camera-interface/), and its udev device tag, this makes a saved site denial or missing basic Snap grant unlikely; Firefox's exact WebRTC failure is still unknown.
- DKMS autoinstall succeeded for a second installed Ubuntu kernel with matching headers. No reboot or kernel update was performed; persistence across either remains unverified.

## Remaining validation

The repository installer now deploys the pinned OV5693 tuning file, sets `max_buffers=4`, preserves the tested 1296 × 972 source mode, and corrects camera-name escaping. The host deployment completed after a successful rollback. The manually started service now delivers moving frames through `/dev/video83`.

Still needed: first retest Firefox with every other browser camera stream stopped, then use Mozilla's WebRTC test page to capture the exact Firefox error and selected camera; resolve GStreamer device-provider hiding/capability metadata and default-MMAP buffer allocation so Cheese can reliably enumerate and open the camera; assess image quality under normal room lighting; design an on-demand producer if the user wants the LED off while idle; verify the delayed service after an approved reboot; and test a later Ubuntu kernel installation. No reboot has been performed in this test sequence. Do not retry the earlier raw-buffer path as the next diagnostic; moving pixels and V4L2 read/write loopback readback are proven with the installed settings.

Moving non-black frames from `/dev/video83` are verified. Ordinary application access succeeded once in Cheese but currently fails to enumerate reliably, so it remains open acceptance work. Acceptance also requires persistence after reboot/kernel update and acceptable image quality. Build success, camera enumeration, an LED, or negotiated caps alone are not acceptance.


## Controlled Firefox and Cheese probes — 6 October 2026

The user's application matrix remains: Brave and Opera show live video; Firefox and Cheese do not. The following headless and temporary-node tests are separate from that user-visible result.

### Firefox

The installed browser node is /dev/video83; Mozilla's Linux V4L2 backend scans numbered nodes only through /dev/video63 ([Firefox source](https://searchfox.org/firefox-main/source/third_party/libwebrtc/modules/video_capture/linux/video_capture_v4l2.cc)). This explains why the current node is absent from Firefox's scanner, but moving the loopback into range has not produced a repeatable fix.

A temporary native loopback node /dev/video62 passed a five-frame V4L2 read. One Firefox WebRTC log then counted 12 capture devices: 11 raw ipu4p entries followed by Surface Pro 7 Front Camera. Its default getUserMedia({video:true}) still selected a raw endpoint and failed with NotReadableError. A later repeat using a fresh temporary Firefox profile with a local camera permission counted only the 11 raw entries; page JavaScript saw one unlabeled input and got NotFoundError. No real Firefox profile or preference was changed. The native camera's appearance at node 62 is therefore inconsistent, and no targeted successful Firefox capture is verified.

### Cheese and GStreamer discovery

With the deployed exclusive_caps=1 setting, the ordinary gst-device-monitor-1.0 Video/Source listing omits /dev/video83. The --include-hidden report shows the card label and YUYV 1280 × 720 caps, but advertises device.capabilities=:video_output: while V4L2's device_caps includes Video Capture. This remains the concrete discovery mismatch to investigate.

A temporary exclusive_caps=0 reload made the ordinary GStreamer monitor list the camera as a Video/Source. It did not prove usable frames: a bounded v4l2src io-mode=rw read timed out with “Signal lost / No input source was detected,” and a V4L2 MMAP probe printed VIDIOC_STREAMON I/O error even though v4l2-ctl returned exit code 0. Do not count that command's exit code as a frame-read pass. The setting was rejected and is not deployed.

GNOME documents that Cheese's --device argument expects the camera's display name, not a /dev/videoX path ([GNOME Bug 777047](https://bugzilla.gnome.org/show_bug.cgi?id=777047#c1)). My first direct Cheese invocation passed /dev/video83, so it did not select the loopback. Later isolated attempts using the reported display names still showed the Cheese process holding raw /dev/video42, not /dev/video83; they do not establish a Cheese capture pass. The ordinary GStreamer visibility change under exclusive_caps=0 also did not establish that Cheese read frames.

### Rollback and current host state

One temporary test runner failed inside its cleanup after Cheese did not exit on the first signal. I stopped the bridge, removed the temporary loopback module, reloaded it from the unchanged product configuration, restarted the bridge, and verified recovery. Subsequent node-62 probes used the existing rollback harness and restored node 83.

The final bounded read from /dev/video83 received five frames. The loaded settings are again node 83, four buffers, and exclusive_caps=1; the camera service is active. The test sequence installed no packages and performed no reboot. The highest observed temperature was 72°C, below the user's 95°C pause threshold.

No Cheese or Firefox fix is accepted yet. Keep the product experimental. Next, resolve the V4L2/GStreamer capture-class mismatch without changing the rejected PipeWire path; then verify that Cheese opens /dev/video83 and returns frames. For Firefox, repeat selection only when its actual device list exposes the Surface camera; a scanner log entry or a node in range is not a capture pass.


## Scoped GStreamer provider prototype — 6 October 2026

The earlier provider-hide explanation is now confirmed for ordinary GStreamer enumeration. A temporary, process-local no-op interposition for gst_device_provider_hide_provider made a normal gst-device-monitor-1.0 Video/Source listing reveal /dev/video83; it also revealed raw IPU V4L2 endpoints. This proves why blanket un-hiding is too broad. Do not install the shim or globally unhide the V4L2 provider. The installed libcamera provider's default hiding behavior and the upstream [libcamera discussion](https://patchwork.libcamera.org/patch/20002/) are consistent with this result.

A second prototype in /tmp registered a distinct GStreamer provider. It queried the configured loopback node through V4L2 and exposed it only when the driver was v4l2 loopback, the ioctl reported V4L2_CAP_VIDEO_CAPTURE, and the card label matched Surface Pro 7 Front Camera. Under a fresh GStreamer registry and explicit temporary GST_PLUGIN_PATH=/tmp, ordinary gst-device-monitor-1.0 Video/Source listed the Surface camera with YUY2 1280 × 720 at 30 fps and showed an element recipe using v4l2src device=/dev/video83 io-mode=rw. The provider did not expose the raw IPU nodes in that listing.

A temporary C harness obtained that GstDevice, called gst_device_create_element(), and its v4l2src pipeline delivered five buffers and reached EOS. However, it emitted two GStreamer-CRITICAL messages (gst_element_message_full_with_details: assertion GST_IS_ELEMENT failed), with the stack in Ubuntu's libgstvideo4linux2.so. A direct bounded gst-launch-1.0 -e v4l2src device=/dev/video83 io-mode=rw num-buffers=5 ! fakesink sync=false completed with EOS and did not emit those messages. The warning difference remains unexplained; the provider prototype is not ready for deployment.

All prototype source, binaries, registries, and logs remained in /tmp and were loaded only by those test processes. No package, system plugin, service, camera module, browser setting, or PipeWire configuration was installed or changed. The bridge stayed active; no reboot or module reload occurred. This was GStreamer enumeration and a provider-created frame-flow test, not a Cheese UI test. Cheese was not launched because the user was unavailable to observe the desktop. Brave and Opera remain user-reported passes; Firefox and Cheese remain unresolved.

Next: explain and remove the V4L2-plugin criticals, then test Cheese in the user's desktop session with the scoped provider. Only after that should the provider be added to the installer and scripts/rollback.sh. Firefox remains a separate WebRTC issue: the temporary node-62 tests did not produce a targeted capture and must not be described as a fix.
