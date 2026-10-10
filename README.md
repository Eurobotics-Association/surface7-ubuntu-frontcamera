# Surface Pro 7 front camera on Ubuntu

Experimental GStreamer/libcamera → V4L2 compatibility camera for Microsoft Surface Pro 7 (not 7+), Ubuntu 24.04 x86_64 and the installed Ubuntu HWE kernel.

**10 October 2026: the proposed design requires explicit startup after login. It must not initialize physical or virtual cameras during boot.** The repository implementation is prepared; deployment and reboot acceptance are pending. The currently installed earlier design can still pull its disabled boot service in through dependent units.

Read the [startup design, exact deployment/rollback plan and verification protocol](docs/explicit-start.md) before changing the host. There is no network-triggered, timer-triggered or automatic login startup.

From the reviewed checkout:

```sh
./scripts/deploy-services.sh --plan
# Only after explicit approval for host deployment:
./scripts/deploy-services.sh
```

The service migration does not install packages, replace DKMS modules or firmware, load/unload camera modules, test the camera or reboot. It preserves rollback snapshots before host changes and rebuilds existing initrds with the module guard. Already loaded modules remain until a separately approved reboot. Fresh hardware installation is temporarily paused pending acceptance of the broader DKMS transaction.

After deployment and a clean, separately approved reboot, an interactive logged-in user can explicitly arm the camera:

```sh
sudo surface7-camera start
sudo surface7-camera status
sudo surface7-camera stop
```

Once armed, the relay keeps `/dev/video83` discoverable with one initialization frame. Physical capture starts only when an application requests video. A startup or capture failure latches the camera off for that boot; no automatic retry loop is used. Firmware authentication remains unresolved, so this design is experimental.

Rollback from the reviewed checkout:

```sh
./scripts/rollback.sh --startup-policy
```

This restores files, initrds and saved unit enablement, keeping services stopped. `--startup-policy-resume` also restores previously active services and requires approval because it may start the old camera design. Keep the reviewed checkout: restoring the installed rollback helper can replace it with the older version.

Earlier WebcamTests sessions produced 1280×720 RGB at about 29 FPS, including observed moving frames, but required repeated manual test clicks. Reliable first-click startup, Cheese, Firefox, Teams and Meet remain unaccepted. See the [handoff](docs/handoff-current.md), [test record](docs/testing.md) and [earlier investigation](docs/on-demand-v4l2-prototype.md).

No PipeWire camera configuration is used. Existing PipeWire audio/desktop services, Surface 5, and `upstream/surface-pro-7-camera` remain unchanged. All package operations use Ubuntu APT and require separate approval in the current task.
