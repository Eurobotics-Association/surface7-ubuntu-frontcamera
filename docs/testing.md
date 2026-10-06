# Camera testing and acceptance

Updated: 6 October 2026

## Current host state

Robert authorized the camera-service transition and asked to stop the
continuous feed. The always-on `surface7-front-camera.service` is stopped,
its boot timer is disabled, and Robert confirmed that the white front-camera
LED went out. There is no camera GStreamer process running. The virtual
`/dev/video83` node and loaded camera modules remain present. No reboot,
module reload, or package operation was needed to stop the feed.

The first on-demand deployment is now active on the host: the idle relay
and event controller run, while the old always-on service and timer are
inactive. At idle, no physical `gst-launch-1.0` process is running. The relay
logs one initialization frame and then waits on its FIFO.

During the first browser capture attempt, the event watcher reported capture
active and the controller launched GStreamer, but the pipeline exited before
producing a live image: the installed `libcamerasrc` rejects the
`ae-enable` property. `gst-inspect-1.0 libcamerasrc` lists
`camera-name` and `auto-focus-mode`, but no `ae-enable`. The corrected
repository pipelines remove that unsupported property; the host needs the
merged update and another capture test before on-demand behavior can be
validated.

The initial service migration also printed an error while copying the
persistent rollback helper because its parent `scripts/` directory was
missing. Service activation continued. The one-time pre-transition snapshot
was created successfully. A follow-up hardens error handling, creates the
helper directory, and restarts the controller on redeploy; reinstall it from
`main` before further client acceptance testing.

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

Run each client separately, wait for the live image, then close the client.
Record whether the picture is upright, whether frames move, the physical LED
state, and whether the physical GStreamer process stops after the two-second
grace period.

| Client | Discovery | Moving frames | Orientation | LED off after close |
| --- | --- | --- | --- | --- |
| Cheese | Pending | Pending | Pending | Pending |
| Firefox | Pending | Pending | Pending | Pending |
| Brave | Pending | Pending | Pending | Pending |
| Opera | Pending | Pending | Pending | Pending |
| WebcamTests.com | Pending | Pending | Pending | Pending |

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
- Temperatures observed before this update were below 95°C. Continue below and
  at 95°C; if readings exceed 95°C, pause heavy work for three minutes and
  resume while monitoring.

## Historical investigation

Earlier kernel, module, Firefox, Cheese, GStreamer enumeration, and provider
experiments are preserved in
[the dated testing archive](testing-archive-2026-10-05-and-06.md). Those notes
include intermediate failures and temporary settings; refer to the current
sections above for the latest service and acceptance state.
