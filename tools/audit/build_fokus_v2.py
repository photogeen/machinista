"""Render real V2 engine states to contact sheets, without any hardware I/O."""
from pathlib import Path
import array,json,math,sys,tempfile,wave
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from PIL import Image,ImageDraw,ImageFont
from tests.test_fokus_v2 import fixture
from app.controller_inputs import ControllerInputs
from app.mk2_surface import Mk2Surface
from app.mk2_display import Mk2Renderer,snapshot
from app.ni_display import frame
from app.waveform import read_envelope
from app.ui_inventory import WORKFLOWS,PAGES

OUT=Path(__file__).resolve().parents[2]/'outputs/fokus-v2-actual'
OUT.mkdir(exist_ok=True)
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',16)
small=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',12)

def image(p,w,mikro=False):
    im=Image.new('L',(w,64));im.putdata([(1-v if mikro else v)*255 for v in p]);return im.convert('RGB')

with tempfile.TemporaryDirectory() as tmp:
    a=fixture(tmp);path=Path(a.track()['sample'])
    with wave.open(str(path),'wb') as wav:
        wav.setparams((1,2,44100,0,'NONE','not compressed'))
        wav.writeframes(array.array('h',(round(math.sin(i*.062)*math.exp(-(i%11025)/2200)*24000) for i in range(44100))).tobytes())
    a.track()['sampler']={'type':'ADSR','attack':100,'decay':300,'sustain':50,'release':400,'filter':'LP2','cutoff':1800}
    envelope=read_envelope(path);surface=Mk2Surface(a,ControllerInputs(a));renderer=Mk2Renderer()
    try:
        # Wait only in this offline audit; live rendering remains asynchronous.
        renderer.waveforms.envelope(path,0,44100)
        if renderer.waveforms.future:renderer.waveforms.future.result()
        catalog=[]
        for group,pages in WORKFLOWS.items():
            unique=list(dict.fromkeys(pages));sheet=Image.new('RGB',(1088,50+len(unique)*205),'#171a1d');d=ImageDraw.Draw(sheet)
            d.text((16,14),'MACHINISTA FOKUS V2 / '+group.upper(),font=font,fill='#e3e7eb')
            for i,page in enumerate(unique):
                a.page=page;a.message='';y=50+i*205
                a.sampler_page=1 if page=='SAMPLER' else a.sampler_page
                state=snapshot(surface);left,right=renderer(state)
                mk2=Image.new('RGB',(528,64));mk2.paste(image(left,256),(0,0));mk2.paste(image(right,256),(272,0))
                mikro=image(frame(a,envelope),128,True)
                slug=page.lower().replace(' ','-');mk2.save(OUT/(slug+'-mk2.png'));mikro.save(OUT/(slug+'-mikro.png'))
                d.text((16,y),page,font=font,fill='#e3e7eb');sheet.paste(mk2.resize((1056,128),Image.Resampling.NEAREST),(16,y+25))
                sheet.paste(mikro.resize((256,128),Image.Resampling.NEAREST),(16,y+25)) if False else None
                d.text((16,y+160),'8 echte Encoder-Bindungen / Engine-Zustand; separate Mikro-Datei mit 128 x 64 Pixeln',font=small,fill='#b3bdc7')
                catalog.append(dict(page=page,mk2=slug+'-mk2.png',mikro=slug+'-mikro.png'))
            sheet.save(OUT/('overview-'+group.lower().replace(' / ','-').replace(' ','-')+'.png'))
        (OUT/'catalog.json').write_text(json.dumps(catalog,indent=2))
        print(len(PAGES),'workspaces rendered from the actual engine')
    finally:renderer.close()
