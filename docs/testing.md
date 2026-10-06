# Camera testing and acceptance

Updated: 6 October 2026, 23:40 CEST

## Current deployment and result

The experimental on-demand services are installed on Robert's Surface Pro 7. The old always-on camera service and timer are stopped/disabled. The idle relay keeps /dev/video83 discoverable with one retained initialization frame; the physical GStreamer/libcamera pipeline starts on a V4L2 capture request and stops after capture becomes idle. The relay does not emit repeating black frames.

Robert confirmed the white camera LED went out after the old continuous service was stopped. In the latest on-demand browser test, he reports that WebcamTests.com eventually showed live video and reported RGB, 1280×720, 29 FPS, and “Surface Pro 7 Front Camera.” It took three attempts; the feed started and stopped between attempts. After the successful session, closing the tab stopped the feed and the LED went out. The host service journal showed multiple capture sessions during the browser sequence. This verifies one successful browser session and idle release, not stable first-try startup.

The latest Cheese attempt did not discover the synthetic camera. An earlier isolated-provider Cheese run showed a preview, but that result does not establish reliable discovery in the current deployment. Firefox has not been retested on the current on-demand services; earlier tests failed. Robert previously reported Brave and Opera working with the earlier camera service. Those reports do not yet establish current on-demand compatibility.

## Current application matrix

| Client/path | Current result | Evidence and limits |
| --- | --- | --- |
| WebcamTests.com | User-reported success after three attempts; RGB 1280×720 at 29 FPS. | Feed started/stopped during retries. Closing the successful tab stopped capture and the LED went out. First-try reliability is unresolved. |
| Cheese | Current user-reported failure: synthetic camera not discovered. | An earlier isolated GStreamer-provider preview worked once. Treat Cheese as unresolved until the current command reliably discovers the camera and displays moving frames. |
| Firefox | Not retested against the current on-demand deployment; earlier attempt failed. | Previous page showed a generic “in use or blocked” message. Exact WebRTC error remains unknown. |
| Brave | User previously reported a live image on the earlier service. | Must be retested with the current on-demand deployment. |
| Opera | User previously reported a live image on the earlier service. | Must be retested with the current on-demand deployment. |
| Direct V4L2 read | Pass in an earlier on-demand test: 30 frames read from /dev/video83. | A temporary frame was upright, with the ceiling at the top. This proves frame flow, not app discovery. |
| Idle release | Pass for the latest WebcamTests.com session, per Robert. | Closing the tab stopped the source and white LED. LED state is user-observed; it is not software-readable. |

Orientation reports have differed across applications and test sessions. The direct V4L2 sample was upright; some browser/desktop previews appeared inverted while Brave and Opera had earlier looked correct. No global image flip has been applied. Recheck and record orientation per client after its live stream is stable.

The device label reportedly changed during the browser permission/retry flow. Media Capture devices can have restricted or empty labels before permission is granted and expose labels after permission; this is a plausible explanation, not a diagnosis of the retry sequence. See the [W3C Media Capture and Streams specification](https://www.w3.org/TR/mediacapture-streams/).

## Deployment and rollback audit

The public install entry point is the curl command at the beginning of README.md. scripts/install-from-github.sh fetches the repository from GitHub and invokes scripts/install.sh. The installer checks the target Surface, Ubuntu 24.04 x86_64, running kernel, and matching headers. scripts/install-build-deps.sh checks and installs missing build/GStreamer packages through Ubuntu APT and sudo.

For a fresh install, scripts/install.sh builds and registers the camera modules with DKMS, then deploys the camera services. DKMS AUTOINSTALL is enabled for later kernel installs. On an existing project-owned installation, --install checks ownership and the recorded running kernel, then updates the service design without rebuilding DKMS. --deploy-services updates just the on-demand services.

scripts/deploy-services.sh checks package availability, the active kernel against the deployment record, and the product-built libcamerasrc plugin. It compiles the event watcher and relay with warnings treated as errors, checks Python syntax, snapshots the previous service files and enablement/active states once, disables/removes the old always-on service, and enables the relay/controller. Deployment errors invoke the previous-deployment rollback. The deploy script does not test Cheese or browser previews; systemd activation is not app acceptance.

Previous service rollback:

~~~sh
/usr/local/lib/surface7-ubuntu-frontcamera/scripts/rollback.sh --previous-deployment
~~~

Full project rollback and system-file restoration:

~~~sh
/usr/local/lib/surface7-ubuntu-frontcamera/scripts/rollback.sh
~~~

Previous-deployment rollback restores the prior service and its recorded active/enabled state, so restoring an always-on service may turn the camera LED on again. Full rollback removes the project-owned modules and restores backed-up files; a manual reboot may be needed to restore the prior module state. Neither rollback mode reboots automatically.

## Earlier verified on-demand path

A bounded v4l2-ctl read opened /dev/video83 and triggered the controller. It received 30 frames. Libcamera logs showed the OV5693 front sensor, tuning file, software ISP processing, and autofocus updates. A temporary image from the stream was upright. Temporary capture files were deleted.

The first on-demand GStreamer attempt used an unsupported ae-enable property; that property was removed. The next attempt loaded Ubuntu's stock libcamerasrc and could not find the configured Surface camera. The service lacked the product-built libcamera plugin path used by the old service. PR #15 added the product GST_PLUGIN_PATH, a runtime-scoped GStreamer registry, and a plugin preflight. After merge and redeployment, direct V4L2 capture succeeded. PR #16 recorded the frame and client-test limits. The corresponding GitHub Actions validation passed before those merges.

Cheese has a separate GStreamer discovery issue. Ordinary gst-device-monitor-1.0 Video/Source listing hid /dev/video83; --include-hidden showed the loopback with misleading provider capability metadata. A process-local scoped provider prototype exposed only the Surface loopback and a provider-created v4l2src pipeline read frames, but emitted two GStreamer critical warnings. It was not installed system-wide. The current Cheese failure must be resolved with a repeatable, scoped-provider and Cheese UI test before integrating that workaround.

## Next validation sequence

1. Test Cheese alone. Confirm whether ordinary discovery lists /dev/video83; if not, use the isolated provider script and capture Cheese/GStreamer logs. Verify the selected source is the synthetic Surface camera, then confirm moving frames and orientation. Keep any provider process-scoped until it passes repeatable tests.
2. Test WebcamTests.com in one browser at a time. Close all other camera clients, grant permission, wait for stable frames, note source transitions, then close the tab and verify that capture and the LED stop.
3. Repeat the same controlled test in Brave and Opera on the current deployment; then test Firefox alone and record its exact selected device and failure.
4. Record orientation separately for each app. Do not rotate the shared source to correct a single application's display.
5. Keep the deployment experimental until these checks are repeatable. Do not reboot or reload camera modules without explicit authorization; before any reboot, broadcast the two-minute all-user warning and wait the full interval.

## Historical investigation

Earlier kernel, module, Firefox, Cheese, GStreamer enumeration, and provider experiments are preserved in the [dated testing archive](testing-archive-2026-10-05-and-06.md). That archive is historical; this page is the current acceptance record.
