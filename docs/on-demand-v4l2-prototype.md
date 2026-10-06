# On-demand V4L2 camera implementation

Updated: 6 October 2026

## Status

This branch implements an experimental on-demand camera path for the Surface
Pro 7 front RGB camera. It keeps the V4L2 camera node discoverable without
running the physical sensor pipeline continuously.

The observer was tested against the installed `/dev/video83`: the in-app
WebcamTests page and Cheese caused `CLIENT_USAGE` transitions, and both
returned to idle after capture ended. Cheese and browser image capture worked
on the existing always-on producer. Robert confirmed that the Cheese preview
was upright. The currently installed always-on systemd service has since been
stopped, its boot timer disabled, and Robert confirmed the white camera LED
went out; no reboot or module reload was needed.

The relay/controller deployment and full desktop/browser acceptance tests are
still pending. Do not describe the on-demand implementation as validated until
the new services produce moving frames and stop the physical GStreamer
pipeline after capture in the user-facing tests.

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

The controller starts GStreamer with the already documented camera name,
source mode, automatic exposure, and output size. It sends YUYV to the FIFO,
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
- **On-demand relay/controller live test and the Cheese/Firefox/Brave/Opera
  acceptance matrix:** pending deployment and validation.

## Sources

- [Pinned v4l2loopback source base](source-bases.md)
- [Linux V4L2 STREAMON/STREAMOFF documentation](https://docs.kernel.org/userspace-api/media/v4l/vidioc-streamon.html)
- [v4l2loopback v0.15.4 event implementation](https://github.com/v4l2loopback/v4l2loopback/blob/v0.15.4/v4l2loopback.c)
- [Linux V4L2 event queue](https://github.com/torvalds/linux/blob/master/drivers/media/v4l2-core/v4l2-event.c#L976-L1058)
