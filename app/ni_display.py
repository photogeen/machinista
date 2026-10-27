"""Independent 128x64 layouts following the Mikro manual's monochrome hierarchy.
Logical pixel 1 is dark, pixel 0 is light in these original-style layouts.
"""
from pathlib import Path
import time
import math
from app.surface import PROCESSING

from app.lcd_font import FONTS
from app.lcd_text import display_text


def width(value,tabular_digits=False,font='regular7',bold=False,preserve_case=False):
    value=display_text(str(value))
    glyphs=FONTS['bold5' if bold else font]
    digit_width=7 if font=='regular7' and not bold else max(len(glyphs[c][0]) for c in '0123456789')
    return max(0,sum((digit_width if tabular_digits and c.isdigit() else len(glyphs.get(c,glyphs[' '])[0]))+1 for c in (value if preserve_case else value.upper()))-1)


def rect(p,x,y,w,h,color,fill=True):
    for yy in range(max(0,y),min(64,y+h)):
        for xx in range(max(0,x),min(128,x+w)):
            if fill or yy in (y,y+h-1) or xx in (x,x+w-1):p[yy*128+xx]=color

def label(p,x,y,value,color=0,center=False,tabular_digits=False,bold=False,max_width=None,font='regular7',preserve_case=False):
    value=display_text(str(value));value=value if preserve_case else value.upper();glyphs=FONTS['bold5' if bold else font]
    if max_width is not None:
        while value and width(value,tabular_digits,font,bold,preserve_case)>max_width:value=value[:-1]
    if center:x=max(x,(128-width(value,tabular_digits,font,bold,preserve_case))//2)
    digit_width=7 if font=='regular7' and not bold else max(len(glyphs[c][0]) for c in '0123456789')
    for c in value:
        rows=glyphs.get(c,glyphs[' ']);w=len(rows[0])
        cell_width=digit_width if tabular_digits and c.isdigit() else w
        glyph_x=x+(cell_width-w)//2
        if x+cell_width>127:break
        for yy,row in enumerate(rows):
            for xx,bit in enumerate(row):
                if bit=='1' and 0<glyph_x+xx<127 and 0<y+yy<63:p[(y+yy)*128+glyph_x+xx]=color
        x+=cell_width+1


def name(app):
    from app.sound_names import sound_name
    return sound_name(app,empty=f'SOUND {app.pad+1}')

def note_name(note):
    return ('C','C#','D','D#','E','F','F#','G','G#','A','A#','B')[note%12]+str(note//12-2)


def tiny_label(p,x,y,value,color=0):
    from tools.mikro_feedback import GLYPHS
    for c in value.upper():
        glyph='101111101111101' if c=='#' else GLYPHS.get(c,GLYPHS[' '])
        for yy in range(5):
            for xx in range(3):
                if glyph[yy*3+xx]=='1':p[(y+yy)*128+x+xx]=color
        x+=4

def softkey_label(p,left,tab_width,text,color):
    text=display_text(str(text))
    small=width(text,font='regular5')>tab_width-4
    shown=text[:9] if small else text
    if small:
        from tools.mikro_feedback import GLYPHS
        rows=[GLYPHS.get(c,GLYPHS[' ']) for c in shown.upper()]
        columns=[i*4+x for i,glyph in enumerate(rows) for y in range(5) for x in range(3) if glyph[y*3+x]=='1']
    else:
        columns=[];offset=0
        for c in shown.upper():
            glyph=FONTS['regular5'].get(c,FONTS['regular5'][' '])
            columns.extend(offset+x for row in glyph for x,bit in enumerate(row) if bit=='1');offset+=len(glyph[0])+1
    if not columns:return
    first,last=min(columns),max(columns)
    x=left+(tab_width-(last-first+1))//2-first
    if small:tiny_label(p,x,3,shown,color)
    else:label(p,x,3,shown,color,font='regular5')


def pattern_grid(p,app):
    from app.pattern_display import pattern_body,pattern_state
    pattern_body(p,pattern_state(app))


def dotted_rect(p,x,y,w,h):
    for xx in range(x,x+w,2):
        rect(p,xx,y,1,1,0);rect(p,xx,y+h-1,1,1,0)
    for yy in range(y,y+h,2):
        rect(p,x,yy,1,1,0);rect(p,x+w-1,yy,1,1,0)


def finish_frame(p):
    # One dark pixel around every view, including message overlays.
    rect(p,0,0,128,1,1);rect(p,0,63,128,1,1)
    rect(p,0,0,1,64,1);rect(p,127,0,1,64,1)
    return p


def formatted(value,key=''):
    if key=='midi_target' and isinstance(value,str) and value.startswith('GROUP '):
        index=int(value.split()[1]);return 'GROUP '+chr(65+index%8)+(str(index//8+1) if index>=8 else '')
    if type(value) is bool:return 'ON' if value else 'OFF'
    if key in ('note','root','key_lo','key_hi','edit_note','edit_input') and isinstance(value,(int,float)):return note_name(int(value))
    if key in ('gain','aux1_level','aux2_level','input_gain'):
        return '-INF DB' if float(value)<=0 else f'{20*math.log10(float(value)/100):.1f} DB'
    if key in ('attack','hold','decay','release','mod_attack','mod_decay','glide'):return f'{value:g} MS'
    if key in ('cutoff','lfo_rate'):return f'{value:g} HZ'
    if key in ('tune','eq_gain'):return f'{value:.2f}'+(' DB' if key=='eq_gain' else '')
    if key=='pan':return 'CENTER' if value==0 else f'{abs(value):g} % '+('L' if value<0 else 'R')
    if key in ('amount','comp','drive','sr','resonance','sustain','vel_volume','vel_cutoff','vel_start','wheel_cutoff','wheel_pan','mod_cutoff','gate','dynamic'):return f'{value:g} %'
    if key in ('choke_group','link_group') and value==0:return 'NONE'
    return str(value).replace('_',' ')


def plugin_value(port,value):
    if port.get('synth_inactive'):return 'N/A'
    if port.get('profile_action')=='synth_wave':value=port['default']
    if port.get('preset_parameter') and value<=-999:
        if 'preset_value' not in port:return 'PRESET'
        value=port['preset_value']
    if port.get('unit')=='pan':return 'RND' if value==64 else 'C' if value==0 else ('L' if value<0 else 'R')+str(abs(round(value)))
    for number,label in port.get('choices',()):
        if abs(number-(round(value) if port.get('integer') else value))<1e-6:return label
    if port.get('toggle'):return 'ON' if value>=.5 else 'OFF'
    if port.get('unit')=='cents':
        from app.plugin_units import cents_label
        return cents_label(port,value)
    unit=port.get('unit')
    if unit=='signed_percent':return f'{round(value*100):+d}%' if value else '0%'
    if unit=='octaves':return f'{value:+.2f} OCT'
    if unit=='semitones':return f'{value:+.1f} ST'
    if unit=='db':return f'{value:.1f} DB'
    if unit=='ratio':return f'{value:.1f}:1'
    if unit=='amplitude_db':
        import math
        return f'{20*math.log10(value):+.1f} DB' if value>0 else '-INF DB'
    if unit=='hz':return f'{value/1000:.2f} KHZ' if abs(value)>=1000 else f'{value:.2f} HZ' if abs(value)<10 else f'{value:.0f} HZ'
    if unit=='ms':return f'{value:.1f} MS' if abs(value)<10 else f'{value:.0f} MS'
    if unit=='s':return f'{value:.2f} S'
    if unit=='degree':return f'{value:.0f} DEG'
    if port.get('integer'):return str(round(value))
    from app.plugin_units import normalized,percent
    if normalized(port):return percent(value)
    return f'{value:.3g}'


def nav_tiles(p,labels,index,title,detail,prev=False,next=True,disabled_top=False):
    if disabled_top:
        for i in range(3):dotted_rect(p,1+i*43,2,40,10)
    for col,text in enumerate(labels):
        x=3+col*31;selected=col==index
        rect(p,x,17,29,14,0,selected)
        label(p,x+(29-width(text,font='regular5'))//2,22,text,1 if selected else 0,font='regular5')
        if selected:rect(p,x+13,32,3,4,0)
    rect(p,1,37,126,26,0,False);rect(p,1,37,126,11,0)
    label(p,3,40,title,1,bold=True,max_width=121)
    label(p,2,53,detail,center=True,font='regular5')
    if prev:label(p,3,53,'<',font='regular5')
    if next:label(p,121,53,'>',font='regular5')
    return finish_frame(p)


def sampling_navigation(p,app):
    from app.sampler import ZONE_PAGES
    index=app.sampling_nav
    if index==4:
        label(p,4,18,'AUTO',bold=True,max_width=120)
        label(p,4,35,'AUTOSAMPLER',max_width=120)
        label(p,4,48,'RELEASE NAV TO OPEN',font='regular5',max_width=120)
        return finish_frame(p)
    detail=(('MONITOR' if app.capture_section else 'RECORD'),
            ('SEL. RANGE' if app.range_page else 'PLAY RANGE'),
            ('ENGINE' if app.slice_section else 'TIME'),
            ('PLAY RANGE','LOOP','TUNE / MIX','ENVELOPE','MAP')[app.zone_page])[index]
    prev=(app.capture_section>0,app.range_page>0,app.slice_section>0,app.zone_page>0)[index]
    next=(app.capture_options()['source']!='INTERNAL' and not app.capture_section,
          not app.range_page,app.slice_mode=='DETECT' and not app.slice_section,app.zone_page<4)[index]
    return nav_tiles(p,('REC','EDIT','SLICE','ZONE'),index,('RECORD','EDIT','SLICE','ZONE')[index],detail,prev,next,True)


def zone_waveform(p,app,envelope):
    zone=app.zone()
    if not zone or not envelope or not envelope.frames:
        label(p,2,30,'NO SAMPLE' if not zone else 'LOADING WAVE');return
    span=max(1,(envelope.frames if envelope.end is None else envelope.end)-envelope.start)
    def wx(value):return max(3,min(124,3+round((value-envelope.start)/span*121)))
    rect(p,2,23,124,19,0,False)
    for col,(low,high) in enumerate(envelope.peaks[:120]):
        x=4+col;source=envelope.start+col/120*span
        selected=zone['start']<=source<zone['end']
        for yy in range(max(24,32-round(high*8)),min(40,32-round(low*8))+1):
            if selected or (x+yy)%2==0:p[yy*128+x]=0
    for marker in (zone['start'],zone['end']):rect(p,wx(marker),23,1,19,0)
    if zone['loop']:
        rect(p,wx(zone['loop_start']),24,max(1,wx(zone['loop_end'])-wx(zone['loop_start'])),2,0)


def parameter_navigation(p,app):
    # NAV has its own hierarchy, without the ordinary focus/tempo header.
    for x,w,text,selected in ((43,40,'CHNL.',app.parameter_kind=='CHNL'),
                               (85,42,'PLUG-IN',app.parameter_kind=='PLUG-IN')):
        rect(p,x,1,w,10,0,selected)
        label(p,x+(w-width(text,font='regular5'))//2,3,text,1 if selected else 0,font='regular5')
    rect(p,1,10,126,1,0)
    choices=app.parameter_choices();index=min(app.parameter_choice,len(choices)-1)
    first=max(0,index-3);visible=choices[first:first+4]
    aliases={'INPUT':'IN','OUTPUT':'OUT','GROOVE':'GRV','MACRO':'MCR','SAMPLER':'1','ADD PLUGIN':'+'}
    for col,choice in enumerate(visible):
        x=11+col*26;selected=first+col==index
        rect(p,x,17,25,14,0,selected)
        caption=aliases.get(choice,str(first+col+1))
        label(p,x+(25-width(caption,font='regular5'))//2,22,caption,1 if selected else 0,font='regular5')
        if selected:rect(p,x+10,32,3,4,0)
    if app.parameter_kind=='PLUG-IN':
        for col in range(len(visible),4):dotted_rect(p,11+col*26,17,25,14)
    choice=choices[index];title=choice;detail='AUDIO';page=0;pages=1
    if app.parameter_kind=='CHNL':
        detail={'INPUT':'AUDIO','OUTPUT':('AUDIO','AUX 1','AUX 2','MIDI')[app.channel_page],
                'GROOVE':'GROOVE','MACRO':'MACROS'}[choice]
        if choice=='OUTPUT':page=app.channel_page;pages=4 if app.control_level==2 else 3
    elif choice=='SAMPLER':
        from app.sampler import SAMPLER_PAGES
        detail=SAMPLER_PAGES[app.sampler_page][0]
        page=app.sampler_page;pages=len(SAMPLER_PAGES)
    elif choice=='ADD PLUGIN':title='(NONE)';detail='NO PARAMETER PAGE'
    else:
        slot=max(0,index-int(app.sampler_slot_present()));chain=app.plugin_target().get('plugins',[])
        meta=app.plugin_metadata(chain[slot]['uri']) if slot<len(chain) else None
        title=meta['name'] if meta else choice;detail='PARAMETERS'
        count=len(meta['ports']) if meta else 0
        if meta:
            from app.plugin_profiles import controls
            count=len(controls(app,chain[slot],meta['ports']))
        page=app.plugin_param//8;pages=max(1,math.ceil(count/8))
    rect(p,1,37,126,26,0,False);rect(p,1,37,126,11,0)
    label(p,3,40,title,1,bold=True,max_width=121)
    label(p,2,53,detail,center=True,font='regular5')
    if page>0:label(p,3,53,'<',font='regular5')
    if page<pages-1:label(p,121,53,'>',font='regular5')
    return finish_frame(p)


def system_body(p, app):
    from app.system_info import system_page_count,core_page_count
    stats=app.system_stats;count=system_page_count(stats)
    app.system_index=min(app.system_index,count-1)
    # Product name keeps the requested casing; no HEADLESS subtitle.
    rect(p,1,12,126,11,0)
    label(p,4,14,'Machinista',1,preserve_case=True)
    page=f'{app.system_index+1}/{count}'
    label(p,123-width(page,font='regular5'),15,page,1,font='regular5')
    def gauge(y, caption, percent, detail='', compact=False):
        label(p,3,y,caption,font='regular5',max_width=90)
        value='--%' if percent is None else f'{round(percent)}%'
        label(p,124-width(value,font='regular5'),y,value,font='regular5')
        rect(p,3,y+7,122,4 if compact else 6,0,False)
        if percent is not None:rect(p,5,y+(8 if compact else 9),round(118*max(0,min(100,percent))/100),2,0)
        if detail:label(p,3,y+(13 if compact else 15),detail,font='regular5',max_width=121)
    if app.system_index==0:
        from app.branding import paint_logo,VERSION
        paint_logo(p,128,4,27,120)
        label(p,2,52,VERSION,center=True,font='regular5')
    elif app.system_index==1:
        gauge(25,'CPU',stats['cpu'])
        ram=stats['ram']
        gauge(43,'RAM',ram['percent'] if ram else None)
    elif app.system_index<2+core_page_count(stats):
        rows=stats.get('cpu_cores',[])[(app.system_index-2)*4:(app.system_index-1)*4]
        for i,core in enumerate(rows):
            y=25+i*9;value=core['percent'];label(p,3,y,'C'+str(core['id']+1),font='regular5')
            rect(p,21,y,69,6,0,False)
            if value is not None:rect(p,23,y+2,round(65*max(0,min(100,value))/100),2,0)
            caption='--%' if value is None else f'{round(value)}%'
            label(p,124-width(caption,font='regular5'),y,caption,font='regular5')
    else:
        first=(app.system_index-2-core_page_count(stats))*2
        disks=stats['storage'][first:first+2]
        for i,disk in enumerate(disks):
            gauge(24+i*20,'SD' if disk['name']=='SD CARD' else disk['name'],disk['percent'],f'{disk["used"]/1e9:.1f}/{disk["total"]/1e9:.1f} GB',compact=True)
        if not disks:label(p,3,29,'READING STORAGE',font='regular5')


def frame(app,envelope=None):
    from app.fokus import enabled,utility
    if enabled() and app.page=='PATTERN GRID':
        from app.pattern_display import pattern_frame,pattern_state
        return pattern_frame(pattern_state(app))
    pixels=legacy_frame(app,envelope)
    if not enabled():return pixels
    from app.live_display import ASYNC_PAGES
    if app.page in ASYNC_PAGES:return pixels
    return utility(app,pixels,envelope)


def legacy_frame(app,envelope=None):
    from app.control_display import PARAMETER_PAGES,control_frame,control_state
    if app.page in PARAMETER_PAGES:return control_frame(control_state(app))
    if app.page in ('MIXER','PATTERN','SCENE','VIEW NAV'):
        from app.live_display import live_state,live_frame
        return live_frame(live_state(app))
    if app.page=='STEP':
        from app.step_display import step_frame,step_state
        return step_frame(step_state(app))
    p=bytearray([1]*8192)
    if app.page=='PARAM NAV':return parameter_navigation(p,app)
    if app.page=='SAMPLING NAV':return sampling_navigation(p,app)
    keys=app.softkeys();active=app.active_softkeys()
    disabled=set()
    if app.page=='ZONE':
        from app.sampler import zones
        if app.zone_index==0:disabled.add(0)
        if app.zone_index>=len(zones(app.track()))-1:disabled.add(1)
    if app.page=='SAMPLING' and app.capture_started is None and not app.capture_armed:
        history=app.record_history.get((app.group,app.pad),[]);cursor=app.record_cursor.get((app.group,app.pad),len(history)-1)
        if cursor<=0:disabled.add(1)
        if cursor>=len(history)-1:disabled.add(2)
    if app.page=='SAMPLING' and app.capture_started is None and not app.capture_armed:keys=('START','PREV','NEXT')
    for i,k in enumerate(keys):
        x=i*43;tab_width=40 if i==2 else 41
        unavailable=i in disabled or k in ('','-')
        if unavailable:dotted_rect(p,x+1,1,tab_width,10)
        else:rect(p,x+1,1,tab_width,10,0,i in active)
        if k in ('','-'):continue
        softkey_label(p,x+1,tab_width,k,1 if i in active and not unavailable else 0)
    from app.navigation import CONTROL_PAGES
    title={'PAD':'MASTER' if app.control_level==0 else f'GROUP {app.group_name()}' if app.control_level==1 else name(app),
           'OPTIONS':'GRID','RECORD SETTINGS':'RECORD SETUP','PAD CONFIG':'PAD MODE','SAMPLING':'RECORD: MONITOR' if app.capture_section else 'RECORD',
           'SAMPLE EDIT':'EDIT: '+name(app),'CHOP':'SLICE: ENGINE' if app.slice_section and app.slice_mode=='DETECT' else 'SLICE','PATTERN GRID':f'PAT {app.pattern+1:02} GROUP {app.group_name()}','GRID EDIT':'EVENT EDIT','PATTERN':'PATTERN','SCENE':'SCENE',
           'MUTE':'MUTE SOUND','SOLO':'SOLO SOUND','STEP':'STEP MODE','BROWSE':app.browser.title()}.get(app.page,app.page)
    if app.page=='PROJECT NAME' and app.name_action in ('SAVE SOUND','SAVE GROUP'):title=app.name_action
    if app.page=='RELINK BROWSE':title=app.relink_browser.title()
    if app.page=='RELINK RESULTS':title='RELINK: CHOOSE FILE'
    if app.page=='PRESET LOAD':title='LOAD '+app.preset_kind
    if app.page=='SETTINGS':title=app.settings_title()
    if app.page=='RECORD PREPARE':title='RECORD'
    if app.page in CONTROL_PAGES:
        title=app.project['name'] if app.control_level==0 else f'{app.group_name()}. '+app.project['groups'][app.group].get('name','GROUP') if app.control_level==1 else f'{app.pad+1}. '+name(app)
    if app.page in ('SAMPLE EDIT','CHOP','ZONE','STRETCH','SAMPLING'):
        title=name(app) if app.track()['sample'] else 'NO RECORDED SAMPLE' if app.page=='SAMPLING' else 'NO SAMPLE'
    if app.page=='SAMPLING' and not app.record_history.get((app.group,app.pad)):title='NO RECORDED SAMPLE'
    if app.page in CONTROL_PAGES+('PAD CONFIG','TEMPO','STEP','PATTERN GRID') and (app.playing or app.recording or app.count_remaining):
        title=app.transport_title()
    rect(p,1,12,126,11,0);label(p,4,15,title,1,bold=True,max_width=120)
    position=app.pattern_position()
    if app.page in CONTROL_PAGES:
        label(p,125-width(position,True),29,position,tabular_digits=True)
    if app.page in ('STEP','MUTE','SOLO','NOTE REPEAT','ARP','OPTIONS','RECORD SETTINGS','RECORD PREPARE'):
        tempo_y=25 if app.page=='STEP' else 29
        label(p,3,tempo_y,f'{app.project["tempo"]:.2f}');label(p,125-width(position,True),tempo_y,position,tabular_digits=True)
    def parameter(caption,value):
        import re
        rect(p,1,43,126,1,0)
        label(p,1,48,caption,center=True,max_width=110,font='regular5')
        label(p,1,57,str(value),center=True,bold=True,max_width=122)
        indexed=re.search(r'(\d+)/(\d+):',caption)
        if indexed:
            index,count=map(int,indexed.groups())
            if index>1:label(p,2,48,'<',font='regular5')
            if index<count:label(p,122,48,'>',font='regular5')
    from app.preferences import PREFERENCES
    if app.page in PREFERENCES:
        key,_,_=PREFERENCES[app.page]
        from app.controller_settings import preference_values
        parameter(app.page,str(preference_values(app,key)[key])+(' MS' if app.page=='MIDI OFFSET' else ''))
    elif app.page in ('SAMPLE EDIT','CHOP'):
        if envelope and envelope.frames:
            track=app.track();start,end=track['start'],track['end']
            if app.page=='SAMPLE EDIT' and app.range_page:start,end=track.get('selection_start',start),track.get('selection_end',end)
            view_start=envelope.start;view_end=envelope.frames if envelope.end is None else envelope.end
            span=max(1,view_end-view_start)
            def wx(frame):return 4+round((frame-view_start)/span*119)
            for col,(low,high) in enumerate(envelope.peaks):
                x=4+col;inside=start<=view_start+col/120*span<end
                background=1 if app.page=='CHOP' else 0
                rect(p,x,24,1,18,background)
                for yy in range(max(24,33-round(high*8)),min(41,33-round(low*8))+1):
                    if inside or (x+yy)%2==0:p[yy*128+x]=1-background
            for marker in (start,end):
                if view_start<=marker<=view_end:
                    x=max(4,min(123,wx(marker)));rect(p,x,22,1,22,0 if app.page=='CHOP' else 1)
            if app.page=='CHOP':
                ranges=app.slice_ranges()
                for a,b in ranges[1:]:
                    marker=a
                    if view_start<=marker<=view_end:rect(p,wx(marker),22,1,22,0)
                a,b=ranges[min(app.slice_index,len(ranges)-1)]
                left,right=wx(a),wx(b)
                for y in range(24,42):
                    for x in range(max(4,left),min(124,right)):p[y*128+x]^=1
        else:label(p,2,30,'NO SAMPLE' if not app.track()['sample'] else 'LOADING WAVE')
        if app.wave_view():
            zoom=envelope.frames/max(1,span) if envelope and envelope.frames else 2**app.wave_zoom
            parameter(('1/2: ZOOM' if app.view_field==0 else '2/2: POSITION') if app.wave_selected else 'PRESS F2: WAVE',f'X{zoom:g} POS {app.wave_offset*100//max(1,envelope.frames if envelope else 1)}%')
        elif app.page=='CHOP':
            ranges=app.slice_ranges()
            if app.slice_edit:
                captions=('SLICE','START','END');values=(app.slice_index+1,)+tuple(ranges[min(app.slice_index,len(ranges)-1)]) if ranges else (0,0,0)
                parameter(f'{app.slice_field+1}/3: '+captions[app.slice_field],values[app.slice_field])
            else:
                captions,values=app.slice_parameters()
                field=min(app.slice_field,len(captions)-1)
                parameter(f'{field+1}/{len(captions)}: '+captions[field],formatted(values[field]))
        else:
            key=('selection_' if app.range_page else '')+('start' if app.sample_field==0 else 'end')
            parameter((f'Z{app.zone_index+1:02} ' if app.track().get('slice_source') else '')+f'{app.sample_field+1}/2: '+('START' if app.sample_field==0 else 'END'),app.track().get(key,app.track()['start' if app.sample_field==0 else 'end']))
    elif app.page=='GROUP':
        label(p,2,26,f'BANK {app.group_bank+1}/8');label(p,2,37,'PADS A-H');parameter('GROUP',app.group_name())
    elif app.page in ('MUTE','SOLO'):
        rect(p,1,43,126,1,0)
    elif app.page in ('ARP','NOTE REPEAT'):
        from app.performance import ARP_DEFAULTS
        key=tuple(ARP_DEFAULTS)[app.arp_field];value=app.project['repeat_presets'][app.repeat_bank*2+app.repeat_preset] if key=='rate' else app.project['arp'][key]
        parameter(f'{app.arp_field+1}/8: '+key.upper(),'1/'+str(value) if key=='rate' else formatted(value,key))
    elif app.page=='EXPORT DONE':
        label(p,2,26,app.export_result_device[:10]+': exports/',font='regular5',max_width=124)
        result=Path(app.export_result).name
        label(p,2,37,result[:24],font='regular5',max_width=124)
        label(p,2,46,result[24:48],font='regular5',max_width=124)
    elif app.page=='EXPORT':
        from app.export_audio import FIELDS
        if app.export_busy:
            label(p,2,28,app.export_status,font='regular5',max_width=124)
            label(p,2,40,'F1 CANCEL',font='regular5')
        else:
            label(p,2,26,'MIDI / 96 PPQ' if app.export_kind=='MIDI' else f'{app.export_format} {app.export_bits}'+('F' if app.export_bits==32 else ' BIT')+' / STEREO',font='regular5')
            fields=app.export_fields()
            parameter(f'{app.export_field+1}/{len(fields)}: '+fields[app.export_field],app.export_value())
    elif app.page=='PROJECT MANAGE':
        from app.project_manager import MANAGE
        first=max(0,app.manage_index-1)
        for i,choice in enumerate(MANAGE[first:first+3]):
            selected=first+i==app.manage_index
            if selected:rect(p,1,24+i*11,126,10,0)
            label(p,2,25+i*11,choice,1 if selected else 0)
    elif app.page=='MISSING SAMPLES':
        rows=app.missing_rows;first=max(0,app.missing_index-1)
        if app.relink_busy:label(p,3,27,'SCANNING...',font='regular5')
        elif not rows:label(p,3,27,'NO MISSING SAMPLES',font='regular5')
        else:
            for i,row in enumerate(rows[first:first+2]):
                selected=first+i==app.missing_index
                if selected:rect(p,1,24+i*11,126,10,0)
                label(p,3,25+i*11,Path(row['path']).name,1 if selected else 0,font='regular5',max_width=121)
            row=app.selected_missing();g,s=row['slots'][0]
            label(p,3,49,f'{app.group_name(g)}:{s+1:02} {len(row["slots"])} SND',font='regular5',max_width=88)
            count=f'{app.missing_index+1}/{len(rows)}'
            label(p,124-width(count,font='regular5'),49,count,font='regular5')
    elif app.page=='RELINK RESULTS':
        if app.relink_busy:label(p,3,27,'SEARCHING...',font='regular5')
        elif not app.relink_paths:
            label(p,3,27,'NO MATCHING WAV',font='regular5');label(p,3,40,'USE F3 BROWSE',font='regular5')
        else:
            path=Path(app.relink_paths[app.relink_index])
            rect(p,1,24,126,10,0);label(p,3,25,path.name,1,font='regular5',max_width=121)
            folder=str(path.parent)
            while folder and width(folder,font='regular5')>121:folder=folder[1:]
            label(p,3,39,folder,font='regular5',max_width=121)
            label(p,3,49,f'{app.relink_index+1}/{len(app.relink_paths)} MATCHES',font='regular5')
    elif app.page=='RELINK BROWSE':
        browser=app.relink_browser;entries=browser.entries();first=max(0,browser.index-1)
        for i,path in enumerate(entries[first:first+3]):
            selected=first+i==browser.index
            if selected:rect(p,1,24+i*11,126,10,0)
            label(p,3,25+i*11,browser.label(path),1 if selected else 0,font='regular5',max_width=121)
        if not entries:label(p,3,27,'EMPTY FOLDER',font='regular5')
    elif app.page=='PRESET LOAD':
        files=app.preset_files();first=max(0,app.preset_index-1)
        for i,path in enumerate(files[first:first+3]):
            selected=first+i==app.preset_index
            if selected:rect(p,1,24+i*11,126,10,0)
            label(p,3,25+i*11,path.parent.name,1 if selected else 0,font='regular5',max_width=121)
        if not files:label(p,3,28,'NO '+app.preset_kind+' PRESETS',font='regular5')
    elif app.page=='PROJECT NAME':
        label(p,2,23,app.name_action or 'NAME')
        first=max(0,app.name_cursor-16)
        value=app.name_value.upper().ljust(32)
        for i,c in enumerate(value[first:first+17]):
            selected=first+i==app.name_cursor
            if selected:rect(p,2+i*7,33,7,9,0)
            label(p,3+i*7,34,c,1 if selected else 0)
        label(p,2,46,f'CHAR {app.name_cursor+1:02}/32')
        tiny_label(p,2,57,'ARROWS:CURSOR ENC:CHAR')
    elif app.page=='MACRO ASSIGN':
        choices=app.macro_targets();choice=choices[app.macro_choice] if choices else None
        label(p,2,27,choice['name'] if choice else 'NO LV2 PARAMETERS');parameter('TARGET',f"BUS {choice['bus']} SLOT {choice['slot']+1}" if choice else '-')
    elif app.page=='PLUGIN BROWSE':
        items=[{'name':'REMOVE PLUG-IN' if app.plugin_selected() else '*EMPTY SLOT*'}]+app.plugin_items();first=max(0,app.plugin_browser_index)
        for row,item in enumerate(items[first:first+3]):
            selected=first+row==app.plugin_browser_index+1
            if selected:rect(p,1,25+row*10,126,9,0)
            label(p,3,26+row*10,item['name'],1 if selected else 0)
        if len(items)==1 and app.plugin_browser_index!=-1:label(p,2,28,'NO COMPATIBLE PLUGINS')
        label(p,2,56,'LV2 '+app.plugin_filter)
    elif app.page=='PLUGIN MOVE':
        label(p,2,26,'MOVE PLUGIN');parameter('DESTINATION SLOT',app.plugin_move_to+1)
    elif app.page=='ZONE':
        from app.sampler import ZONE_PAGES,zones
        z=app.zone();zone_waveform(p,app,envelope)
        key=ZONE_PAGES[app.zone_page][1][app.zone_field]
        parameter(f'{app.zone_field+1}/{len(ZONE_PAGES[app.zone_page][1])}: '+key.upper().replace('_',' '),formatted(z[key],key) if z else 'NO SAMPLE')
    elif app.page=='SLICE TARGET':
        target='ALL SOUNDS' if app.slice_target_sound is None else f'SOUND {app.slice_target_sound+1:02}'
        label(p,3,25,f'{app.group_name(app.slice_target_group)}: {target}',font='regular5',max_width=121)
        label(p,3,34,'GROUP + PAD: TARGET',font='regular5',max_width=121)
        parameter('1/2: PATTERN' if app.slice_target_field==0 else '2/2: MONO',app.slice_pattern if app.slice_target_field==0 else 'ON' if app.slice_options()['mono'] else 'OFF')
    elif app.page=='PATTERN GRID':
        pattern_grid(p,app)
    elif app.page=='GRID EDIT':
        targets=app.grid_targets();notes=app.event_notes()
        identity=sorted(targets)[0] if targets else (app.pad,app.grid_step*app.grid_ticks())
        row,tick=identity[:2];event=notes.get(identity,{'velocity':100,'probability':100})
        pitch=event.get('note',app.project['groups'][app.group]['pads'][row].get('note',36+row))
        label(p,2,25,f'PAD {row+1:02}  {len(targets)} EVENTS')
        label(p,2,36,f'GRID {app.timing()["grid"]}')
        position=f'{tick//384+1}:{tick%384//96+1}:{tick%96:02}'
        parameter(('1/5: POSITION','2/5: NOTE','3/5: VELOCITY','4/5: PROBABILITY','5/5: LENGTH')[app.grid_field],
                  (position,note_name(pitch),event['velocity'],str(event['probability'])+'%',str(event.get('length',app.grid_ticks()))+' TICKS')[app.grid_field])
    elif app.page=='EVENT':
        event=app.event();label(p,2,26,name(app))
        parameter(('1/3: STEP','2/3: VELOCITY','3/3: PROBABILITY')[app.event_field],
                  (app.event_step+1,event['velocity'],str(event['probability'])+'%')[app.event_field])
    elif app.page=='OPTIONS':
        t=app.timing()
        if app.grid_tab==2:
            parameter(('1/4: GRID','2/4: GRID ON','3/4: NUDGE','4/4: REC QUANT')[app.grid_field],
                      (t['grid'],'ON' if t['grid_on'] else 'OFF',t['nudge'],'ON' if t['record_quantize'] else 'OFF')[app.grid_field])
        elif app.grid_tab==1:
            parameter('1/1: SWING',str(t['swing'])+'%')
        else:
            parameter(('1/3: STRENGTH','2/3: TARGET','3/3: GRID')[app.grid_field],
                      (str(t['strength'])+'%',t['target'],t['grid'])[app.grid_field])
    elif app.page=='RECORD PREPARE':
        steps=app.pattern_steps()
        parameter('1/2: LENGTH' if app.prepare_field==0 else '2/2: PATGRID',f'{steps//16}:{steps%16//4}:{steps%4}' if app.prepare_field==0 else app.timing()['grid'])
    elif app.page=='RECORD SETTINGS':
        t=app.timing()
        parameter(('1/3: METRO LEVEL','2/3: COUNT LENGTH','3/3: REC QUANT')[app.record_field],
                  (str(t['metro_level'])+'%',str(t['count_bars'])+' BAR','ON' if t['record_quantize'] else 'OFF')[app.record_field])
    elif app.page=='MIDI TRACK':
        track=app.track();label(p,2,26,name(app))
        parameter(('1/3: SOURCE','2/3: NOTE','3/3: CHANNEL')[app.track_field],
                  (track['source'],track['note'],track['channel'])[app.track_field])
    elif app.page=='SELECT':
        label(p,2,26,('GROUP '+str(app.group+1)) if app.selection_level==1 else f'{app.pad+1}. '+name(app),max_width=123)
        label(p,2,35,f'{len(app.selected_groups) if app.selection_level==1 else len(app.selected_pads)} '+('GROUPS' if app.selection_level==1 else 'SOUNDS')+' SELECTED',max_width=123)
        rect(p,1,43,126,1,0)
    elif app.page=='DUPLICATE':
        label(p,2,26,'SELECT SOURCE PAD' if app.duplicate_source is None else 'SELECT TARGET PAD')
        parameter('COPY SOUND / PATTERN','+ EVENTS' if app.duplicate_events else 'SOUND ONLY')
    elif app.page=='STRETCH':
        zone_waveform(p,app,envelope)
        parameter(('1/2: LENGTH','2/2: PITCH')[app.sample_field],str(app.track().get('stretch_ratio',100))+'%' if app.sample_field==0 else app.track().get('stretch_pitch',0))
    elif app.page=='SAMPLE DELETE':
        for i,item in enumerate(('REMOVE FROM PAD','DELETE FILE')):
            selected=i==app.sample_delete_index
            if selected:rect(p,1,27+i*13,126,11,0)
            label(p,3,29+i*13,item,1 if selected else 0)
        label(p,2,56,'ENTER: CONFIRM')
    elif app.page=='SAMPLING':
        source=app.capture_options()['source'];internal=source=='INTERNAL'
        peaks=getattr(app,'capture_stereo_peak',(0.,0.))
        for channel,peak in enumerate(peaks):
            y=28+channel*8
            rect(p,3,y,118,6,0,False)
            level=max(0,min(114,round((20*math.log10(max(peak,0.001))+60)*114/60)))
            rect(p,5,y+2,level,2,0)
            rect(p,123,y,2,6,0,peak>=1)
        if app.capture_options()['mode']=='DETECT':
            threshold=5+max(0,min(113,round((app.capture_options()['threshold']+60)*114/60)))
            rect(p,threshold,25,1,2,0);rect(p,threshold-1,24,3,1,0)
            for channel in range(2):
                y=28+channel*8
                for yy in range(y-1,y+7):p[yy*128+threshold]^=1
        if app.capture_started is not None:
            # Keep meters visible while timing the take.
            seconds=max(0,int(time.monotonic()-app.capture_started))
            tiny_label(p,73,24,f'REC {seconds//60:02}:{seconds%60:02}')
        elif app.capture_armed:tiny_label(p,82,24,'WAITING')
        fields=app.capture_fields();app.capture_field=min(app.capture_field,len(fields)-1)
        key=fields[app.capture_field];value=app.capture_options()[key]
        if key=='source':value={'EXT STEREO':'EXT. STER.','EXT MONO':'EXT. MONO','INTERNAL':'INTERNAL'}[value]
        elif key=='input':value=app.capture_source_label()
        elif key=='monitor':value='ON' if value else 'OFF'
        elif key=='bars' and value!='FREE':value=str(value)+' BARS'
        parameter(f'{app.capture_field+1}/{len(fields)}: '+('LENGTH' if key=='bars' else key.upper()),str(value)+(' DB' if key=='threshold' else ''))
    elif app.page=='SYSTEM':
        system_body(p,app)
    elif app.page=='SETTINGS':
        from app.settings_menu import SETTINGS_LABELS
        entries=app.setting_entries();first=max(0,min(app.menu-1,len(entries)-3))
        for row,index in enumerate(range(first,min(first+3,len(entries)))):
            y=25+row*11;chosen=index==app.menu
            if chosen:rect(p,1,y-1,126,10,0)
            label(p,3,y,SETTINGS_LABELS.get(entries[index],entries[index]),1 if chosen else 0,max_width=122)
        label(p,2,57,f'{app.menu+1}/{len(entries)}',font='regular5')
    elif app.page=='BROWSE':
        entries=app.entries();entry=app.browser.selected();index=app.browser_index
        first=max(0,min(index-1,len(entries)-3))
        for row,path in enumerate(entries[first:first+3]):
            y=24+row*10;selected=first+row==index
            if selected:rect(p,1,y,126,9,0)
            label(p,3,y+1,('> ' if selected else '  ')+app.browser.label(path),1 if selected else 0)
        if not entries:label(p,2,28,'EMPTY FOLDER')
        tiny_label(p,2,57,app.browser.error or f'{index+1 if entries else 0}/{len(entries)} {app.group_name()}:{app.pad+1:02} '+('PREH ON' if app.browser.prehear else 'PREH OFF'))
    else:
        _,body,footer=app.display()
        for i,line in enumerate(body[:3]):
            if line.startswith('>'):
                rect(p,0,24+i*11,128,10,0);label(p,2,25+i*11,line[1:],1)
            else:label(p,2,25+i*11,line)
    if app.page in ('SAMPLE EDIT','CHOP','ZONE','STRETCH') and envelope and envelope.frames:
        from app.wave_playback import position,visible_path
        point=position(app,visible_path(app))
        if point is None and app.page=='CHOP':point=app.live_chop_position()
        first=envelope.start;last=envelope.frames if envelope.end is None else envelope.end
        if point is not None and first<=point<last:
            x=max(4,min(123,4+round((point-first)/max(1,last-first)*119)))
            for yy in range(24,42):p[yy*128+x]^=1
    from app.fokus import enabled
    if app.message and not enabled():
        rect(p,0,55,128,8,0);label(p,2,56,app.message,1)
    return finish_frame(p)
