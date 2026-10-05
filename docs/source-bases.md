# Source bases and licenses

The vendored source in upstream/surface-pro-7-camera is preserved from tag sp7-camera-five-profile-final-2026-09-29, commit a74741e27a6632a9acf9c8d7cc9c1a5912bed7cd.

The pinned vendor installer SHA-256 is e389583af1cf99a46e51377332b95236f153737e4685f8a171a4aabb2390ef6b. The Ubuntu adapter refuses to operate if this changes.

| Component | Source pin or reference |
| --- | --- |
| Linux stable | tag v6.19.8, commit 86818b2e7d9c22225b15f2ae91d3f35c4a07dfd9 |
| Surface Pro 7 IPU4P | georgemihaila/sp7-ipu4-camera, commit aa0043f3649c3bff9247d5f99de5d164c3cdcc75 |
| libcamera | commit 191e202178f02430b5942397c70d215cdd2056fa |
| OV5693 simple IPA tuning | ConsultingFuture4200/sp7-camera, commit 9bb8ec8bed3ca02c774ef211332fcc8259232b90, CC0-1.0 |
| v4l2loopback | tag v0.15.4, commit 0f9ee86760b7f2bea174b7e3e7a1d38845da0ab4 |
| IPU4 firmware | ruslanbay/ipu4-drivers, commit 4ea36123f12e8eafe4f12017614e7b642feb5430 |
| Direct front-camera GStreamer reference | georgemihaila/sp7-ipu4-camera/docs/front-camera.md, reviewed 2026-10-04 |
| GStreamer source element behavior | official libcamera GStreamer documentation, reviewed 2026-10-04 |

Firmware source file: firmware/ipu4-20191030.bin, installed as /usr/lib/firmware/ipu4p_cpd.bin.

Firmware SHA-256: ff2c36cc81a5c726508b22970c2e2538ff06107dc5a72c93401403c227e5157f.

The pinned source tree contains its original LICENSE and component license files under LICENSES. Preserve these with their source files. New deployment files are marked GPL-2.0-or-later.

## Release provenance

- Upstream tagged implementation: [surface-pro-7-camera tag](https://github.com/Elefantenjongleur/surface-pro-7-camera/tree/sp7-camera-five-profile-final-2026-09-29)
- Surface 7 camera discussion: [Linux Surface discussion #1353](https://github.com/linux-surface/linux-surface/discussions/1353)
- Direct GStreamer path: [Surface 7 front-camera notes](https://github.com/georgemihaila/sp7-ipu4-camera/blob/main/docs/front-camera.md)
- GStreamer plugin behavior: [libcamera getting started](https://docs.libcamera.org/master/getting-started.html)
