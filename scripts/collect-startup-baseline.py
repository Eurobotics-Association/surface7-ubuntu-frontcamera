#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Read-only boot/CPU baseline. Optional bounded CPU workload; no camera opens."""
import argparse
import json
import multiprocessing
from pathlib import Path
import re
import subprocess
import time


def output(*args):
    p = subprocess.run(args, capture_output=True, text=True, timeout=30)
    return p.stdout.strip() if p.returncode == 0 else {'error': p.stderr.strip()}


def read(path):
    try: return Path(path).read_text().strip()
    except OSError: return None


def workload(seconds):
    end = time.monotonic() + seconds
    value = 1
    while time.monotonic() < end:
        value = (value * 1664525 + 1013904223) & 0xffffffff


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True, help='Private local JSON, do not commit raw host inventory')
    p.add_argument('--cpu-load-seconds', type=int, default=0, choices=range(0, 31), metavar='0..30')
    args = p.parse_args()
    if args.output.exists(): raise SystemExit('Refusing to overwrite an earlier baseline')
    boot = output('journalctl', '-b', '-o', 'short-monotonic', '--no-pager')
    if not isinstance(boot, str): raise SystemExit(boot)
    events = []
    for line in boot.splitlines():
        match = re.match(r'\[\s*([0-9.]+)\]', line)
        if match and re.search(r'FW authentication failed|CSE boot_load failed|blocked for more|v4l_id|input:.*(?:Keyboard|Mouse)|Started.*Bluetooth', line, re.I):
            events.append({'seconds': float(match[1]), 'message': line})
    info = {'boot_id': read('/proc/sys/kernel/random/boot_id'),
            'uptime_before': read('/proc/uptime'), 'systemd_analyze': output('systemd-analyze', 'time'),
            'graphical_target': output('systemctl', 'show', 'graphical.target', '-p', 'ActiveEnterTimestampMonotonic'),
            'power_profile': output('powerprofilesctl', 'get'),
            'ac_online': {str(x): read(x) for x in Path('/sys/class/power_supply').glob('*/online')},
            'events': events, 'cpu_workload': 'one Python worker' if args.cpu_load_seconds else 'none',
            'cpu_samples': []}
    worker = None
    try:
        if args.cpu_load_seconds:
            worker = multiprocessing.Process(target=workload, args=(args.cpu_load_seconds,))
            worker.start()
        for _ in range(max(3, args.cpu_load_seconds)):
            temps = {str(x): read(x) for x in Path('/sys/class/thermal').glob('thermal_zone*/temp')}
            hot = any(int(x) > 95000 for x in temps.values() if x and x.lstrip('-').isdigit())
            info['cpu_samples'].append({'monotonic': time.monotonic(),
                'khz': {str(x): read(x) for x in Path('/sys/devices/system/cpu/cpufreq').glob('policy*/scaling_cur_freq')},
                'max_khz': {str(x): read(x) for x in Path('/sys/devices/system/cpu/cpufreq').glob('policy*/scaling_max_freq')},
                'temperatures_mC': temps})
            if hot and worker:
                worker.terminate(); worker.join(timeout=2)
                info['thermal_pause'] = 'Workload stopped above 95 C; wait three minutes before any further heavy work'
                break
            time.sleep(1)
    finally:
        if worker:
            worker.join(timeout=2)
            if worker.is_alive(): worker.terminate(); worker.join(timeout=2)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(info, indent=2) + '\n'); args.output.chmod(0o600)
    print(args.output)

if __name__ == '__main__': main()
