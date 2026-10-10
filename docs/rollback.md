> **10 October 2026:** Startup policy was deployed and one camera-free boot was verified. The first explicit camera start failed; the PSYS-gate hotfix and its rollback are described in [the explicit-start plan](explicit-start.md). Older commands below are historical.

# Rollback

Installations made from this revision copy a self-contained rollback helper and its two configuration files into the product-owned directory before deployment starts. Run it as the desktop user; it will ask sudo when needed:

~~~sh
/usr/local/lib/surface7-ubuntu-frontcamera/scripts/rollback.sh
~~~

This persistent path works after the one-line GitHub installer removes its successful temporary checkout. If deployment fails, that installer keeps the checkout and prints its rollback command. Installations made before this helper was added should use their local repository checkout. A local clone can run:

~~~sh
./scripts/rollback.sh
~~~

The deployment writes an ownership marker before installing system files. Rollback checks that marker before removing the project library directory. It stops the camera services, restores the prior contents of any system file or kernel-module path it replaced, removes project files that did not exist before deployment, restores service enablement state, and refreshes depmod and ldconfig.

The installer records the exact deployed kernel in the product library directory. Rollback reads that record instead of assuming the currently booted kernel is the one used for deployment.

The libcamera build is staged first. Deployment copies only its product-specific library directory into `/usr/local/lib/surface7-ubuntu-frontcamera`; public development headers or other staged paths are not copied into global `/usr/local` directories. The separate OV8865 and OV5693 IPA tuning files are backed up before replacement. Rollback restores each saved file or removes the project copy if no prior file existed.

The earlier test's backups remain under the product backup directory, in a child directory named for the retired custom-kernel target. This is a historical backup path, not the new kernel target. Keep it until the host and any future deployment are checked; do not delete it as part of kernel-package cleanup. Rollback restores module files on disk but does not unload modules that are already running; reboot manually to return to the selected kernel's module state.

As of 5 October 2026, the host is running Ubuntu's HWE kernel with experimental DKMS camera modules. A later timer-only deployment saved the prior service state and unit contents under the same product backup directory; it leaves running camera processes untouched. The current deployment includes the pinned OV5693 tuning file and four-buffer loopback setting. The historical rollback backup directory may remain after the retired kernel packages were purged.

APT packages installed to build or run the stack remain installed after rollback. Removing those packages is a separate, optional cleanup and is not performed by this script.

The installer refuses to overwrite an existing product library directory. Roll back a previous or partial deployment before trying again. The product-specific `/etc/modprobe.d/sp7-v4l2loopback.conf` file is also backed up; its `max_buffers=4` option allows GStreamer to allocate the three buffers requested by its V4L2 sink. Rollback restores the prior file, but a currently loaded loopback module keeps its active parameters until that module is reloaded or the host is rebooted.

`scripts/deploy-services.sh` updates only the systemd units on an existing owned installation. It stores the prior contents and enablement state under the deployment's existing backup directory; `scripts/rollback.sh` restores those files and states. The service update does not stop a camera process already running in the current session.
