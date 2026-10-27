#!/usr/bin/env python3
"""Create/sign an update from an already sanitized, ARM-tested image payload.

Does not upload, change branches or install anything. Private keys stay external.
"""
import argparse,base64,hashlib,json,re,subprocess,tarfile,tempfile,sys
from pathlib import Path,PurePosixPath
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.update_manager import ALLOWED,members,version

def main():
    p=argparse.ArgumentParser();p.add_argument('--payload',type=Path,required=True);p.add_argument('--key',type=Path,required=True);p.add_argument('--repository',required=True);p.add_argument('--channel',choices=('beta','release'),required=True);p.add_argument('--version',required=True);p.add_argument('--minimum-version',required=True);p.add_argument('--os-codename',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--notes',default='');args=p.parse_args()
    version(args.version);version(args.minimum_version)
    assert re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',args.repository)
    if args.channel=='release' and '-' in args.version:raise ValueError('Release channel requires a final version.')
    args.output.mkdir(parents=True,exist_ok=True);name=f'machinista-{args.version}-arm64.tar.gz';target=args.output/name
    with tarfile.open(args.payload) as source,tarfile.open(target,'w:gz') as dest:
        for item in source:
            parts=PurePosixPath(item.name).parts
            if not parts or parts[0] not in ALLOWED or (parts[0]=='output' and (len(parts)!=3 or parts[1]!='pdf' or not parts[2].endswith('.pdf'))):continue
            # Optional OB-Xd banks ship in clean images and as a separate import.
            # Keep updates compatible with deployed brokers and preserve user banks.
            if item.name.startswith('presets/plugin-banks/obxd/'):continue
            if item.isdir():continue
            if not item.isfile() or item.name.startswith('/') or '..' in parts:raise ValueError('Unsafe source payload.')
            stream=source.extractfile(item)
            if item.name=='app/branding.py':
                body=stream.read();match=re.search(rb'VERSION\s*=\s*[\'"]([^\'"]+)',body)
                if not match or match[1].decode()!=args.version:raise ValueError('Payload version does not match update version.')
                import io
                stream=io.BytesIO(body)
            item.uid=item.gid=0;item.uname=item.gname='';dest.addfile(item,stream)
    members(target)
    m=dict(schema=1,channel=args.channel,version=args.version,minimum_version=args.minimum_version,os_codename=args.os_codename,architecture='arm64',notes=args.notes,
        artifact=dict(url=f'https://github.com/{args.repository}/releases/download/v{args.version}/{name}',size=target.stat().st_size,sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
    raw=(json.dumps(m,indent=2)+'\n').encode();manifest=args.output/'update.json';manifest.write_bytes(raw)
    with tempfile.TemporaryDirectory() as tmp:
        sig=Path(tmp)/'signature'
        subprocess.run(['openssl','pkeyutl','-sign','-rawin','-inkey',str(args.key),'-in',str(manifest),'-out',str(sig)],check=True)
        (args.output/'update.json.sig').write_bytes(base64.b64encode(sig.read_bytes())+b'\n')
    print(json.dumps(m,indent=2))
if __name__=='__main__':main()
