# Scoped GStreamer provider candidate

Updated: 6 October 2026

## Why this exists

The camera producer delivers frames to the working `/dev/video83` loopback. Brave and Opera have displayed it, but Cheese's device monitor has not consistently exposed it. The default GStreamer monitor omits `/dev/video83`; `--include-hidden` reveals an entry with stale `video_output` capability metadata even though V4L2 reports capture capability. This is consistent with provider-side capability filtering, but that metadata has not been proven as the root cause.

`gstreamer/surface7-v4l2-device-provider.c` is a narrowly scoped candidate provider. It checks the selected node with `VIDIOC_QUERYCAP`, requires the `v4l2 loopback` driver, capture capability, and the exact product card label, then publishes a `Video/Source` device whose source element uses `v4l2src io-mode=rw`. It does not unhide or alter the normal V4L2 provider, so it does not expose the raw IPU nodes seen in the earlier provider-unhiding experiment.

The provider is not installed by the system installer. Its current use is a temporary per-process diagnostic to determine whether Cheese can discover and open the right loopback device. It has no effect on Firefox's independent V4L2/WebRTC enumeration.

## Build and run the desktop check

The build uses the already installed Ubuntu GStreamer development package. It makes no system changes:

~~~sh
bash ./scripts/build-gstreamer-provider.sh /tmp/libgstsurface7v4l2camera.so
~~~

When the desktop user is available to observe the result, launch Cheese with the provider loaded only in that process:

~~~sh
bash ./scripts/run-cheese-with-provider.sh
~~~

Close other browser/app camera tests first, but leave the GStreamer camera service running. Select **Surface Pro 7 Front Camera** if Cheese asks for a device. Record separately whether Cheese lists it and whether live frames appear. The helper builds in a temporary directory, uses a fresh GStreamer registry, runs Cheese without `sudo`, and removes its temporary files when Cheese exits. It does not install packages or change services, modules, or system plugin directories.

For a headless, bounded test of the same device-monitor and source-element path, run this only when no other application is using the camera:

~~~sh
bash ./scripts/test-gstreamer-provider-capture.sh
~~~

## Probe results so far

- Earlier, a `/tmp` prototype compiled on the Surface host and, with the provider loaded through `GST_PLUGIN_PATH` and a fresh registry, `gst-device-monitor-1.0 Video/Source` listed the Surface front-camera label and a recipe using `v4l2src device=/dev/video83 io-mode=rw`.
- That prototype's temporary C harness created its provider element and received five buffers followed by EOS. Two non-fatal `GStreamer-CRITICAL` warnings were logged from Ubuntu's V4L2 plugin. Keeping a device reference did not remove them.
- The same two criticals were then reproduced with the default device monitor plus a directly created `v4l2src`, with the custom provider plugin unloaded. A standalone `gst-launch-1.0 v4l2src ... io-mode=rw num-buffers=5` completed without those criticals. The warning is therefore not yet attributed to this provider; its exact cause and impact remain unknown.
- The checked-in source now builds with GStreamer 1.24.2 and loads as a registered device-provider plugin. The current build shell has no `/dev/video83` or `/dev/media0`, so enumeration and capture with this exact checked-in source have not yet been repeated here. `tests/gstreamer-provider-capture.c` and `scripts/test-gstreamer-provider-capture.sh` preserve the five-buffer hardware test for the Surface host.
- The user reports Cheese currently finds no camera. No Cheese UI test with this candidate has been performed, because it requires the user to observe the desktop.

The five-buffer capture demonstrates GStreamer element capture only. Device-monitor enumeration and successful pipeline buffers do not establish Cheese compatibility. Do not integrate this provider into the automatic deployment or describe Cheese as fixed until the observed desktop test passes and the warnings are understood.
