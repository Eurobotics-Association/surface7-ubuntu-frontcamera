#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
set -euo pipefail
REPOSITORY="https://github.com/Eurobotics-Association/surface7-ubuntu-frontcamera.git"
REF="${SURFACE7_GITHUB_REF:-main}"
SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" 2>/dev/null && pwd || true)"
if [[ -n "$SCRIPT_DIR" && -x "$SCRIPT_DIR/install.sh" ]]; then
    exec "$SCRIPT_DIR/install.sh" "$@"
fi
command -v git >/dev/null 2>&1 || {
    echo "git is required to fetch this installer from GitHub." >&2
    exit 1
}
TMP="$(mktemp -d -t surface7-frontcamera.XXXXXXXX)"
trap 'rm -rf "$TMP"' EXIT
git clone --depth 1 --branch "$REF" "$REPOSITORY" "$TMP/repository"
"$TMP/repository/scripts/install.sh" "$@"
