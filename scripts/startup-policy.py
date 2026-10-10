#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Transactional explicit-start deployment. CLI has no alternate filesystem root."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import sys

LIB = '/usr/local/lib/surface7-ubuntu-frontcamera'
BACKUP = '/var/lib/surface7-ubuntu-frontcamera/backup/explicit-start-v1'
OLD = ['sp7-camera-boot.service', 'surface7-front-camera.service', 'surface7-front-camera.timer']
NEW = ['surface7-camera-init.service', 'surface7-front-camera-idle-relay.service',
       'surface7-front-camera-on-demand.service']
UNITS = OLD + NEW
MODULES = ['dw9719', 'ov5693', 'ov8865', 'ov7251', 'ipu_bridge', 'intel_ipu4p',
           'intel_ipu4p_isys', 'intel_ipu4p_psys', 'intel_ipu4p_isys_csslib',
           'intel_ipu4p_psys_csslib', 'v4l2loopback']


def run(*args, timeout=180):
    child = subprocess.Popen(args, text=True, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, start_new_session=True)
    try:
        out, err = child.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(child.pid, signal.SIGKILL)
        raise RuntimeError(f'{args[0]} exceeded {timeout}s; refusing to continue')
    if child.returncode:
        raise RuntimeError(f'{" ".join(args)} failed: {err.strip() or out.strip()}')
    return out.strip()


def record(path):
    if path.is_symlink():
        return {'kind': 'link', 'target': os.readlink(path)}
    if not path.exists():
        return {'kind': 'absent'}
    if not path.is_file():
        raise RuntimeError(f'Refusing non-file: {path}')
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return {'kind': 'file', 'sha256': h.hexdigest(), 'mode': stat.S_IMODE(path.stat().st_mode),
            'uid': path.stat().st_uid, 'gid': path.stat().st_gid}


def regular(data, mode=0o644):
    return {'kind': 'file', 'sha256': hashlib.sha256(data).hexdigest(), 'mode': mode,
            'uid': 0, 'gid': 0}


class Policy:
    def __init__(self, source, root=Path('/')):
        self.source, self.root = Path(source), Path(root)
        self.backup = self.path(BACKUP)
        self.desired = {}
        self.payload = {}

    def path(self, path):
        return self.root / path.lstrip('/')

    def add(self, path, data, mode=0o644):
        self.payload[path] = data
        self.desired[path] = regular(data, mode)

    def prepare(self, built):
        for unit in OLD:
            self.desired['/etc/systemd/system/' + unit] = {'kind': 'link', 'target': '/dev/null'}
        for unit in NEW:
            self.add('/etc/systemd/system/' + unit,
                     (self.source / 'systemd/system' / unit).read_bytes())
        self.add('/etc/modules-load.d/sp7-v4l2loopback.conf',
                 b'# Surface7 managed: no camera modules at boot\n')
        self.add('/etc/modprobe.d/surface7-camera-manual.conf',
                 (self.source / 'config/modprobe.d/surface7-camera-manual.conf').read_bytes())
        self.add('/etc/initramfs-tools/hooks/surface7-camera-manual',
                 (self.source / 'config/initramfs-tools/hooks/surface7-camera-manual').read_bytes(), 0o755)
        # Retire direct callers too. Never leave a second physical loader available.
        self.add('/usr/local/sbin/sp7-camera-boot',
                 b'#!/bin/sh\n# Surface7 managed: retired boot loader\necho "Use sudo surface7-camera start after login" >&2\nexit 1\n', 0o755)
        for src, dst, mode in [
            ('scripts/surface7-camera', '/usr/local/sbin/surface7-camera', 0o755),
            ('prototypes/on-demand-gstreamer-controller.py', '/usr/local/libexec/surface7-front-camera-controller.py', 0o755),
            ('scripts/rollback.sh', LIB + '/scripts/rollback.sh', 0o755),
            ('scripts/startup-policy.py', LIB + '/scripts/startup-policy.py', 0o755),
            ('config/ubuntu.env', LIB + '/config/ubuntu.env', 0o644),
            ('config/ownership-marker', LIB + '/config/ownership-marker', 0o644),
            ('config/front-camera.env', '/etc/default/surface7-front-camera', 0o644),
        ]:
            self.add(dst, (self.source / src).read_bytes(), mode)
        for name in ('surface7-v4l2-idle-relay', 'surface7-v4l2-client-watch'):
            self.add('/usr/local/libexec/' + name, (Path(built) / name).read_bytes(), 0o755)
        rules = self.path('/usr/lib/udev/rules.d/60-persistent-v4l.rules').read_bytes()
        anchor = b'IMPORT{program}="v4l_id $devnode"'
        if rules.count(anchor) != 1 or b'LABEL="persistent_v4l_end"' not in rules:
            raise RuntimeError('Unreviewed Ubuntu V4L rule structure; refusing override')
        rules = b'# Surface7 managed: preserve distro rules except IPU4 physical-node probes\n' + rules.replace(
            anchor, b'KERNELS=="intel-ipu4-mmu[01]", GOTO="persistent_v4l_end"\n' + anchor)
        self.add('/etc/udev/rules.d/60-persistent-v4l.rules', rules)
        self.add('/etc/udev/rules.d/71-surface7-camera-private.rules',
                 b'# Surface7 managed: apps use the virtual node; root libcamerasrc owns physical nodes\n'
                 b'SUBSYSTEM=="video4linux", KERNELS=="intel-ipu4-mmu[01]", GROUP="root", MODE="0600", TAG-="uaccess"\n'
                 b'SUBSYSTEM=="media", KERNELS=="intel-ipu4-mmu[01]", GROUP="root", MODE="0600", TAG-="uaccess"\n')

    def verify_owned(self):
        marker = self.source / 'config/ownership-marker'
        if self.path(LIB + '/.surface7-ubuntu-frontcamera-owned').read_bytes() != marker.read_bytes():
            raise RuntimeError('Product ownership marker does not match')
        allow = json.loads((self.source / 'config/startup-legacy-sha256.json').read_text())
        for path, desired in self.desired.items():
            current = record(self.path(path))
            if current['kind'] == 'absent' or current == desired:
                continue
            if current['kind'] == 'file' and current['sha256'] in allow.get(path, []):
                continue
            if current == {'kind': 'link', 'target': '/dev/null'} and path.endswith(tuple(OLD)):
                continue
            raise RuntimeError(f'Refusing to replace unrecognized file: {path}')

    def snapshot(self, unit_states, initrds):
        # Never overwrite the original snapshot, even after rollback.
        self.backup.mkdir(parents=True, mode=0o700, exist_ok=False)
        before = {}
        for path in [*self.desired, *initrds]:
            before[path] = record(self.path(path))
            if before[path]['kind'] != 'absent':
                saved = self.backup / 'files' / path.lstrip('/')
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(self.path(path), saved, follow_symlinks=False)
                if before[path]["kind"] == "file" and os.geteuid() == 0:
                    os.chown(saved, before[path]["uid"], before[path]["gid"])
        manifest = {'version': 1, 'before': before, 'after': self.desired,
                    'units': unit_states, 'initrds': initrds,
                    'modules': self.path('/proc/modules').read_text()}
        self.save(manifest)
        (self.backup / '.complete').write_text('surface7-explicit-start-v1\n')
        return manifest

    def save(self, manifest):
        tmp = self.backup / 'manifest.next'
        tmp.write_text(json.dumps(manifest, indent=2) + '\n')
        tmp.replace(self.backup / 'manifest.json')

    def write(self, path, spec, data=None):
        dest = self.path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        temp = dest.with_name(dest.name + '.surface7-new')
        if temp.exists() or temp.is_symlink():
            raise RuntimeError(f'Refusing leftover transaction path {temp}')
        if spec['kind'] == 'absent':
            dest.unlink(missing_ok=True)
        elif spec['kind'] == 'link':
            temp.symlink_to(spec['target'])
            temp.replace(dest)
        else:
            if isinstance(data, Path):
                shutil.copyfile(data, temp)
            else:
                temp.write_bytes(data)
            temp.chmod(spec['mode'])
            if os.geteuid() == 0:
                os.chown(temp, spec['uid'], spec['gid'])
            temp.replace(dest)

    def validate_restore(self, manifest):
        for path, old in manifest['before'].items():
            if old['kind'] != 'absent':
                saved = self.backup / 'files' / path.lstrip('/')
                if record(saved) != old:
                    raise RuntimeError(f'Backup damaged: {path}')
            current = record(self.path(path))
            if current not in (old, manifest['after'].get(path, old)):
                raise RuntimeError(f'Refusing rollback over later changes: {path}')

    def restore_files(self, manifest):
        self.validate_restore(manifest)
        for path, old in manifest['before'].items():
            saved = self.backup / 'files' / path.lstrip('/')
            self.write(path, old, saved if old['kind'] == 'file' else None)


def unit_state(unit):
    p = subprocess.run(['systemctl', 'show', unit, '-p', 'UnitFileState', '-p', 'ActiveState',
                        '-p', 'LoadState'], capture_output=True, text=True, check=True)
    result = dict(x.split('=', 1) for x in p.stdout.splitlines() if '=' in x)
    if result.get('ActiveState') not in ('active', 'inactive', 'failed'):
        raise RuntimeError(f'Unit in transition: {unit}')
    if result.get('UnitFileState', '') not in ('enabled', 'enabled-runtime', 'disabled', 'static',
                                               'masked', 'masked-runtime', '', 'not-found'):
        raise RuntimeError(f'Unsupported enablement state: {unit}')
    return result


def audit_other_paths():
    # Refuse alternate explicit loaders rather than silently editing unrelated configuration.
    import re
    pattern = re.compile(r'\b(?:intel[-_]ipu4p\S*|ipu[-_]bridge|v4l2loopback|ov5693|ov8865|ov7251|dw9719)\b')
    known = Path('/etc/modules-load.d/sp7-v4l2loopback.conf')
    paths = [Path('/etc/modules'), Path('/etc/initramfs-tools/modules')]
    for folder in ('/etc/modules-load.d', '/usr/lib/modules-load.d', '/run/modules-load.d'):
        paths += list(Path(folder).glob('*.conf'))
    for path in paths:
        if path == known or not path.is_file():
            continue
        for line in path.read_text().splitlines():
            if pattern.search(line.split('#', 1)[0]):
                raise RuntimeError(f'Unmanaged camera module-loading entry: {path}')
    for base in ('/etc/systemd/system', '/run/systemd/system', '/usr/lib/systemd/system'):
        for unit in UNITS:
            if list((Path(base) / (unit + '.d')).glob('*.conf')):
                raise RuntimeError(f'Unreviewed unit drop-in: {base}/{unit}.d')
    # Explicit loaders or root-level startup hooks outside this deployment need
    # review. Block rather than edit someone else's cron/rc/initramfs setup.
    hooks = [Path('/etc/rc.local')]
    for base in ('/etc/cron.d', '/etc/initramfs-tools/scripts', '/etc/initramfs-tools/hooks'):
        if Path(base).exists():
            hooks += [p for p in Path(base).rglob('*') if p.is_file()]
    for path in hooks:
        if path.is_file():
            for line in path.read_text(errors='replace').splitlines():
                if pattern.search(line.split('#', 1)[0]):
                    raise RuntimeError(f'Unreviewed camera startup hook: {path}')
    # An initrd built with these built in cannot honor modprobe policy.
    for config in Path('/boot').glob('config-*'):
        text = config.read_text()
        if re.search(r'^CONFIG_VIDEO_(?:INTEL_IPU|INTEL_IPU4|V4L2LOOPBACK)=y$', text, re.M):
            raise RuntimeError(f'Camera built into kernel; module gate cannot protect {config.name}')


def restore_units(states, resume):
    run('systemctl', 'daemon-reload')
    for unit, saved in states.items():
        state = saved.get('UnitFileState')
        # Existing masks are restored as files; runtime masks need explicit recreation.
        if state in ('enabled', 'enabled-runtime'):
            cmd = ['systemctl', 'enable']
            if state == 'enabled-runtime':
                cmd.append('--runtime')
            run(*cmd, unit)
        elif state == 'masked-runtime':
            run('systemctl', 'mask', '--runtime', unit)
    run('systemctl', 'daemon-reload')
    if resume:
        for unit in UNITS:
            if states[unit].get('ActiveState') == 'active':
                run('systemctl', 'start', unit)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['plan', 'deploy', 'rollback', 'rollback-resume'])
    p.add_argument('--built', type=Path)
    args = p.parse_args()
    policy = Policy(Path(__file__).resolve().parent.parent)
    if args.action == 'plan':
        print('Deploy explicit-start policy: snapshot all six unit states, managed files, loaded-module inventory and every existing initrd; mask three legacy units; disable new units; install module/probe guards; rebuild initrds. No package install, module load/unload, camera test or reboot. Rollback restores snapshots; --startup-policy-resume also restarts previously active services and may activate hardware.')
        return 0
    if os.geteuid() != 0:
        raise RuntimeError('Deployment/rollback requires sudo; read the plan first')
    import fcntl
    lock = open('/run/lock/surface7-startup-policy.lock', 'a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    if args.action.startswith('rollback'):
        if policy.path(LIB + '/.surface7-ubuntu-frontcamera-owned').read_bytes() != (policy.source / 'config/ownership-marker').read_bytes():
            raise RuntimeError('Product ownership marker does not match')
        manifest = json.loads((policy.backup / 'manifest.json').read_text())
        if (policy.backup / '.complete').read_text() != 'surface7-explicit-start-v1\n':
            raise RuntimeError('Incomplete snapshot')
        policy.validate_restore(manifest)
        stop_units()
        disable_units()
        policy.restore_files(manifest)
        restore_units(manifest['units'], args.action == 'rollback-resume')
        run('udevadm', 'control', '--reload-rules')
        (policy.backup / '.restored').touch()
        print('Files, exact initrds and unit enablement restored. No module load/unload or reboot issued.')
        if args.action == 'rollback':
            print('Services deliberately remain stopped. --startup-policy-resume restores saved active services after separate approval; it may start the camera.')
        print('Saved loaded-module inventory is in manifest.json. Exact kernel runtime state requires an approved reboot; no forced unloading.')
        return 0
    if args.built is None:
        raise RuntimeError('Use scripts/deploy-services.sh to build the two small helpers first')
    audit_other_paths()
    policy.prepare(args.built)
    policy.verify_owned()
    if policy.backup.exists():
        raise RuntimeError(f'Immutable snapshot already exists: {policy.backup}; inspect it rather than overwriting')
    initrds = []
    for image in Path('/boot').glob('initrd.img-*'):
        if image.is_symlink():
            raise RuntimeError(f'Review initrd symlink before deployment: {image}')
        if image.is_file():
            initrds.append(str(image))
    if not initrds or not Path('/boot/initrd.img-' + os.uname().release).is_file():
        raise RuntimeError('Running-kernel initrd missing; refusing incomplete boot protection')
    states = {unit: unit_state(unit) for unit in UNITS}
    manifest = policy.snapshot(states, sorted(initrds))
    try:
        stop_units()
        disable_units()
        for path, spec in policy.desired.items():
            policy.write(path, spec, policy.payload.get(path))
        run('systemctl', 'daemon-reload')
        run('udevadm', 'control', '--reload-rules')
        # Generate into transaction storage, never overwrite an initrd before its
        # expected hash is recorded. Interrupted builds leave originals untouched.
        for image in manifest['initrds']:
            kernel = Path(image).name.removeprefix('initrd.img-')
            staged = policy.backup / ('new-initrd-' + kernel)
            run('mkinitramfs', '-o', str(staged), kernel)
            listing = run('lsinitramfs', str(staged))
            if 'etc/modprobe.d/surface7-camera-manual.conf' not in listing:
                raise RuntimeError('Generated initrd lacks the module guard')
            manifest['after'][image] = {**manifest['before'][image], 'sha256': record(staged)['sha256']}
            policy.save(manifest)
            policy.write(image, manifest['after'][image], staged)
        (policy.backup / '.deployed').touch()
    except BaseException:
        # Restore config/enablement without restarting the failing boot design.
        # If the snapshot verification fails, stop and print a recovery path.
        print('Deployment failed; restoring snapshot with services stopped.', file=sys.stderr)
        policy.restore_files(manifest)
        restore_units(states, False)
        run('udevadm', 'control', '--reload-rules')
        raise
    print('Explicit-start policy deployed. No camera modules were loaded/unloaded.')
    print('Already loaded modules remain until an approved reboot. Before that reboot, do not test the camera.')
    print('After login on a clean boot: sudo surface7-camera start')


def stop_units():
    # Ordered stop, no --now on mask/disable and no ignoring failures.
    for unit in reversed(UNITS):
        state = unit_state(unit)
        if state.get('LoadState') != 'not-found':
            run('systemctl', 'stop', unit)


def disable_units():
    for unit in UNITS:
        state = unit_state(unit)
        if state.get('UnitFileState') in ('enabled', 'enabled-runtime'):
            if state.get('UnitFileState') == 'enabled-runtime':
                run('systemctl', 'disable', '--runtime', unit)
            else:
                run('systemctl', 'disable', unit)
        if state.get('UnitFileState') == 'masked-runtime':
            run('systemctl', 'unmask', '--runtime', unit)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f'startup policy: {exc}', file=sys.stderr)
        sys.exit(1)
