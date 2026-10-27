#!/usr/bin/env python3
"""Generic beta first boot; only operates when the image marker is absent."""
from pathlib import Path
import json
import os
import subprocess

def run(*args,**kwargs):return subprocess.run(args,check=True,text=True,**kwargs)

def expand_root():
    source=Path(subprocess.check_output(['findmnt','-n','-o','SOURCE','/'],text=True).strip()).resolve()
    parent=subprocess.check_output(['lsblk','-no','PKNAME',str(source)],text=True).strip()
    number=Path('/sys/class/block')/source.name/'partition'
    if not parent or not number.exists():return False
    partition=int(number.read_text());device='/dev/'+parent
    table=json.loads(subprocess.check_output(['sfdisk','--json',device],text=True))['partitiontable']
    if table['partitions'][-1]['node']!=str(source):return False
    run('sfdisk','--no-reread','--force','-N',str(partition),device,input=',+\n',stdout=subprocess.DEVNULL)
    subprocess.run(['partx','-u',device],check=False,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    result=subprocess.run(['resize2fs',str(source)],check=False)
    return result.returncode!=0

def main():
    state=Path('/var/lib/machinista');state.mkdir(mode=0o755,exist_ok=True)
    if (state/'initialized').exists():
        source=subprocess.check_output(['findmnt','-n','-o','SOURCE','/'],text=True).strip()
        subprocess.run(['resize2fs',source],check=False,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        return
    # Machine ID is created by systemd before this unit. No source-Pi keys exist.
    run('ssh-keygen','-A')
    run('smbpasswd','-s','-a','machinista',input='machinista\nmachinista\n',stdout=subprocess.DEVNULL)
    root=Path('/home/machinista/Machinista')
    for folder in ('Kicks','Snares','Hi-Hats','Loops'):(root/'samples/Library'/folder).mkdir(parents=True,exist_ok=True)
    run('chown','-R','machinista:machinista',str(root/'samples'),str(root/'projects'),str(root/'config'))
    reboot=False
    try:reboot=expand_root()
    except (OSError,ValueError,subprocess.CalledProcessError):print('Automatic SD expansion requires a manual check.',flush=True)
    (state/'initialized').write_text('Machinista beta 0.1.0-beta.6\n')
    if reboot:run('systemctl','--no-block','reboot')
if __name__=='__main__':main()
