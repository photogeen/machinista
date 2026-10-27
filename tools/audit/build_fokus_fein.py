"""Render every MK2 workspace/variant using the installed renderer, offline."""
from pathlib import Path
import sys,tempfile,wave,array,math,json,html,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from PIL import Image,ImageDraw,ImageFont
from tests.test_fokus_v2 import fixture
from tools.audit.fokus_fein_cases import cases,apply
from app.controller_inputs import ControllerInputs
from app.mk2_surface import Mk2Surface
from app.mk2_display import Mk2Renderer,snapshot
from app.waveform import Envelope
from unittest.mock import Mock

OUT=Path(__file__).resolve().parents[2]/'outputs/fokus-fein-mk2';OUT.mkdir(exist_ok=True)
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',16)
rows=[]
with tempfile.TemporaryDirectory() as tmp:
    sample=Path(tmp)/'samples/example.wav';sample.parent.mkdir(exist_ok=True)
    with wave.open(str(sample),'wb') as f:
        f.setparams((1,2,44100,0,'NONE','not compressed'));f.writeframes(array.array('h',(round(math.sin(i*.065)*math.exp(-(i%11025)/2400)*26000) for i in range(44100))).tobytes())
    (sample.parent/'Library').mkdir(exist_ok=True)
    for filename in ('Kick 01.wav','Snare 01.wav','Very long sample filename for boundary review.wav'):(sample.parent/filename).write_bytes(sample.read_bytes())
    for n,(label,page,values) in enumerate(cases()):
        a=fixture(tmp);a.message='';a.track()['name']='DESERT WIND';a.project['name']='RAPID SAND'
        a.track()['sampler']={'type':'ADSR','filter':'EQ','cutoff':2400,'resonance':32,'attack':100,'decay':300,'sustain':50,'release':400}
        a.track().update(start=4800,end=37200)
        surface=Mk2Surface(a,ControllerInputs(a));apply(a,surface,page,values)
        if page=='BROWSE':a.browser.directory=sample.parent;a.browser.index=3;a.browser.prehear=True
        r=Mk2Renderer()
        try:
            r.waveforms.envelope(sample,0,44100)
            if r.waveforms.future:r.waveforms.future.result()
            state=snapshot(surface);pixels=r(state);pair=Image.new('L',(528,64))
            for i,p in enumerate(pixels):
                assert not any(p[61*256:]),label
                pair.paste(Image.frombytes('L',(256,64),bytes(255*v for v in p)),(i*272,0))
            file=f'{n:03}-{page.lower().replace(" ","-")}.png';pair.save(OUT/file)
            rows.append(dict(label=label,page=page,file=file,fields=[f for f in state['fields']],sha256=hashlib.sha256(b''.join(pixels)).hexdigest()))
        finally:r.close()
for start in range(0,len(rows),8):
    group=rows[start:start+8];sheet=Image.new('RGB',(1080,len(group)*160),'#171a1d');d=ImageDraw.Draw(sheet)
    for i,row in enumerate(group):
        y=i*160;d.text((12,y+5),row['label'],font=font,fill='white');sheet.paste(Image.open(OUT/row['file']).resize((1056,128),Image.Resampling.NEAREST),(12,y+27))
    sheet.save(OUT/f'contact-{start//8:02}.png')
(OUT/'catalog.json').write_text(json.dumps(rows,indent=2))
# A complete local gallery; no live device or network dependency.
options=''.join(f'<option value="{i}">{html.escape(row["label"])}</option>' for i,row in enumerate(rows))
(OUT/'index.html').write_text('''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Fokus fein – MK2</title>
<style>body{background:#171a1d;color:#eee;font:16px system-ui;margin:24px}select{max-width:100%;padding:8px}img{width:100%;max-width:1584px;image-rendering:pixelated;margin-top:24px}button{padding:8px;margin:8px}p{color:#bbc4cc}</style>
<h1>Fokus fein · alle MK2-Ansichten</h1><p>Offline-Render aus dem tatsächlichen Code. Beispieldaten, keine Hardwareaufnahmen.</p><button id="prev">Zurück</button><select id="choose">'''+options+'''</select><button id="next">Weiter</button><div><img id="lcd" alt="Beide MK2-Displays"></div><p id="label"></p><script>
const rows='''+json.dumps(rows)+''';const choice=document.getElementById('choose');function show(){let row=rows[+choice.value];document.getElementById('lcd').src=row.file;document.getElementById('label').textContent=(+choice.value+1)+' / '+rows.length+' · '+row.label}choice.onchange=show;for(const [id,delta] of [['prev',-1],['next',1]])document.getElementById(id).onclick=()=>{choice.value=String((+choice.value+delta+rows.length)%rows.length);show()};show();</script>''')
print(len(rows),'states;',len(set(row['page'] for row in rows)),'workspaces;',len(list(OUT.glob('contact-*.png'))),'contact sheets')
