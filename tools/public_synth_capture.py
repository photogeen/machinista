"""Actual first plug-in page with a selected original synth factory patch."""
import copy,json,shutil,tempfile
from pathlib import Path
from PIL import Image

def capture(out):
 from app.model import Application
 from app.plugin_profiles import profile
 from app.synth_library import URI
 from app.controller_inputs import ControllerInputs
 from app.mk2_surface import Mk2Surface
 from app.mk3_surface import Mk3Surface
 from app.mk2_display import Mk2Renderer,snapshot
 from app.mk3_display import Mk3Renderer
 from app.mk3_state import snapshot as color_snapshot
 from app.ni_display import frame
 root=Path(__file__).resolve().parents[1]
 with tempfile.TemporaryDirectory() as tmp:
  folder=Path(tmp)/'presets/plugin-banks/machinista-synth';folder.mkdir(parents=True)
  source=root/'presets/plugin-banks/machinista-synth/category-keys.json';shutil.copyfile(source,folder/source.name)
  bank=json.loads(source.read_text());patch=bank['patches'][0];p=profile(URI);a=Application(tmp)
  a.page='PLUGIN';a.control_level=2;a.plugin_slot=0;a.plugin_param=0
  a.plugin_catalog=[dict(uri=URI,name=p['title'],kind='INSTRUMENT',supported=True,builtin=True,ports=p['parameters'])]
  a.track()['name']='Machinista Synth';a.track()['plugins']=[dict(uri=URI,kind='INSTRUMENT',controls=copy.deepcopy(patch['controls']),profile_preset=dict(bank=source.stem,program=0,name=patch['name']))]
  inputs=ControllerInputs(a);mk2=Mk2Surface(a,inputs);mk3=Mk3Surface(a,inputs);r=Mk2Renderer();rgb=Mk3Renderer()
  try:
   im=Image.new('L',(128,64));im.putdata([(1-v)*255 for v in frame(a)]);im.resize((384,192),Image.Resampling.NEAREST).save(out/'synth-mikro.png')
   pair=Image.new('RGB',(528,64),'#29231e')
   for i,pix in enumerate(r(snapshot(mk2))):
    im=Image.new('L',(256,64));im.putdata([v*255 for v in pix]);pair.paste(im,(i*272,0))
   pair.resize((1584,192),Image.Resampling.NEAREST).save(out/'synth-mk2.png')
   pair=Image.new('RGB',(976,272),'#29231e')
   for i,im in enumerate(rgb.images(color_snapshot(mk3))):pair.paste(im,(i*496,0))
   pair.resize((1952,544),Image.Resampling.NEAREST).save(out/'synth-mk3.png')
  finally:r.close();rgb.close()
