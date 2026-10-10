#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""One-file, reversible hotfix for the post-login PSYS authentication gate."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys

BACKUP = Path('/var/lib/surface7-ubuntu-frontcamera/backup/psys-gate-v1')
BASE = Path('/var/lib/surface7-ubuntu-frontcamera/backup/explicit-start-v1')
TARGET = Path('/usr/local/sbin/surface7-camera')
OLD_SHA256 = 'cf30431d6cbe7129fb7f56150fc04b9627391526eb4db7c54460e7b1f8c4c911'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def replace_from(source):
    temp = TARGET.with_name(TARGET.name + '.psys-gate-new')
    if temp.exists() or temp.is_symlink():
        raise RuntimeError(f'Refusing leftover temporary file: {temp}')
    try:
        shutil.copyfile(source, temp)
        temp.chmod(0o755)
        os.chown(temp, 0, 0)
        temp.replace(TARGET)
    finally:
        temp.unlink(missing_ok=True)


def deploy(source):
    if not (BASE / '.deployed').is_file() or (BASE / '.restored').exists():
        raise RuntimeError('Base startup-policy deployment is not active')
    if BACKUP.exists():
        raise RuntimeError(f'Immutable hotfix snapshot already exists: {BACKUP}')
    if not TARGET.is_file() or digest(TARGET) != OLD_SHA256:
        raise RuntimeError('Installed camera helper is not the reviewed base version')
    if not source.is_file() or source.is_symlink():
        raise RuntimeError('Hotfix source is missing or a symlink')
    before = TARGET.stat()
    if (stat.S_IMODE(before.st_mode) != 0o755 or before.st_uid != os.geteuid()
            or before.st_gid != os.getegid()):
        raise RuntimeError('Installed camera helper ownership/mode differs from reviewed base')
    BACKUP.mkdir(parents=True, mode=0o700, exist_ok=False)
    shutil.copy2(TARGET, BACKUP / 'previous-camera-helper')
    manifest = {'before_sha256': OLD_SHA256, 'after_sha256': digest(source),
                'path': str(TARGET), 'mode': 0o755, 'uid': 0, 'gid': 0}
    (BACKUP / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (BACKUP / '.complete').write_text('surface7-psys-gate-v1\n')
    try:
        replace_from(source)
        if digest(TARGET) != manifest['after_sha256']:
            raise RuntimeError('Installed helper hash mismatch')
    except BaseException:
        if digest(BACKUP / 'previous-camera-helper') == OLD_SHA256:
            replace_from(BACKUP / 'previous-camera-helper')
        raise
    (BACKUP / '.deployed').touch()
    print('PSYS gate installed; camera services and modules were not changed')


def rollback(if_installed):
    if not BACKUP.exists():
        if if_installed:
            return
        raise RuntimeError('Hotfix snapshot is absent')
    if (BACKUP / '.complete').read_text() != 'surface7-psys-gate-v1\n':
        raise RuntimeError('Incomplete hotfix snapshot')
    manifest = json.loads((BACKUP / 'manifest.json').read_text())
    if manifest['path'] != str(TARGET) or manifest['before_sha256'] != OLD_SHA256:
        raise RuntimeError('Hotfix manifest does not match reviewed target')
    original = BACKUP / 'previous-camera-helper'
    if digest(original) != OLD_SHA256:
        raise RuntimeError('Hotfix backup is damaged')
    current = digest(TARGET)
    if current not in (OLD_SHA256, manifest['after_sha256']):
        raise RuntimeError('Refusing to overwrite a later camera helper edit')
    if current != OLD_SHA256:
        replace_from(original)
    (BACKUP / '.restored').touch()
    print('PSYS gate rolled back to reviewed base helper')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['deploy', 'rollback', 'rollback-if-installed'])
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise RuntimeError('Run through sudo as the desktop user')
    source = Path(__file__).resolve().parent / 'surface7-camera'
    if args.action == 'deploy':
        deploy(source)
    else:
        rollback(args.action == 'rollback-if-installed')


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError) as exc:
        print(f'psys gate: {exc}', file=sys.stderr)
        sys.exit(1)
