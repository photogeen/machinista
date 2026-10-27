"""Read-only controller UX audit, actual renderers and temporary example data."""
from pathlib import Path
import array,html,json,math,os,sys,tempfile,wave
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from PIL import Image,ImageDraw,ImageFont
from tests.test_fokus_v2 import fixture
from app.controller_inputs import ControllerInputs
from app.mk2_surface import Mk2Surface
from app.mk2_display import Mk2Renderer,snapshot
from app.ni_display import frame
from app.waveform import read_envelope
from app.fokus import Canvas
from app.sampler import SAMPLER_PAGES,ZONE_PAGES
from tools.audit.fokus_fein_cases import cases,apply
OUT=Path(__file__).resolve().parents[2]/'outputs'/os.environ.get('UX_REVIEW_OUTPUT','ux-review-2026-10-13');OUT.mkdir(exist_ok=True)
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',14)
def bitmap(p,width,mikro=False):return Image.frombytes('L',(width,64),bytes(255*(1-v if mikro else v) for v in p)).convert('RGB')
rows=[];base=[];seen=set();nav=[]
with tempfile.TemporaryDirectory() as tmp:
 sample=Path(tmp)/'samples/example.wav';sample.parent.mkdir()
 with wave.open(str(sample),'wb') as f:
  f.setparams((1,2,44100,0,'NONE','not compressed'));f.writeframes(array.array('h',(round(math.sin(i*.06)*22000) for i in range(44100))).tobytes())
 envelope=read_envelope(sample)
 for n,(label,page,values) in enumerate(cases()):
  a=fixture(tmp);a.track()['sampler']={'type':'ADSR','filter':'LP2','cutoff':1800};s=Mk2Surface(a,ControllerInputs(a));apply(a,s,page,values);r=Mk2Renderer()
  try:
   r.waveforms.envelope(sample,0,44100)
   if r.waveforms.future:r.waveforms.future.result()
   left,right=r(snapshot(s));micro=bitmap(frame(a,envelope),128,True)
   pair=Image.new('RGB',(528,64));pair.paste(bitmap(left,256),(0,0));pair.paste(bitmap(right,256),(272,0))
   micro.save(OUT/f'{n:03}-mikro.png');pair.save(OUT/f'{n:03}-mk2.png')
   row=dict(label=label,page=page,mikro=f'{n:03}-mikro.png',mk2=f'{n:03}-mk2.png');rows.append(row)
   if page not in seen:seen.add(page);base.append(row)
  finally:r.close()
 for origin,total in (('SAMPLER',6),('CHANNEL',4),('ZONE',5)):
  for index in range(total):
   a=fixture(tmp);a.page=origin
   if origin=='SAMPLER':a.sampler_page=index;section=SAMPLER_PAGES[index][0]
   elif origin=='CHANNEL':a.channel_page=index;section=('AUDIO','AUX 1','AUX 2','MIDI')[index]
   else:a.zone_page=index;section=ZONE_PAGES[index][0]
   a.button('NAV',True)
   image=bitmap(frame(a,envelope),128,True);name=f'nav-{origin.lower()}-{index+1}.png';image.save(OUT/name)
   nav.append(dict(origin=origin,section=section,held_page=a.page,file=name))
 for title,section,index,total in (('SAMPLER','FX / FILTER',2,6),('OUTPUT','AUX 1',1,4),('ZONE','LOOP',1,5)):
  c=Canvas();c.header(('-','CHNL.','PLUG-IN') if title!='ZONE' else ('RECORD','EDIT','SLICE'))
  c.title(title,f'{index+1}/{total}');c.text(4,29,section,120,font='regular7');c.text(4,40,'SOUND A:01',120)
  c.field('NAV RELEASE','OPEN');bitmap(c.finish(),128,True).resize((512,256),Image.Resampling.NEAREST).save(OUT/('proposal-'+title.lower()+'.png'))
for device in ('mikro','mk2'):
 for start in range(0,len(base),12):
  group=base[start:start+12];w=272 if device=='mikro' else 544;h=166 if device=='mikro' else 102
  sheet=Image.new('RGB',(w*3,h*4),'#171a1d');draw=ImageDraw.Draw(sheet)
  for i,row in enumerate(group):
   x=i%3*w;y=i//3*h;draw.text((x+5,y+3),row['page'],font=font,fill='white');im=Image.open(OUT/row[device])
   if device=='mikro':im=im.resize((256,128),Image.Resampling.NEAREST)
   sheet.paste(im,(x+5,y+25))
  sheet.save(OUT/f'{device}-overview-{start//12:02}.png')
(OUT/'catalog.json').write_text(json.dumps(dict(workspaces=base,variants=rows,nav=nav),indent=2))
options=''.join(f'<option value="{i}">{html.escape(row["label"])}</option>' for i,row in enumerate(rows))
(OUT/'index.html').write_text('''<!doctype html><meta charset="utf-8"><title>Machinista UX review</title><style>body{background:#171a1d;color:white;font:16px system-ui;margin:24px}img{image-rendering:pixelated;display:block;margin:24px 0;max-width:100%}#mikro{width:512px}#mk2{width:1056px}select{padding:8px;max-width:100%}</style><h1>Machinista · UX-Prüfung</h1><p>Aktuelle echte Renderer; Beispieldaten. Keine Änderungen an der Bedienung.</p><select id="choose">'''+options+'''</select><img id="mikro"><img id="mk2"><script>const rows='''+json.dumps(rows)+''';let s=document.getElementById('choose');s.onchange=()=>{let r=rows[+s.value];document.getElementById('mikro').src=r.mikro;document.getElementById('mk2').src=r.mk2};s.onchange()</script>''')
print(len(base),'workspaces;',len(rows),'variants;',len(nav),'held NAV cases')
