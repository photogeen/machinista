#!/usr/bin/env python3
"""Root-owned update broker. Fixed commands only; no web-supplied URLs/paths."""
import argparse,json,os,pwd,socket,socketserver,struct,sys
from pathlib import Path
# Installed beside root-owned update_manager.py, not imported from the app root.
from update_manager import Manager,config

def main():
    p=argparse.ArgumentParser();p.add_argument('--user',default='machinista');p.add_argument('--root',type=Path,default=Path('/home/machinista/Machinista'));p.add_argument('--config',type=Path,default=Path('/etc/machinista/updater.json'));args=p.parse_args()
    user=pwd.getpwnam(args.user);runtime=Path('/run/machinista-updater');runtime.mkdir(exist_ok=True);runtime.chmod(0o755)
    app=runtime/'app';app.mkdir(exist_ok=True);os.chown(app,user.pw_uid,user.pw_gid);app.chmod(0o700)
    manager=Manager(config(args.config),args.root,'/var/lib/machinista-updater',runtime,user.pw_uid,user.pw_gid);manager.publish()
    path=runtime/'control.sock';path.unlink(missing_ok=True)
    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            self.request.settimeout(2)
            _,uid,_=struct.unpack('3i',self.request.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
            if uid not in (0,user.pw_uid):return
            try:
                raw=self.rfile.readline(2049)
                if len(raw)>2048 or not raw.endswith(b'\n'):raise ValueError('Invalid updater request.')
                value=json.loads(raw)
                if not isinstance(value,dict) or set(value)-{'op','channel','expected'}:raise ValueError('Invalid updater request.')
                result=manager.command(value.get('op'),value.get('channel'),value.get('expected'))
            except Exception as error:result={'error':str(error)[:240]}
            self.wfile.write(json.dumps(result).encode()+b'\n')
    class Server(socketserver.ThreadingUnixStreamServer):daemon_threads=True
    with Server(str(path),Handler) as server:
        os.chown(path,0,user.pw_gid);path.chmod(0o660);server.serve_forever()
if __name__=='__main__':main()
