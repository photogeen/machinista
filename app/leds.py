"""Manual-derived LED states on experimentally mapped Mikro MK1 channels."""
import time
from app.performance import PARAMETER_PLAY_PAGES
GROUP_SLOTS=(12,13,14,15,8,9,10,11)
OFF,DIM,FULL=0,4,31


def led_report(app,channels,now=None):
    now=time.monotonic() if now is None else now
    report=bytearray([0x80]+[0]*60)
    def pad(slot,value,color='orange'):
        index=channels.get((slot,color))
        if index is not None:report[index+1]=value
    def button(name,value):
        index=app.button_led_map.get(name)
        if index is not None:report[index+1]=value
    group=app.project['groups'][app.group]
    any_solo=any(t['solo'] for t in group['pads'])
    for slot,track in enumerate(group['pads']):
        present=app.sound_present(slot)
        keyboard_empty=False
        value=DIM if present else OFF
        if slot==app.pad:value=FULL
        if app.page=='LIVE FX':value=FULL if slot==app.live_fx_pad else DIM
        if app.page in ('BROWSE','SAMPLING'):
            value=FULL if slot==app.pad else DIM if present else OFF
        elif app.page=='VIEW NAV':
            enabled=(0,1,2,5,3,7) if app.view_target=='PAT' and app.grid_notes else (0,1,2,5)
            value=(FULL if slot in app.held_pads else DIM) if slot in enabled else OFF
        elif app.page=='PARAM NAV':
            enabled=tuple(range(12,16)) if app.parameter_kind=='PLUG-IN' or app.control_level else (13,14,15)
            selected=12+app.parameter_choice+(1 if app.control_level==0 and app.parameter_kind=='CHNL' else 0)
            value=FULL if slot==selected else DIM if slot in enabled else OFF
        elif app.wave_view():
            value=(FULL if slot in app.held_pads else DIM) if app.wave_selected and slot in (0,1,2,5) else OFF
        elif app.page=='SAMPLING NAV':
            value=FULL if slot==(12,13,14,15,8)[app.sampling_nav] else DIM if slot in (12,13,14,15,8) else OFF
        elif app.page=='MIXER' and app.mixer_level==1:
            value=OFF
        elif app.page=='GROUP':
            value=OFF
        elif app.page=='SLICE TARGET':
            value=OFF if 'GROUP' in app.held_buttons else FULL if app.slice_target_sound is None or slot==app.slice_target_sound else DIM
        elif app.page=='PATTERN':
            index=app.pattern_bank*16+slot;value=FULL if index==app.pattern else DIM if index in group['pattern_created'] or app.pattern_present(index) else OFF
        elif app.page=='SCENE':
            index=app.scene_bank*16+slot;used=index in app.project['scene_created']
            value=FULL if index==app.scene else DIM if used else OFF
        elif app.page=='STEP':
            cell=app.bank*16+slot
            value=FULL if cell<app.step_cell_count() and app.notes_in_cell(app.pad,cell) else OFF
            if app.playing and cell==app.phase_cell():value=DIM if value==FULL else FULL
        elif app.page in ('MUTE','SOLO'):
            audible=not track['mute'] and (not any_solo or track['solo'])
            value=(FULL if audible else DIM) if present else OFF
        elif app.page=='CHOP':
            index=app.slice_bank*16+slot
            keyboard_empty=not (index<len(app.slice_ranges()) and app.track()['sample'])
            value=OFF if keyboard_empty else FULL if index==app.slice_index or slot in app.held_pads else DIM
            if app.slice_mode=='MANUAL' and not app.slice_edit:
                playing=app.live_chop_position(now) is not None
                next_index=len(app.slice_ranges()) if playing else 0 if len(app.slice_ranges())==1 else -1
                if index==next_index and next_index<128:keyboard_empty=False;value=FULL if int(now*4)%2 else OFF
        elif app.velocities16 and app.page in ('PAD','PAD CONFIG','MIXER')+PARAMETER_PLAY_PAGES:
            keyboard_empty=not app.sound_present(app.pad)
            value=OFF if keyboard_empty else FULL if slot in app.held_pads else DIM
        elif (app.keyboard_enabled or app.page in ('KEYBOARD','CHORD','ARP')) and not app.slice_keyboard() and (app.performance()['chord_mode']!='OFF' or app.page=='CHORD' and app.chord):
            # Chord pads describe mappings, independent of the selected Sound's
            # sample/zones. Shared chord tones must not select other pads.
            keyboard_empty=not app.performance_notes(slot)
            value=OFF if keyboard_empty else FULL if slot in app.held_pads or slot==getattr(app,'chord_focus',0) else DIM
        elif app.keyboard_enabled or app.page in ('KEYBOARD','CHORD','ARP'):
            notes=app.performance_notes(slot)
            if not app.sound_present(app.pad):notes=[]
            sound=app.track();mapped=sound.get('zones',[])
            instrument=sound.get('routing',{}).get('midi_target','NONE')!='NONE' or bool(sound.get('plugins') and sound['plugins'][0].get('kind')=='INSTRUMENT')
            if mapped and sound.get('source')!='MIDI' and not instrument:
                notes=[n for n in notes if any(z.get('key_lo',0)<=n<=z.get('key_hi',127) and z.get('sample') and z.get('end',0)>z.get('start',0) for z in mapped)]
            keyboard_empty=not notes
            if app.slice_keyboard():
                focus=app.step_input_note()
                root_selected=notes and notes[0]==(0 if focus is None else focus)
            else:root_selected=slot==getattr(app,'chord_focus',0) if app.performance()['chord_mode']=='CUSTOM' else notes and notes[0]%12==app.keyboard_root%12
            value=OFF if keyboard_empty else FULL if slot in app.held_pads or root_selected or any(n in app.performance_lights for n in notes) else DIM
        if app.page=='SELECT':
            value=FULL if slot in app.selected_pads else DIM if present else OFF
        if not app.shift and 'ERASE' in app.held_buttons and ('SELECT' in app.held_buttons or app.page=='SELECT'):
            target=app.erase_target(slot)
            if target:
                g,pat,pads,pitches=target
                present=any(key[0] in pads and (pitches is None or bool(pitches.intersection(event.get('chord',[event.get('note',app.project['groups'][g]['pads'][key[0]].get('note',36+key[0]))])))) for key,event in app.event_notes(g,pat).items())
                keyboard_empty=not present;value=FULL if present else OFF
        if app.shift and 'SELECT' in app.held_buttons and app.page=='SELECT':
            events=app.event_notes()
            pitches=set(app.performance_notes(slot))
            keys={k for k,e in events.items() if k[0]==app.pad and e.get('note',app.track().get('note',36+app.pad)) in pitches} if app.keyboard_enabled else {k for k in events if k[0]==slot}
            value=FULL if keys and keys<=app.grid_selected else DIM if keys else OFF
        if not keyboard_empty and app.page not in ('VIEW NAV','PARAM NAV') and not app.wave_view() and not (app.shift and 'SELECT' in app.held_buttons) and app.flash_until.get(slot,0)>now and app.page not in ('GROUP','PATTERN','SCENE','STEP','MUTE','SOLO','SLICE TARGET') and not (app.page=='MIXER' and app.mixer_level==1):
            value=FULL
        pad(slot,value)
    if app.page=='GROUP':
        for i,slot in enumerate(GROUP_SLOTS):
            i+=app.group_bank*8;g=app.project['groups'][i]
            present=i==0 or any(app.sound_present(slot,i) for slot in range(16)) or any(any(any(l) for l in p) for p in g['patterns'])
            origin=app.mode_origins.get('GROUP')
            if origin in ('MUTE','SOLO'):
                solo=any(gr.get('solo',False) for gr in app.project['groups'])
                audible=not g.get('mute',False) and (not solo or g.get('solo',False))
                value=(FULL if audible else DIM) if present else OFF
            elif origin=='SELECT':value=FULL if i in app.selected_groups else DIM if present else OFF
            else:value=FULL if i==app.group else DIM if present else OFF
            if not app.shift and 'ERASE' in app.held_buttons:
                value=FULL if slot in app.held_pads else DIM if app.notes(i,app.active_patterns[i]) else OFF
            pad(slot,value,'blue')
    if app.page=='MIXER' and app.mixer_level==1:
        for i,slot in enumerate(GROUP_SLOTS):
            index=app.group//8*8+i
            if index<len(app.project['groups']):pad(slot,FULL if index==app.group else DIM,'blue')
    if app.page=='SLICE TARGET' and 'GROUP' in app.held_buttons:
        for i,slot in enumerate(GROUP_SLOTS):
            index=(app.slice_target_group//8)*8+i
            pad(slot,FULL if index==app.slice_target_group else DIM,'blue')
    modes={'SAMPLING':('SAMPLING','SAMPLE EDIT','CHOP','PROCESS','SAMPLING NAV','SAMPLE DELETE','ZONE','SLICE TARGET','AUTOSAMPLER'),'BROWSE':('BROWSE',),
           'PATTERN':('PATTERN','LENGTH','PATTERN GRID','GRID EDIT'),'SCENE':('SCENE','SONG'),'VIEW':('VIEW NAV','MIXER'),
           'PAD MODE':('PAD CONFIG','KEYBOARD','CHORD'),'SELECT':('SELECT','EVENT'),
           'MUTE':('MUTE',),'SOLO':('SOLO',),'MAIN':('SETTINGS','AUDIO','MIDI IN','MIDI OUT','MIDI CHANNEL','TEMPO','BRIGHTNESS','CONTRAST','AUDIO RATE','PROJECT','SYSTEM'),
           'GROUP':('GROUP',),'GRID':('OPTIONS','RECORD SETTINGS'),'NOTE REPEAT':('NOTE REPEAT','ARP')}
    from app.settings_menu import SETTINGS_VIEWS
    modes['MAIN'] = tuple(set(modes['MAIN']) | set(SETTINGS_VIEWS))
    for name,pages in modes.items():button(name,FULL if app.page in pages else DIM)
    if app.page=='LIVE FX':button('SOLO',FULL)
    if app.page=='SLICE TARGET' and 'GROUP' in app.held_buttons:button('GROUP',FULL)
    if app.main_controls_active():button('MAIN',FULL)
    button('PLAY',FULL if app.playing else DIM)
    button('REC',FULL if app.recording else FULL if app.count_remaining and int(now*4)%2 else DIM)
    button('SHIFT',FULL if app.shift else DIM)
    for name in ('RESTART','TRANSPORT LEFT','TRANSPORT RIGHT','ERASE','DUPLICATE','NAV','NAV LEFT','NAV RIGHT','ENTER'):
        button(name,FULL if name in app.held_buttons else DIM)
    button('NAV',FULL if app.page in ('PARAM NAV','SAMPLING NAV') else DIM)
    if app.replace_context is not None:button('ERASE',FULL)
    if app.record_prepare:button('REC',FULL)
    if app.page=='STEP':button('NOTE REPEAT',FULL)  # MK1 STEP MODE is SHIFT+NOTE REPEAT.
    elif app.repeat_locked:button('NOTE REPEAT',DIM)
    if app.duplicate_source is not None:
        kind,g,slot=app.duplicate_source
        if kind=='GROUP':slot=GROUP_SLOTS[slot%8]
        if g==app.group or kind=='GROUP':pad(slot,FULL if int(now*6)%2 else OFF,'blue' if kind=='GROUP' else 'orange')
    if app.wave_view():button('VIEW',FULL)
    active=app.active_softkeys()
    for i,label in enumerate(app.softkeys()):
        button(f'F{i+1}',OFF if label=='-' else FULL if i in active else DIM)
    if app.page=='SAMPLING':
        button('F1',(FULL if int(now*4)%2 else OFF) if app.capture_armed else FULL if app.capture_started is not None else DIM if app.audio and (app.audio.capture or app.capture_options()['source']=='INTERNAL') else OFF)
    return report
