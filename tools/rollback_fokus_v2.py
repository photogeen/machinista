#!/usr/bin/env python3
"""Restore pre-Fokus application code; retain current projects/settings/samples."""
import argparse
from pathlib import Path,PurePosixPath
import shutil
import subprocess
import tarfile
import tempfile

ROOT=Path(__file__).resolve().parents[1]
CODE={'app','tools','tests','src','web','deploy','docs'}
FILES={'CMakeLists.txt','README.md','SESSION_STATUS.md','THIRD_PARTY_NOTICES.md','PROJECT_HANDOFF.md'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,default=ROOT/'backups/machinist-v1-full-before-fokus-v2-2026-10-11.tar.gz')
    parser.add_argument('--apply',action='store_true',help='Stop Machinista and restore V1 code, retaining user data')
    args=parser.parse_args()
    if not args.archive.is_file():parser.error('Backup archive is missing')
    with tarfile.open(args.archive,'r:gz') as archive:
        members=[]
        for item in archive.getmembers():
            path=PurePosixPath(item.name)
            if path.is_absolute() or '..' in path.parts:raise ValueError('Unsafe archive path')
            if not path.parts or path.parts[0] not in CODE and str(path) not in FILES:continue
            if item.isfile():members.append((item,path))
        if not any(str(path)=='app/model.py' for _,path in members):raise ValueError('Invalid V1 code backup')
        print(f'V1 code: {len(members)} files. Projects, config, samples, exports and binaries are retained.')
        if not args.apply:print('Verified dry run. Use --apply to restore.');return
        with tempfile.TemporaryDirectory(prefix='fokus-rollback-',dir=ROOT/'backups') as folder:
            stage=Path(folder)
            for item,path in members:
                target=stage/str(path);target.parent.mkdir(parents=True,exist_ok=True)
                with archive.extractfile(item) as source,target.open('wb') as dest:shutil.copyfileobj(source,dest)
                target.chmod(item.mode & 0o777)
            subprocess.run(['sudo','systemctl','stop','machinista'],check=True)
            for _,path in members:
                target=ROOT/str(path);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(stage/str(path),target)
            subprocess.run(['sudo','systemctl','start','machinista'],check=True)
            print('V1 code restored; Machinista started. Current user data retained.')


if __name__=='__main__':main()
