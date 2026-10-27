#!/usr/bin/env python3
"""Root-owned local broker: save/stop Machinista, then one fixed power operation."""
import fcntl
import argparse
import json
import os
from pathlib import Path
import pwd
import socket
import socketserver
import struct
import subprocess
import threading
import time

class SSHManager:
    """Only fixed SSH service operations; never accept shell text or credentials."""
    def __init__(self,run=subprocess.run,user=None):
        self.run=run;self.user=user;self.lock=threading.Lock()
    def command(self,*args):
        return self.run(['systemctl',*args],check=True,timeout=8,capture_output=True,text=True)
    def status(self):
        values={}
        for unit in ('ssh.service','ssh.socket'):
            result=self.command('show',unit,'--property=ActiveState','--property=UnitFileState')
            values[unit]=dict(line.split('=',1) for line in result.stdout.splitlines() if '=' in line)
        service=values['ssh.service'];sock=values['ssh.socket']
        return dict(user=self.user,active=service.get('ActiveState')=='active' or sock.get('ActiveState')=='active',
                    enabled=service.get('UnitFileState') in ('enabled','enabled-runtime') or sock.get('UnitFileState') in ('enabled','enabled-runtime'))
    def change(self,action):
        if action not in ('ssh-enable','ssh-disable'):raise ValueError('Invalid SSH action.')
        with self.lock:
            self.command('start','machinista-'+action+'.service')
            return self.status()

class PowerManager:
    def __init__(self,runtime,run=subprocess.run,sync=os.sync):
        self.runtime=Path(runtime);self.run=run;self.sync=sync
        self.lock=threading.Lock();self.pending=None;self.error=None;self.lease=None
    def status(self):
        try:
            path=self.runtime/'status.json'
            if path.stat().st_size>4096:raise ValueError('Invalid application status.')
            status=json.loads(path.read_text())
            ready=0<=time.time()-status['updated']<5
            busy=bool(status['busy'])
        except (OSError,ValueError,KeyError,TypeError):ready=False;busy=True
        return dict(ready=ready,busy=busy,pending=self.pending,error=self.error)
    def accept(self,action):
        if action not in ('reboot','shutdown'):raise ValueError('Invalid power action.')
        with self.lock:
            state=self.status()
            if self.pending:raise ValueError('A power operation is already in progress.')
            if not state['ready']:raise ValueError('Application not ready. Please try again.')
            if state['busy']:raise ValueError('Stop recording and wait for processing to finish first.')
            lock=self.runtime/'maintenance.lock'
            if self.lease:self.lease.close()
            self.lease=os.fdopen(os.open(lock,os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW,0o600),'w')
            try:fcntl.flock(self.lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError:self.lease.close();self.lease=None;raise ValueError('An update or power operation is already running.')
            self.pending=action;self.error=None
        return dict(ok=True,message='RESTARTING...' if action=='reboot' else 'SHUTTING DOWN...')
    def execute(self,action):
        try:
            state=self.status()
            if not state['ready'] or state['busy']:
                self.error='Stop recording and wait for processing to finish first.'
                self.pending=None
                if self.lease:self.lease.close();self.lease=None
                return
            # SIGTERM follows the application's normal project/plug-in save path.
            self.run(['systemctl','stop','machinista.service'],check=True,timeout=25,capture_output=True)
            result=self.run(['systemctl','show','machinista.service','--property=Result','--value'],check=True,timeout=5,capture_output=True,text=True)
            if result.stdout.strip()!='success':raise RuntimeError('Application did not stop cleanly; power operation cancelled.')
            self.sync()
            self.run(['systemctl','--no-block','reboot' if action=='reboot' else 'poweroff'],check=True,timeout=10,capture_output=True)
        except (OSError,RuntimeError,subprocess.SubprocessError) as error:
            self.error='Power operation failed. Please try again.'
            print(str(error),flush=True)
            # A failed request must not leave the user without their controller.
            try:self.run(['systemctl','start','machinista.service'],check=True,timeout=25,capture_output=True)
            except (OSError,subprocess.SubprocessError):pass
            self.pending=None
            if self.lease:self.lease.close();self.lease=None

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--user',default='machinista');parser.add_argument('--runtime',type=Path,default=Path('/run/machinista-power'));args=parser.parse_args()
    account=pwd.getpwnam(args.user);runtime=args.runtime
    runtime.mkdir(exist_ok=True);os.chown(runtime,0,account.pw_gid);runtime.chmod(0o770)
    path=runtime/'control.sock';path.unlink(missing_ok=True)
    manager=PowerManager(runtime);ssh=SSHManager(user=account.pw_name)
    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            self.request.settimeout(3)
            _,uid,_=struct.unpack('3i',self.request.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,struct.calcsize('3i')))
            if uid not in (0,account.pw_uid):return
            action=None
            try:
                raw=self.rfile.readline(1025)
                if len(raw)>1024 or not raw.endswith(b'\n'):raise ValueError('Invalid request.')
                value=json.loads(raw)
                if not isinstance(value,dict) or set(value)!= {'action'}:raise ValueError('Invalid request.')
                action=value['action']
                if action=='ssh-status':result=ssh.status()
                elif action in ('ssh-enable','ssh-disable'):result=ssh.change(action)
                else:result=manager.status() if action=='status' else manager.accept(action)
            except (OSError,subprocess.SubprocessError):result={'error':'SSH service operation failed.'}
            except (ValueError,TypeError) as error:result={'error':str(error)}
            self.wfile.write(json.dumps(result).encode()+b'\n');self.wfile.flush()
            if action in ('reboot','shutdown') and result.get('ok'):
                timer=threading.Timer(2,manager.execute,args=(action,));timer.daemon=True;timer.start()
    class Server(socketserver.ThreadingUnixStreamServer):daemon_threads=True
    with Server(str(path),Handler) as server:
        os.chown(path,0,account.pw_gid);path.chmod(0o660)
        server.serve_forever()
if __name__=='__main__':main()
