"""Small immutable waveform/envelope snapshots; renderer does no file I/O."""
import json
import math
from functools import lru_cache
from pathlib import Path
import struct
from app.synth_library import URI,FACTORY,asset

@lru_cache(maxsize=1)
def factory():return json.loads((Path(__file__).resolve().parents[1]/'assets/synth-waves.json').read_text())

@lru_cache(maxsize=12)
def user_preview(root,identity,fallback="",version=0):
    path=asset(root,identity)
    if not path.is_file() and fallback:path=Path(fallback)
    try:
        if path.stat().st_size>17*1024**2:return []
        data=path.read_bytes();count,size=struct.unpack_from('<II',data,8)
        if data[:8] not in (b'MWAVE001',b'MWAVET02') or not 1<=count<=256 or not 32<=size<=16384 or len(data)!=16+4*count*size*(10 if data[:8]==b'MWAVET02' else 1):return []
        return [[struct.unpack_from('<f',data,16+4*(f*size*(10 if data[:8]==b'MWAVET02' else 1)+min(size-1,i*size//64)))[0] for i in range(64)] for f in range(count)]
    except (OSError,ValueError,struct.error):return []

def view(app):
    if app.page!='PLUGIN':return None
    selected=app.plugin_selected()
    if not selected or selected['uri']!=URI:return None
    controls=app.plugin_controls()
    if not controls:return None
    port=controls[min(app.plugin_param,len(controls)-1)];section=port.get('section','SYNTH');c=selected.get('controls',{})
    if section.startswith('OSC '):
        osc=section[4];prefix=f'osc{osc}_';w=max(0,min(32,int(c.get(prefix+'wave',2 if osc=='1' else 0))));shape=max(0,min(1,c.get(prefix+'shape',.5)));xfade=max(0,min(1,c.get(prefix+'xfade',1)))
        row=selected.get('synth_waves',{}).get(osc,{})
        fallback=str(Path(selected['state']).parent/f'osc{osc}.mwave') if selected.get('state') else ''
        version=0
        if w==32 and row.get('id'):
            try:version=(asset(app.root,row['id']) if asset(app.root,row['id']).is_file() else Path(fallback)).stat().st_mtime_ns
            except OSError:pass
        frames=user_preview(str(app.root),row['id'],fallback,version) if w==32 and row.get('id') else factory()[w] if w<32 else []
        title=f'OSC {osc} / '+(row.get('name','MISSING USER WAVE') if w==32 else FACTORY[w])
        if not frames:return dict(title=title,points=(),missing=True)
        pos=shape*(len(frames)-1);a=int(pos);b=min(a+1,len(frames)-1);t=pos-a;t=0 if xfade<=0 else max(0,min(1,(t-(1-xfade)/2)/xfade))
        points=[(1-t)*frames[a][i]+t*frames[b][i] for i in range(64)]
        if w==4:points=[.85 if i/64<.02+.96*shape else -.85 for i in range(64)]
        elif w==6:points=[(1-shape)*factory()[6][0][i]+shape*factory()[3][0][i] for i in range(64)]
        if w==2 and c.get(prefix+'direction',0):points=points[::-1]
        return dict(title=title,points=tuple(points),missing=False,phase=None if c.get(prefix+'free',0) or w in (7,8) else c.get(prefix+'phase',0))
    if 'ENV' in section:
        index=2 if section=='AMP / FILTER ENV' and port['symbol'].startswith('env2_') else 1 if section.startswith('AMP') else 2 if section.startswith('FILTER') else 3 if section.startswith('PITCH') else 4;pre=f'env{index}_'
        times=[c.get(pre+k,d) for k,d in [('delay',0),('attack',5),('hold',0),('decay',250),('release',200)]];sustain=c.get(pre+'sustain',.8 if index==1 else 0)
        points=[];segments=[(times[0],0,0),(times[1],0,1),(times[2],1,1),(times[3],1,sustain),(max(50,sum(times)*.2),sustain,sustain),(times[4],sustain,0)];total=max(1,sum(t for t,_,_ in segments))
        for i in range(64):
            t=i*total/63;value=0
            for duration,a,b in segments:
                if duration>0 and t<=duration:value=a+(b-a)*(t/duration)**(3**(-c.get(pre+'curve',0)));break
                t-=duration
            points.append(value*1.8-.9)
        return dict(title=section,points=tuple(points),missing=False)
    if section in ('FILTER 1','FILTER 2'):
        pre='filter'+section[-1]+'_';kind=int(c.get(pre+'type',1 if section[-1]=='1' else 0));cut=c.get(pre+'cutoff',12000);res=c.get(pre+'resonance',.1);points=[]
        for i in range(64):
            frequency=20*1000**(i/63);w=frequency/max(20,cut);den=math.sqrt((1-w*w)**2+(2-1.95*res)**2*w*w)
            magnitude=1 if not kind else (1 if kind<=2 else w*w if kind<=4 else w if kind<=6 else abs(1-w*w))/max(.0001,den)
            if kind and kind%2==0:magnitude*=magnitude
            db=20*math.log10(max(.001,magnitude));points.append(max(-1,min(1,(db+24)/36)))
        return dict(title=section,points=tuple(points),missing=False)
    if 'LFO' in section:
        index=(3 if section.startswith('GLOBAL') else 1)+(1 if section.endswith('2') else 0);pre=f'lfo{index}_';shape=int(c.get(pre+'wave',0))
        points=[]
        for i in range(64):
            x=(i/64+c.get(pre+'phase',0))%1;points.append(math.sin(math.tau*x) if shape==0 else 1-4*abs(x-.5) if shape==1 else 2*x-1 if shape==2 else 1-2*x if shape==3 else 1 if shape==4 and x<.5 else -1 if shape==4 else math.sin(int(x*8)*73.1))
        return dict(title=section,points=tuple(v*c.get(pre+'level',1) for v in points),missing=False)
    if section.startswith('MOD MATRIX'):
        from app.synth_library import SOURCES
        index=int(section.rsplit(' ',1)[-1]);pre=f'mod{index}_'
        targets=next(p['choices'] for p in app.plugin_metadata(URI)['ports'] if p['symbol']==pre+'target')
        target=dict(targets).get(c.get(pre+'target',0),'Off').replace('_',' ').upper()
        return dict(title=section,route=(SOURCES[max(0,min(len(SOURCES)-1,int(c.get(pre+'source',0))))].upper(),target),amount=c.get(pre+'amount',0))
    return dict(title=section,levels=tuple(c.get(f'osc{i}_level',.65 if i==1 else 0)*c.get(f'osc{i}_on',1) for i in range(1,5)))

def draw(canvas,state,y=27,height=17):
    width=canvas.w-8;canvas.rect(3,y,width+2,height,canvas.bg)
    if state.get('missing'):canvas.fitted(4,y+4,'MISSING WAVE / CHOOSE SOURCE',width);return
    if 'route' in state:
        source,target=state['route'];half=(width-12)//2
        canvas.rect(4,y+1,half,height-2,canvas.ink,False);canvas.rect(4+half+12,y+1,half,height-2,canvas.ink,False)
        canvas.fitted(6,y+height//2-2,source,half-4);canvas.fitted(6+half+12,y+height//2-2,target,half-4)
        x=4+half;middle=y+height//2;canvas.line(x,middle,x+10,middle);canvas.line(x+7,middle-3,x+10,middle);canvas.line(x+7,middle+3,x+10,middle)
        return
    if 'levels' in state:
        for i,value in enumerate(state['levels']):
            x=4+i*width//4;canvas.text(x+2,y,str(i+1),12);canvas.rect(x+16,y+1,max(1,round((width//4-20)*max(0,min(1,value)))),height-3)
        return
    points=state['points'];middle=y+height//2;amplitude=max(1,height//2-1)
    for i in range(0,width,4):canvas.rect(4+i,middle,1,1)
    last=None
    for i,v in enumerate(points):
        x=4+i*(width-1)//max(1,len(points)-1);yy=middle-round(max(-1,min(1,v))*amplitude)
        if last is not None:
            steps=max(abs(x-last[0]),abs(yy-last[1]),1)
            for n in range(steps+1):canvas.rect(round(last[0]+(x-last[0])*n/steps),round(last[1]+(yy-last[1])*n/steps),1,1)
        last=(x,yy)
    if state.get('phase') is not None:
        x=4+round((state['phase']%1)*(width-1))
        for yy in range(y,y+height,2):canvas.rect(x,yy,1,1)
