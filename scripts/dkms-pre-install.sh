#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
set -euo pipefail
KVER="${1:-}"
[[ "$KVER" =~ ^[A-Za-z0-9._+-]+$ ]] || exit 2
backup="/var/lib/surface7-ubuntu-frontcamera/backup/$KVER"
module_dir="/lib/modules/$KVER/updates/dkms"
modules=(ov8865 dw9719 ipu-bridge intel-ipu4p intel-ipu4p-isys intel-ipu4p-psys intel-ipu4p-isys-csslib intel-ipu4p-psys-csslib v4l2loopback)

for module in "${modules[@]}"; do
    source="$module_dir/$module.ko"
    [[ -e "$source" || -L "$source" ]] || continue
    destination="$backup$source"
    install -d -m 0755 "$(dirname -- "$destination")"
    if [[ ! -e "$destination" && ! -L "$destination" ]]; then
        cp -a -- "$source" "$destination"
    fi
done
