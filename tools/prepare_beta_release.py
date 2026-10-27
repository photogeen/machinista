#!/usr/bin/env python3
"""Assemble a public image payload from an explicit, personal-data-free file set.

Native executables must have been compiled/tested in the ARM image toolchain.
This tool creates archives/manifests only; it never mounts a disk or edits a Pi.
"""
from pathlib import Path
import argparse,hashlib,json,tarfile,struct,getpass,re
ROOT=Path(__file__).resolve().parents[1]

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--version',required=True);parser.add_argument('--native',type=Path,required=True)
 args=parser.parse_args();version=args.version
 from app.branding import VERSION
 assert version==VERSION,(version,VERSION)
 work=ROOT/'.build'/('beta-'+version);release=ROOT/'releases'/version
 work.mkdir(parents=True,exist_ok=True);release.mkdir(parents=True,exist_ok=True)
 files={}
 def add(p,name=None):
  p=Path(p);name=name or str(p.relative_to(ROOT));assert p.is_file();files[name]=p
 for directory in ('app','web','src','tests','deploy','assets/branding','assets/manual-web','assets/fonts','assets/instrument-art'):
  for p in (ROOT/directory).rglob('*'):
   if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc':add(p)
 for p in (ROOT/'tools').iterdir():
  if p.is_file() and p.suffix in ('.py','.cpp','.cjs') and p.name not in ('install_machinista_branding.py','install_lv2_web.py'):add(p)
 for p in (ROOT/'tools/audit').glob('*.py'):add(p)
 for name in ('WEB_UI.md','USER_MANUALS.md','SOUNDS_AND_AUTOSAMPLER.md','SOUNDFONT_IMPORT.md','MK1_MIDI.md','MK3_SUPPORT.md','LIVE_FX_PITCH.md','BETA_WORKFLOW_SMOKE.md','UPDATER_PLAN.md'):add(ROOT/'docs'/name)
 for p in (ROOT/'output/pdf').glob('Machinista_*_User_Manual_*.pdf'):add(p)
 for name in ('CMakeLists.txt','THIRD_PARTY_NOTICES.md'):add(ROOT/name)
 maps=work/'maps';maps.mkdir(exist_ok=True)
 for name in ('mikro-mk1-pad-led-map.json','mikro-mk1-button-map.json','mikro-mk1-button-led-map.json','maschine-mk2-hardware-map.json'):
  data=json.loads((ROOT/'captures'/name).read_text())
  if isinstance(data,dict):
   data.pop('evidence',None)
   if isinstance(data.get('device'),dict):data['device'].pop('serial',None)
  p=maps/name;p.write_text(json.dumps(data,indent=2)+'\n');add(p,'captures/'+name)
 # Bundle only the declared original Factory bank and its referenced generated tables.
 # Never copy the user's oscillator library or other plugin banks wholesale.
 from tools.factory_payload import factory_files
 for path in factory_files(ROOT):add(path)
 for p in args.native.iterdir():
  if not p.is_file():continue
  body=p.read_bytes();assert body[:4]==b'\x7fELF' and body[4]==2 and struct.unpack_from('<H',body,18)[0]==183,p
  add(p,'build/'+p.name)
 for needed in ('audio_engine','mikro_monitor','mk1_monitor','mk2_monitor'):assert 'build/'+needed in files
 for p in release.glob('*.md'):add(p,p.name)
 add(release/'README.md','BETA-README.txt')
 edition=work/'image-edition.json';edition.write_text(json.dumps(dict(edition='standard',updater=True,channel='release'),indent=2)+'\n');add(edition,'deploy/image-edition.json')
 for name,p in files.items():
  assert not any(part.endswith('.lv2') for part in Path(name).parts),name
  assert p.suffix.lower() not in ('.wav','.mp3','.flac','.rom','.bin','.sound','.xpm'),name
  if p.suffix.lower()=='.syx':assert name=='tests/data/dexed-warm-circuits/Machinista-Warm-Circuits.syx',name
  if p.suffix in ('.py','.cpp','.hpp','.h','.md','.json','.service','.rules'):
   content=p.read_text()
   for private in (str(Path.home()),'/home/'+getpass.getuser(),getpass.getuser()+'@'):assert private not in content,(name,private)
   assert not re.search(r'192[.]168[.]10[.](164|170)\b',content),name
 manifest={name:hashlib.sha256(p.read_bytes()).hexdigest() for name,p in sorted(files.items())}
 with tarfile.open(work/'machinista-payload.tar.gz','w:gz') as tar:
  for name,p in sorted(files.items()):tar.add(p,arcname=name)
 (work/'payload-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 print(json.dumps(dict(version=version,edition='standard',files=len(files),plugins=0,manuals=sum(name.endswith('.pdf') for name in files),payload=str(work/'machinista-payload.tar.gz'))))
if __name__=='__main__':main()
