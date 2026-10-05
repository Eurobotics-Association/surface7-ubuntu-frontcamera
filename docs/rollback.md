# Rollback

Run from the repository as the desktop user:

~~~sh
./scripts/rollback.sh
~~~

The deployment writes an ownership marker before installing system files. Rollback checks that marker before removing the project library directory. It stops the camera services, restores the prior contents of any system file or kernel-module path it replaced, removes project files that did not exist before deployment, restores service enablement state, and refreshes depmod and ldconfig.

The earlier test's backups are retained under `/var/lib/surface7-ubuntu-frontcamera/backup/6.19.8-surface-3`. This is a historical backup path for the legacy target, not the new kernel target. Keep it until the host and any future deployment are checked; do not delete it as part of kernel-package cleanup. Rollback restores module files on disk but does not unload modules that are already running; reboot manually to return to the selected kernel's module state.

As of 5 October 2026, the camera deployment has been rolled back and the host is running its original Ubuntu HWE kernel. The legacy `6.19.8-surface-3` kernel and headers are being removed separately at the user's request. The rollback backup directory may remain after those packages are purged.

APT packages installed to build or run the stack remain installed after rollback. Removing those packages is a separate, optional cleanup and is not performed by this script.

The installer refuses to overwrite an existing product library directory. Roll back a previous or partial deployment before trying again.
