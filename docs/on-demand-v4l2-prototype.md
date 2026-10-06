# On-demand V4L2 camera prototype

Updated: 6 October 2026

## Scope and status

This is a separate, experimental branch: `codex/on-demand-v4l2-prototype-20261006`.
It starts a GStreamer-based prototype for powering the Surface Pro 7 front
camera only while a V4L2 client is capturing. It does not change the main
branch, deploy files to the host, install packages, reload modules, or reboot.

The first prototype component, `prototypes/v4l2loopback-client-watch.c`, is
only an event observer. It subscribes to the v4l2loopback `CLIENT_USAGE`
event and prints the capture-active state. It does not start or stop GStreamer
and does not call `VIDIOC_STREAMON`. It compiles locally with the Ubuntu C
compiler and strict warnings enabled. It has not yet been run against a V4L2
node or the Surface camera. Live testing needs Robert present with the
elevated `surf7cam-test` tmux session available.

## Why this design

The currently deployed `surface7-front-camera.service` continuously owns the
physical camera and sends frames to `/dev/video83`. This explains why the
front-camera LED remains lit when no application is viewing the feed.

The V4L2 device node and the physical sensor have separate lifecycles. Keep a
stable virtual camera node for applications to discover, then start the real
GStreamer/libcamera pipeline when a client actually requests capture. Stop the
pipeline after the last capture request has ended and a short grace period has
passed. An idle event listener can wait for transitions without generating
frames or recording image data. No app-name detection or TCP webcam server is
needed; the operating-system camera interface remains `/dev/videoN`.

The Surface Pro 7 source bundle already vendors unmodified v4l2loopback
v0.15.4. Its `CLIENT_USAGE` private event is emitted on capture
`VIDIOC_STREAMON` and `VIDIOC_STREAMOFF`; the payload represents inactive or
active capture state, not the requesting application's identity. The bundle
also contains an observer at
`upstream/surface-pro-7-camera/src/sp7-camera-client-usage.c`. Its full
camera backend starts PipeWire streams. This prototype borrows only the
v4l2loopback event interface and will start the existing GStreamer/libcamera
front-camera path. It will not add a PipeWire camera source, SPA plugin, or
WirePlumber rule.

References:

- [Pinned v4l2loopback source base](source-bases.md): v0.15.4,
  commit `0f9ee86760b7f2bea174b7e3e7a1d38845da0ab4`.
- [Upstream v4l2loopback event implementation](https://github.com/v4l2loopback/v4l2loopback/blob/main/v4l2loopback.c)
  queues the private usage event at capture stream start/stop.
- [Linux V4L2 STREAMON/STREAMOFF documentation](https://docs.kernel.org/userspace-api/media/v4l/vidioc-streamon.html)
  defines those operations as starting/stopping capture or output streaming.
- [Upstream loopback capability notes](https://github.com/v4l2loopback/v4l2loopback/blob/main/README.md#options)
  explain why `exclusive_caps=1` devices can be invisible as cameras before a
  producer is attached. The `keep_format` control and producer attachment
  interaction must be tested before selecting idle-device settings.

## Proposed flow

~~~text
Cheese / Firefox / Brave / Opera requests V4L2 capture
        |
        v
v4l2loopback CLIENT_USAGE event: capture active
        |
        v
small controller starts the existing GStreamer/libcamera service
        |
        v
Surface front sensor -> IPU4P -> libcamerasrc -> v4l2sink -> /dev/video83
        |
        v
client stops capture -> event reports inactive -> grace timer -> stop service
~~~

The virtual node must stay discoverable with no producer, and the producer
must still be able to attach after a client requests capture. That interaction
is the first design question to resolve. Upstream `exclusive_caps=1` behavior
changes the advertised V4L2 capability when a producer appears. `keep_format`
may help preserve the capture format, but it can also affect producer
attachment. No persistent module or camera configuration is changed until
this is demonstrated on a disposable test node.

## Idle-node discovery without a continuous black video stream

The current configuration uses `exclusive_caps=1`. With no producer attached,
v4l2loopback advertises an OUTPUT-only device, which ordinary webcam apps may
not list. Two idle-device approaches need a controlled comparison:

1. **Retain a negotiated capture format.** Try `keep_format` on a temporary
   loopback node. Confirm that applications see a CAPTURE device with no
   producer, then confirm a GStreamer producer can still attach after a real
   capture request. Upstream documentation and code describe related format
   behavior, but do not establish that this sequence works for this camera and
   these clients.
2. **Keep a tiny idle relay attached.** The vendored upstream bundle has a
   relay design for this exact exclusive-caps discovery problem. It writes one
   black YUYV initialization frame so the node is advertised as CAPTURE, then
   waits for real frames on a named FIFO. It does not generate black frames on
   a timer. The physical camera can remain off while the relay holds the
   virtual producer side open. On `CLIENT_USAGE` active, an on-demand GStreamer
   pipeline would write live `libcamerasrc` frames to the FIFO; after the last
   inactive event and grace period, that pipeline would stop. The one
   initialization frame is held in the loopback's memory until live video
   arrives; it is not written to disk. Applications may briefly see a black
   initial frame or time out while the sensor starts, so this needs the full
   desktop/browser test matrix.

The relay approach costs one small idle process, an open loopback device, and
memory for the retained frame. It avoids a continuously running capture
pipeline and repeated frame generation. The FIFO should live under a runtime
directory such as `/run`, not on persistent storage. The unmodified vendor
relay source is a reference only; this project will keep the vendor snapshot
unchanged and implement any GStreamer adaptation in a separate prototype.

## Prototype phases

1. **Event observer:** compile the small watcher without sudo, then run it on
   the selected loopback node while applications start and stop capture. Confirm
   that enumeration alone leaves the state idle and active capture produces
   transitions. The watcher opens the loopback node only to subscribe to its
   event; it does not stream video.
2. **Idle-node compatibility:** on a separate temporary V4L2 loopback node,
   compare `keep_format` with the one-frame idle relay. Determine whether
   Cheese and browsers discover the camera before live frames exist, and
   whether GStreamer can attach after `STREAMON`. Keep `/dev/video83` and its
   current producer untouched during this phase.
3. **On-demand controller:** only after the event and node behavior are
   confirmed, add a controller that starts the existing GStreamer service on
   active capture and stops it after a grace period. Keep system changes behind
   the existing backup and rollback protections.
4. **User-visible acceptance:** with Robert present, test Cheese, Firefox,
   Brave, Opera, and WebcamTests.com. For each, record camera discovery,
   actual non-black frames, orientation, LED-on while capturing, and LED-off
   after the last client stops. Also test two clients, permission denial,
   abrupt client exit, and application startup latency.

No camera test has been performed for this prototype yet. Do not report the
event observer as an on-demand camera implementation or as proof that the LED
turns off. If the `CLIENT_USAGE` event is absent or unsuitable in the installed
module, evaluate a minimal DKMS event patch before considering a new V4L2
driver.

## Build and later live observation

Build, without installing anything:

~~~sh
cc -O2 -Wall -Wextra -Werror \
  -o /tmp/surface7-v4l2-client-watch \
  prototypes/v4l2loopback-client-watch.c
~~~

When Robert is present and the selected device is confirmed to be the
v4l2loopback camera node:

~~~sh
/tmp/surface7-v4l2-client-watch /dev/video83
~~~

Stop with Ctrl-C. This observer is intended to run as the desktop user with
ordinary access to the video device; do not run Cheese or a browser through
`sudo`. The active always-on producer remains untouched during the first event
check. Switching to an idle sensor or testing module settings requires an
explicit rollback plan and the user's elevated tmux session.

## Rollback boundary

The files on this branch are not deployed. Removing the observer binary and
ending the process restores its entire local effect. The running camera
service, module configuration, loaded kernel modules, packages, and system
files remain unchanged. Any later controller or device-configuration change
must first be covered by `scripts/rollback.sh`, and this branch must remain
experimental until all four applications and the LED behavior pass live tests.
