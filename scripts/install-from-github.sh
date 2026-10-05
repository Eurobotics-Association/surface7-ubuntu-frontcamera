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
KEEP_TMP=0
cleanup() {
    if [[ "$KEEP_TMP" -eq 0 ]]; then
        rm -rf -- "$TMP"
    fi
}
trap cleanup EXIT
git clone --depth 1 --branch "$REF" "$REPOSITORY" "$TMP/repository"
if "$TMP/repository/scripts/install.sh" "$@"; then
    exit 0
else
    status=$?
    KEEP_TMP=1
    echo "Installation failed; source checkout retained at $TMP/repository." >&2
    echo "If deployment created its ownership marker, roll back with:" >&2
    echo "  $TMP/repository/scripts/rollback.sh" >&2
    exit "$status"
fi
