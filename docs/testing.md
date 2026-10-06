# Camera testing and acceptance

Updated: 6 October 2026

## Current host state

Robert authorized the camera-service transition and asked to stop the
continuous feed. The always-on `surface7-front-camera.service` is stopped,
its boot timer is disabled, and Robert confirmed that the white front-camera
LED went out. There is no camera GStreamer process running. The virtual
`/dev/video83` node and loaded camera modules remain present. No reboot,
module reload, or package operation was needed to stop the feed.

PR #15 is merged, and the GitHub installer has updated the existing
project-owned deployment from `main`. The product-built libcamera plugin and
runtime registry are selected by the active on-demand service. Its preflight
passed all 22 checks with no warnings or failures; required Ubuntu packages
were already installed. No kernel rebuild, reboot, or module reload was needed.

The old always-on service and timer are inactive. The idle relay and controller
are active, and the physical GStreamer source stops after capture ends. A
bounded `v4l2-ctl` read from `/dev/video83` triggered the controller and
received 30 frames. Camera logs show the OV5693 front sensor, its tuning file,
software ISP debayering, and live autofocus frame updates. A temporary image
made from the captured stream was upright (ceiling at the top). Temporary
capture files were removed. This verifies live frames through the on-demand
V4L2 path and confirms the stream can stop at idle.

The internal WebcamTests.com page detected the device, but its launch state
changed from “waiting for permission” to “video track paused” without a visible
preview or populated frame statistics. It did trigger the camera pipeline,
which then stopped when capture became inactive. Cheese was launched through
the isolated temporary provider for 20 seconds; its V4L2 request started the
controller and returned it to idle at test close, but the Cheese preview could
not be inspected through this session's UI controls. Those two application
previews remain unverified. Brave, Firefox, and Opera were not available in
the current UI-control inventory for live retesting. The white LED is not
software-readable; Robert had confirmed it went out after the old continuous
service was stopped, and the new service now leaves the physical pipeline
stopped at idle.

## Evidence from the previous GStreamer service

| Client | Observed result | Scope |
| --- | --- | --- |
| Cheese | Robert confirmed the temporary scoped-provider launch displayed an upright live preview. | The provider was isolated to the Cheese process; the system-wide on-demand service was not tested. Two non-fatal GStreamer critical warnings appeared. |
| WebcamTests.com in the Codex in-app browser | RGB 1280×720 at 29 FPS; video was visible. | An earlier preview appeared upside down. It does not establish Brave, Opera, or Firefox results. |
| Brave | Robert reported live video. | User-reported test of the previous always-on service; later orientation reports varied. |
| Opera | Robert reported live video. | User-reported test of the previous always-on service. |
| Firefox | Previously showed the site's generic “in use or blocked” message; no successful frame was confirmed by the agent. | Exact WebRTC failure remains unknown. |
| Idle LED | LED went out after stopping the always-on service. | Robert observed this directly; no reboot was needed. |

Earlier GStreamer readback tests on the previous service produced visible
moving frames from `/dev/video83`. Those results prove the physical
GStreamer/libcamera path can deliver frames; they do not prove the on-demand
controller works.

## On-demand acceptance matrix

| Client/path | Discovery/request | Moving frames | Orientation | Idle result |
| --- | --- | --- | --- | --- |
| V4L2 read test | `/dev/video83` opened and triggered the controller. | 30 frames read; temporary sample converted to PNG. | Upright; ceiling at top. | Controller stopped GStreamer after the client closed. LED not software-readable. |
| Cheese | Isolated provider launched; controller started on its V4L2 request. | Preview not visually inspected in this UI session. | Not verified in this run. | Controller returned to idle when the 20-second test ended. |
| WebcamTests.com in Codex browser | Device listed; click reached a waiting state then “video track paused.” | No visible browser preview or frame statistics. | Not verified in this run. | Controller stopped after capture became inactive. |
| Firefox | Not retested; native app UI unavailable to this session. | Not verified. | Not verified. | Not verified. |
| Brave | Not retested; native app UI unavailable to this session. | Not verified. | Not verified. | Not verified. |
| Opera | Not retested; native app UI unavailable to this session. | Not verified. | Not verified. | Not verified. |

The V4L2 `CLIENT_USAGE` payload is a Boolean, not a client count: `0` means
idle and `1` means a capture stream is active. Concurrent-client behavior
must be tested as contention separately.

## Build and safety checks

- The watcher compiled with `cc -O2 -Wall -Wextra -Werror`.
- The pinned vendor relay compiled with the same warning flags.
- The Python controller passed syntax compilation.
- The new and existing systemd units passed `systemd-analyze verify` in a temporary root with stubbed executable paths and standard target units.
- `scripts/deploy-services.sh` performs package preflight, checks the running
  kernel against the deployment marker, builds into a temporary directory,
  snapshots the old service state once, disables/removes the always-on unit and
  timer, installs the rollback helper, and enables/restarts the relay/controller
  services. Failures are routed through the previous-deployment rollback.
- `scripts/rollback.sh --previous-deployment` restores the pre-transition
  service files and their enabled/active states while keeping DKMS, firmware,
  and packages. Full rollback restores the original project-level backup.
- The highest thermal-zone reading during this capture/testing session was
  59°C. Continue through 95°C; if a reading exceeds 95°C, pause heavy work for
  three minutes and resume while monitoring.
- GitHub Actions static validation passed for PR #15 before merge.

## Historical investigation

Earlier kernel, module, Firefox, Cheese, GStreamer enumeration, and provider
experiments are preserved in
[the dated testing archive](testing-archive-2026-10-05-and-06.md). Those notes
include intermediate failures and temporary settings; refer to the current
sections above for the latest service and acceptance state.
