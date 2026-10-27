#!/usr/bin/env python3
"""Low priority, independent browser library service."""
from pathlib import Path
import argparse
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.web_server import Library, Server

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);parser.add_argument('--host',default='0.0.0.0');parser.add_argument('--port',type=int,default=8080)
    parser.add_argument('--password-file',type=Path)
    parser.add_argument('--no-auth',action='store_true',help='Explicitly allow LAN access without login')
    args=parser.parse_args();password=None
    if not args.no_auth:
        password=(args.password_file or args.root/'config/web-ui-password').read_text().strip()
        if len(password)<12:parser.error('Web password must contain at least 12 characters.')
    server=Server((args.host,args.port),Library(args.root,password=password),allow_unauthenticated=args.no_auth)
    print(f'Machinista Web UI listening on {args.host}:{args.port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
if __name__=='__main__':main()
