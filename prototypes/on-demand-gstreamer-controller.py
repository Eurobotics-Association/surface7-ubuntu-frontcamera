#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Start the GStreamer camera source only during V4L2 capture requests.

Prototype only. A separate v4l2loopback relay must already own the output
side of the virtual device and read frames from the named FIFO. This program
never configures modules, changes services, or writes image files.
"""

from __future__ import annotations

import argparse
import os
import re
import selectors
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path


EVENT_RE = re.compile(rb"capture_active=([01])")
SOURCE_MODES = {
    "source-width": "SOURCE_WIDTH",
    "source-height": "SOURCE_HEIGHT",
    "source-fps-num": "SOURCE_FPS_NUM",
    "source-fps-den": "SOURCE_FPS_DEN",
    "output-width": "OUTPUT_WIDTH",
    "output-height": "OUTPUT_HEIGHT",
    "output-fps-num": "OUTPUT_FPS_NUM",
    "output-fps-den": "OUTPUT_FPS_DEN",
}

running = True


def stop_requested(_signum: int, _frame: object) -> None:
    global running
    running = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watcher", required=True, help="compiled client-watch helper")
    parser.add_argument("--device", required=True, help="v4l2loopback node, such as /dev/video83")
    parser.add_argument("--fifo", required=True, help="existing named FIFO consumed by the idle relay")
    parser.add_argument("--camera-name", required=True, help="libcamera camera-name from front-camera config")
    for option, env_name in SOURCE_MODES.items():
        parser.add_argument("--" + option, required=True, type=int, metavar=env_name)
    parser.add_argument("--grace-seconds", type=float, default=2.0)
    parser.add_argument("--gst-launch", default="gst-launch-1.0")
    args = parser.parse_args()

    if args.grace_seconds < 0:
        parser.error("--grace-seconds must be zero or greater")
    for option in SOURCE_MODES:
        if getattr(args, option.replace("-", "_")) <= 0:
            parser.error(f"--{option} must be greater than zero")
    return args


def log(message: str) -> None:
    print(f"{time.monotonic():.3f} {message}", flush=True)


def gst_command(args: argparse.Namespace) -> list[str]:
    source_caps = (
        f"video/x-raw,width={args.source_width},height={args.source_height},"
        f"framerate={args.source_fps_num}/{args.source_fps_den}"
    )
    output_caps = (
        f"video/x-raw,format=YUY2,width={args.output_width},"
        f"height={args.output_height},"
        f"framerate={args.output_fps_num}/{args.output_fps_den}"
    )
    return [
        args.gst_launch,
        "-e",
        "libcamerasrc",
        f"camera-name={args.camera_name}",
        "!",
        source_caps,
        "!",
        "queue",
        "max-size-buffers=4",
        "max-size-bytes=0",
        "max-size-time=0",
        "leaky=downstream",
        "!",
        "videoconvert",
        "!",
        "videoscale",
        "!",
        output_caps,
        "!",
        "filesink",
        f"location={args.fifo}",
        "sync=false",
    ]


def signal_process_group(process: subprocess.Popen[bytes], sig: int) -> None:
    try:
        os.killpg(process.pid, sig)
    except ProcessLookupError:
        pass


def stop_child(process: subprocess.Popen[bytes] | None, name: str) -> None:
    if process is None or process.poll() is not None:
        return
    log(f"stopping {name} pid={process.pid}")
    signal_process_group(process, signal.SIGINT)
    try:
        process.wait(timeout=3.0)
        return
    except subprocess.TimeoutExpired:
        log(f"{name} did not exit after SIGINT; sending SIGTERM")
    signal_process_group(process, signal.SIGTERM)
    try:
        process.wait(timeout=2.0)
        return
    except subprocess.TimeoutExpired:
        log(f"{name} did not exit after SIGTERM; sending SIGKILL")
    signal_process_group(process, signal.SIGKILL)
    process.wait()


def main() -> int:
    args = parse_args()
    watcher = Path(args.watcher)
    fifo = Path(args.fifo)

    if not watcher.is_file() or not os.access(watcher, os.X_OK):
        print(f"watcher is not an executable file: {watcher}", file=sys.stderr)
        return 2
    try:
        fifo_mode = fifo.stat().st_mode
    except OSError as exc:
        print(f"cannot inspect FIFO {fifo}: {exc}", file=sys.stderr)
        return 2
    if not stat.S_ISFIFO(fifo_mode):
        print(f"refusing non-FIFO output path: {fifo}", file=sys.stderr)
        return 2

    signal.signal(signal.SIGINT, stop_requested)
    signal.signal(signal.SIGTERM, stop_requested)

    watcher_process: subprocess.Popen[bytes] | None = None
    gst_process: subprocess.Popen[bytes] | None = None
    selector = selectors.DefaultSelector()
    pending = bytearray()
    capture_active = False
    stop_deadline: float | None = None

    try:
        watcher_process = subprocess.Popen(
            [str(watcher), args.device],
            stdout=subprocess.PIPE,
            stderr=None,
            bufsize=0,
            start_new_session=True,
        )
        assert watcher_process.stdout is not None
        os.set_blocking(watcher_process.stdout.fileno(), False)
        selector.register(watcher_process.stdout, selectors.EVENT_READ)
        log(f"watching {args.device}; media source remains stopped until capture starts")

        while running:
            if watcher_process.poll() is not None:
                raise RuntimeError(f"client event watcher exited with {watcher_process.returncode}")

            if gst_process is not None and gst_process.poll() is not None:
                log(f"GStreamer source exited with {gst_process.returncode}")
                gst_process = None

            timeout = None
            if stop_deadline is not None:
                timeout = max(0.0, stop_deadline - time.monotonic())
            ready = selector.select(timeout)

            if not ready and stop_deadline is not None:
                if not capture_active and time.monotonic() >= stop_deadline:
                    stop_child(gst_process, "GStreamer source")
                    gst_process = None
                    stop_deadline = None
                    log("capture idle; GStreamer source stopped")
                continue

            for key, _mask in ready:
                try:
                    chunk = os.read(key.fd, 4096)
                except BlockingIOError:
                    continue
                if not chunk:
                    raise RuntimeError("client event watcher closed its output")
                pending.extend(chunk)

                while b"\n" in pending:
                    line, _, remainder = pending.partition(b"\n")
                    pending = bytearray(remainder)
                    match = EVENT_RE.search(line)
                    if match is None:
                        continue

                    capture_active = match.group(1) == b"1"
                    if capture_active:
                        stop_deadline = None
                        if gst_process is None or gst_process.poll() is not None:
                            command = gst_command(args)
                            log("capture active; starting GStreamer source")
                            gst_process = subprocess.Popen(
                                command,
                                stdin=subprocess.DEVNULL,
                                start_new_session=True,
                            )
                            log(f"GStreamer source pid={gst_process.pid}")
                    elif gst_process is not None:
                        stop_deadline = time.monotonic() + args.grace_seconds
                        log(f"capture inactive; stop grace={args.grace_seconds:.1f}s")

        return 0
    except (OSError, RuntimeError) as exc:
        log(f"controller error: {exc}")
        return 1
    finally:
        stop_child(gst_process, "GStreamer source")
        stop_child(watcher_process, "client event watcher")
        selector.close()


if __name__ == "__main__":
    raise SystemExit(main())
