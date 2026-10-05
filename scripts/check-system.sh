#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
set -u
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
source "$ROOT/config/ubuntu.env"
BUILD_TARGET=0
for arg in "$@"; do
    case "$arg" in
        --build-target) BUILD_TARGET=1 ;;
        -h|--help) printf 'Usage: %s [--build-target]\n' "$0"; exit 0 ;;
        *) printf 'Unknown option: %s\n' "$arg" >&2; exit 2 ;;
    esac
done
pass=0
warn=0
fail=0
ok() { printf 'PASS  %s\n' "$*"; pass=$((pass + 1)); }
note() { printf 'INFO  %s\n' "$*"; }
bad() { printf 'FAIL  %s\n' "$*"; fail=$((fail + 1)); }
soft() { printf 'WARN  %s\n' "$*"; warn=$((warn + 1)); }
printf 'Surface 7 Ubuntu front-camera preflight\n========================================\n'
product="$(cat /sys/class/dmi/id/product_name 2>/dev/null || true)"
printf 'Device: %s\n' "${product:-unknown}"
case "$product" in
    *"Surface Pro 7+"*) bad "Surface Pro 7+ is not supported" ;;
    *"Surface Pro 7"*) ok "Surface Pro 7 detected" ;;
    *) bad "Expected Microsoft Surface Pro 7" ;;
esac
source /etc/os-release
printf 'OS: %s\n' "${PRETTY_NAME:-unknown}"
if [[ "${ID:-}" == "$SURFACE7_OS_ID" && "${VERSION_ID:-}" == "$SURFACE7_OS_VERSION" ]]; then
    ok "Ubuntu 24.04 detected"
else
    bad "Expected Ubuntu 24.04"
fi
arch="$(uname -m)"
printf 'Architecture: %s\n' "$arch"
[[ "$arch" == "$SURFACE7_ARCH" ]] && ok "x86_64" || bad "Expected x86_64"
running="$(uname -r)"
printf 'Running kernel: %s\n' "$running"
if [[ "$running" == "$SURFACE7_TARGET_KERNEL" ]]; then
    ok "Selected Ubuntu kernel is running"
elif [[ "$BUILD_TARGET" -eq 1 ]]; then
    soft "Build target differs from running kernel; build-only will use $SURFACE7_TARGET_KERNEL"
else
    bad "Selected kernel $SURFACE7_TARGET_KERNEL is not running"
fi
if [[ -f "/lib/modules/$SURFACE7_TARGET_KERNEL/build/Makefile" ]]; then
    ok "Target kernel build tree exists"
else
    soft "Missing target headers: /lib/modules/$SURFACE7_TARGET_KERNEL/build (the package helper can install them)"
fi
if ! command -v lspci >/dev/null 2>&1; then
    soft "lspci is missing; the Ubuntu package helper can install pciutils"
elif lspci -nn 2>/dev/null | grep -qi '8086:8a19'; then
    ok "Intel IPU4P controller 8086:8a19 detected"
else
    bad "Intel IPU4P controller 8086:8a19 not detected"
fi
if command -v mokutil >/dev/null 2>&1; then
    sb="$(mokutil --sb-state 2>&1 || true)"
    if grep -qi 'SecureBoot disabled' <<<"$sb"; then
        ok "Secure Boot is disabled"
    elif grep -qi 'SecureBoot enabled' <<<"$sb"; then
        bad "Secure Boot is enabled; unsigned modules will not load"
    else
        soft "Could not determine Secure Boot state: $sb"
    fi
else
    soft "mokutil is missing; Secure Boot state is unknown"
fi
printf '\nBuild tools:\n'
for cmd in git git-lfs gcc g++ make cmake meson ninja pkg-config python3 modinfo readelf ldd sha256sum; do
    if command -v "$cmd" >/dev/null 2>&1; then ok "$cmd"; else soft "$cmd is not installed"; fi
done
if python3 -c 'import jinja2, ply, yaml' >/dev/null 2>&1; then
    ok "Python build modules"
else
    soft "Python modules jinja2, ply and/or yaml are missing"
fi
printf '\nPASS: %s  WARN: %s  FAIL: %s\n' "$pass" "$warn" "$fail"
if [[ "$fail" -ne 0 ]]; then exit 1; fi
if [[ "$warn" -ne 0 ]]; then note "Preflight passed with warnings; install missing build dependencies before compiling."; fi
