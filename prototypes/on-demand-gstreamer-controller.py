#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Start the GStreamer camera source only during V4L2 capture requests.

Prototype only. A separate v4l2loopback relay must already own the output
side of the virtual device and read frames from the named FIFO. This program
never configures modules, changes services, or writes image files.
"""

from __future__ import annotations

import argparse
import math
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
    parser.add_argument("--start-delay", type=float, default=1.2)
    parser.add_argument("--startup-timeout", type=float, default=20.0)
    parser.add_argument("--stall-timeout", type=float, default=10.0)
    args = parser.parse_args()

    if not math.isfinite(args.grace_seconds) or args.grace_seconds < 0:
        parser.error("--grace-seconds must be zero or greater")
    for option in ("startup_timeout", "stall_timeout"):
        if not math.isfinite(getattr(args, option)) or getattr(args, option) <= 0:
            parser.error(f"--{option.replace('_', '-')} must be finite and positive")
    if not math.isfinite(args.start_delay) or args.start_delay < 0:
        parser.error("--start-delay must be finite and nonnegative")
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
        "stdbuf", "-oL",
        args.gst_launch,
        "-m",
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
        "progressreport",
        "name=surface7_progress",
        "update-freq=1",
        "silent=true",
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
    try:
        process.wait(timeout=5.0)
    except subprocess.TimeoutExpired:
        log(f"{name} still blocked after SIGKILL; systemd must reap its control group")


class CaptureController:
    """One producer; observe events even while its previous process is stopping."""

    def __init__(self, args: argparse.Namespace, selector: selectors.BaseSelector):
        self.args = args
        self.selector = selector
        self.process: subprocess.Popen[bytes] | None = None
        self.active = False
        self.idle_deadline: float | None = None
        self.start_at = 0.0
        self.stopping = 0
        self.stop_deadline = 0.0
        self.started_at = 0.0
        self.last_progress: float | None = None
        self.output = bytearray()

    def usage(self, active: bool, now: float) -> None:
        if active != self.active:
            if active:
                self.start_at = now + self.args.start_delay
            log(f"capture_active={int(active)}")
        self.active = active
        if active:
            self.idle_deadline = None
        elif self.idle_deadline is None:
            # Repeated zero events must not postpone physical camera release.
            self.idle_deadline = now + self.args.grace_seconds

    def request_stop(self, now: float, reason: str) -> None:
        if self.process is None or self.stopping:
            return
        log(f"stopping source pid={self.process.pid} reason={reason}")
        signal_process_group(self.process, signal.SIGINT)
        self.stopping = 1
        self.stop_deadline = now + 1.0

    def read_output(self, now: float) -> None:
        assert self.process is not None and self.process.stdout is not None
        try:
            chunk = os.read(self.process.stdout.fileno(), 65536)
        except BlockingIOError:
            return
        if not chunk:
            self.selector.unregister(self.process.stdout)
            self.process.stdout.close()
            return
        self.output.extend(chunk)
        while b"\n" in self.output:
            line, _, rest = self.output.partition(b"\n")
            self.output = bytearray(rest)
            if b'from element "surface7_progress" (element): progress,' in line:
                if self.last_progress is None:
                    log(f"source buffers flowing after {now - self.started_at:.3f}s; "
                        "client capture still requires verification")
                self.last_progress = now
            elif b"(state-changed)" not in line and b"(stream-status)" not in line:
                log("gst: " + line.decode(errors="replace"))
        if len(self.output) > 65536:
            raise RuntimeError("GStreamer output line exceeded limit")

    def tick(self, now: float) -> None:
        if self.process is not None and self.process.poll() is not None:
            code = self.process.returncode
            unexpected_exit = not self.stopping
            if self.process.stdout is not None and not self.process.stdout.closed:
                self.selector.unregister(self.process.stdout)
                self.process.stdout.close()
            log(f"source exited code={code} stopping={bool(self.stopping)}")
            self.process = None
            self.output.clear()
            self.stopping = 0
            if unexpected_exit:
                raise RuntimeError(f"source exited unexpectedly ({code}); no automatic retry")

        if not self.active and self.idle_deadline is not None and now >= self.idle_deadline:
            self.request_stop(now, "capture idle")
            self.idle_deadline = None

        if self.process is not None:
            if self.stopping:
                if now >= self.stop_deadline:
                    if self.stopping == 1:
                        signal_process_group(self.process, signal.SIGTERM)
                        self.stopping = 2
                        self.stop_deadline = now + 1.0
                        log("source shutdown: SIGTERM")
                    elif self.stopping == 2:
                        signal_process_group(self.process, signal.SIGKILL)
                        self.stopping = 3
                        self.stop_deadline = now + 5.0
                        log("source shutdown: SIGKILL")
                    else:
                        raise RuntimeError("source did not exit after SIGKILL; refusing a second producer")
            elif self.last_progress is None:
                if now - self.started_at >= self.args.startup_timeout:
                    raise RuntimeError("startup timeout without buffer progress; no automatic retry")
            elif now - self.last_progress >= self.args.stall_timeout:
                raise RuntimeError("buffer progress stalled; no automatic retry")
            return

        if self.active and now >= self.start_at:
            log("starting source; failures require recovery, no automatic retry")
            self.process = subprocess.Popen(
                gst_command(self.args), stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, start_new_session=True, bufsize=0,
                env={**os.environ, "LC_ALL": "C"},
            )
            assert self.process.stdout is not None
            os.set_blocking(self.process.stdout.fileno(), False)
            self.selector.register(self.process.stdout, selectors.EVENT_READ, "source")
            self.started_at = now
            self.last_progress = None


def main() -> int:
    args = parse_args()
    watcher = Path(args.watcher)
    fifo = Path(args.fifo)
    if not watcher.is_file() or not os.access(watcher, os.X_OK):
        print(f"watcher is not executable: {watcher}", file=sys.stderr)
        return 2
    try:
        if not stat.S_ISFIFO(fifo.stat().st_mode):
            raise RuntimeError(f"refusing non-FIFO output: {fifo}")
    except (OSError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    signal.signal(signal.SIGINT, stop_requested)
    signal.signal(signal.SIGTERM, stop_requested)
    selector = selectors.DefaultSelector()
    controller = CaptureController(args, selector)
    watcher_process = None
    pending = bytearray()
    try:
        watcher_process = subprocess.Popen(
            [str(watcher), args.device], stdout=subprocess.PIPE,
            bufsize=0, start_new_session=True,
        )
        assert watcher_process.stdout is not None
        os.set_blocking(watcher_process.stdout.fileno(), False)
        selector.register(watcher_process.stdout, selectors.EVENT_READ, "watcher")
        log(f"watching {args.device}; physical source stopped until capture request")
        while running:
            if watcher_process.poll() is not None:
                raise RuntimeError(f"client event watcher exited: {watcher_process.returncode}")
            # Bounded wait notices child death and SIGTERM even with no V4L2 events.
            for key, _ in selector.select(0.1):
                if not running:
                    break
                now = time.monotonic()
                if key.data == "source":
                    controller.read_output(now)
                    continue
                try:
                    chunk = os.read(key.fd, 4096)
                except BlockingIOError:
                    continue
                if not chunk:
                    raise RuntimeError("client event watcher closed its output")
                pending.extend(chunk)
                # Drain all available state changes before deciding to start/stop.
                while b"\n" in pending:
                    line, _, rest = pending.partition(b"\n")
                    pending = bytearray(rest)
                    match = EVENT_RE.search(line)
                    if match:
                        controller.usage(match.group(1) == b"1", now)
                if len(pending) > 65536:
                    raise RuntimeError("watcher output line exceeded limit")
            if running:
                controller.tick(time.monotonic())
        return 0
    except (OSError, RuntimeError) as exc:
        log(f"controller error: {exc}")
        return 1
    finally:
        stop_child(controller.process, "GStreamer source")
        stop_child(watcher_process, "client event watcher")
        selector.close()


if __name__ == "__main__":
    raise SystemExit(main())
