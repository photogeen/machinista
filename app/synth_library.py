"""Original synth waveform catalog. Immutable assets survive catalog deletion."""
import hashlib
import json
import math
import time
from functools import lru_cache
import os
from pathlib import Path
import re
import secrets
import struct
import subprocess
from app.sound_library import folders,tags,name as valid_name

URI='urn:machinista:instrument:synth'
SOURCES=['Off','Velocity','Key','Mod Wheel','Pressure','Random','Amp Env','Filter Env','Pitch Env','Aux Env','LFO 1','LFO 2','Global LFO 1','Global LFO 2','Ramp 1','Ramp 2','Counter 1','Counter 2']
MAX_BYTES=32*1024**2
FACTORY=['Sine','Triangle','Saw','Square','Pulse','Warm Sine','Saw-Square','Noise White','Noise Pink','Odd Harmonics','Even Harmonics','Hollow','Organ Soft','Organ Bright','Reed','Nasal','Metal','Bell','Vowel A','Vowel E','Vowel O','Digital 1','Digital 2','Digital 3','Table Basic','Table Pulse','Table Hollow','Table Organ','Table Vowel','Table Metal','Table Bright','Table Digital']

def folder(root):
    path=Path(root)/'presets/Oscillators'
    if path.is_symlink() or (path/'.assets').is_symlink():raise ValueError('Unsafe oscillator library.')
    return path

def asset(root,identity):
    if not isinstance(identity,str) or not re.fullmatch('[0-9a-f]{32}',identity):raise ValueError('Invalid waveform ID.')
    path=folder(root)/'.assets'/(identity+'.mwave')
    if path.is_symlink():raise ValueError('Unsafe oscillator asset.')
    return path

_catalog_cache={}
def listing(root):
    key=str(root);now=time.monotonic();old=_catalog_cache.get(key)
    if old and now<old[0]:return old[1]
    result=[]
    for path in sorted(folder(root).glob('*.json'))[:512]:
        try:
            if path.is_symlink() or path.stat().st_size>8192:continue
            row=json.loads(path.read_text());identity=row['id']
            if path.stem!=identity or not asset(root,identity).is_file():continue
            valid_name(row['name']);folders(row.get('folder',''));tags(row.get('tags',[]))
            result.append(row)
        except (OSError,ValueError,KeyError,TypeError):continue
    result=sorted(result,key=lambda r:(r.get('folder','').casefold(),r['name'].casefold()));_catalog_cache[key]=(now+1,result);return result

def parse_wav(data,cycle=0,mono=False):
    if len(data)<44 or data[:4]!=b'RIFF' or data[8:12]!=b'WAVE':raise ValueError('Choose an uncompressed WAV file.')
    if struct.unpack_from('<I',data,4)[0]+8>len(data):raise ValueError('Truncated WAV file.')
    fmt=payload=None;offset=12
    while offset+8<=len(data):
        key=data[offset:offset+4];length=struct.unpack_from('<I',data,offset+4)[0];start=offset+8
        if start+length>len(data):raise ValueError('Truncated WAV chunk.')
        if key==b'fmt ':fmt=data[start:start+length]
        if key==b'data':payload=data[start:start+length]
        offset=start+length+(length&1)
    if fmt is None or len(fmt)<16 or payload is None:raise ValueError('Missing WAV format or audio.')
    kind,channels,rate,_,align,bits=struct.unpack_from('<HHIIHH',fmt)
    if kind==65534:
        if len(fmt)<40:raise ValueError('Invalid extensible WAV.')
        kind=struct.unpack_from('<H',fmt,24)[0]
    if channels not in (1,2) or channels==2 and not mono:raise ValueError('Choose mono WAV or enable stereo to mono conversion.')
    if kind not in (1,3) or bits not in (16,24,32) or kind==3 and bits!=32 or align!=channels*(bits//8) or len(payload)%align or not 8000<=rate<=192000:raise ValueError('Unsupported waveform WAV encoding.')
    size=cycle or len(payload)//align
    if size<32 or size>16384:raise ValueError('Cycle size must be between 32 and 16384 samples.')
    count=len(payload)//align
    if count%size or not 1<=count//size<=256:raise ValueError('WAV length must match 1–256 complete cycles. Check the cycle size.')
    result=bytearray(b'MWAVE001'+struct.pack('<II',count//size,size));width=bits//8
    for i in range(count):
        value=0
        for ch in range(channels):
            pos=(i*channels+ch)*width;sample=payload[pos:pos+width]
            v=struct.unpack('<f',sample)[0] if kind==3 else int.from_bytes(sample,'little',signed=True)/(2**(bits-1))
            if not math.isfinite(v) or abs(v)>8:raise ValueError('Waveform contains invalid or excessively loud values.')
            value+=v/channels
        result.extend(struct.pack('<f',value))
    return bytes(result),dict(frames=count//size,cycle=size,rate=rate,kind='Wavetable' if count//size>1 else 'Single Cycle')

def upload(root,filename,stream,length,cycle=0,mono=False,category='',tag_values=None):
    if not filename.lower().endswith('.wav') or not 0<length<=MAX_BYTES:raise ValueError('Choose a WAV up to 32 MiB.')
    data=stream.read(length)
    if len(data)!=length:raise ValueError('Incomplete waveform upload.')
    prepared,details=parse_wav(data,cycle,mono);identity=hashlib.sha256(prepared).hexdigest()[:32]
    row=dict(schema=1,id=identity,name=valid_name(Path(filename).stem),folder=folders(category),tags=tags(tag_values or []),**details)
    base=folder(root);base.mkdir(parents=True,exist_ok=True);(base/'.assets').mkdir(exist_ok=True)
    path=asset(root,identity)
    if not (base/(identity+'.json')).exists() and len(listing(root))>=512:raise ValueError('Maximum 512 user waveforms. Remove an unused entry first.')
    disk=os.statvfs(base)
    if disk.f_bavail*disk.f_frsize<len(prepared)*12+len(data)+256*1024**2:raise ValueError('Not enough free space for waveform preparation (256 MiB reserved).')
    if not path.exists():
        temporary=base/'.assets'/('.'+secrets.token_hex(16))
        try:
            with temporary.open('xb') as f:f.write(prepared);f.flush();os.fsync(f.fileno())
            engine=Path(root)/'build/audio_engine'
            if engine.is_file():
                rendered=temporary.with_name(temporary.name+'.prepared')
                try:
                    process=subprocess.run([str(engine),'--synth-prepare',str(temporary),str(rendered)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=90)
                    if process.returncode or not rendered.is_file() or rendered.stat().st_size<16:raise ValueError('Waveform preparation failed.')
                    os.replace(rendered,temporary)
                finally:rendered.unlink(missing_ok=True)
            os.replace(temporary,path)
        finally:temporary.unlink(missing_ok=True)
    original=base/'.assets'/(identity+'.wav')
    if not original.exists():
        with original.open('xb') as f:f.write(data)
    manifest=base/(identity+'.json');temporary=base/('.'+secrets.token_hex(16))
    try:
        temporary.write_text(json.dumps(row,indent=2)+'\n');os.replace(temporary,manifest)
    finally:temporary.unlink(missing_ok=True)
    _catalog_cache.clear();return row

def edit(root,identity,value):
    if not isinstance(value,dict):raise ValueError('Invalid waveform metadata.')
    asset(root,identity);path=folder(root)/(identity+'.json')
    if path.is_symlink():raise ValueError('Unsafe waveform entry.')
    row=json.loads(path.read_text());row.update(name=valid_name(value.get('name',row['name'])),folder=folders(value.get('folder',row.get('folder',''))),tags=tags(value.get('tags',row.get('tags',[]))))
    temp=path.with_name('.'+secrets.token_hex(16))
    try:temp.write_text(json.dumps(row,indent=2)+'\n');os.replace(temp,path)
    finally:temp.unlink(missing_ok=True)
    _catalog_cache.clear();return row

def delete(root,identity):
    asset(root,identity);path=folder(root)/(identity+'.json')
    if path.is_symlink():raise ValueError('Unsafe waveform entry.')
    path.unlink();_catalog_cache.clear();return dict(ok=True)

# Port metadata and matrix destination labels are immutable. Building them in
# every input dispatch used to cost ~170 ms per MK2 knob report on a Pi 4.
# Keep a bounded layout cache, retaining the metadata owner against id reuse.
_layout_cache=[]
def _control_layout(app,selected,ports):
    for owner,layout,special in _layout_cache:
        if owner is ports:return layout,special
    from app.plugin_profiles import controls as generic
    result=[];special=[]
    for index,port in enumerate(generic(app,selected,ports,False)):
        v=dict(port);symbol=v['symbol']
        if re.fullmatch('mod[0-9]+_target',symbol):
            v['choices']=[(i,label.replace('_',' ').upper()) for i,label in v.get('choices',[])]
        match=re.fullmatch(r'osc([1-4])_(wave|shape|xfade|direction|phase|free|random_phase)',symbol)
        if match:special.append((index,*match.groups()))
        if symbol.startswith('@'):special.append((index,'',symbol))
        result.append(v)
    layout=tuple(result);special=tuple(special)
    _layout_cache.append((ports,layout,special))
    if len(_layout_cache)>4:del _layout_cache[0]
    return layout,special

def controls(app,selected,ports):
    from app.plugin_profiles import profile,selection
    rows=listing(app.root);available,bank,patch=selection(app.root,selected,profile(URI))
    values=selected.get('controls',{});waves=selected.get('synth_waves',{})
    wave_state=tuple((values.get(f'osc{o}_wave',2 if o==1 else 0),
                      tuple(waves.get(str(o),{}).get(k) for k in ('id','name','frames','cycle'))) for o in range(1,5))
    # Ordinary parameter values are read directly by the surface. Only source
    # selection, library/bank changes and preset selection affect this layout.
    key=(str(app.root),bank,patch,selected.get('profile_preset',{}).get('name'),wave_state)
    old=getattr(app,'_synth_controls_cache',None)
    if old and old[0] is selected and old[1] is ports and old[2] is rows and old[3] is available and old[4]==key:
        return list(old[5])
    base,special=_control_layout(app,selected,ports);result=list(base)
    chosen=available[bank] if bank is not None else None
    for index,osc,kind in special:
        v=dict(base[index]);result[index]=v
        if kind.startswith('@'):
            is_bank=kind=='@bank';items=available if is_bank else chosen['patches'] if chosen else []
            v.update(default=(bank if bank is not None else 0) if is_bank else patch,
                     max=max(0,len(items)-1),choices=list(enumerate(item['name'] for item in items)))
            if chosen is None:v.update(default=-1,choices=[(-1,'MISSING BANK')])
            continue
        stored=waves.get(osc,{});wave=values.get(f'osc{osc}_wave',2 if osc=='1' else 0)
        row=next((r for r in rows if r['id']==stored.get('id')),None)
        if kind=='wave':
            labels=FACTORY+[r.get('folder','')+'/'+r['name'] if r.get('folder') else r['name'] for r in rows]
            choice=wave
            if choice==32:
                choice=next((i+32 for i,r in enumerate(rows) if r['id']==stored.get('id')),None)
                if choice is None:labels.append('SAVED: '+stored.get('name','MISSING USER WAVE'));choice=len(labels)-1
            v.update(default=choice,min=0,max=len(labels)-1,choices=list(enumerate(labels)),profile_action='synth_wave',integer=True,choice=True)
            continue
        table=24<=wave<=31 or wave==32 and (row or stored).get('frames',1)>1
        if kind=='shape':v['name']='POSITION' if table else 'PULSE WIDTH' if wave==4 else 'SHAPE'
        inactive=(kind=='shape' and wave not in (4,6) and not table or kind=='xfade' and not table or kind=='direction' and wave!=2 or kind in ('phase','free','random_phase') and wave in (7,8))
        if inactive:v['synth_inactive']=True
    result=tuple(result)
    app._synth_controls_cache=(selected,ports,rows,available,key,result)
    return list(result)

def rotate_wave(app,selected,port,delta):
    rows=listing(app.root);symbol=port['symbol'];old=int(port['default']);index=max(0,min(31+len(rows),old+delta))
    if index==old:return True
    app.remember();selected['controls'][symbol]=index if index<32 else 32
    if index>=32:
        row=rows[index-32];selected.setdefault('synth_waves',{})[symbol[3]]=dict(id=row['id'],name=row['name'],frames=row['frames'],cycle=row['cycle'])
    app.plugin_update();return True


def validate_preset_waves(controls,waves):
    """Bank waveform references are asset IDs, never file paths or URLs."""
    if not isinstance(waves,dict) or len(waves)>4:raise ValueError('Invalid preset waveforms.')
    for osc,row in waves.items():
        if osc not in ('1','2','3','4') or not isinstance(row,dict):raise ValueError('Invalid preset oscillator.')
        if not isinstance(row.get('id'),str) or not re.fullmatch('[0-9a-f]{32}',row['id']):raise ValueError('Invalid preset waveform ID.')
        if not isinstance(row.get('name'),str) or not 1<=len(row['name'])<=160:raise ValueError('Invalid preset waveform name.')
        if type(row.get('frames')) is not int or not 1<=row['frames']<=256 or type(row.get('cycle')) is not int or not 32<=row['cycle']<=16384:raise ValueError('Invalid preset waveform dimensions.')
    for osc in ('1','2','3','4'):
        if controls.get(f'osc{osc}_wave')==32 and osc not in waves:raise ValueError('Preset waveform reference missing.')
    return waves


def preset_waves(root,preset):
    import copy
    waves=validate_preset_waves(preset['controls'],preset.get('synth_waves',{}))
    for osc,row in waves.items():
        if preset['controls'].get(f'osc{osc}_wave')==32 and not asset(root,row['id']).is_file():
            raise ValueError('Preset waveform missing: '+row['name'])
    return copy.deepcopy(waves)
