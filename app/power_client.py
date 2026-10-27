"""Unprivileged power requests; filesystem/socket work stays off the audio/UI loop."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import os
import socket
import time

RUNTIME=Path('/run/machinista-power')

def request(action, runtime=RUNTIME):
    if action not in ('status','reboot','shutdown','ssh-status','ssh-enable','ssh-disable'):raise ValueError('Invalid power action.')
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(25 if action in ('ssh-enable','ssh-disable') else 3)
        connection.connect(str(Path(runtime)/'control.sock'))
        connection.sendall(json.dumps({'action':action}).encode()+b'\n')
        data=b''
        while b'\n' not in data:
            part=connection.recv(4096)
            if not part or len(data)+len(part)>8192:raise OSError('Power service unavailable.')
            data+=part
    result=json.loads(data.split(b'\n',1)[0])
    if result.get('error'):raise ValueError(result['error'])
    return result

class PowerControl:
    def __init__(self,runtime=RUNTIME):
        self.runtime=Path(runtime);self.next=0;self.writer=None;self.command=None
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='power-control')
    def publish(self,busy):
        try:
            temporary=self.runtime/'status.json.tmp'
            temporary.write_text(json.dumps(dict(busy=bool(busy),updated=time.time(),pid=os.getpid())))
            os.replace(temporary,self.runtime/'status.json')
        except OSError:pass
    def poll(self,app,now,busy=False):
        if self.command is not None and self.command.done():
            future,self.command=self.command,None
            try:app.message=future.result()['message']
            except (OSError,ValueError,KeyError):app.message='POWER REQUEST FAILED'
        if now>=self.next and (self.writer is None or self.writer.done()):
            self.next=now+.5;self.writer=self.pool.submit(self.publish,busy)
    def submit(self,action):
        if self.command is None:self.command=self.pool.submit(request,action,self.runtime)
    def close(self):self.pool.shutdown(wait=False,cancel_futures=True)
