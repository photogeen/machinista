"""Compact Mixer/Pattern/Scene/VIEW snapshots for the LCD worker."""
import math
from app.ni_display import rect,label,tiny_label,softkey_label,dotted_rect,finish_frame
from app.runtime_audio import meter_height
from app.control_display import PARAMETER_PAGES

ASYNC_PAGES=('STEP','PATTERN GRID','MIXER','PATTERN','SCENE','VIEW NAV')+PARAMETER_PAGES


def live_state(app):
    from app.ui_context import pinned,visible_message
    if app.page=='VIEW NAV' and app.view_selector and app.view_tool is None:
        from app.mikro_navigate import state
        return state(app)
    if app.page in PARAMETER_PAGES:
        from app.control_display import control_state
        return control_state(app)
    if app.page=='STEP':
        from app.step_display import step_state
        return step_state(app)
    if app.page=='PATTERN GRID' or app.page=='VIEW NAV' and app.view_target=='PAT':
        from app.pattern_display import pattern_state
        state=pattern_state(app)
        if app.page=='VIEW NAV':
            state['title']='VIEW NAV'
            state['view_nav_footer']=('ZOOM ' if app.view_field==0 else 'SCROLL ')+str(app.view_count)
        return state
    state=dict(kind=app.page,keys=app.softkeys(),active=tuple(app.active_softkeys()),message=visible_message(app),pinned=pinned(app))
    if app.page=='MIXER':
        from app.layout import GROUP_BASE,MASTER
        from app.routing import route_defaults
        bus,count=app.mixer_watch();levels=app.mixer_levels;first=0 if app.mixer_level==0 else app.group//8*8 if app.mixer_level==1 else app.pad//8*8
        selected=0 if app.mixer_level==0 else app.group if app.mixer_level==1 else app.pad
        names=('M',) if app.mixer_level==0 else tuple(app.group_name(first+i) for i in range(count)) if app.mixer_level==1 else tuple(f'{first+i+1:02}' for i in range(count))
        target=app.mixer_target();pan=route_defaults(target)['pan']
        title='MASTER' if app.mixer_level==0 else f'GROUP {names[0]}-{names[-1]}' if app.mixer_level==1 else f'SOUND {app.group_name()} {first+1:02}-{first+count:02}'
        value=f'{target.get("gain",100)}%' if app.mixer_field==0 else 'C' if pan==0 else f'{abs(pan)}'+('L' if pan<0 else 'R')
        if app.mixer_field==2:value=route_defaults(target)['dest']
        peak=max(app.mixer_peaks.get(app.mixer_bus(),(0,0)))
        state.update(title=title,first=first,selected=selected,names=names,
                     master_mixer=app.mixer_level==0,mixer_field=app.mixer_field,mixer_value=value,
                     levels=tuple(tuple(levels.get(bus+i,(0,0))) for i in range(count)),
                     peaks=tuple(tuple(app.mixer_peaks.get(bus+i,(0,0))) for i in range(count)),
                     footer=f'{names[selected-first]} {("VOL","PAN","OUT")[app.mixer_field]} {value} PK '+(f'{20*math.log10(peak):.1f}' if peak>0 else '-INF'))
    elif app.page in ('PATTERN','SCENE'):
        pattern=app.page=='PATTERN';length=app.pattern_steps() if pattern else app.scene_steps()
        phase=max(0,app.clock_phase)%(length*24)
        state.update(title=app.page,selected=(app.pattern if pattern else app.scene)+1,
                     bank=(app.pattern_bank if pattern else app.scene_bank)+1,length=length,
                     playing=bool(app.playing),position=f'{phase//384+1}:{phase%384//96+1}:{phase%96//24+1}',progress=phase/(length*24))
    elif app.page=='VIEW NAV':
        song=app.project['song'];count=app.view_song_count;first=app.view_song_first;columns=min(8,count)
        state.update(title='VIEW NAV',first=first,count=count,song_length=len(song),
                     scenes=tuple(song[index]+1 if index<len(song) else None for index in (first+col*count//columns for col in range(columns))),
                     footer=('ZOOM ' if app.view_field==0 else 'SCROLL ')+str(count))
    return state


def live_frame(state):
    if state.get('kind')=='MIKRO NAV':
        from app.mikro_navigate import render
        return render(state)
    from app.fokus import enabled,live
    pixels=legacy_live_frame(state)
    if enabled() and state.get('kind') not in ('CONTROL','PATTERN GRID'):return live(state,pixels)
    return pixels


def legacy_live_frame(state):
    if state.get('kind')=='CONTROL':
        from app.control_display import control_frame
        return control_frame(state)
    if state.get('kind')=='PATTERN GRID':
        from app.pattern_display import pattern_frame
        return pattern_frame(state)
    if state.get('kind') not in ('MIXER','PATTERN','SCENE','VIEW NAV'):
        from app.step_display import step_frame
        return step_frame(state)
    p=bytearray([1]*8192)
    for i,key in enumerate(state['keys']):
        x=i*43;w=40 if i==2 else 41;active=i in state['active']
        if key in ('','-'):dotted_rect(p,x+1,1,w,10)
        else:rect(p,x+1,1,w,10,0,active);softkey_label(p,x+1,w,key,1 if active else 0)
    rect(p,1,12,126,11,0);label(p,4,15,state['title'],1,bold=True,max_width=120)
    kind=state['kind']
    if kind=='MIXER':
        count=len(state['levels']);width=124//count
        for index,(left,right) in enumerate(state['levels']):
            slot=state['first']+index;x=3+index*width
            meter_width=width-5;half=max(1,(meter_width-3)//2)
            rect(p,x,26,meter_width,24,0,False)
            for channel,peak in enumerate((left,right)):
                offset=1+channel*(half+1);height=meter_height(peak)
                if height:rect(p,x+offset,48-height,half,height,0)
                held=state['peaks'][index][channel]
                if held>0:rect(p,x+offset,48-max(1,meter_height(held)),half,1,0)
                if held>=1:rect(p,x+offset,27,half,1,0)
            if slot==state['selected']:rect(p,x-1,25,meter_width+2,26,0,False)
            label(p,x,52,state['names'][index],font='regular5')
        label(p,2,58,state['footer'],font='regular5',max_width=124)
    elif kind in ('PATTERN','SCENE'):
        label(p,2,26,f'{kind} {state["selected"]} B{state["bank"]}')
        if state['playing']:
            label(p,2,36,state['position'],tabular_digits=True,font='regular5')
            rect(p,43,36,83,5,0,False);rect(p,44,37,max(1,round(state['progress']*81)),3,0)
        rect(p,1,43,126,1,0)
        label(p,1,48,'1/1: LENGTH',center=True,max_width=110,font='regular5')
        label(p,1,57,f'{state["length"]/16:g} BAR',center=True,bold=True,max_width=122)
    else:
        columns=len(state['scenes'])
        for col,scene in enumerate(state['scenes']):
            x=2+col*(124//columns);rect(p,x,29,122//columns,16,0,False)
            tiny_label(p,x+2,34,f'{scene:02}' if scene is not None else '--')
        tiny_label(p,2,23,f'SONG {state["first"]+1}-{min(state["song_length"],state["first"]+state["count"])}' if state['song_length'] else 'EMPTY SONG')
        label(p,2,56,state['footer'])
    from app.fokus import enabled
    if state['message'] and not enabled():
        rect(p,0,55,128,8,0);label(p,2,56,state['message'],1)
    return bytes(finish_frame(p))
