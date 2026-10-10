#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Validate startup graph offline; never starts host services or opens cameras."""
import importlib.util
from pathlib import Path
import re
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('policy', root / 'scripts/startup-policy.py')
p = importlib.util.module_from_spec(spec); spec.loader.exec_module(p)
with tempfile.TemporaryDirectory() as tmp:
    dest = Path(tmp)
    paths = []
    for unit in p.UNITS:
        text = (root / 'systemd/system' / unit).read_text()
        assert '[Install]' not in text, unit
        assert not re.search(r'^(WantedBy|RequiredBy|OnBootSec|OnStartupSec)=', text, re.M), unit
        if unit in p.NEW:
            assert 'ConditionPathExists=/run/surface7-camera/requested' in text, unit
            assert 'ConditionPathExists=!/run/surface7-camera/failed' in text, unit
            assert 'Restart=no' in text, unit
            assert 'sp7-camera-boot.service' not in text, unit
        else:
            assert 'RefuseManualStart=yes' in text, unit
        # Verify syntax/order using real systemd parser. Substitute only commands
        # unavailable before deployment; all dependencies/conditions stay intact.
        text = text.replace('/usr/local/sbin/surface7-camera', '/usr/bin/true')
        text = text.replace('/usr/local/libexec/surface7-v4l2-idle-relay', '/usr/bin/true')
        if unit.endswith('.timer'):
            # Retired file intentionally has no timer trigger; deployment masks it.
            continue
        path = dest / unit; path.write_text(text); paths.append(str(path))
    subprocess.run(['systemd-analyze', 'verify', '--man=no', *paths], check=True)
print('PASS: no automatic activation; guarded dependency graph verified offline')
