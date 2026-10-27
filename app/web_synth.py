"""Full native synth editor; controller layout stays compact and IDs stay stable."""
import copy
import math
import time
from app.synth_library import URI,listing,FACTORY
from app.plugin_profiles import profile,banks


def schema(root):
    p=profile(URI)
    # Matrix targets share one list over the wire, rather than 32 copies.
    choices={};parameters=[]
    for port in p['parameters']:
        row=dict(port)
        if row['symbol'].startswith('mod') and row['symbol'].endswith('_target'):
            choices['targets']=row.pop('choices');row['choice_group']='targets'
        parameters.append(row)
    from app.synth_display import factory
    return dict(parameters=parameters,pages=p['web_pages'],choices=choices,waves=FACTORY,
                previews=factory(),users=listing(root),banks=[dict(id=b['id'],name=b['name'],patches=[v['name'] for v in b['patches']]) for b in banks(root,p)])


def apply(app,value):
    slot=value.get('slot');plugins=app.track().get('plugins',[])
    if type(slot) is not int or not 0<=slot<len(plugins) or plugins[slot]['uri']!=URI or value.get('uri')!=URI:
        raise ValueError('Select Machinista Synth on the current Sound first.')
    plugin=plugins[slot];p=profile(URI);specs={port['symbol']:port for port in p['parameters']}
    updates=value.get('controls',{});wave=value.get('wave');preset=value.get('preset')
    if not isinstance(updates,dict) or len(updates)>128 or not(updates or wave or preset):raise ValueError('Invalid synth edit.')
    if preset and (updates or wave):raise ValueError('Apply a preset separately.')
    changes={};wave_changes={};preset_value=None
    for symbol,number in updates.items():
        port=specs.get(symbol)
        if not port or type(number) not in (float,int) or not math.isfinite(number) or not port['min']<=number<=port['max'] or port.get('integer') and number!=round(number):
            raise ValueError('Invalid synth parameter.')
        if symbol.endswith('_wave') and symbol.startswith('osc') and number==32:raise ValueError('Choose an imported waveform from the source list.')
        changes[symbol]=number
    if wave is not None:
        if not isinstance(wave,dict) or type(wave.get('osc')) is not int or not 1<=wave['osc']<=4:raise ValueError('Invalid oscillator.')
        row=next((r for r in listing(app.root) if r['id']==wave.get('id')),None)
        if row is None:raise ValueError('Waveform no longer available. Refresh the editor.')
        osc=str(wave['osc']);changes[f'osc{osc}_wave']=32
        wave_changes[osc]={k:row[k] for k in ('id','name','frames','cycle')}
    if preset is not None:
        if not isinstance(preset,dict) or type(preset.get('patch')) is not int:raise ValueError('Invalid preset.')
        bank=next((b for b in banks(app.root,p) if b['id']==preset.get('bank')),None)
        if not bank or not 0<=preset['patch']<len(bank['patches']):raise ValueError('Preset no longer available.')
        patch=bank['patches'][preset['patch']];changes=copy.deepcopy(patch['controls'])
        from app.synth_library import preset_waves
        wave_changes=preset_waves(app.root,patch)
        preset_value=dict(bank=bank['id'],program=patch.get('_program',preset['patch']),name=patch['name'])
    gesture=value.get('gesture','')
    if not isinstance(gesture,str) or len(gesture)>80:raise ValueError('Invalid edit gesture.')
    now=time.monotonic();context=(id(app.project),app.group,app.pad,slot,gesture)
    old=getattr(app,'_web_synth_gesture',None)
    if gesture and old and old[0]==context and old[1]==app.revision and app.undo and old[2] is app.undo[-1] and now-old[3]<1:
        app.revision+=1;app.dirty=True
    else:app.remember()
    plugin.setdefault('controls',{}).update(changes)
    if preset_value:plugin['synth_waves']=wave_changes
    elif wave_changes:plugin.setdefault('synth_waves',{}).update(wave_changes)
    if preset_value:plugin['profile_preset']=preset_value
    app._web_synth_gesture=(context,app.revision,app.undo[-1] if app.undo else None,now)
    bus=app.group*16+app.pad
    for symbol in changes:app.midi_touch_until[(bus,'plugin',slot,symbol)]=now+1
    app.actions.append(('plugins',(bus,copy.deepcopy(plugins))))
    return dict(ok=True,group=app.group,pad=app.pad,generation=app.project_generation,revision=app.revision)
