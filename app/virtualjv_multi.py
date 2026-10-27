"""One Group rack, seven melodic Parts plus rhythm, explicit internal MIDI links."""
import json
from pathlib import Path
from app.layout import GROUP_BASE,MASTER
from app.virtualjv_controls import SPECS,PRESET,banks,controls as single_controls

URI='urn:machinista:ports:virtualjv-multi'
SPECS_MULTI=tuple(json.loads(Path(__file__).with_name('virtualjv_multi_parameters.json').read_text()))
BY_SYMBOL={p['symbol']:p for p in SPECS_MULTI}
BASE_SYMBOLS=frozenset(p['symbol'] for p in SPECS)
_controls_cache={}
MIXER_SUFFIXES=('_mixer_gain','_mixer_pan','_mixer_mute')
FX={'reverb_type','reverb_level','reverb_time','reverb_feedback','chorus_type','chorus_level','chorus_rate','chorus_depth','chorus_feedback','chorus_output'}
PATCH_COMMON={'velocity_switch':(12,128,7,0),'bend_down':(23,255,0,-64),'bend_up':(24,15,0,0),'portamento_mode':(24,16,4,0),'portamento_type':(25,128,7,0),'solo_legato':(24,32,5,0)}


def internal_destination(track):
    value=track.get('routing',{}).get('midi_target','NONE')
    if not isinstance(value,str) or not value.startswith('GROUP '):return None
    try:index=int(value[6:]);channel=track.get('channel',1)-1
    except (ValueError,TypeError):return None
    return (GROUP_BASE+index,channel) if 0<=index<MASTER-GROUP_BASE and type(channel) is int and 0<=channel<16 else None


def rack(group):
    slots=group.get('plugins',[])
    return slots[0] if slots and slots[0].get('uri')==URI else None


def part(selected):return max(0,min(7,round(selected.get('controls',{}).get('editor_part',0))))


def selected_patch(selected,index=None):
    values=selected.get('controls',{});index=part(selected) if index is None else index
    bank=round(values.get(f'p{index+1}_bank',0));bank=round(values.get('expansion',0)) if bank==3 else bank
    return dict(uri='urn:machinista:ports:virtualjv',controls=dict(bank=bank,program=round(values.get(f'p{index+1}_program',0)),rhythm=int(index==7)))


def channel_choices(selected,index):
    values=selected.get('controls',{});current=round(values.get(f'p{index+1}_channel',10 if index==7 else index+1))
    occupied={round(values.get(f'p{n+1}_channel',10 if n==7 else n+1)) for n in range(8) if n!=index}
    return tuple(n for n in range(1,17) if n==current or n not in occupied)


def controls(app,selected,ports):
    root=app.root;index=part(selected);prefix=f'p{index+1}_';by={p['symbol']:p for p in ports};available=banks(root)
    values=selected.get('controls',{});key=(str(root),id(ports),id(available),index,values.get('expansion',0),values.get(prefix+'bank',0),values.get(prefix+'program',0),tuple(values.get(f'p{n+1}_channel',10 if n==7 else n+1) for n in range(8)))
    if key in _controls_cache:return _controls_cache[key][2]
    # The single editor decodes exactly one immutable factory patch and annotates
    # its native values. Reuse it without copying user ROM data or changing state.
    originals=[]
    for original in ports:
        symbol=original['symbol']
        if symbol.startswith(prefix) and symbol[len(prefix):] in BASE_SYMBOLS:originals.append(dict(original,symbol=symbol[len(prefix):]))
    decoded={p['symbol']:p for p in single_controls(root,selected_patch(selected,index),originals)}
    preset_common={}
    try:
        chosen=selected_patch(selected,index);bank=available.get(chosen['controls']['bank']);table=bank.get('_table') if bank else None
        program=chosen['controls']['program']
        if table and 0<=program<len(bank.get('patches',())):
            path,start=table
            with path.open('rb') as stream:
                stream.seek(start+program*362);raw=stream.read(362)
            if len(raw)==362:
                for name,(offset,mask,shift,*adjust) in PATCH_COMMON.items():
                    raw_value=(raw[offset]&mask)>>shift
                    preset_common[name]=raw_value+(adjust[0] if adjust else 0)
    except (OSError,TypeError,ValueError,KeyError):pass
    result=[]
    basic=['editor_part','expansion',prefix+'bank',prefix+'program',prefix+'channel',prefix+'level',prefix+'pan',prefix+'on']
    effects=['reverb_type','reverb_level','reverb_time','reverb_feedback','chorus_type','chorus_level','chorus_rate','chorus_depth']
    patch=['chorus_feedback','chorus_output']+[prefix+s for s in ('patch_level','patch_pan','analog_feel','portamento','porta_time','key_assign')]
    performance=[prefix+s for s in ('mod_wheel','expression','sustain','pitch_bend','coarse','fine','reverb_on','chorus_on')]
    sections=[('MULTI / PART '+str(index+1),basic),('COMMON / EFFECTS',effects)]
    if index<7:sections.append(('PART '+str(index+1)+' / PATCH',patch))
    sections.append(('PART '+str(index+1)+' / PERFORMANCE',performance))
    if index<7:
        for start in range(20,len(SPECS),8):
            group=SPECS[start:start+8];sections.append((f'P{index+1} '+group[0]['section'].replace('TONE ','T'),[prefix+p['symbol'] for p in group]))
    if index<7:
        sections.append(('PART '+str(index+1)+' / PATCH ADVANCED',[prefix+s for s in ('velocity_switch','bend_down','bend_up','portamento_mode','portamento_type','solo_legato')]))
    for section,symbols in sections:
        for symbol in symbols:
            if symbol not in by:continue
            port=dict(by[symbol],section=section);spec=BY_SYMBOL[symbol]
            base_symbol=symbol[len(prefix):] if symbol.startswith(prefix) else symbol
            if base_symbol in decoded:
                port.update({k:v for k,v in decoded[base_symbol].items() if k not in ('symbol','index','name','section')})
            elif spec['role']==100:
                if spec.get('special'):
                    if spec.get('choices'):port.update(choice=True,choices=((-1000,'PATCH'),)+tuple(enumerate(spec['choices'])))
                    port['preset_parameter']=True
                    if spec['special'] in preset_common:port['preset_value']=preset_common[spec['special']]
                else:
                    source=SPECS[spec['parameter']]
                    if source.get('choices'):port.update(choice=True,choices=tuple(enumerate(source['choices'])))
            port['symbol']=symbol;port['index']=by[symbol]['index'];port['min']=spec['min'];port['max']=spec['max']
            if spec['role']==100:port['reset_value']=spec['default']
            if symbol=='editor_part':port.update(choice=True,choices=tuple((p,'RHYTHM' if p==7 else f'PART {p+1}') for p in range(8)))
            elif symbol=='expansion':port.update(choice=True,choices=((0,'NONE'),)+tuple((k,v['name']) for k,v in sorted(available.items()) if k>=3))
            elif spec['role']==2:
                card=available.get(round(selected.get('controls',{}).get('expansion',0)))
                choices=[(i,available.get(i,{}).get('name',name)) for i,name in enumerate(('Internal A','Internal B','Internal User'))]
                if card and (index<7 or card.get('drums')):choices.append((3,card['name']))
                port.update(choice=True,choices=tuple(choices))
            elif spec['role']==3:
                from app.virtualjv_controls import presets
                bank=selected_patch(selected,index)['controls'];port.update(choice=True,choices=tuple(enumerate(presets(available.get(bank['bank']),index==7))))
            elif spec['role']==4:port.update(choice=True,choices=tuple((n,str(n)) for n in channel_choices(selected,index)))
            elif spec['role'] in (7,10,11):port.update(choice=True,choices=((0,'OFF'),(1,'ON')))
            elif spec['role']==6:port['unit']='pan'
            result.append(port)
    if len(_controls_cache)>32:_controls_cache.clear()
    _controls_cache[key]=(ports,available,result)
    return result


def reset_part(selected,index):
    for p in SPECS_MULTI:
        if p['part']==index and p['role']==100:selected['controls'][p['symbol']]=p['default']


def changed(app,selected,port,old=None):
    symbol=port['symbol'];spec=BY_SYMBOL.get(symbol)
    if spec and spec['role']==4 and old is not None:
        destination=f'GROUP {app.group}'
        for group in app.project['groups']:
            for track in group['pads']:
                if track.get('routing',{}).get('midi_target')==destination and track.get('channel',1)==round(old):track['channel']=selected['controls'][symbol]
        return
    if symbol=='editor_part':app.plugin_param=0;return
    if symbol=='expansion':
        available=banks(app.root)
        for index in range(8):
            if selected['controls'].get(f'p{index+1}_bank',0)!=3:continue
            reset_part(selected,index);bank=available.get(round(selected['controls'].get('expansion',0)))
            from app.virtualjv_controls import presets
            choices=presets(bank,index==7)
            if not choices:selected['controls'][f'p{index+1}_bank']=0;selected['controls'][f'p{index+1}_program']=0
            else:selected['controls'][f'p{index+1}_program']=max(0,min(len(choices)-1,round(selected['controls'].get(f'p{index+1}_program',0))))
        return
    if spec and spec['role'] in (2,3):
        reset_part(selected,spec['part']);patch=selected_patch(selected,spec['part'])
        from app.virtualjv_controls import presets
        choices=presets(banks(app.root).get(patch['controls']['bank']),spec['part']==7)
        if choices:selected['controls'][f'p{spec["part"]+1}_program']=max(0,min(len(choices)-1,round(patch['controls']['program'])))


def link_empty_pads(app):
    """Use only empty pads, preserving all existing samples and instruments."""
    group=app.project['groups'][app.group];target=f'GROUP {app.group}';plugin=rack(group)
    if not plugin:return 0
    used={p.get('channel',1) for g in app.project['groups'] for p in g['pads'] if p.get('routing',{}).get('midi_target')==target}
    count=0
    for part_index in range(8):
        channel=round(plugin.get('controls',{}).get(f'p{part_index+1}_channel',10 if part_index==7 else part_index+1))
        if channel in used:continue
        track=next((p for p in group['pads'] if not (p.get('sample') or p.get('plugins') or p.get('zones') or p.get('source','SAMPLE')!='SAMPLE' or internal_destination(p))),None)
        if track is None:break
        track.setdefault('routing',{})['midi_target']=target;track['channel']=channel;track['note']=36 if part_index==7 else 60
        used.add(channel);count+=1
    return count
