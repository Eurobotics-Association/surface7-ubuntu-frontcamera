# Current handoff — 10 October 2026

The priority is now **no physical or virtual camera activation during boot**. Browser testing is paused. The user requires approval before any deployment, package installation, host service/module change, camera test or reboot; earlier testing authorization does not apply to this task.

The [explicit-start design and deployment/rollback plan](explicit-start.md) is implemented in the repository and awaiting review. The host remains on the previous deployed candidate. Do not confuse repository validation with deployment or camera acceptance.

The read-only audit confirms that the disabled `sp7-camera-boot.service` is required by the enabled relay and on-demand units. It loads IPU4P before the display manager. A separate modules-load file loads v4l2loopback. The current boot shows early firmware-authentication failures and blocked `v4l_id` probes. Use monotonic timestamps; initial wall-clock dates are unreliable. A camera contribution to Bluetooth delay and low CPU frequency remains a hypothesis.

The new design masks three legacy units, removes new-unit boot enablement, blocks camera module loading (also in rebuilt initrds), skips physical IPU4 udev video probing and restricts physical nodes to root. `sudo surface7-camera start` after interactive login is the only supported activation path. Failures latch off without automatic retries. Kernel tasks in uninterruptible sleep may still require an approved reboot.

Before deployment, the transaction snapshots all six units' enablement and active state, all affected files, all existing initrd images and the loaded-module inventory. Read `explicit-start.md` for exact commands, refusal conditions, safe rollback versus active-state restoration, and recovery limits. Do not alter CPU power controls, module binaries, firmware, the Surface 5 repository or upstream sources.

Correction to the 6 October wording: Robert explicitly clarified that he had to click “Test my webcam” repeatedly. A later controlled test also succeeded on the second click with visible moving frames at 1280×720, about 29 FPS. The selected label/device identifier stayed stable during that controlled test; this does not disprove his earlier observed transitions. The repeated-click problem is unresolved. Low-light static-scene checks are not moving-frame acceptance.

Next sequence: review repository diff and tests → request deployment approval → verify the deployed inactive policy → separately request controlled reboot approval, broadcast a system-wide warning and wait 120 seconds → compare boot, Bluetooth, camera errors and CPU metrics without starting the camera → request a later explicit camera test. No implied approval between these steps.
