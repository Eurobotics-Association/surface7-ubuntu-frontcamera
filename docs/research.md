# Surface Pro 7 front-camera research

Research reviewed before deployment planning, 4 October 2026.

Updated 5 October 2026 after the host target was corrected: the target is the latest Ubuntu HWE kernel installed on the Surface, with matching headers. The legacy `6.19.8-surface-3` target is not the user's requested target and has been removed. This public repository omits exact host-kernel inventory.

## Hardware and capture path

The [Linux Surface discussion #1353](https://github.com/linux-surface/linux-surface/discussions/1353) reports the Surface Pro 7 IPU4P stack working with the front OV5693 sensor and rear camera. It is useful evidence about the Surface 7 hardware and kernel drivers; its reported desktop camera bridge is not used here.


The newer [ConsultingFuture4200/sp7-camera work](https://github.com/ConsultingFuture4200/sp7-camera) reports both SP7 cameras capturing through IPU4P and libcamera. Its 2026-09-20 update adds fixes for ISYS probe faults, frame-size enumeration on the clean BE SOC capture path, and Windows-derived front-camera receiver timing. Its [runtime notes](https://github.com/ConsultingFuture4200/sp7-camera/blob/main/docs/both-cameras-working.md#runtime) say to prevent module autoload, load the stack once after boot, and pin MMU1 on before ISYS creates the video nodes; udev probing and an early CSE handshake can otherwise wedge initialization. The local boot helper already follows the ordered load and MMU1 pin steps. This project tests a 60-second systemd timer as a repeatable way to defer that one-time load; the reference does not prescribe that exact interval. The recipe is validated against a 6.19.8 kernel, and its author explicitly says those patches do not apply directly to 7.x. It is the latest driver evidence, but not a drop-in replacement for this Ubuntu HWE target; it needs an audited forward-port.

The [official libcamera GStreamer documentation](https://docs.libcamera.org/master/getting-started.html) documents libcamerasrc as an optional GStreamer source plugin. The Ubuntu deployment uses APT packages for the build environment and builds the camera libraries from pinned source.

These reports establish plausible Surface 7 implementations, not a validated Ubuntu result. The GStreamer approach remains the selected path; PipeWire camera integration is out of scope. The Ubuntu-specific package and service configuration still requires local moving-frame tests.

## Earlier Zorin OS report

The [Zorin forum thread about Surface Pro 7 cameras](https://forum.zorin.com/t/surface-pro-7-internal-camera-not-working-in-zorin-os-17-3-pro/49863) is from August 2025 and predates the later IPU4P work. It is historical context rather than the current hardware solution.

## Surface 5 repository review

The complete Eurobotics-Association/surface5-frontcamera repository was read before adapting this project, including its source, documentation, scripts, checks, and rollback instructions. Surface 5 uses an Intel IPU3 CIO2/IMGU graph and the `libcamera` IPU3 pipeline; Surface 7 uses Intel IPU4P, which is not supported by an upstream kernel driver and needs a patched out-of-tree stack plus CSE firmware authentication. Both can use GStreamer at the application/bridge layer, but GStreamer cannot compensate for an absent or unauthenticated kernel camera pipeline. Surface 5's successful result therefore validates the capture approach, not the Surface 7 driver stack. Process ideas carried forward include pinned source provenance, read-only preflight, build-only mode, bounded backups, rollback, and moving-frame acceptance checks. No Surface 5 files were changed.

## Ubuntu adaptation

The Surface 7 source release's installer targets a different Linux distribution, package manager, and kernel release. The local adapter uses Ubuntu APT, selects the running Ubuntu HWE kernel with matching headers, stages userspace output in a project-specific library directory, and registers kernel modules through DKMS. DKMS installation and a build for another installed Ubuntu kernel succeeded. The adapter changes only a temporary copy; the vendor snapshot remains unchanged. The installed driver source already includes equivalents of the newer frame-size enumeration and SP7 front timing fixes. Earlier live attempts showed IPU firmware-authentication errors. A later one-time `iommu=pt` diagnostic boot enumerated both cameras and yielded raw GStreamer buffers without matching CSE/DMAR errors during that test, but pixel data was saturated or zero. This correlation does not establish a root cause or a working stream. The temporary GRUB entry was removed after the trial.

The pinned IPU4P commit (`georgemihaila/sp7-ipu4-camera@aa0043f3649c3bff9247d5f99de5d164c3cdcc75`) handles the Surface Pro 7's signed 20191030 CPD firmware versus 20181222 CSS library pairing with a DMI- and device-specific exception in `ipu-cpd.c`. Unlike the newer working reference's driver, this pinned source does not expose `fw_version_check`; carrying that parameter in its modprobe config only produces an ignored-option warning. The Ubuntu adaptation removes it from the temporary deployment copy and preserves the scoped source check. The observed CSE boot-load failure remains a separate unresolved runtime issue.

## Current-kernel compatibility

The target is Ubuntu 24.04 x86_64 with the latest installed Ubuntu HWE kernel. The [Surface 7 reference's working report](https://github.com/ConsultingFuture4200/sp7-camera/blob/main/docs/both-cameras-working.md) is validated on Arch/Linux 6.19.8 and says its patches do not apply directly to newer kernels. This project's DKMS modules build and load on the target Ubuntu kernel. In one temporary `iommu=pt` boot, libcamera enumerated both cameras and GStreamer negotiated a front Bayer stream, but captured buffers did not contain usable image data. A successful build, media-node enumeration, camera enumeration, negotiated caps, or buffer arrival alone does not establish runtime compatibility. The approved next step is a bounded direct-libcamera capture with buffer-layout and control metadata recorded; see [the investigation log](front-camera-investigation-2026-10-05.md).

## DKMS assessment

DKMS is a plausible way to keep the out-of-tree IPU4P and loopback kernel modules rebuilt when Ubuntu installs a new kernel. Its module source must remain under `/usr/src` with a valid `dkms.conf`; `AUTOINSTALL="yes"` enables automatic attempts, and `dkms autoinstall` installs modules built for other kernel revisions. A matching kernel headers package is still needed, and DKMS recompiles modules for each kernel version. It does not make an incompatible driver patch compatible with a new kernel or guarantee the build succeeds. See the [Ubuntu 24.04 DKMS manual](https://manpages.ubuntu.com/manpages/noble/man8/dkms.8.html) and [upstream DKMS manual](https://github.com/dkms-project/dkms/blob/main/dkms.8.in).

The plan approved on 5 October 2026 is to build the kernel sources against the host's current Ubuntu kernel, then register the modules with DKMS. The modules compile and load, but this alone does not prove runtime compatibility. The separately built libcamera/GStreamer userspace components are not DKMS modules; kernel upgrades do not normally require rebuilding them, though the camera path must be rechecked after kernel-driver changes. Moving-frame validation remains pending.

## Surface Pro 7 ventilation context

The linux-surface project has a long-running [Surface Pro 7 thermal-throttling issue](https://github.com/linux-surface/linux-surface/issues/221) and a [thermald configuration discussion](https://github.com/linux-surface/linux-surface/discussions/558). These are historical reports, not a diagnosis of this unit's fan behavior. Investigate this separately using sensor/cooling-device reports, fan telemetry where available, and service/kernel logs before considering configuration changes. Keep this separate from camera driver deployment.
