# Rollback

Run from the repository as the desktop user:

~~~sh
./scripts/rollback.sh
~~~

The deployment writes an ownership marker before installing system files. Rollback checks that marker before removing the project library directory. It stops the camera services, restores the prior contents of any system file or kernel-module path it replaced, removes project files that did not exist before deployment, restores service enablement state, and refreshes depmod and ldconfig.

The installer records the exact deployed kernel in the product library directory. Rollback reads that record instead of assuming the currently booted kernel is the one used for deployment.

The libcamera build is staged first. Deployment copies only its product-specific library directory into `/usr/local/lib/surface7-ubuntu-frontcamera`; public development headers or other staged paths are not copied into global `/usr/local` directories. The only separate libcamera data file is the OV8865 tuning file, which is backed up before replacement.

The earlier test's backups are retained under `/var/lib/surface7-ubuntu-frontcamera/backup/6.19.8-surface-3`. This is a historical backup path for the legacy target, not the new kernel target. Keep it until the host and any future deployment are checked; do not delete it as part of kernel-package cleanup. Rollback restores module files on disk but does not unload modules that are already running; reboot manually to return to the selected kernel's module state.

As of 5 October 2026, the current Ubuntu HWE kernel is running with the experimental camera deployment installed. The legacy `6.19.8-surface-3` kernel and header packages were purged at the user's request. A later timer-only deployment saved the prior service state and unit contents under the same product backup directory; it leaves running camera processes untouched. The historical rollback backup directory may remain after those packages are purged.

APT packages installed to build or run the stack remain installed after rollback. Removing those packages is a separate, optional cleanup and is not performed by this script.

The installer refuses to overwrite an existing product library directory. Roll back a previous or partial deployment before trying again.

`scripts/deploy-services.sh` updates only the systemd units on an existing owned installation. It stores the prior contents and enablement state under the deployment's existing backup directory; `scripts/rollback.sh` restores those files and states. The service update does not stop a camera process already running in the current session.
