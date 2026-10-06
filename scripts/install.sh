#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
source "$ROOT/config/ubuntu.env"
MODE=""
for arg in "$@"; do
    case "$arg" in
        --build-only)
            [[ -z "$MODE" ]] || { echo "Choose one operation." >&2; exit 2; }
            MODE=build
            ;;
        --install)
            [[ -z "$MODE" ]] || { echo "Choose one operation." >&2; exit 2; }
            MODE=install
            ;;
        --deploy-services)
            [[ -z "$MODE" ]] || { echo "Choose one operation." >&2; exit 2; }
            MODE=deploy
            ;;
        -h|--help)
            cat <<'EOF'
Usage:
  ./scripts/install.sh --build-only
  ./scripts/install.sh --install
  ./scripts/install.sh --deploy-services

--build-only targets the currently running Ubuntu kernel and makes no system changes.
--install deploys a fresh DKMS stack or updates an existing project-owned deployment.
--deploy-services updates the on-demand camera services without rebuilding kernel modules.
Both install modes ask sudo when system changes are required.
EOF
            exit 0
            ;;
        *)
            echo "Unknown option: $arg" >&2
            exit 2
            ;;
    esac
done
[[ -n "$MODE" ]] || { echo "Choose --build-only or --install. See --help." >&2; exit 2; }
if [[ "$MODE" == build ]]; then
    "$ROOT/scripts/check-system.sh" --build-target
    "$ROOT/scripts/install-build-deps.sh"
    "$ROOT/scripts/check-system.sh" --build-target
else
    "$ROOT/scripts/check-system.sh"
fi

if [[ "$MODE" == deploy ]]; then
    "$ROOT/scripts/deploy-services.sh"
    exit $?
fi

if [[ "$MODE" == install ]]; then
    if [[ $EUID -eq 0 ]]; then
        echo "Run as your desktop user; the installer will ask sudo when required." >&2
        exit 1
    fi
    if [[ "$(uname -r)" != "$SURFACE7_TARGET_KERNEL" ]]; then
        echo "Installation requires selected kernel $SURFACE7_TARGET_KERNEL to be running." >&2
        exit 1
    fi
    "$ROOT/scripts/install-build-deps.sh"
    "$ROOT/scripts/check-system.sh"
    library_marker="$SURFACE7_LIBDIR/.surface7-ubuntu-frontcamera-owned"
    if [[ -e "$SURFACE7_LIBDIR" ]]; then
        if sudo test -f "$library_marker" &&
           [[ "$(sudo cat "$library_marker")" == "$(cat "$ROOT/config/ownership-marker")" ]] &&
           sudo test -f "$SURFACE7_LIBDIR/deployment-kernel" &&
           [[ "$(sudo cat "$SURFACE7_LIBDIR/deployment-kernel")" == "$(uname -r)" ]]; then
            echo "Updating the existing project-owned camera deployment without rebuilding kernel modules."
            "$ROOT/scripts/deploy-services.sh"
            exit $?
        fi
        echo "A product library directory already exists at $SURFACE7_LIBDIR, but its ownership or kernel record does not match." >&2
        echo "Refusing to overwrite it. Inspect it and use its matching rollback helper if needed." >&2
        exit 1
    fi
fi

tmp="$(mktemp -d -t surface7-frontcamera-build.XXXXXXXX)"
cleanup() { rm -rf "$tmp"; }
trap cleanup EXIT
upstream="$tmp/upstream"
cp -a "$ROOT/upstream/surface-pro-7-camera" "$upstream"
mkdir -p "$upstream/ubuntu-deployment"
install -m 0755 "$ROOT/scripts/surface7-front-camera" "$upstream/ubuntu-deployment/surface7-front-camera"
install -m 0644 "$ROOT/systemd/system/surface7-front-camera.service" "$upstream/ubuntu-deployment/surface7-front-camera.service"
install -m 0644 "$ROOT/systemd/system/surface7-front-camera.timer" "$upstream/ubuntu-deployment/surface7-front-camera.timer"
install -m 0644 "$ROOT/systemd/system/sp7-camera-boot.service" "$upstream/ubuntu-deployment/sp7-camera-boot.service"
install -m 0644 "$ROOT/config/front-camera.env" "$upstream/ubuntu-deployment/front-camera.env"
install -m 0644 "$ROOT/config/ipa/simple/ov5693.yaml" "$upstream/ubuntu-deployment/ov5693.yaml"
install -D -m 0755 "$ROOT/scripts/dkms-build-modules.sh" "$upstream/scripts/dkms-build-modules.sh"
install -D -m 0755 "$ROOT/scripts/dkms-pre-install.sh" "$upstream/scripts/dkms-pre-install.sh"
install -D -m 0644 "$ROOT/dkms/dkms.conf" "$upstream/dkms.conf"
install -D -m 0644 "$ROOT/config/ownership-marker" "$upstream/config/ownership-marker"
python3 "$ROOT/scripts/prepare-upstream-installer.py" "$upstream/install.sh"
chmod +x "$upstream/install.sh"
export SURFACE7_TARGET_KERNEL
SURFACE7_BUILD_JOBS="${SURFACE7_BUILD_JOBS:-2}"
if [[ ! "$SURFACE7_BUILD_JOBS" =~ ^[1-9][0-9]*$ ]]; then
    echo "SURFACE7_BUILD_JOBS must be a positive integer." >&2
    exit 2
fi
export SURFACE7_BUILD_JOBS
if [[ "$MODE" == build ]]; then
    "$upstream/install.sh" --build-only
    exit $?
fi
echo "Creating the product ownership marker and persistent rollback helper."
sudo -v
sudo install -d -m 0755 "$SURFACE7_LIBDIR/config" "$SURFACE7_LIBDIR/scripts"
sudo install -m 0644 "$ROOT/config/ubuntu.env" \
    "$SURFACE7_LIBDIR/config/ubuntu.env"
sudo install -m 0644 "$ROOT/config/ownership-marker" \
    "$SURFACE7_LIBDIR/config/ownership-marker"
sudo install -m 0755 "$ROOT/scripts/rollback.sh" \
    "$SURFACE7_LIBDIR/scripts/rollback.sh"
sudo install -m 0644 "$ROOT/config/ownership-marker" \
    "$SURFACE7_LIBDIR/.surface7-ubuntu-frontcamera-owned"
printf '%s\n' "$SURFACE7_TARGET_KERNEL" | sudo tee \
    "$SURFACE7_LIBDIR/deployment-kernel" >/dev/null
"$upstream/install.sh"
"$ROOT/scripts/deploy-services.sh"
printf '\nOn-demand camera services installed for %s.\n' "$SURFACE7_TARGET_KERNEL"
printf 'No reboot was issued. Roll back the previous camera service with: %s/scripts/rollback.sh --previous-deployment\n' "$SURFACE7_LIBDIR"
printf 'Full product rollback: %s/scripts/rollback.sh\n' "$SURFACE7_LIBDIR"
