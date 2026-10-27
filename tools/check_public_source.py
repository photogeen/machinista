#!/usr/bin/env python3
"""Audit a prepared public tree; never deletes or rewrites its files."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
RUNTIME={'build','.build','.git','.venv','__pycache__','.pytest_cache'}
PRIVATE={'output','outputs','tmp','backups','releases','diagnostics','config','projects','samples','cache','exports'}
FIXTURE='tests/data/dexed-warm-circuits/Machinista-Warm-Circuits.syx'
FORBIDDEN={'.wav','.mp3','.flac','.rom','.bin','.img','.raw','.so','.o','.a','.pem','.key','.pyc'}
TEXT={'.py','.cpp','.hpp','.h','.md','.json','.service','.rules','.txt','.yml','.yaml','.cjs','.js','.html','.css','.conf'}

def audit(root):
    root=Path(root).resolve();errors=[];files={}
    for path in sorted(root.rglob('*')):
        relative=path.relative_to(root);parts=relative.parts
        if any(v in RUNTIME for v in parts):continue
        if parts[0] in PRIVATE:
            if path.is_dir() and len(parts)==1:errors.append(str(relative)+': local data directory')
            continue
        if path.is_symlink():errors.append(str(relative)+': symlink');continue
        if path.is_dir():
            if path.name.endswith('.lv2'):errors.append(str(relative)+': external plug-in bundle')
            continue
        if not path.is_file():continue
        name=str(relative);suffix=path.suffix.lower();body=path.read_bytes()
        if suffix in FORBIDDEN or suffix=='.syx' and name!=FIXTURE or name.endswith('.img.xz'):
            errors.append(name+': excluded binary/user data')
        if path.name.startswith(('id_rsa','id_ed25519')) or path.name=='.env' or path.name.startswith('.env.') and path.name!='.env.example':
            errors.append(name+': credential filename')
        if len(body)>10*1024**2:errors.append(name+': larger than 10 MiB; use release assets')
        if body.startswith((b'\x7fELF',b'MZ',b'\xcf\xfa\xed\xfe',b'\xfe\xed\xfa\xcf')):errors.append(name+': native executable')
        if suffix in TEXT or path.name.startswith(('README','LICENSE','COPYING')):
            try:text=body.decode('utf-8')
            except UnicodeDecodeError:errors.append(name+': non-UTF8 source text');continue
            patterns={
                'developer home path':r'/Us'+r'ers/[^/\s]+|/home/'+('eu'+'gen')+r'\b',
                'development connection':r'192[.]168[.]10[.](?:164|170)\b|'+('eu'+'gen')+r'@',
                'private key':r'-----BEGIN (?:OPENSSH |RSA |EC |DSA |ENCRYPTED )?PRIVATE KEY-----',
                'GitHub credential':r'\bgh[pousr]_[A-Za-z0-9]{30,}|\bgithub_pat_[A-Za-z0-9_]{40,}',
            }
            # The scanner contains regexes, never complete keys or host identities.
            for reason,pattern in patterns.items():
                if re.search(pattern,text):errors.append(name+': '+reason)
            if suffix=='.json':
                try:
                    data=json.loads(text)
                    def inspect(value):
                        if isinstance(value,dict):
                            for key,item in value.items():
                                if key.lower() in ('serial','serial_number','wifi_password','private_key') and item not in (None,'',False):errors.append(name+': identifying/secret JSON field '+key)
                                inspect(item)
                        elif isinstance(value,list):
                            for item in value:inspect(item)
                    inspect(data)
                except ValueError:errors.append(name+': invalid JSON')
        files[name]=hashlib.sha256(body).hexdigest()
    return dict(ok=not errors,files=len(files),bytes=sum((root/p).stat().st_size for p in files),errors=errors,sha256=files)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=ROOT);parser.add_argument('--report',type=Path)
    args=parser.parse_args();report=audit(args.root)
    if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='sha256'},indent=2))
    return 0 if report['ok'] else 1

if __name__=='__main__':sys.exit(main())
