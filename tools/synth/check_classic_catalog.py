"""Validate/import classic banks and protect the previous 160 programs."""
import hashlib,json,tarfile,tempfile,zipfile
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from app.plugin_profiles import profile,validate_bank
from app.plugin_bank_import import import_bank
P=profile('urn:machinista:instrument:synth')
def check():
 manifest=json.loads((ROOT/'output/native-synth/classic-banks/manifest.json').read_text());names=set();files=[]
 with tempfile.TemporaryDirectory() as td,tarfile.open(ROOT/'backups/classic-banks-160-before/banks.tar.gz') as prior:
  for entry in manifest:
   path=ROOT/entry['file'];data=validate_bank(json.loads(path.read_text()),P)
   assert len(data['patches'])==32
   if entry['file'] in prior.getnames():assert prior.extractfile(entry['file']).read()==path.read_bytes(),entry['name']
   for p in data['patches']:
    assert p['name'] not in names;names.add(p['name'])
   imported=import_bank(Path(td),P['id'],path.name,path.read_bytes());assert imported['patches']==32
   files.append(dict(file=entry['file'],sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
 assert len(manifest)==8 and len(names)==256
 dest=ROOT/'output/presets/Machinista-Classic-Banks.zip';dest.parent.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
  for entry in manifest:z.write(ROOT/entry['file'],entry['name'].replace(' ','-')+'.json')
  z.write(ROOT/'docs/synth/CLASSIC_BANKS.md','Patch-Guide.md')
  z.writestr('README.txt','Machinista Synth: eight banks of 32 original patches.\nOn a fresh system: WebUI > LV2 > preset bank import > Machinista Synth, then upload each JSON.\nSelect BANK and PATCH on the controller or WebUI Synth. No LV2 is required.\nIf these banks are already installed, do not import again: the in-place application update preserves existing bank IDs and programs.\nRead Patch-Guide.md for inspirations and limitations.\n')
 result=dict(banks=8,patches=256,original_programs_preserved=160,imports_passed=8,files=files,zip=str(dest))
 (ROOT/'output/native-synth/classic-banks-256/catalog-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':check()
