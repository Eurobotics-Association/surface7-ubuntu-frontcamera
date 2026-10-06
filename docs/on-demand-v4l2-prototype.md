# On-demand V4L2 camera implementation

Updated: 6 October 2026, 23:40 CEST

## Status

This experimental implementation keeps the Surface Pro 7 front RGB camera discoverable as /dev/video83 without continuously running the physical sensor pipeline.

The installed design uses an idle relay plus a capture-event controller. While idle, the relay holds one initialization frame in v4l2loopback and waits on a FIFO. It does not generate repeating black frames. When a client starts capture, v4l2loopback CLIENT_USAGE changes to active and the controller starts the GStreamer/libcamera pipeline. After the capture state remains idle for the two-second grace period, the controller stops GStreamer and releases the physical camera.

Robert's latest WebcamTests.com run eventually showed live 1280×720 RGB video at 29 FPS, labeled “Surface Pro 7 Front Camera.” The user reports three attempts and repeated source start/stop cycles before a sustained result. Closing the successful tab stopped the source and the white LED went out. This is a successful browser capture and idle-release observation, with startup reliability still open.

The latest Cheese attempt did not discover the synthetic camera. Earlier Cheese tests with an isolated provider showed a preview, but this has not been reliable in the current deployment. Firefox has not been retested on the current on-demand services; earlier tests failed. Brave and Opera previously worked in user tests on an earlier service version and still need current-version retesting. Some sessions showed an inverted image while Brave/Opera earlier looked upright. Do not add a global rotation; verify orientation separately for each application.

The implementation remains experimental. The exact current state and next tests are in [the handoff note](handoff-current.md) and [the test matrix](testing.md).

## Why on-demand

The old surface7-front-camera.service continuously ran libcamerasrc into /dev/video83. That kept the physical front-camera LED lit even when no application was capturing. Stopping this service extinguished the LED without a reboot.

Applications need a V4L2 node to discover before capture starts, so the virtual node stays present while the sensor is idle. The relay owns the v4l2loopback producer side and writes a single initialization frame; the sensor pipeline is started only after a capture request. This keeps device discovery separate from sensor power and avoids an always-on video stream.

This uses no application-name detection, TCP camera server, PipeWire camera source, SPA plugin, or WirePlumber camera rule. The virtual device remains /dev/video83.

## V4L2 event semantics

The pinned v4l2loopback source is v0.15.4, commit 0f9ee86760b7f2bea174b7e3e7a1d38845da0ab4. Its client_usage_queue_event() stores !has_capture_token(stream_tokens) in the event payload. The value is Boolean: 0 means no capture stream is active; 1 means capture is active. It does not identify an application and does not count clients. Events are queued on capture VIDIOC_STREAMON and VIDIOC_STREAMOFF.

The observer subscribes with V4L2_EVENT_SUB_FL_SEND_INITIAL, polls the event fd, and drains the nonblocking queue. Linux returns ENOENT when VIDIOC_DQEVENT finds an empty queue; that is treated as normal. The controller starts GStreamer on state 1 and stops after state 0 remains for the configured two-second grace period. Concurrent-client behavior is a separate acceptance case; it is not inferred from the Boolean event.

## Runtime flow

~~~text
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
~~~

The idle relay source is the pinned and unmodified upstream/surface-pro-7-camera/src/sp7-camera-relay.c. It sets a 1280×720 YUYV output format, writes one initialization frame, then polls the named FIFO for complete live frames. A dummy FIFO writer prevents an idle EOF. The one frame is retained in v4l2loopback memory and is not saved to disk. The relay does not continuously generate frames.

The controller uses the configured camera name, sensor mode, output size, and frame rate. It sends YUYV to the FIFO and does not persist camera frames. The short grace period prevents unnecessary power cycling during brief client interruptions.

## Public deployment and rollback

The supported one-line installer is:

~~~sh
curl -fsSL https://raw.githubusercontent.com/Eurobotics-Association/surface7-ubuntu-frontcamera/main/scripts/install-from-github.sh | bash -s -- --install
~~~

The bootstrap fetches this GitHub repository and runs scripts/install.sh. The installer checks Surface model, Ubuntu version/architecture, the running kernel, matching headers, and packages. Missing build/GStreamer packages are installed from Ubuntu APT with sudo. A fresh install builds/registers the kernel modules with DKMS before deploying services. An existing project-owned install is updated without rebuilding DKMS. DKMS AUTOINSTALL handles later kernel installation when matching headers are available. No install path reboots automatically.

scripts/deploy-services.sh verifies the project ownership marker and recorded running kernel, checks that the Surface-built libcamerasrc plugin loads, compiles the watcher and relay in a temporary directory, and checks controller syntax before replacing services. It takes a one-time snapshot of the previous service files plus unit enablement/active states under /var/lib/surface7-ubuntu-frontcamera/backup/<kernel>/pre-on-demand. It disables/removes the old always-on unit and timer, installs the idle relay/controller and rollback helper, and enables the new units. Errors invoke the previous-deployment rollback. This deployment check verifies prerequisites and service activation; it does not certify app-level discovery or live preview.

Update only the services from a repository checkout:

~~~sh
./scripts/install.sh --deploy-services
~~~

Restore the previous camera-service setup while retaining DKMS, firmware, and packages:

~~~sh
/usr/local/lib/surface7-ubuntu-frontcamera/scripts/rollback.sh --previous-deployment
~~~

Remove the project deployment and restore backed-up files:

~~~sh
/usr/local/lib/surface7-ubuntu-frontcamera/scripts/rollback.sh
~~~

The previous-deployment rollback restores recorded active/enabled states. If the old state ran continuous capture, that rollback may turn the LED on again. Full rollback restores prior system/module files, but a manual reboot may be needed to restore the old module state. Neither rollback mode reboots automatically.

## Current acceptance record

| Test | Result | What it proves |
| --- | --- | --- |
| Direct V4L2 read | Earlier pass: 30 frames received from /dev/video83. | The on-demand relay/controller can deliver real frames. A temporary sample was upright (ceiling at top). |
| WebcamTests.com | Latest user-reported pass after three attempts; 1280×720 RGB at 29 FPS. | Browser capture can work. Repeated source start/stop before success remains a reliability issue. |
| Stop on close | User observed feed stop and white LED turn off after closing the successful browser tab. | The physical source is released at idle for that session. |
| Cheese | Latest user report: Cheese did not discover the synthetic camera. | Not accepted. Earlier isolated-provider preview is historical and needs repeatable retesting. |
| Firefox | Not retested on current on-demand deployment; previous attempts failed. | Not accepted. |
| Brave and Opera | Previously reported working on the earlier service design. | Not yet verified on current on-demand deployment. |
| Orientation | Varies by test/client history. | Recheck every client; no shared source transform is deployed. |

## Investigation history

- The old always-on GStreamer service did deliver camera frames but kept the white LED lit while no app was capturing. Stopping it turned off the LED without rebooting.
- The first on-demand GStreamer attempt used an unsupported ae-enable property; removing it allowed startup to continue.
- The next attempt loaded Ubuntu's stock libcamerasrc and could not find the configured Surface camera. The on-demand unit lacked the product-built libcamera plugin path. PR #15 added the Surface plugin path, a runtime-scoped GStreamer registry, and a load preflight. After merge/redeployment, a bounded V4L2 read delivered 30 frames. PR #16 recorded that evidence and its limits.
- The ordinary GStreamer Video/Source monitor hides /dev/video83 because the libcamera provider hides V4L2 devices it does not own. The --include-hidden listing showed the node with misleading provider capability metadata. A process-scoped GStreamer provider prototype exposed only the loopback and its v4l2src element delivered buffers, but emitted two GStreamer critical warnings. It was not installed globally.
- An isolated Cheese provider previously showed a preview, but later tests and the latest user report found Cheese could not discover the synthetic camera. The application integration remains unresolved.
- User WebcamTests.com testing later succeeded, unlike an earlier in-app attempt that ended in a paused track. The latest browser session required retries and then released the camera/LED on tab close; do not keep the earlier paused state as the latest result.

## Next tests

1. Resolve Cheese discovery with the process-scoped provider. Inspect what Cheese and GstDeviceMonitor see, confirm the selected device is /dev/video83, and verify actual moving frames through Cheese. Capture logs for the provider's GStreamer critical warnings.
2. Repeat WebcamTests in one browser at a time, note permission/device-label changes and capture start/stop events, wait for stable frames, then close the tab and verify idle release.
3. Test Brave and Opera against this deployment, then test Firefox alone and record its selected device and exact failure.
4. Record orientation per client; avoid global rotation until all client results support it.
5. Keep the provider temporary until repeatable Cheese results, robust rollback coverage, and application tests pass. Do not reboot or reload modules without explicit authorization. Any approved reboot requires a system-wide warning and a full two-minute wait.

## Sources

- [Pinned source revisions and licenses](source-bases.md)
- [Linux V4L2 STREAMON/STREAMOFF documentation](https://docs.kernel.org/userspace-api/media/v4l/vidioc-streamon.html)
- [v4l2loopback v0.15.4 event implementation](https://github.com/v4l2loopback/v4l2loopback/blob/v0.15.4/v4l2loopback.c)
- [Linux V4L2 event queue](https://github.com/torvalds/linux/blob/master/drivers/media/v4l2-core/v4l2-event.c#L976-L1058)
