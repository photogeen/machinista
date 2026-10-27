"""Curate real offline-rendered app screens for the public README; no hardware I/O."""
from pathlib import Path
import json
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
def build():
 source=ROOT/'tmp/pdfs/manual-assets/catalog.json'
 if not source.is_file():
  from tools.build_user_manuals import render_assets
  catalog=render_assets()
 else:catalog=json.loads(source.read_text())
 choices={
 'events':'Tutorial / Events range',
 'slicing':'Tutorial / Slice zoom',
 'mixer':'Mixer / scope 1 / field 0',
 'live-fx':'Performance / LIVE FX',
 'chords':'Tutorial / Custom chords',
 'synth':'Native Synth / Presets',
 'synth-filter':'Native Synth / Filter',
 }
 out=ROOT/'assets/screens';out.mkdir(exist_ok=True)
 manifest=[]
 for key,label in choices.items():
  row=next(v for v in catalog if v['label']==label)
  for device in ('mikro','mk2','mk3'):
   im=Image.open(row['paths'][device]);im.save(out/(key+'-'+device+'.png'))
  manifest.append(dict(feature=key,state=label,devices=['mikro','mk2','mk3']))
 from tools.public_synth_capture import capture
 capture(out)
 (out/'README.md').write_text('# Application screens\n\nActual current offline renderer output with illustrative project data. These are\nnot photographs of hardware. Mikro images also represent Mikro MK2; dual\nmonochrome screens represent MK1/MK2, color screens MK3/Maschine+ controller mode.\nNo factory audio or third-party sample files are bundled with these images.\n\nRegenerate from the manual render catalog with `python3 -m tools.build_public_gallery`.\n')
 (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 print('Published gallery:',len(manifest),'features across three display formats')
if __name__=='__main__':build()
