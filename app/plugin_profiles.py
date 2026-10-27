"""Declarative plugin layouts and host-managed parameter-bank selection.

Only the application thread reads bank files. Audio receives numeric snapshots;
neither the real-time renderer nor detached display workers open these files.
"""
import copy
import json
import time
from functools import lru_cache
from pathlib import Path

DATA=Path(__file__).with_name('plugin_profiles_data')
_cache={}
_live_banks={}

@lru_cache(maxsize=1)
def profiles():
    return tuple(json.loads(p.read_text()) for p in sorted(DATA.glob('*.json')))

def profile(uri):return next((p for p in profiles() if p['uri']==uri),None)

def bank_folder(root,p):return Path(root)/'presets/plugin-banks'/p['id']

def validate_bank(data,p):
    import math
    if not isinstance(data,dict) or data.get('schema')!=1 or data.get('uri')!=p['uri']:raise ValueError('Wrong plugin bank format')
    if not isinstance(data.get('name'),str) or not data['name'].strip() or len(data['name'])>128:raise ValueError('Invalid bank name')
    patches=data.get('patches');specs={v['symbol']:v for v in p['parameters']}
    if not isinstance(patches,list) or not 1<=len(patches)<=(512 if p['uri']=='urn:machinista:instrument:synth' else 256):raise ValueError('Invalid patch count')
    for patch in patches:
        if not isinstance(patch,dict) or not isinstance(patch.get('name'),str) or not patch['name'].strip() or len(patch['name'])>128:raise ValueError('Invalid patch name')
        c=patch.get('controls')
        if not isinstance(c,dict) or set(c)!=set(specs):raise ValueError('Incomplete patch parameters')
        if any(type(v) not in (float,int) or not math.isfinite(v) or not specs[k].get('min',0)<=v<=specs[k].get('max',1) or specs[k].get('integer') and v!=round(v) for k,v in c.items()):raise ValueError('Invalid patch parameter')
        if p['uri']=='urn:machinista:instrument:synth':
            from app.synth_library import validate_preset_waves
            validate_preset_waves(c,patch.get('synth_waves',{}))
        elif 'synth_waves' in patch:raise ValueError('Waveforms require Machinista Synth')
    return data

def is_init_name(name):
    import re
    return bool(re.fullmatch(r'init(?:[ _-]+(?:patch|voice|sound|bank|program))?',name.strip(),re.I))

def read_banks(root,p,old=None):
    now=time.monotonic()
    paths=[]
    for path in sorted(bank_folder(root,p).glob('*.json'))[:256]:
        try:
            stat=path.stat()
            if not path.is_symlink() and stat.st_size<=8*1024**2:paths.append((path,stat.st_mtime_ns,stat.st_size))
        except OSError:continue
    signature=tuple((str(path),stamp,size) for path,stamp,size in paths)
    if old and signature==old[2]:
        return (now+1,old[1],signature)
    result=[]
    initial=dict(id='init',name='Init',patches=[dict(name='Init',controls={v['symbol']:v['default'] for v in p['parameters']})])
    for path,_,_ in paths:
        try:
            if path.is_symlink() or path.stat().st_size>8*1024**2:continue
            data=validate_bank(json.loads(path.read_text()),p)
            # Keep original program identities when displaying Init patches last.
            order=sorted(range(len(data['patches'])),key=lambda i:is_init_name(data['patches'][i]['name']))
            patches=([dict(data['patches'][i],_program=i) for i in order] if order!=list(range(len(order))) else list(data['patches']))
            result.append(dict(data,id=path.stem,patches=patches))
        except (OSError,ValueError,TypeError):continue
    result.sort(key=lambda v:is_init_name(v['name']))
    result.append(initial)
    return (now+1,result,signature)

def banks(root,p):
    live=_live_banks.get(str(root))
    if live is not None and p['id'] in live.entries:return live.entries[p['id']][1]
    key=(str(root),p['id']);now=time.monotonic();old=_cache.get(key)
    if old and now<old[0]:return old[1]
    entry=read_banks(root,p,old);_cache[key]=entry
    return entry[1]

def selection(root,selected,p):
    available=banks(root,p);stored=selected.get('profile_preset',{});stored=stored if isinstance(stored,dict) else {}
    index=next((i for i,b in enumerate(available) if b['id']==stored.get('bank','init')),None)
    if index is None:return available,None,0
    number=stored.get('program',0);number=number if type(number) is int else 0
    patches=available[index]['patches']
    position=next((i for i,v in enumerate(patches) if v.get('_program',i)==number),max(0,min(len(patches)-1,number)))
    if stored.get('name') and patches[position]['name']!=stored['name']:
        # Bank maintenance may move entries. Prefer the saved identity/name
        # without changing the stored controls of an existing Sound/project.
        position=next((i for i,v in enumerate(patches) if v['name']==stored['name']),position)
    return available,index,position


def controls(app,selected,ports,native=True):
    p=profile(selected['uri'])
    if not p:return ports
    if native and selected['uri']=='urn:machinista:instrument:synth':
        from app.synth_library import controls as provider
        return provider(app,selected,ports)
    if p['provider']=='native-ducktor':
        from app.ducktor import controls as provider
        return provider(app,selected,ports)
    if p['provider']=='virtualjv-multi':
        from app.virtualjv_multi import controls as provider
        return provider(app,selected,ports)
    if p['provider']=='virtualjv':
        from app.virtualjv_controls import controls as provider
        return provider(app.root,selected,ports)
    available,bank,patch=selection(app.root,selected,p);chosen=available[bank] if bank is not None else None
    by={v['symbol']:v for v in ports};result=[];seen=set()
    for page in p['pages']:
        for symbol in page['controls']:
            if symbol.startswith('@'):
                is_bank=symbol=='@bank';items=available if is_bank else chosen['patches'] if chosen else []
                labels=[v['name'] for v in items]
                v=dict(symbol=symbol,name='BANK' if is_bank else 'PATCH',min=0,max=max(0,len(items)-1),default=(bank if bank is not None else 0) if is_bank else patch,integer=True,choice=True,choices=list(enumerate(labels)),profile_action='bank' if is_bank else 'patch')
                if chosen is None:v.update(default=-1,choices=[(-1,'MISSING BANK')])
            elif symbol in by:
                v=dict(by[symbol],**p.get('overrides',{}).get(symbol,{}));seen.add(symbol)
            else:continue
            v['name']=page.get('labels',{}).get(symbol,v['name'])
            v['section']=page['title'];result.append(v)
    if not p.get('controller_compact'):result.extend(v for v in ports if v['symbol'] not in seen)
    return result

def names(root,selected):
    p=profile(selected['uri'])
    if not p or p['provider']!='parameter-bank':
        from app.virtualjv_controls import names as provider
        return provider(root,selected)
    available,bank,patch=selection(root,selected,p)
    if bank is None:
        stored=selected.get('profile_preset',{});return ('MISSING BANK',stored.get('name','SAVED PATCH'))
    return available[bank]['name'],available[bank]['patches'][patch]['name']

def rotate(app,selected,port,delta):
    """Return True for UI-only selectors; never send these as native ports."""
    if not port.get('profile_action'):return False
    if port['profile_action']=='synth_wave':
        from app.synth_library import rotate_wave
        return rotate_wave(app,selected,port,delta)
    if port['profile_action']=='ducktor_source':
        from app.ducktor import rotate_source
        return rotate_source(app,selected,delta)
    p=profile(selected['uri']);available,bank,patch=selection(app.root,selected,p)
    if port['profile_action']=='bank':
        bank=max(0,min(len(available)-1,(bank if bank is not None else -1)+delta));patch=0
    elif bank is None:
        app.message='SELECT BANK FIRST';return True
    else:patch=max(0,min(len(available[bank]['patches'])-1,patch+delta))
    chosen=available[bank];preset=chosen['patches'][patch]
    waves=None
    if selected['uri']=='urn:machinista:instrument:synth':
        from app.synth_library import preset_waves
        try:waves=preset_waves(app.root,preset)
        except ValueError:app.message='PRESET WAVE MISSING';return True
    app.remember();selected['controls'].update(copy.deepcopy(preset['controls']))
    if waves is not None:selected['synth_waves']=waves
    selected['profile_preset']=dict(bank=chosen['id'],program=preset.get('_program',patch),name=preset['name'])
    app.plugin_update();return True
