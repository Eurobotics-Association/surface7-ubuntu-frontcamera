# Surface Pro 7 camera work — current handoff

Updated: 6 October 2026, 23:40 CEST

## Goal

Finish a reliable Ubuntu front-camera setup for Microsoft Surface Pro 7. Keep the virtual camera discoverable, start the physical camera only while a client requests capture, and stop the source/white LED when the last client closes. Make the result work in Cheese, Firefox, Brave, Opera, and WebcamTests.com.

## Current implementation

- Ubuntu 24.04 x86_64; build/deploy targets the currently running Ubuntu kernel and its matching headers. Keep exact host kernel inventory out of public docs.
- GStreamer with the Surface-built libcamera plugin and libcamerasrc feeds the V4L2 loopback device /dev/video83.
- The on-demand relay holds one initialization frame; it does not emit black frames continuously.
- The controller watches the v4l2loopback CLIENT_USAGE Boolean and starts/stops the physical pipeline. The old always-on unit/timer are disabled.
- No PipeWire camera source is used. Leave PipeWire audio/desktop services alone.
- Root README has the public curl install command. Install and rollback details are in README.md and on-demand-v4l2-prototype.md.

## Latest evidence and unresolved apps

- Direct V4L2 testing previously read 30 frames. A temporary sample was upright, with the ceiling at the top.
- Robert reports WebcamTests.com eventually displayed 1280×720 RGB at 29 FPS and “Surface Pro 7 Front Camera” after three attempts. There were source start/stop cycles during retries. Closing the successful tab stopped capture and the white LED went out.
- Cheese did not discover the synthetic camera in the latest attempt. An isolated provider showed a preview in an earlier test, but not reliably. Cheese remains unresolved.
- Firefox has not been retested against the current on-demand deployment; earlier attempts failed.
- Robert previously reported Brave and Opera working with an earlier service version. Retest both against the current deployment.
- Image orientation has differed across application tests. Do not add a global rotation; capture and record one result for each client.
- The current design is experimental. A browser success and a direct V4L2 read do not prove the app matrix or first-try startup reliability.

## Main investigation findings

- Always-on GStreamer delivered images but kept the physical camera and white LED active while idle. Stopping that service extinguished the LED without a reboot.
- On-demand startup first failed due to an unsupported libcamerasrc property; after its removal it loaded Ubuntu's stock plugin rather than the Surface-built plugin. PR #15 fixed plugin selection and runtime registry handling.
- After deployment of that fix, a V4L2 read delivered 30 frames. PR #16 documented the frame test and application-test limits.
- Ordinary GStreamer device discovery hides the loopback node. A process-scoped provider prototype exposed only /dev/video83, but emitted GStreamer critical warnings. Keep it temporary until Cheese can reliably discover the device and display moving frames.
- WebcamTests first appeared paused in the in-app browser; the later user test succeeded after retries. The latter is the current browser evidence.

## Continue with these tests

1. Test Cheese by itself. Compare normal GStreamer device discovery with the isolated provider. Confirm Cheese selects /dev/video83, displays moving frames, and shows the correct orientation. Capture provider and Cheese logs, including the GStreamer criticals.
2. Test one browser at a time: grant camera access, keep the stream active long enough to confirm steady frames, note device labels and source transitions, close the tab, then verify the physical pipeline stops and LED goes out.
3. Repeat for Brave, Opera, and Firefox on the current deployment. Record the actual Firefox error rather than relying on the site's generic “busy or blocked” message.
4. Do not install the provider globally, change the source rotation, reload camera modules, or reboot until the change is rollback-covered and the needed hardware test is explicitly authorized.

## Install and rollback

Public installer:

~~~sh
curl -fsSL https://raw.githubusercontent.com/Eurobotics-Association/surface7-ubuntu-frontcamera/main/scripts/install-from-github.sh | bash -s -- --install
~~~

Update the on-demand services from a checkout with:

~~~sh
./scripts/install.sh --deploy-services
~~~

Restore the previous service deployment with:

~~~sh
/usr/local/lib/surface7-ubuntu-frontcamera/scripts/rollback.sh --previous-deployment
~~~

Full rollback:

~~~sh
/usr/local/lib/surface7-ubuntu-frontcamera/scripts/rollback.sh
~~~

Rollback does not reboot. The previous-deployment rollback can restore the old always-on service, which may turn the LED on. Before any reboot, broadcast a warning to every logged-in user and wait at least two minutes.

## Repository instructions

Follow AGENTS.md. Use the GitHub plugin for all repository reads/writes, target only Eurobotics-Association/surface7-ubuntu-frontcamera, use Ubuntu APT, preserve the upstream source unchanged, and never modify Surface 5.
