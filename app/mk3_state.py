"""Detached native-size MK3 details; no changes to the engine's edit bindings."""
from fractions import Fraction
from app.mk2_display import snapshot as shared_snapshot
from app.ni_display import note_name


def tick_text(tick):
    tick=max(0,int(tick));text=f'{tick//384+1}.{tick%384//96+1}.{tick%96//24+1}'
    return text+(f'+{tick%24}' if tick%24 else '')

def length_text(ticks):
    ratio=Fraction(max(1,int(ticks)),384)
    return f'{ratio.numerator}/{ratio.denominator}' if ratio.denominator in (1,2,3,4,6,8,12,16,24,32,48,64,96,128) else f'{ticks}t'


def event_state(a):
    events=a.event_notes();targets=a.grid_targets()
    key=min(targets) if targets else None;selected=events.get(key) if key else None
    unit=a.grid_ticks();start=min(a.view_first,max(0,a.grid_length()-1))*unit;end=min(a.pattern_ticks(),start+a.view_count*unit)
    focus=a.grid_note if a.grid_notes else a.pad
    top=min(127,max(7,focus+4)) if a.grid_notes else max(7,min(15,a.pad+3))
    values=tuple(top-i for i in range(8))
    rows=tuple((note_name(v) if a.grid_notes else f'{v+1:02}',v==focus) for v in values)
    visible=[];velocities=[]
    for k,event in events.items():
        pad,tick=k[:2]
        if a.grid_notes and pad!=a.pad:continue
        duration=max(1,event.get('length',unit))
        if tick>=end or tick+duration<=start:continue
        pitch=event.get('note',a.project['groups'][a.group]['pads'][pad].get('note',36+pad))
        value=pitch if a.grid_notes else pad
        marked=k in a.grid_selected;cursor=k==key
        if value in values:
            visible.append((values.index(value),tick,duration,marked,cursor))
        if tick>=start:velocities.append((tick,event.get('velocity',100),marked,cursor))
    # Bound pipe/raster work for pathological dense imported patterns. Explicit
    # selection/cursor remains visible rather than being dropped at the limit.
    visible=tuple(sorted(visible,key=lambda v:not (v[3] or v[4]))[:1024])
    velocities=tuple(sorted(velocities,key=lambda v:not (v[2] or v[3]))[:512])
    phase=max(0,a.clock_phase)%a.pattern_ticks()
    active=a.pattern==a.active_patterns[a.group] and a.active_clips[a.group]
    playhead=phase if active and start<=phase<end else None
    detail=None
    if selected is not None:
        pitch=selected.get('note',a.project['groups'][a.group]['pads'][key[0]].get('note',36+key[0]))
        detail=dict(pitch=note_name(pitch),position=tick_text(key[1]),length=length_text(selected.get('length',unit)),velocity=selected.get('velocity',100),probability=selected.get('probability',100),sound=key[0]+1)
    return dict(rows=rows,notes=visible,velocities=velocities,start=start,end=end,unit=unit,
                cursor=a.grid_step*unit,playhead=playhead,selection_range=a.grid_selection_range,selected_count=len(a.grid_selected),detail=detail,
                follow=a.grid_follow,notes_mode=a.grid_notes,grid=a.timing()['grid'] if a.timing()['grid_on'] else 'FREE')


def output_art(app):
    track=app.plugin_target()
    if track.get('sample'):return None  # A loaded sample always keeps its waveform.
    target=track;seen=set();effects=False
    for _ in range(4):
        if id(target) in seen:break
        seen.add(id(target))
        chain=target.get('plugins',[]);effects=effects or bool(chain)
        for plugin in chain:
            uri=plugin.get('uri','');metadata=app.plugin_metadata(uri) or {}
            if plugin.get('kind',metadata.get('kind'))=='INSTRUMENT':
                return 'machinista-synth' if uri=='urn:machinista:instrument:synth' else 'generic-synth'
        route=target.get('routing',{}).get('midi_target','NONE')
        if not isinstance(route,str) or not route.startswith('GROUP '):break
        try:index=int(route[6:]);groups=app.project['groups']
        except (ValueError,TypeError):break
        if not 0<=index<len(groups):break
        target=groups[index]
    if effects:return 'generic-filter'
    return 'generic-synth' if track.get('source')=='MIDI' else None

def chain_state(surface):
    a=surface.app;items=[]
    if a.sampler_slot_present():
        from app.audio_loop import is_audio_sound
        items.append(dict(name='AUDIO' if is_audio_sound(a.track()) else 'SAMPLER',art=None,bypass=False))
    offset=len(items)
    for plugin in a.plugin_target().get('plugins',[]):
        uri=plugin['uri'];meta=a.plugin_metadata(uri) or {}
        art=('machinista-synth' if uri=='urn:machinista:instrument:synth' else 'generic-synth') if plugin.get('kind',meta.get('kind'))=='INSTRUMENT' else 'generic-filter'
        items.append(dict(name=meta.get('name') or plugin.get('name') or uri.rsplit('/',1)[-1],art=art,bypass=bool(plugin.get('bypass'))))
    selected=0 if a.page in ('SAMPLER','AUDIO LOOP') else a.plugin_slot+offset
    return dict(items=tuple(items),selected=min(selected,max(0,len(items)-1)),
                context=(a.project_generation,a.control_level,a.group,a.pad),motion=getattr(surface,'chain_motion',(0,'')))


def snapshot(surface):
    state=shared_snapshot(surface);a=surface.app
    state['group_label']=a.group_name();state['group_bank']=a.group_bank
    state['wave_preload']=a.track().get('sample')
    if a.page in ('PAD','CHANNEL'):state['output_art']=output_art(a)
    if a.page in ('SAMPLER','PLUGIN','AUDIO LOOP') and state.get('page_index',0)==0:
        state['chain_cards']=chain_state(surface)
    if a.page in ('PATTERN GRID','GRID EDIT'):
        state['events_native']=event_state(a)
        fields=list(state['fields']);detail=state['events_native']['detail']
        for i in (4,5,6):
            if fields[i]:
                label,value=fields[i]
                value=(detail[('position','length','pitch')[i-4]] if detail else
                       tick_text(a.grid_step*a.grid_ticks()) if i==4 else length_text(a.grid_ticks()) if i==5 else note_name(a.grid_note))
                fields[i]=(label,value)
        state['fields']=tuple(fields)
    if 'mixer' in state:
        m=state['mixer'];first=m['first'];level=a.mixer_level
        targets=([a.project] if level==0 else a.project['groups'][first:first+len(m['levels'])] if level==1 else a.project['groups'][a.group]['pads'][first:first+len(m['levels'])])
        m['status']=tuple((bool(t.get('mute')),bool(t.get('solo'))) for t in targets)
        m['colors']=tuple((first+i)%8 if level==1 else a.group%8 for i in range(len(targets)))
        if a.mixer_field==0:
            from app.ni_display import formatted
            state['fields']=tuple((f[0],formatted(f[1],'gain')) if f and isinstance(f[1],(int,float)) else f for f in state['fields'])
    return state
