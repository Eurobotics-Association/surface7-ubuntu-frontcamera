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
        -h|--help)
            cat <<'EOF'
Usage:
  ./scripts/install.sh --build-only
  ./scripts/install.sh --install

--build-only targets 6.19.8-surface-3 and makes no system changes.
--install requires that target kernel to be running and asks sudo for system deployment.
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

if [[ "$MODE" == install ]]; then
    if [[ $EUID -eq 0 ]]; then
        echo "Run as your desktop user; the installer will ask sudo when required." >&2
        exit 1
    fi
    if [[ "$(uname -r)" != "$SURFACE7_TARGET_KERNEL" ]]; then
        echo "Installation requires booting $SURFACE7_TARGET_KERNEL first." >&2
        exit 1
    fi
    "$ROOT/scripts/install-build-deps.sh"
    "$ROOT/scripts/check-system.sh"
    library_marker="$SURFACE7_LIBDIR/.surface7-ubuntu-frontcamera-owned"
    if [[ -e "$SURFACE7_LIBDIR" ]]; then
        echo "A product library directory already exists at $SURFACE7_LIBDIR." >&2
        echo "Run ./scripts/rollback.sh before deploying again." >&2
        [[ -f "$library_marker" ]] || echo "It is not marked as owned by this project; do not remove it manually." >&2
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
install -m 0644 "$ROOT/config/front-camera.env" "$upstream/ubuntu-deployment/front-camera.env"
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
echo "Creating the product ownership marker for safe rollback."
sudo -v
sudo install -d -m 0755 "$SURFACE7_LIBDIR"
sudo install -m 0644 "$ROOT/config/ownership-marker" \
    "$SURFACE7_LIBDIR/.surface7-ubuntu-frontcamera-owned"
"$upstream/install.sh"
printf '\nDeployment files installed. Reboot into %s before camera validation.\n' "$SURFACE7_TARGET_KERNEL"
printf 'Rollback command: %s/scripts/rollback.sh\n' "$ROOT"
