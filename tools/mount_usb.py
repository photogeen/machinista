#!/usr/bin/env python3
"""Root media service: mount USB data filesystems for sample browsing and explicit exports."""
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time

BASE = Path('/media/maschineos')
MANIFEST = Path('/run/maschineos-media.json')
FILESYSTEMS = {'vfat', 'exfat', 'ntfs', 'ntfs3', 'ext4', 'ext3', 'ext2', 'iso9660'}


def candidates(devices, usb=False):
    result = []
    for item in devices:
        is_usb = usb or item.get('tran') == 'usb'
        if is_usb and item.get('fstype') in FILESYSTEMS and item.get('path') and item.get('uuid'):
            result.append(item)
        result.extend(candidates(item.get('children', []), is_usb))
    return result


def scan_devices():
    # Without --tree, lsblk omits children when NAME is not a selected column.
    # Partition TRAN is often null: inherit USB identity from its parent disk.
    output = subprocess.run(['lsblk', '--tree', '-J', '-o', 'PATH,TRAN,FSTYPE,LABEL,UUID,MOUNTPOINTS'],
                            check=True, capture_output=True, text=True, timeout=3)
    return candidates(json.loads(output.stdout)['blockdevices'])


def mount_options(fstype):
    options=('ro' if fstype=='iso9660' else 'rw')+',nosuid,nodev,noexec'
    if fstype in ('vfat','exfat','ntfs','ntfs3'):options+=',uid=1000,gid=1000,umask=022'
    return options


def mount_filesystem(path,target,fstype):
    def run(options):
        return subprocess.run(['mount','-o',options,'--source',path,'--target',str(target)],capture_output=True,text=True,timeout=5)
    result=run(mount_options(fstype))
    if result.returncode and fstype!='iso9660':
        print(f'Mount {path} read-write failed; trying read-only: {result.stderr.strip()}',flush=True)
        options=mount_options(fstype).replace('rw,','ro,',1)
        if fstype in ('ext3','ext4'):options+=',noload'
        result=run(options)
    return result


def write_manifest(rows):
    temporary = MANIFEST.with_suffix('.tmp')
    temporary.write_text(json.dumps(rows)+'\n')
    temporary.chmod(0o644)
    os.replace(temporary, MANIFEST)


def main():
    if os.geteuid() != 0:
        raise PermissionError('media service must run as root')
    BASE.mkdir(parents=True, exist_ok=True)
    stopped = False
    owned = {}
    def stop(*_):
        nonlocal stopped
        stopped = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while not stopped:
        rows = []
        try:
            available = scan_devices()
            present = {item['path'] for item in available}
            for path, target in list(owned.items()):
                if path not in present:
                    subprocess.run(['umount', '-l', str(target)], capture_output=True, timeout=3)
                    del owned[path]
            for item in available:
                identifier = item['uuid']
                if not re.fullmatch(r'[A-Za-z0-9-]{1,100}', identifier):
                    continue
                path = item['path']
                if not re.fullmatch(r'/dev/[A-Za-z0-9]+', path):
                    continue
                mounts = [p for p in item.get('mountpoints', []) if p]
                target = BASE/identifier
                # Publish existing user mounts, but never own/unmount them.
                if mounts and str(target) not in mounts:
                    existing = next((p for p in mounts if p.startswith(('/media/', '/mnt/', '/run/media/'))), None)
                    if existing:
                        rows.append({'name': item.get('label') or identifier, 'path': existing, 'uuid': identifier})
                    continue
                target.mkdir(exist_ok=True)
                if not mounts:
                    mount = mount_filesystem(path,target,item['fstype'])
                    if mount.returncode:
                        print(f'Mount {path}: {mount.stderr.strip()}', flush=True)
                        continue
                owned[path] = target
                rows.append({'name': item.get('label') or identifier, 'path': str(target), 'uuid': identifier})
            write_manifest(rows)
        except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
            print(f'Media scan: {error}', flush=True)
        for _ in range(20):
            if stopped:
                break
            time.sleep(0.1)
    write_manifest([])
    for target in owned.values():
        subprocess.run(['umount', str(target)], capture_output=True, timeout=3)


if __name__ == '__main__':
    main()
