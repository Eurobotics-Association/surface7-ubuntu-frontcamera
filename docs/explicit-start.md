# Explicit camera startup — experimental, 10 October 2026

This change was merged and deployed on 10 October 2026. One clean reboot confirmed the no-camera-at-boot behavior, but the first explicit start failed firmware authentication and moving-frame testing is pending. It supersedes every older instruction to enable the camera at boot, after a boot timer, or automatically at login. The target remains Surface Pro 7 (not 7+), Ubuntu 24.04 x86_64, with the installed Ubuntu HWE kernel and matching headers. Surface 5 and the pinned upstream tree are unchanged.

## Behavior

A fresh boot must load neither IPU4P nor v4l2loopback, expose no project camera, and start no camera services. Network availability is irrelevant. Logging in alone does not start it. After boot has completed and an interactive user session exists, the user may run:

```sh
sudo surface7-camera start
sudo surface7-camera status
sudo surface7-camera stop
```

`start` requires a terminal and an active logind user session belonging to the caller; a greeter is not a user session. It creates a root-owned request under `/run/surface7-camera`, which disappears at reboot. All new units require that request and refuse a failed-boot latch. They have no `[Install]` section and no automatic restart. They do not order themselves before the display manager. Dependencies cannot bypass the absent request.

The legacy boot service, continuous service and timer are **masked**, not merely disabled. The old `/usr/local/sbin/sp7-camera-boot` becomes a non-loading stub. A dedicated modprobe configuration blacklists the camera modules and sets their `install` actions to `/bin/false`; both alias loading and ordinary explicit legacy modprobe calls are covered. The reviewed loader uses `--ignore-install` for one module at a time in dependency order. This is a startup policy, not a security boundary against root deliberately overriding it.

The modules-load file becomes a comment-only file. A managed initramfs-tools hook copies the same module guard into the early boot image. All existing initrds are rebuilt with that guard, including the running kernel's image, so a stale initramfs cannot retain the earlier boot behavior. Built-in camera drivers or unreviewed module lists, camera-related initramfs/cron/rc hooks, and service drop-ins cause deployment to refuse rather than silently alter unrelated files. The IPU4 PCI alias on the audited machine resolves to the guarded `intel_ipu4p` module. New kernels and local startup customizations still require re-audit.

After explicit initialization, the existing relay provides a single initialization frame on `/dev/video83`. The GStreamer/libcamera physical source starts only for sustained application demand and stops after a two-second idle grace period. The number 83 is retained for this change. `stop` stops the services; it does not forcibly unload modules. Modules that were loaded after login remain until reboot. **No physical GStreamer process while idle is different from no camera drivers loaded during boot**; this policy addresses both phases separately. The physical LED still needs visual verification during later acceptance.

## Firmware and probing failures

The generated `/etc/udev/rules.d/60-persistent-v4l.rules` preserves the installed Ubuntu rule content, inserting an early skip for descendants of `intel-ipu4-mmu0` and `intel-ipu4-mmu1` before `v4l_id`. USB cameras and the virtual camera retain the distro rules. Deployment refuses an unexpected source rule structure or an unrecognized existing override. A second rule, ordered after `70-uaccess` and before seat ACL processing, restricts those physical video/media nodes to root and removes their desktop `uaccess` tag. Root GStreamer/libcamera owns physical capture; applications use the compatibility node. This avoids unprivileged browser/desktop enumeration opening the physical nodes again.

Initialization runs once per boot, with a 40-second userspace deadline, individual module commands limited to eight seconds, and a 45-second service deadline. It does not call `v4l_id`, open video devices, wait on global `udevadm settle`, or repeatedly bind devices. The existing camera-specific MMU1 workaround is preserved; no CPU, governor, thermal, fan or power-profile setting is changed.

The controller filters brief demand probes for 1.2 seconds. A source exit, missing initial buffer progress for 20 seconds, or a ten-second progress stall is fatal. It no longer retries automatically. Failed services latch `/run/surface7-camera/failed`; closing/reopening the application, restarting a unit or resetting its failed state does not clear the latch. Inspect logs and leave the camera stopped until a separately approved recovery reboot. Successful normal idle/start cycles remain allowed. The deployed PSYS readiness gate waits up to eight seconds for successful firmware authentication before loading ISYS, which creates the physical video nodes. If PSYS does not bind, the attempt fails without loading ISYS or the virtual camera. The gate has not yet been hardware-tested.

These are userspace limits. A module insertion or source process stuck in uninterruptible kernel sleep may outlive SIGKILL and systemd's deadline. No userspace timeout can promise to recover that driver. The design prevents boot activation and removes the known mass-probe and automatic retry paths; it does not claim to repair firmware authentication or all internal driver retries. Do not repeatedly unload/reload or clear the latch to work around a failure.

## Exact deployment procedure and result

The user approved deployment. PR #19 was merged into main at `0bfa0cae938165bfd29ac05a2453c54009cb1df7`. Deployment then finished successfully on the target host. The immutable snapshot is complete and marked deployed; it records 23 paths, all six unit states and the prior loaded-module inventory. Both installed initrd hashes match the generated images, and both backed-up original hashes match the manifest. The initrd generation step verified inclusion of the module guard. The three legacy units are masked and inactive; the three new units are static and inactive. The modules-load file is comment-only. The installed transaction engine and rollback script match this repository's reviewed bytes. No packages were installed, no camera modules were loaded/unloaded, and no camera test or reboot was run during deployment. Camera modules loaded by the earlier design remain in this boot. **Do not interpret these checks as clean-boot or moving-frame acceptance.**

Run from the reviewed checkout, as the desktop user. Do not use the older dirty checkout's installer by mistake.

1. Preserve the before baseline privately using `scripts/collect-startup-baseline.py` (below). Review active clients and close them. Confirm the Surface model, Ubuntu release, running HWE kernel, headers, and firmware digest. Review any root/user unit, autostart, cron, initramfs, modules-load or modprobe override found by the audit. No packages are installed automatically by this service deployment.
2. Review `./scripts/deploy-services.sh --plan`. After explicit approval, run **`./scripts/deploy-services.sh`**. This compiles only the small watcher and relay, checks the installed GStreamer dependency, then invokes the transactional deployment with sudo. It does not rebuild/install DKMS modules or firmware.
3. Before the first host mutation, create the immutable snapshot `/var/lib/surface7-ubuntu-frontcamera/backup/explicit-start-v1`. Save all affected files (including absence, symlinks, permissions and ownership), the enablement and active state of all six units, the loaded-module inventory, and every existing `/boot/initrd.img-*` image. The marker and manifest must be complete before stopping any service. An existing snapshot is never overwritten; a second deployment requires review, not an implicit new baseline.
4. Stop controller, relay, init and legacy units; disable existing enablement; apply the masks, guarded static units and configuration below. Reload the systemd manager and udev rules **without triggering device enumeration**. No camera module is loaded or unloaded.
5. Build replacement initrds in snapshot staging with `mkinitramfs`, confirm inclusion of the module guard, record each new image's expected hash, then atomically replace its original. This includes all existing images, not just the running kernel. The originals remain available for exact restoration. A failure restores the snapshot with services stopped; no automatic restart of the old failing design occurs.
6. Verify masks, absence of enablement links, effective dependencies, module policy and initrd content. Already loaded modules remain in this boot. This deployment is **not** evidence of a camera-free boot; perform no camera test before the separately approved reboot.

Affected paths:

| Path | Change |
| --- | --- |
| `/etc/systemd/system/{sp7-camera-boot.service,surface7-front-camera.service,surface7-front-camera.timer}` | Replace with `/dev/null` masks |
| `/etc/systemd/system/{surface7-camera-init.service,surface7-front-camera-idle-relay.service,surface7-front-camera-on-demand.service}` | Guarded units, no boot enablement/restarts |
| `/etc/modules-load.d/sp7-v4l2loopback.conf` | Empty of module requests |
| `/etc/modprobe.d/surface7-camera-manual.conf` | Alias and explicit-load guards, including physical sensor modules |
| `/etc/initramfs-tools/hooks/surface7-camera-manual` | Copy guard into every rebuilt early boot image |
| `/etc/udev/rules.d/60-persistent-v4l.rules` | Preserve distro rules; skip IPU4 physical probes |
| `/etc/udev/rules.d/71-surface7-camera-private.rules` | Root-only physical nodes; remove uaccess |
| `/usr/local/sbin/{sp7-camera-boot,surface7-camera}` | Retired stub and explicit control helper |
| `/usr/local/libexec/{surface7-front-camera-controller.py,surface7-v4l2-idle-relay,surface7-v4l2-client-watch}` | Controller and compiled existing helpers |
| `/etc/default/surface7-front-camera` | Reviewed front-camera settings |
| `/usr/local/lib/surface7-ubuntu-frontcamera/scripts/{rollback.sh,startup-policy.py}` | Persistent rollback entry point and transaction engine |
| `/usr/local/lib/surface7-ubuntu-frontcamera/config/{ubuntu.env,ownership-marker}` | Rollback dependencies |
| Existing `/boot/initrd.img-*` | Guarded images; exact originals backed up |

No module binaries, DKMS registration, firmware, PipeWire configuration, Bluetooth configuration or CPU power settings are replaced. The original pre-on-demand and kernel/DKMS backups remain untouched. Fresh hardware installation is temporarily refused until its larger DKMS transaction is accepted with this policy; build-only validation and migration of an existing owned installation remain supported. The temporary upstream adapter also removes timer enablement and virtual-module autoload entries as defense in depth.

## Exact rollback plan — approval required

For the follow-up PSYS gate, `sudo python3 scripts/deploy-psys-gate.py deploy` changes only `/usr/local/sbin/surface7-camera` after checking its exact reviewed base hash. It creates an immutable backup at `/var/lib/surface7-ubuntu-frontcamera/backup/psys-gate-v1` before replacing the helper. It does not start services, load/unload modules, or rebuild initrds. `sudo python3 scripts/deploy-psys-gate.py rollback` restores that helper first; the reviewed `./scripts/rollback.sh --startup-policy` now performs that step automatically before the original full startup-policy rollback. The hotfix rollback refuses an unrelated later edit. The base snapshot and all six saved unit states remain untouched.

Keep this reviewed checkout until acceptance. It remains usable even when rollback restores an older installed helper.

```sh
./scripts/rollback.sh --startup-policy
```

This validates all saved hashes and refuses to overwrite a file edited after deployment. It stops the six units, restores every affected file and exact initrd bytes, reloads systemd/udev configuration, and restores saved enablement (including runtime enablement/masks) for the newer relay and on-demand services as well as the legacy units. It deliberately leaves services stopped. The saved module inventory is retained; because deployment does not load/unload or replace module binaries, there is no forced module operation to reverse in the deployment boot.

To restore saved **active** service states as well, obtain explicit approval for camera activation, then use the reviewed checkout:

```sh
./scripts/rollback.sh --startup-policy-resume
```

This may reintroduce the old boot activation and start physical hardware immediately. Merely restoring boot enablement also restores the old behavior on the next reboot. Neither mode reboots or unloads modules. After an intervening reboot or a later explicit camera test, exact kernel runtime state can only be restored through a separately approved reboot or recovery action; copying files does not recreate runtime module state. A hung kernel task may require reboot. The older `--previous-deployment` and full-removal modes are blocked while this startup snapshot remains deployed; first restore the startup policy, then separately review the older removal operation.

For an interrupted deployment, use the same reviewed checkout and `--startup-policy`; original and planned replacement hashes are accepted, unrelated content is not. If validation fails, preserve the snapshot and inspect the reported path; do not force overwrite. Backups and manifests are not deleted by rollback.

## Controlled reboot verification — separate approval required

Capture before/after files privately. They contain host identifiers, input-device names and exact kernel inventory and must not be committed. Use monotonic timestamps throughout; early wall-clock dates were wrong.

```sh
python3 scripts/collect-startup-baseline.py --output /tmp/surface7-before.json --cpu-load-seconds 10
# After a separately approved deployment and reboot:
python3 scripts/collect-startup-baseline.py --output /tmp/surface7-after.json --cpu-load-seconds 10
```

The optional workload is one Python worker, not a frequency benchmark or an effective-clock measurement. Compare the same workload, mains state, profile, session and temperatures on both boots; `scaling_cur_freq` is a sampled driver report. Keep power controls unchanged. Above 95°C, stop heavy work, wait three minutes, then resume monitoring as AGENTS.md requires.

If reboot is approved, broadcast with `wall` to **all logged-in users**, wait the full **120 seconds**, then reboot. Never combine approval for deployment with an assumed approval for reboot or camera testing.

Record these independently:

| Measurement | Before/after method and acceptance |
| --- | --- |
| Boot to graphical | `systemd-analyze time` plus `graphical.target` `ActiveEnterTimestampMonotonic`. Distinguish firmware/loader time, kernel-relative monotonic time and systemd userspace duration. |
| First usable Bluetooth keyboard/mouse | Earliest input registration in the monotonic journal is only a proxy. A person records the first successful typed input and pointer movement after reboot. Keep devices, distance and reconnect procedure the same. Service start is not peripheral usability. |
| Camera errors | Count authentication/CSE failures, blocked-task reports and `v4l_id` events in the first 800 seconds. Leave camera unrequested throughout. Recheck after ten minutes for recurrence. |
| No camera at boot/login | Before explicit start, all six units inactive, three legacy units masked, no camera modules in `/proc/modules`, no project media/video nodes and no physical pipeline. Repeat after login without starting it. |
| CPU | Same ten-second workload and sampling, mains/profile/temperature recorded. Compare frequency distribution; do not change governor, power profile or firmware controls to improve the result. |
| Explicit start, later approval | One start attempt; track monotonic duration, enumeration separately from actual frames, moving-frame test while someone is available, normal close/reopen, idle physical-process release and visual LED behavior. On failure, verify the latch and stop testing. |

Private before-baseline taken on 10 October (current earlier design): graphical target at about **56.2 seconds** monotonic; within the first 800 seconds, **336** firmware-authentication failure lines, **134** CSE boot-load failure lines, **134** `v4l_id` lines and **7** blocked-task reports. The first logged Bluetooth keyboard/mouse input devices registered around **217 seconds**. Under the ten-second single-worker load, reported CPU frequency across samples ranged about **414–577 MHz** (median about **500 MHz**), with maximum observed thermal zone **46°C** and Balanced profile. Input registration is a proxy for usability; no human keystroke or pointer movement was observed by this script. The private JSON stays outside the PR.

On the first post-deployment reboot, no camera modules, media/video nodes, camera services, or explicit request were present before testing. Total startup was **26.4 seconds** versus **76.9 seconds** before; graphical target monotonic time was **16.1 seconds** versus **56.2 seconds**. Mouse and keyboard input nodes registered at **18.9** and **27.2 seconds** versus about **217 seconds** before, and the user reported both devices promptly usable. The first 800 seconds contained **zero** matching firmware-authentication, CSE boot-load, `v4l_id`, or blocked-task messages. Under the same one-worker sampling, frequency was about **2.74–3.50 GHz** (median **3.30 GHz**), maximum observed thermal zone **78°C** and mains power; however, the profile was **Performance** rather than the earlier **Balanced**, so this CPU change cannot be attributed to the camera policy. Do not change power controls as part of this fix. This is one boot, not proof of Bluetooth causality.

The first explicit start after login failed: PSYS firmware authentication returned `-110`, no media graph appeared, and the initialization service latched failure. The already-loaded ISYS driver continued firmware retries and many physical `v4l_id` workers blocked despite the installed udev skip rule. An isolated rule simulation skipped the import as intended, so why live udev workers invoked it remains unresolved. The camera services were stopped; modules were not force-unloaded. **No new camera enumeration through an application or moving-frame capture passed.** A system-wide warning was broadcast and the user-approved recovery reboot occurred after the full requested five-minute wait.

The recovery boot again had no camera modules, media/video nodes, request latch, camera services or matching camera firmware/probe errors in its first 800 seconds. Total startup was **27.3 seconds**, graphical target monotonic time **16.8 seconds**, and mouse/keyboard input nodes registered at **48.6/52.0 seconds**; the user reported Bluetooth working from boot. Under the same one-worker sample, reported CPU frequency ranged **1.13–3.80 GHz** (median **3.50 GHz**) with Performance profile, mains power, and maximum observed thermal zone **88°C**. This confirms a second clean startup, not the cause of the earlier Bluetooth or CPU delays. The merged PSYS gate was then deployed without camera activation. Its immutable backup and installed hashes were verified; hardware retest remains pending.

The camera contribution to Bluetooth delay and low CPU frequency is a strong hypothesis, **not proven causation**. A cleaner subsequent boot supports it but is not sufficient by itself; record other differences and repeat only with further reboot approval.

## Sources and validation limits

Base repository commit: `2ea57dcb431cdce7f2c2a7b39f323fc381fa1847`. The controller lifecycle work was recovered from the previously deployed candidate, then changed to fail without retries. `config/startup-legacy-sha256.json` admits only reviewed main-version and previously installed product files; mismatches fail closed. Module source commits and forum references remain in [source-bases.md](source-bases.md) and [research.md](research.md). Audited firmware SHA-256: `ff2c36cc81a5c726508b22970c2e2538ff06107dc5a72c93401403c227e5157f`; firmware is not changed here.

Ubuntu tools used: `systemd`, `udev`, `kmod`, `initramfs-tools`, `python3`, `build-essential`, and the existing GStreamer packages (including `gstreamer1.0-plugins-good` for `progressreport`). See [Ubuntu modprobe.d semantics](https://manpages.ubuntu.com/manpages/noble/man5/modprobe.d.5.html) and [systemd udev rules](https://www.freedesktop.org/software/systemd/man/latest/udev.html). A blacklist alone does not cover an explicit module request; the install guard is intentional. The udev jump is inside the overridden distro file so its label resolves in that file.

Validation for this revision: shell/Python checks, temporary-copy upstream adaptation, offline systemd dependency parsing, isolated rollback/activation/controller regression tests, userspace helper/provider compilation, synthetic GStreamer buffers to fakesink, successful deployment and installed-state/snapshot verification, followed by two clean-boot checks. The follow-up PSYS gate and one-file rollback tests passed locally; its helper-only deployment and backup hash verification passed, but it has not been camera-tested. **No kernel/DKMS build, successful new camera enumeration, or moving-frame capture has been performed for this design.** Older moving-frame successes remain historical evidence only.
