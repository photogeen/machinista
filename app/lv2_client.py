"""Unprivileged web-side upload stream and fixed-operation local RPC."""
import json
import os
from pathlib import Path
import secrets
import socket
import shutil
from app.lv2_manager import MAX_ARCHIVE, STATE, RUNTIME


def request(operation,**values):
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
        client.settimeout(5);client.connect(str(RUNTIME/'control.sock'))
        client.sendall(json.dumps(dict(operation=operation,**values)).encode()+b'\n')
        with client.makefile('rb') as stream:raw=stream.readline(2*1024**2)
    result=json.loads(raw)
    if result.get('error'):raise ValueError(result['error'])
    return result


def upload(name,stream,length):
    if not isinstance(name,str) or not name.lower().endswith(('.zip','.tar.gz','.tgz','.tar')):raise ValueError('Choose ZIP, TAR.GZ, TGZ or TAR with compiled .lv2 folders.')
    if not 0<length<=MAX_ARCHIVE:raise ValueError('Maximum 128 MiB per plugin archive.')
    if request('status').get('busy'):raise BlockingIOError('Another LV2 operation is in progress.')
    if shutil.disk_usage(STATE).free<length+512*1024**2:raise OSError('Not enough space for upload, validation and the 256 MiB reserve.')
    identifier=secrets.token_hex(16);path=STATE/'incoming'/(identifier+'.upload')
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o640)
    try:
        with os.fdopen(fd,'wb') as out:
            remaining=length
            while remaining:
                data=stream.read(min(65536,remaining))
                if not data:raise ValueError('Upload incomplete.')
                out.write(data);remaining-=len(data)
            out.flush();os.fsync(out.fileno())
        return request('upload',id=identifier,name=Path(name).name)
    except BaseException:path.unlink(missing_ok=True);raise
