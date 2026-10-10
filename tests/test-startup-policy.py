#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Hardware-free transaction and activation regression tests."""
import importlib.machinery
import importlib.util
import hashlib
import itertools
import json
import os
from pathlib import Path
import selectors
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[1]

def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(ROOT / path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module

policy = load('policy', 'scripts/startup-policy.py')
hotfix = load('hotfix', 'scripts/deploy-psys-gate.py')
control = load('manual', 'scripts/surface7-camera')
controller = load('controller', 'prototypes/on-demand-gstreamer-controller.py')


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.p = policy.Policy(ROOT, self.root)
        self.file = self.p.path('/etc/systemd/system/surface7-front-camera-on-demand.service')
        self.file.parent.mkdir(parents=True)
        self.file.write_text('old unit')
        self.file.chmod(0o640)
        self.p.path('/proc').mkdir()
        self.p.path('/proc/modules').write_text('intel_ipu4p loaded\n')
        self.p.add('/etc/systemd/system/surface7-front-camera-on-demand.service', b'new unit')
        self.p.add('/etc/new-policy', b'guard')
        for spec in self.p.desired.values():
            spec.update(uid=os.getuid(), gid=os.getgid())
        self.states = {u: {'ActiveState': 'active', 'UnitFileState': 'enabled'} for u in policy.UNITS}
        self.image = self.p.path('/boot/initrd.img-test')
        self.image.parent.mkdir()
        self.image.write_bytes(b'original initrd bytes')
        self.m = self.p.snapshot(self.states, ['/boot/initrd.img-test'])

    def tearDown(self):
        self.tmp.cleanup()

    def apply(self):
        for path, spec in self.p.desired.items():
            self.p.write(path, spec, self.p.payload[path])

    def test_restore_exact_files_modes_absence_and_initrd(self):
        self.apply()
        self.m['after']['/boot/initrd.img-test'] = policy.regular(b'new initrd')
        self.m['after']['/boot/initrd.img-test'].update(uid=os.getuid(), gid=os.getgid())
        self.p.write('/boot/initrd.img-test', self.m['after']['/boot/initrd.img-test'], b'new initrd')
        self.p.restore_files(self.m)
        self.assertEqual(self.file.read_text(), 'old unit')
        self.assertEqual(self.file.stat().st_mode & 0o777, 0o640)
        self.assertFalse(self.p.path('/etc/new-policy').exists())
        self.assertEqual(self.image.read_bytes(), b'original initrd bytes')
        self.assertEqual(set(self.m['units']), set(policy.UNITS))
        self.assertIn('intel_ipu4p', self.m['modules'])

    def test_partial_deployment_restores_before_and_after_mix(self):
        path = '/etc/new-policy'
        self.p.write(path, self.p.desired[path], self.p.payload[path])
        self.p.restore_files(self.m)
        self.assertFalse(self.p.path(path).exists())
        self.assertEqual(self.file.read_text(), 'old unit')

    def test_refuses_later_unrelated_changes_before_any_restore(self):
        self.apply()
        self.file.write_text('user edit after deployment')
        with self.assertRaisesRegex(RuntimeError, 'later changes'):
            self.p.restore_files(self.m)
        self.assertTrue(self.p.path('/etc/new-policy').exists())

    def test_refuses_corrupt_backup(self):
        saved = self.p.backup / 'files/boot/initrd.img-test'
        saved.write_bytes(b'corrupted')
        with self.assertRaisesRegex(RuntimeError, 'Backup damaged'):
            self.p.restore_files(self.m)

    def test_initramfs_hook_places_guard_in_early_boot_image(self):
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp)
            source = Path('/etc/modprobe.d/surface7-camera-manual.conf')
            # Exercise the real hook in an isolated DESTDIR with a fixture by
            # temporarily replacing its source path in the temp copy.
            fixture = dest / 'source.conf'
            fixture.write_text('install intel_ipu4p /bin/false\n')
            hook = dest / 'hook'
            hook.write_text((ROOT / 'config/initramfs-tools/hooks/surface7-camera-manual').read_text().replace("source=" + str(source), "source=" + str(fixture)))
            hook.chmod(0o755)
            image = dest / 'image'
            subprocess.run([str(hook)], env={**os.environ, 'DESTDIR': str(image)}, check=True)
            self.assertEqual((image / 'etc/modprobe.d/surface7-camera-manual.conf').read_text(), fixture.read_text())

    def test_never_overwrites_snapshot(self):
        with self.assertRaises(FileExistsError):
            self.p.snapshot(self.states, [])

    def test_mask_symlink_restored(self):
        path = '/etc/systemd/system/legacy.service'
        self.p.write(path, {'kind': 'link', 'target': '/dev/null'})
        self.assertEqual(policy.record(self.p.path(path)), {'kind': 'link', 'target': '/dev/null'})
        self.p.write(path, {'kind': 'absent'})
        self.assertFalse(self.p.path(path).is_symlink())

    def test_resume_includes_both_new_services(self):
        with patch.object(policy, 'run') as run:
            policy.restore_units(self.states, True)
        calls = [x.args for x in run.call_args_list]
        for u in policy.NEW:
            self.assertIn(('systemctl', 'enable', u), calls)
            self.assertIn(('systemctl', 'start', u), calls)

    def test_safe_restore_does_not_start_services(self):
        with patch.object(policy, 'run') as run:
            policy.restore_units(self.states, False)
        self.assertFalse(any(c.args[1:2] == ('start',) for c in run.call_args_list))


class PsysGateSnapshotTests(unittest.TestCase):
    def test_hotfix_restores_original_and_refuses_later_edits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / 'base'
            base.mkdir()
            (base / '.deployed').touch()
            target = root / 'surface7-camera'
            source = root / 'replacement'
            target.write_bytes(b'original reviewed helper')
            target.chmod(0o755)
            source.write_bytes(b'PSYS readiness gate')
            with patch.object(hotfix, 'BACKUP', root / 'backup'), \
                 patch.object(hotfix, 'BASE', base), \
                 patch.object(hotfix, 'TARGET', target), \
                 patch.object(hotfix, 'OLD_SHA256', hashlib.sha256(target.read_bytes()).hexdigest()), \
                 patch.object(hotfix.os, 'chown'):
                hotfix.deploy(source)
                self.assertEqual(target.read_bytes(), source.read_bytes())
                target.write_bytes(b'unrelated later edit')
                with self.assertRaisesRegex(RuntimeError, 'later camera helper edit'):
                    hotfix.rollback(False)
                target.write_bytes(source.read_bytes())
                hotfix.rollback(False)
                self.assertEqual(target.read_bytes(), b'original reviewed helper')
                self.assertTrue((root / 'backup/.restored').exists())


class ActivationTests(unittest.TestCase):
    def test_no_terminal_refused_before_system_calls(self):
        with patch.object(control.sys.stdin, 'isatty', return_value=False), patch.object(control, 'command') as cmd:
            with self.assertRaisesRegex(RuntimeError, 'interactive terminal'):
                control.require_login()
            cmd.assert_not_called()

    def test_greeter_is_not_user_login(self):
        with patch.object(control.sys.stdin, 'isatty', return_value=True), \
             patch.object(control.subprocess, 'run', return_value=types.SimpleNamespace(stdout='running\n')), \
             patch.dict(os.environ, {'SUDO_UID': '1000'}), \
             patch.object(control, 'command', side_effect=['1 1000 greeter', 'User=1000\nClass=greeter\nActive=yes\nType=wayland']):
            with self.assertRaisesRegex(RuntimeError, 'No active interactive'):
                control.require_login()

    def test_booting_refused_even_with_terminal(self):
        with patch.object(control.sys.stdin, 'isatty', return_value=True), \
             patch.object(control.subprocess, 'run', return_value=types.SimpleNamespace(stdout='starting\n')):
            with self.assertRaisesRegex(RuntimeError, 'boot has not completed'):
                control.require_login()

    def test_failure_latches_initialization_before_second_modprobe(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(control, 'RUN', Path(tmp)), \
             patch.object(control, 'command', side_effect=RuntimeError('authentication failure')) as cmd:
            (Path(tmp) / 'requested').touch()
            with self.assertRaisesRegex(RuntimeError, 'authentication failure'):
                control.initialize()
            with self.assertRaises(FileExistsError):
                control.initialize()
            self.assertEqual(cmd.call_count, 1)

    def test_initialization_requires_request(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(control, 'RUN', Path(tmp)), \
             patch.object(control, 'command') as cmd:
            with self.assertRaises(RuntimeError): control.initialize()
            cmd.assert_not_called()

    def test_psys_authentication_failure_never_loads_isys(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'requested').touch()
            mmu = root / 'mmu-control'
            mmu.write_text('auto\n')
            ticks = itertools.count()
            with patch.object(control, 'RUN', root), \
                 patch.object(control, 'MMU1_CONTROL', mmu), \
                 patch.object(control, 'PSYS_DRIVER', root / 'missing-driver'), \
                 patch.object(control, 'command') as cmd, \
                 patch.object(control.time, 'monotonic', side_effect=lambda: next(ticks)), \
                 patch.object(control.time, 'sleep'):
                with self.assertRaisesRegex(RuntimeError, 'ISYS left unloaded'):
                    control.initialize()
            loaded = [call.args[2] for call in cmd.call_args_list]
            self.assertIn('intel_ipu4p_psys', loaded)
            self.assertNotIn('intel_ipu4p_isys', loaded)
            self.assertNotIn('v4l2loopback', loaded)


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.args = types.SimpleNamespace(start_delay=1.2, grace_seconds=2,
                                         startup_timeout=20, stall_timeout=10)
        self.sel = selectors.DefaultSelector()
        self.c = controller.CaptureController(self.args, self.sel)
    def tearDown(self): self.sel.close()

    def test_short_probe_does_not_start_capture(self):
        self.c.usage(True, 0)
        with patch.object(controller.subprocess, 'Popen') as popen:
            self.c.tick(1)
            self.c.usage(False, 1.01)
            self.c.tick(2)
            popen.assert_not_called()

    def test_source_failure_exits_instead_of_retry(self):
        child = Mock(returncode=1, stdout=None)
        child.poll.return_value = 1
        self.c.process = child
        with self.assertRaisesRegex(RuntimeError, 'no automatic retry'):
            self.c.tick(1)

    def test_startup_timeout_and_stall_are_fatal(self):
        child = Mock()
        child.poll.return_value = None
        self.c.process = child
        self.c.active = True
        with self.assertRaisesRegex(RuntimeError, 'startup timeout'):
            self.c.tick(21)
        self.c.last_progress = 20
        with self.assertRaisesRegex(RuntimeError, 'progress stalled'):
            self.c.tick(31)

    def test_repeated_idle_does_not_delay_shutdown(self):
        self.c.usage(False, 1)
        self.c.usage(False, 2)
        self.assertEqual(self.c.idle_deadline, 3)

    @unittest.skipUnless(__import__('shutil').which('gst-launch-1.0'), 'GStreamer not installed')
    def test_progress_is_visible_before_pipeline_exits(self):
        # Synthetic buffers to fakesink only: no physical or virtual camera access.
        child = subprocess.Popen(['stdbuf', '-oL', 'gst-launch-1.0', '-m', 'videotestsrc',
                                  'is-live=true', '!', 'progressreport', 'name=surface7_progress',
                                  'update-freq=1', 'silent=true', '!', 'fakesink'],
                                 stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            import time
            os.set_blocking(child.stdout.fileno(), False)
            with selectors.DefaultSelector() as sel:
                sel.register(child.stdout, selectors.EVENT_READ)
                deadline = time.monotonic() + 6
                output = b''
                while time.monotonic() < deadline:
                    for key, _ in sel.select(0.2): output += os.read(key.fd, 65536)
                    if b'from element "surface7_progress" (element): progress,' in output: break
                self.assertIn(b'from element "surface7_progress" (element): progress,', output)
                self.assertIsNone(child.poll())
        finally:
            child.terminate(); child.wait(timeout=5); child.stdout.close()


if __name__ == '__main__': unittest.main()
