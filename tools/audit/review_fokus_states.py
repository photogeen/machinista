"""Offline design audit: populated and boundary states, never controller I/O."""
from pathlib import Path
import sys,tempfile,wave,array,math,json
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from PIL import Image,ImageDraw,ImageFont
from tests.test_fokus_v2 import fixture
from app.controller_inputs import ControllerInputs
from app.mk2_surface import Mk2Surface
from app.mk2_display import Mk2Renderer,snapshot
from app.ni_display import frame
from app.waveform import read_envelope
OUT=Path(__file__).resolve().parents[2]/'outputs/fokus-screen-review';OUT.mkdir(exist_ok=True)
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',14)
cases=[('SAMPLER',i) for i in range(6)]+[('ZONE',i) for i in range(5)]+[('CHOP',m) for m in ('SPLIT','GRID','DETECT','MANUAL')]+[(p,None) for p in ('PLUGIN','PLUGIN MOVE','MUTE','SOLO','SELECT','PATTERN GRID','SYSTEM')]
def im(p,w,mikro=False):
 a=Image.new('L',(w,64));a.putdata([255*(1-v if mikro else v) for v in p]);return a.convert('RGB')
with tempfile.TemporaryDirectory() as tmp:
 catalog=[]
 for n,(page,variant) in enumerate(cases):
  a=fixture(tmp);path=Path(a.track()['sample']);path.parent.mkdir(exist_ok=True)
  with wave.open(str(path),'wb') as w:w.setparams((1,2,44100,0,'NONE','not compressed'));w.writeframes(array.array('h',(round(math.sin(i*.06)*20000) for i in range(44100))).tobytes())
  a.track()['sampler']={'type':'ADSR','filter':'LP2','cutoff':2000,'attack':300,'decay':100,'sustain':45,'release':1000}
  if page=='SAMPLER':a.sampler_page=variant
  if page=='ZONE':a.zone_page=variant
  if page=='CHOP':a.slice_mode=variant
  if page in ('PLUGIN','PLUGIN MOVE'):
   a.plugin_catalog=[dict(uri='urn:review:gain',name='Review Gain',kind='EFFECT',supported=True,ports=[dict(index=0,symbol='gain',name='Gain',default=1,min=0,max=2)])]
   a.track()['plugins']=[dict(uri='urn:review:gain',kind='EFFECT',bypass=False,controls={'gain':.7})]
   a.plugin_move_to=2
  if page in ('MUTE','SOLO'):a.project['groups'][0]['pads'][1][page.lower()]=True
  if page=='SELECT':a.selected_pads={0,2,4}
  if page=='PATTERN GRID':a.edit_grid_event()
  if page=='SYSTEM':a.system_stats['storage'].append(dict(name='USB TEST',percent=70,used=7e9,total=10e9))
  a.page=page;s=Mk2Surface(a,ControllerInputs(a));r=Mk2Renderer()
  try:
   r.waveforms.envelope(path,0,44100)
   if r.waveforms.future:r.waveforms.future.result()
   state=snapshot(s);left,right=r(state);pair=Image.new('RGB',(528,64));pair.paste(im(left,256),(0,0));pair.paste(im(right,256),(272,0))
   micro=im(frame(a,read_envelope(path)),128,True);label=page+' '+str(variant if variant is not None else '')
   pair.save(OUT/f'{n:02}-mk2.png');micro.save(OUT/f'{n:02}-mikro.png');catalog.append(dict(label=label,mk2=f'{n:02}-mk2.png',mikro=f'{n:02}-mikro.png'))
  finally:r.close()
 for start in range(0,len(catalog),6):
  rows=catalog[start:start+6];sheet=Image.new('RGB',(1104,len(rows)*230),'#171a1d');d=ImageDraw.Draw(sheet)
  for i,row in enumerate(rows):
   y=i*230;d.text((12,y+4),row['label'],font=font,fill='white');sheet.paste(Image.open(OUT/row['mk2']).resize((1056,128),Image.Resampling.NEAREST),(12,y+25));sheet.paste(Image.open(OUT/row['mikro']),(12,y+160))
  sheet.save(OUT/f'variants-{start//6+1}.png')
 (OUT/'catalog.json').write_text(json.dumps(catalog,indent=2));print(len(catalog),'populated/section states rendered')
