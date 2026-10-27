#!/usr/bin/env python3
"""Fixed same-user handshake; installed root-owned, executed unprivileged."""
import argparse,json,socket
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args()
with socket.socket(socket.AF_UNIX) as s:
    s.settimeout(8);s.connect(str(a.root/'samples/.sound-control.sock'))
    s.sendall(b'{"operation":"update_prepare"}\n');raw=b''
    while b'\n' not in raw:
        part=s.recv(4096)
        if not part or len(raw)+len(part)>8192:raise SystemExit('Update handshake failed.')
        raw+=part
    result=json.loads(raw.split(b'\n',1)[0])
    if not result.get('ok'):raise SystemExit(result.get('error','Application not ready.'))
