"""Preformatted parameter state; draw only in the independent LCD process."""
from pathlib import Path
import re
from app.navigation import CONTROL_PAGES
from app.ni_display import rect,label,softkey_label,dotted_rect,finish_frame,width,name,note_name,formatted,plugin_value

PARAMETER_PAGES=CONTROL_PAGES+('PAD CONFIG','TEMPO','PLUGIN SLOTS')


def control_state(app):
    from app.ui_context import sound_context,pinned,visible_message
    page=app.page
    title=page
    if page=='PAD CONFIG':title='KEYBOARD' if app.keyboard_enabled else 'PAD MODE'
    if page in CONTROL_PAGES:
        title=app.project['name'] if app.control_level==0 else f'{app.group_name()}. '+app.project['groups'][app.group].get('name','GROUP') if app.control_level==1 else f'{app.pad+1}. '+name(app)
    if page in CONTROL_PAGES and app.control_level==2:title=sound_context(app)
    transport=app.transport_title().split()
    transport_detail='COUNT IN' if app.count_remaining else f'{transport[0]} {transport[2]}' if app.playing or app.recording else ''
    state=dict(kind='CONTROL',page=page,keys=app.softkeys(),active=tuple(app.active_softkeys()),title=title,
               position=app.pattern_position(),show_position=page in CONTROL_PAGES,message=visible_message(app),pinned=pinned(app),transport_detail=transport_detail,
               heading='',caption=None,value='',latency='',plugin_heading=False)
    if page in ('PAD','CHANNEL'):
        from app.routing import route_defaults
        target=app.plugin_target();r=route_defaults(target);fields=app.channel_fields();key=fields[app.channel_field]
        state.update(heading='OUTPUT',caption=f'{app.channel_field+1}/{len(fields)}: '+({'gain':'LEVEL','midi_target':'INTERNAL TO','midi_send':'EXT MIDI'}.get(key,key.upper().replace('_',' '))),
                     value=formatted(target.get(key,100 if key=='gain' else 0) if key in ('gain','note','channel') else r[key],key))
        state['section']=('AUDIO','AUX 1','AUX 2','MIDI')[app.channel_page]
    elif page=='INPUT':
        from app.routing import route_defaults
        r=route_defaults(app.plugin_target())
        state.update(heading='INPUT',caption=f'{app.input_field+1}/2: '+('SOURCE','GAIN')[app.input_field],
                     value=r['input'] if app.input_field==0 else formatted(r['input_gain'],'input_gain'))
    elif page=='GROOVE':
        from app.groove import settings
        g=settings(app.plugin_target(),app.timing()['swing'] if app.control_level==0 else 0);key=('amount','cycle','invert')[app.groove_field]
        state.update(heading='GROOVE',caption=f'{app.groove_field+1}/3: '+key.upper(),value=formatted(g[key],key))
    elif page=='MACRO':
        mapping=app.plugin_target().get('macros',{}).get(str(app.macro_index))
        state.update(heading='MACRO',caption=f'{app.macro_index+1}/8: '+(mapping['name'] if mapping else 'UNASSIGNED'),value=str(mapping['value'])+'%' if mapping else 'SHIFT F2 ASSIGN')
    elif page=='SAMPLER':
        key,caption,default,_=app.sampler_parameter()
        state.update(heading='1. SAMPLER',caption=f'{app.sampler_field+1}/{len(app.sampler_fields())}: '+caption,value=formatted(app.track().get('sampler',{}).get(key,default),key))
    elif page in ('PLUGIN','PLUGIN SLOTS'):
        selected=app.plugin_selected();meta=app.plugin_metadata(selected['uri']) if selected else None
        slot=app.plugin_slot+1+int(app.sampler_slot_present())
        state.update(heading=f'{slot}. '+meta['name'] if meta else '(NONE)',plugin_heading=True,
                     latency=f'CHAIN LAT {app.plugin_latency_ms:.1f} MS' if getattr(app,'plugin_latency_ms',0)>0 else '')
        controls=app.plugin_controls()
        if controls:
            port=controls[min(app.plugin_param,len(controls)-1)]
            if port.get('section'):state['section']=port['section'].replace('TONE ','T').replace(' / ',' ')
            state.update(caption=f'{app.plugin_param+1}/{len(controls)}: '+port['name'],value=plugin_value(port,selected['controls'].get(port['symbol'],port['default'])))
    elif page=='PAD CONFIG':
        state.update(sound_name=name(app),root=note_name(app.keyboard_root if app.keyboard_enabled else app.track().get('note',36)))
        if app.keyboard_enabled:
            settings=app.performance();keys=app.keyboard_fields();key=keys[min(app.pad_field,len(keys)-1)];value=app.keyboard_value(key)
        else:
            key=('choke_group','choke_mode','link_group','link_mode','note','fix_velocity')[app.pad_field]
            value=app.fixed_velocity if key=='fix_velocity' else app.track().get(key,'MASTER' if key.endswith('mode') else 0 if key.endswith('group') else 36)
        caption={'note':'BASE KEY','fix_velocity':'FIX VEL','root':'ROOT NOTE','scale':'SCALE TYPE'}.get(key,key.upper().replace('_',' '))
        state.update(caption=f'{app.pad_field+1}/{len(app.keyboard_fields()) if app.keyboard_enabled else 6}: '+caption,value=formatted(value,key))
        if app.keyboard_enabled and app.slice_keyboard():
            state.update(title='SLICE PADS',heading=f'{len(app.track()["zones"])} SLICES',caption='FIRST SLICE',value=app.keyboard_root+1,root=f'{len(app.track()["zones"])} SLICES')
    elif page=='TEMPO':state['tempo']=f'{app.project["tempo"]:.2f}'
    from app.ducktor import view
    ducktor=view(app)
    if ducktor:state['ducktor']=ducktor
    from app.synth_display import view as synth_view
    synth=synth_view(app)
    if synth:state['synth_graph']=synth
    from app.mikro_pages import position
    state['pages']=position(app)
    state['value']=str(state['value'])
    if page=='SAMPLER':
        from app.sampler import SAMPLER_PAGES,DEFAULTS
        state['section']=SAMPLER_PAGES[app.sampler_page][0]
        state['sampler_values']={**DEFAULTS,**app.track().get('sampler',{})}
        state['sampler_section']=app.sampler_page
    if page in ('PAD','CHANNEL') and app.control_level==2:
        t=app.track();state['sound_wave']=(t.get('sample'),t.get('start',0),t.get('end',0))
        from app.wave_playback import position
        state['wave_cursor']=position(app,t.get('sample'))
    if page=='PLUGIN' and app.plugin_param//8==0 and not state.get('ducktor') and not state['latency']:
        graph=state.get('synth_graph')
        selected=app.plugin_selected()
        if selected and (not graph or 'levels' in graph):
            meta=app.plugin_metadata(selected['uri']) or {}
            from app.mono_instrument_icons import kind
            from app.plugin_profiles import names
            plugin_kind=selected.get('kind',meta.get('kind','EFFECT'))
            named=names(app.root,selected) if plugin_kind=='INSTRUMENT' else None
            title=meta.get('name',selected['uri'])
            state['micro_overview']=dict(icon=kind(selected['uri'],title,plugin_kind),
                name=named[1] if named else title,
                role='BYPASSED' if selected.get('bypass') else 'SOUND' if plugin_kind=='INSTRUMENT' else 'EFFECT')
    return state


def control_frame(state):
    from app.fokus import enabled,control
    if enabled():return control(state)
    p=bytearray([1]*8192)
    for i,key in enumerate(state['keys']):
        x=i*43;w=40 if i==2 else 41;active=i in state['active']
        if key in ('','-'):dotted_rect(p,x+1,1,w,10)
        else:rect(p,x+1,1,w,10,0,active);softkey_label(p,x+1,w,key,1 if active else 0)
    rect(p,1,12,126,11,0);label(p,4,15,state['title'],1,bold=True,max_width=120)
    if state['show_position']:label(p,125-width(state['position'],True),29,state['position'],tabular_digits=True)
    if state['heading']:label(p,3,29,state['heading'],max_width=126-width(state['position'],True)-6 if state['plugin_heading'] else None)
    if state['latency']:label(p,3,38,state['latency'],font='regular5')
    if state['page']=='PAD CONFIG':
        label(p,2,30,state['sound_name'],max_width=92);label(p,126-width(state['root']),30,state['root'])
    if state['page']=='TEMPO':
        label(p,3,29,state['tempo'],tabular_digits=True);label(p,81,29,'BPM')
        label(p,3,46,'ENC: 1.00 BPM',font='regular5');label(p,3,57,'SHIFT/PUSH: 0.01',font='regular5')
    else:
        rect(p,1,43,126,1,0)
        caption=state['caption']
        if caption is not None:
            label(p,1,48,caption,center=True,max_width=110,font='regular5');label(p,1,57,state['value'],center=True,bold=True,max_width=122)
            indexed=re.search(r'(\d+)/(\d+):',caption)
            if indexed:
                index,count=map(int,indexed.groups())
                if index>1:label(p,2,48,'<',font='regular5')
                if index<count:label(p,122,48,'>',font='regular5')
    if state['message']:rect(p,0,55,128,8,0);label(p,2,56,state['message'],1)
    return bytes(finish_frame(p))
