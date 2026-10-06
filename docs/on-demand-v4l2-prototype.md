# On-demand V4L2 camera implementation

Updated: 6 October 2026

## Status

This branch implements an experimental on-demand camera path for the Surface
Pro 7 front RGB camera. It keeps the V4L2 node discoverable without running
the physical sensor pipeline continuously.

The idle relay and event controller are installed on Robert's Surface 7. The
old always-on service is stopped, its boot timer disabled, and the physical
GStreamer process stops at idle. Robert confirmed that the white front-camera
LED has gone out. The relay writes a single initialization frame and then
waits; it does not generate a repeating idle video stream.

PR #15 adds the Surface-built plugin path and a fresh runtime GStreamer
registry to the on-demand service. The merged GitHub installer has deployed
that fix. A bounded V4L2 client read 30 frames through `/dev/video83`; logs
show the front OV5693 sensor, its tuning file and live software-ISP frames.
A temporary captured frame was upright, with the ceiling at the top. After
the client closed, the controller stopped GStreamer and returned to idle.

The internal WebcamTests.com page listed the camera but went from “waiting for
permission” to “video track paused” without showing a preview or statistics.
Cheese started the camera pipeline through the isolated provider and returned
to idle after a 20-second test, but its preview could not be visually inspected
with the available UI controls. Firefox, Brave and Opera were not available
for live retesting from this session. Thus the underlying on-demand V4L2 frame
path is verified; browser and Cheese preview compatibility still need
application-level confirmation.

## Why on-demand

The old `surface7-front-camera.service` continuously ran
`libcamerasrc` into `/dev/video83`. That kept the front-camera LED lit even
when no application was capturing. Stopping this service extinguished the LED
without a reboot.

Applications discover a V4L2 node before capture starts, so the node must stay
present and advertise capture capability while the physical sensor is idle.
The design keeps a small relay attached to v4l2loopback and sends a single
initialization frame. The relay then waits on a named FIFO; it does not emit
repeating black frames. When an application starts V4L2 capture, the kernel
event watcher starts the existing GStreamer/libcamera pipeline. After the
capture-active state returns to idle for a short grace period, the controller
stops GStreamer, which releases the physical camera and should extinguish the
LED.

This uses no app-name detection, TCP webcam server, PipeWire camera source,
SPA plugin, or WirePlumber camera rule. The device remains
`/dev/video83`.

## V4L2 event semantics

The pinned v4l2loopback source is v0.15.4,
commit `0f9ee86760b7f2bea174b7e3e7a1d38845da0ab4`. Its
`client_usage_queue_event()` stores `!has_capture_token(stream_tokens)` in
the event payload. The value is a Boolean: `0` means no capture stream is
active; `1` means capture is active. It does not identify the application
and does not count clients. The event is queued on capture
`VIDIOC_STREAMON` and `VIDIOC_STREAMOFF`.

The observer subscribes with `V4L2_EVENT_SUB_FL_SEND_INITIAL`, polls the
event fd, and drains the nonblocking queue. Linux returns `ENOENT` when
`VIDIOC_DQEVENT` finds an empty queue, which is treated as normal. The
controller starts the GStreamer process on state `1` and stops it after
state `0` remains for the configured two-second grace period. Two-client
contention is a separate acceptance case; it is not inferred from this
Boolean event.

## Runtime flow

```text
Cheese / Firefox / Brave / Opera requests /dev/video83
                 |
                 v
v4l2loopback CLIENT_USAGE reports capture_active=1
                 |
                 v
controller starts libcamerasrc -> convert/scale -> FIFO
                 |
                 v
idle relay writes live YUYV frames to /dev/video83
                 |
                 v
capture_active=0 -> grace period -> stop GStreamer
```

The idle relay source is the pinned and unmodified
`upstream/surface-pro-7-camera/src/sp7-camera-relay.c`. It sets a 1280×720
YUYV output format, writes one black initialization frame, then polls the
named FIFO for complete live frames. A dummy FIFO writer prevents an idle EOF.
The single initialization frame is retained in v4l2loopback memory and is
not saved to disk. The relay process uses little idle CPU and memory; it does
not continuously generate frames. It owns the V4L2 producer side so
`exclusive_caps=1` continues to expose the node as a capture camera.

The controller starts GStreamer with the configured camera name, source mode,
and output size. It relies on libcamera's default exposure behavior and sends
YUYV to the FIFO,
and never writes captured images to persistent storage. The small two-second
grace period prevents rapid camera power cycling during app startup or brief
stream interruptions.

## Deployment and rollback

`scripts/deploy-services.sh` checks/install required Ubuntu packages,
confirms the running kernel matches the existing DKMS deployment marker,
builds the watcher and pinned relay in a temporary directory, and validates
the Python controller. Before replacing system files, it backs up the current
services, timer, binaries, configuration, and unit enablement states. The
pre-on-demand snapshot is stored once under
`/var/lib/surface7-ubuntu-frontcamera/backup/<kernel>/pre-on-demand`.

The deployment disables and removes the old always-on service and timer,
then enables the idle relay and on-demand controller. It does not alter or
reload kernel modules, reboot, or touch Surface 5 files. The GitHub installer
`--install` updates an already project-owned install without rebuilding
DKMS; a fresh install builds and registers DKMS, then deploys these services.

To restore the previous camera-service deployment while keeping DKMS,
firmware, and packages installed:

```sh
/usr/local/lib/surface7-ubuntu-frontcamera/scripts/rollback.sh --previous-deployment
```

To remove the project deployment and restore all backed-up system files:

```sh
/usr/local/lib/surface7-ubuntu-frontcamera/scripts/rollback.sh
```

The full rollback can restore previous kernel module files; reboot remains a
manual, separately authorized action.

## Test record

- **Static observer build:** `cc -O2 -Wall -Wextra -Werror` passed. The
  controller passed Python syntax compilation.
- **Event observer on the installed always-on node:** WebcamTests.com caused
  `capture_active: 0 → 1 → 0`; Cheese briefly toggled during startup, then
  stayed at `1` until its preview closed, returning to `0`. The camera
  service was left unchanged during those observer checks.
- **Cheese on the old path:** the isolated temporary GStreamer provider
  displayed the front camera; Robert confirmed the image was upright. The
  process logged two non-fatal GStreamer `GST_IS_ELEMENT` critical warnings
  and libcamera reported that no IPA was found.
- **Browser site on the old path:** the Codex in-app browser captured
  1280×720 RGB at 29 FPS, but that preview appeared upside down in that
  observation. Robert separately reported successful Brave and Opera tests;
  orientation differed between applications in earlier tests.
- **Firefox:** no successful Firefox camera preview has been verified by the
  agent. It previously showed a generic camera-in-use/blocked message.
- **Always-on stop:** after stopping `surface7-front-camera.service` and
  disabling its timer, no `gst-launch-1.0` process remained. Robert
  confirmed the white LED went out. No reboot or module reload was performed.
- **First on-demand request:** the internal browser request reached the
  watcher/controller. GStreamer exited because the installed source does not
  support `ae-enable`; the merged source removed that property.
- **Second on-demand request:** after that correction, the unit loaded Ubuntu's
  stock `libcamerasrc` 0.2.0 and reported that it could not find the configured
  camera. The enabled OV5693 media-graph link was present. The old always-on
  unit selected the product-built plugin at
  `/usr/local/lib/surface7-ubuntu-frontcamera/gstreamer-1.0`; the new unit had
  omitted that environment. This branch adds the product `GST_PLUGIN_PATH`,
  a runtime-scoped `GST_REGISTRY`, and a preflight load check.
- **PR #15 and redeployment:** GitHub Actions static validation passed. The
  merged GitHub installer updated the existing deployment without rebuilding
  kernel modules; the active unit reports the product
  `GST_PLUGIN_PATH` and runtime registry.
- **On-demand V4L2 frame capture:** `v4l2-ctl` read 30 frames from
  `/dev/video83`, triggering the controller. Libcamera selected
  `_SB_.PCI0.I2C2.CAMF`, loaded the OV5693 tuning file, and the software ISP
  processed live frames. One temporary frame was converted to PNG and visually
  checked: orientation is upright (ceiling at the top). Temporary raw and PNG
  files were deleted after inspection. This verifies actual frames, rather
  than enumeration alone.
- **WebcamTests.com after redeploy:** the device appeared in the in-app browser.
  After launch, the page waited for permission, then reported that its video
  track was paused; no live preview or frame statistics appeared. The event
  did start the physical pipeline, which stopped when the browser capture went
  inactive. The site-level preview remains unverified.
- **Cheese after redeploy:** the repository's isolated provider built and
  Cheese ran under a 20-second timeout. Its request started the on-demand
  source and the controller returned to idle at test end. The process logged
  two non-fatal `GST_IS_ELEMENT` critical warnings and Cheese's stock
  libcamera reported no IPA. This session could not inspect the Cheese window,
  so a visible Cheese preview is not claimed.
- **Brave, Firefox and Opera after redeploy:** not retested because those
  desktop windows were not exposed to the available UI-control session. Prior
  user-reported results apply to the earlier always-on service only.
- **Idle stop:** after both the V4L2 read and Cheese test, the controller logs
  show GStreamer stopped and capture idle. No `gst-launch-1.0` or Cheese
  process remained. The LED itself cannot be read by software; Robert had
  confirmed it went out after stopping the previous continuous service.
  No reboot or module reload was performed.
- **Migration helper issue:** the first install could not copy the persistent
  rollback helper because `$SURFACE7_LIBDIR/scripts` did not exist. The
  deployment continued, while the one-time previous-deployment snapshot was
  present. Follow-up changes create the directory, propagate failures into
  rollback, and restart the controller after code updates.
- **Cheese, Firefox, Brave, Opera and WebcamTests.com on the corrected
  on-demand controller:** pending successful recapture and idle-stop testing.

## Sources

- [Pinned v4l2loopback source base](source-bases.md)
- [Linux V4L2 STREAMON/STREAMOFF documentation](https://docs.kernel.org/userspace-api/media/v4l/vidioc-streamon.html)
- [v4l2loopback v0.15.4 event implementation](https://github.com/v4l2loopback/v4l2loopback/blob/v0.15.4/v4l2loopback.c)
- [Linux V4L2 event queue](https://github.com/torvalds/linux/blob/master/drivers/media/v4l2-core/v4l2-event.c#L976-L1058)
