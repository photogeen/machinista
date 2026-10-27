"""Fokus V2: live, monochrome layouts; no sample/audio work in the renderer.

Mikro logical 1 means black, MK2 logical 1 means white. Keep this distinction
at the drawing boundary. MACHINISTA_UI=v1 selects the preserved V1 renderers.
"""
import os
import re
import math
from app.lcd_font import FONTS
from app.lcd_text import display_text

_sound_waveforms=None


def sample_wave(c,ref,cache,y=32,height=14,playhead=None):
    path,start,end=ref
    if not path:return
    envelope=cache.envelope(path,start,end)
    if not envelope or not envelope.peaks:return
    middle=y+height//2;amplitude=max(1,height//2-1)
    for i,(lo,hi) in enumerate(envelope.peaks):
        x=4+i*(c.w-8)//len(envelope.peaks)
        top=middle-round(hi*amplitude);bottom=middle-round(lo*amplitude)
        c.rect(x,top,max(1,(c.w-8)//len(envelope.peaks)),max(1,bottom-top))

    end=envelope.frames if envelope.end is None else envelope.end
    if playhead is not None and envelope.start<=playhead<end:
        x=4+round((playhead-envelope.start)/max(1,end-envelope.start)*(c.w-9))
        for yy in range(y,y+height):c.p[yy*c.w+x]^=1


def enabled():
    return os.environ.get('MACHINISTA_UI', os.environ.get('MACHINIST_UI','v2')).lower() != 'v1'


class Canvas:
    def __init__(self, width=128):
        self.w=width;self.ink=0 if width==128 else 1
        self.bg=1-self.ink;self.fonts=FONTS
        if width==256:
            from app.mk2_font import FONTS as MK2_FONTS
            self.fonts=MK2_FONTS
        self.p=bytearray([self.bg]*(width*64));self.pinned=False

    def fitted(self,x,y,value,limit,font='regular5',ink=None,center=None):
        value=display_text(str(value))
        if self.text_width(value,font)>limit:
            # Preserve a distinguishing suffix, including a filename extension.
            left=(len(value)+1)//2;right=len(value)-left
            while left+right and self.text_width(value[:left]+'...'+(value[-right:] if right else ''),font)>limit:
                if left>right:left-=1
                else:right-=1
            value=value[:left]+'...'+(value[-right:] if right else '')
        self.text(x,y,value,limit,font=font,ink=ink,center=center)

    def rect(self,x,y,w,h,ink=None,fill=True):
        c=self.ink if ink is None else ink
        for yy in range(max(1,y),min(63,y+h)):
            for xx in range(max(1,x),min(self.w-1,x+w)):
                if fill or yy in (y,y+h-1) or xx in (x,x+w-1):self.p[yy*self.w+xx]=c

    def text_width(self,value,font='regular5'):
        glyphs=self.fonts[font];digit=max(len(glyphs[c][0]) for c in '0123456789')
        return max(0,sum((digit if c.isdigit() else len(glyphs.get(c,glyphs[' '])[0]))+1 for c in display_text(str(value)).upper())-1)

    def text(self,x,y,value,limit=None,font='regular5',ink=None,center=None):
        value=display_text(str(value)).upper();glyphs=self.fonts[font]
        limit=self.w-x-2 if limit is None else limit
        digit=max(len(glyphs[c][0]) for c in '0123456789')
        def cell(c):return digit if c.isdigit() else len(glyphs.get(c,glyphs[' '])[0])
        def width(s):return max(0,sum(cell(c)+1 for c in s)-1)
        while value and width(value)>limit:value=value[:-1]
        if center is not None:x=max(x,center-width(value)//2)
        for c in value:
            rows=glyphs.get(c,glyphs[' '])
            for yy,row in enumerate(rows):
                for xx,b in enumerate(row):
                    if b=='1':self.rect(x+xx,y+yy,1,1,ink)
            x+=cell(c)+1

    def line(self,x,y,xx,yy,ink=None):
        n=max(abs(xx-x),abs(yy-y),1)
        for i in range(n+1):self.rect(round(x+(xx-x)*i/n),round(y+(yy-y)*i/n),1,1,ink)

    def header(self,keys,active=()):
        count=3 if self.w==128 else 4;cell=(self.w-2)//count
        aliases={'PLUG-IN':'PLUG-IN','PREVIEW':'PLAY','COMPARE':'A/B','KEYBOARD':'KEYS','SAMPLING':'REC','PATTERN':'PAT.','BRIGHTNESS':'BRIGHT.'}
        for i,key in enumerate(keys[:count]):
            if not key or key=='-':continue
            x=2+i*cell;chosen=i in active
            if chosen:self.rect(x,2,cell-2,9)
            label=aliases.get(key,key);font='bold7' if self.w==256 else 'bold5'
            if self.text_width(label,font)>cell-4:font='regular5'
            self.text(x+1,4,label,cell-4,font=font,ink=self.bg if chosen else self.ink,center=x+(cell-2)//2)
        self.rect(2,12,self.w-4,1)

    def title(self,title,detail=''):
        self.rect(2,15,self.w-4,8,self.bg)
        detail=str(detail);space=min(self.w//2,len(detail)*6+3) if detail else 0
        edge=self.w-8 if self.pinned else self.w
        self.fitted(3,16,title,edge-6-space,font='regular7')
        if detail:self.text(edge-space,17,detail,space-2)
        if self.pinned:
            self.rect(self.w-7,16,5,3);self.rect(self.w-5,19,1,3)

    def field(self,label,value):
        label=str(label)
        indexed=re.match(r'^(\d+)/(\d+):\s*(.*)',label)
        if indexed:
            index,total,caption=indexed.groups();label=f'{index}/{total} '+caption
        value=display_text(str(value));glyphs=FONTS['regular5']
        digit=max(len(glyphs[c][0]) for c in '0123456789')
        vw=min(self.w-12,max(0,sum((digit if c.isdigit() else len(glyphs.get(c,glyphs[' '])[0]))+1 for c in value.upper())-1))
        # Long values get their own line; never overlap the selected caption.
        if vw>self.w//2:
            self.text(3,46,label,self.w-6)
            self.rect(2,53,self.w-4,9);self.text(4,55,value,self.w-8,ink=self.bg)
        else:
            self.rect(2,51,self.w-4,11)
            self.text(4,54,label,self.w-vw-12,ink=self.bg)
            self.text(self.w-vw-4,54,value,vw,ink=self.bg)

    def rows(self,rows,y=25,step=8):
        for i,row in enumerate(rows):
            selected=str(row).startswith('>');value=str(row).lstrip('> ');yy=y+i*step
            if selected:self.rect(2,yy-1,self.w-4,7)
            self.fitted(4,yy,value,self.w-8,ink=self.bg if selected else self.ink)

    def message(self,message):
        # Notices leave both target/title and editable footer visible.
        if message:self.rect(2,35,self.w-4,9);self.fitted(4,37,message,self.w-8,ink=self.bg)

    def finish(self):return bytes(self.p)


def draw_curve(c,heading,values=None):
    """Graphs show actual sampler parameters; no synthetic waveform samples."""
    values=values or {}
    if heading=='PITCH/ENV' and values.get('type','ONESHOT')!='ONESHOT':
        times=[max(1,float(values.get(k,d))) for k,d in [('attack',0),('decay',250),('release',100)]]
        total=sum(times)+max(1,total_hold:=float(values.get('hold',200)))
        x=5;points=[(x,45)]
        x+=round(times[0]/total*112);points.append((x,32))
        x+=round(times[1]/total*112);sy=45-round(float(values.get('sustain',100))/100*13);points.append((x,sy))
        x+=round(total_hold/total*112);points.append((x,sy));points.append((117,45))
        for a,b in zip(points,points[1:]):c.line(*a,*b)
    elif heading=='LFO':
        shape=values.get('lfo_shape','SINE');prev=None
        for x in range(5,122):
            t=(x-5)/116*2;phase=t%1
            a=math.sin(t*math.tau) if shape=='SINE' else (1 if phase<.5 else -1) if shape=='RECT' else 2*phase-1 if shape=='SAW' else 1-4*abs(phase-.5)
            y=round(39-a*6)
            if prev:c.line(*prev,x,y)
            prev=(x,y)
    elif heading=='FX/FILTER' and values.get('filter','OFF')!='OFF':
        cut=max(20,min(20000,float(values.get('cutoff',18000))));anchor=5+math.log(cut/20)/math.log(1000)*116;prev=None
        for x in range(5,122):
            amount=1/(1+math.exp(max(-50,min(50,(x-anchor)/7))))
            if values.get('filter')=='HP2':amount=1-amount
            if values.get('filter') in ('BP2','EQ'):amount=math.exp(-((x-anchor)/17)**2)
            y=45-round(amount*13)
            if prev:c.line(*prev,x,y)
            prev=(x,y)


def control(state):
    c=Canvas();c.pinned=state.get('pinned',False);c.header(state['keys'],state['active'])
    c.title(state['title'],state.get('transport_detail') or (state['position'] if state['show_position'] else ''))
    page=state['page'];heading=state['heading']
    if page=='TEMPO':
        c.text(4,29,state['tempo'],90,font='regular7');c.text(98,30,'BPM',26)
        c.field('SHIFT 0.01','1 BPM')
    else:
        section=state.get('section',heading)
        pages=state.get('pages')
        overview=state.get('micro_overview')
        if overview:
            from app.mono_instrument_icons import paint_small
            paint_small(c,overview['icon'])
            c.fitted(27,26,overview['role'],67,font='bold5')
            c.fitted(27,37,overview['name'],96)
            if pages:c.text(99,26,f'{pages[0]+1}/{pages[1]}',26)
        else:
            c.text(4,26,section,80 if pages else 120)
            if pages:
                c.text(91,26,f'P{pages[0]+1}/{pages[1]}',34)
        if page=='PAD CONFIG':c.text(4,36,state['sound_name'],88);c.text(99,36,state['root'],25)
        elif page=='SAMPLER':
            from app.fokus_graphics import response
            response(c,state['sampler_section'],state.get('sampler_values',{}),y=33,h=13)
        elif state.get('signal_route'):
            from app.fokus_graphics import route
            route(c,state['signal_route'],y=33)
        elif state['latency']:c.text(4,37,state['latency'],120)
        if state.get('sound_wave',(None,))[0]:
            global _sound_waveforms
            if _sound_waveforms is None:
                from app.waveform_index import IndexedWaveforms
                _sound_waveforms=IndexedWaveforms()
            sample_wave(c,state['sound_wave'],_sound_waveforms,playhead=state.get('wave_cursor'))
        if state.get('synth_graph') and not overview:
            from app.synth_display import draw
            draw(c,state['synth_graph'],y=33,height=12)
        if state.get('ducktor'):
            d=state['ducktor'];c.fitted(4,34,d['source'],84)
            c.text(90,34,f"-{d['reduction']:.0f}DB",34)
            c.rect(4,42,120,3,c.ink,False)
            c.rect(5,43,round(118*max(0,min(1,d['reduction']/max(1,d['depth'])))),1)
        if state['caption'] is not None:c.field(state['caption'],state['value'])
    c.message(state['message']);return c.finish()


def live(state,legacy):
    """Retain all live meter/grid detail while applying Fokus chrome and footer."""
    if state.get('kind')=='CONTROL':return control(state)
    c=Canvas();c.pinned=state.get('pinned',False);c.p[:]=legacy
    c.rect(1,1,126,22,c.bg);c.header(state['keys'],state['active']);c.title(state['title'])
    if state.get('kind')=='MIXER' and state.get('master_mixer'):
        # One stereo master is not an eight-strip mixer stretched to one column.
        # Keep meters, peak markers and the editable parameter visually distinct.
        c.rect(1,15,126,48,c.bg)
        peaks=state['peaks'][0];levels=state['levels'][0]
        peak=max(peaks)
        detail='PK '+(f'{20*math.log10(peak):.1f}' if peak>0 else '-INF')
        c.title('MASTER',detail)
        def fraction(value):
            return max(0,min(1,(20*math.log10(max(.001,value))+60)/60)) if value>0 else 0
        for i,caption in enumerate(('L','R')):
            y=26+i*10
            c.text(3,y+2,caption,9)
            c.rect(13,y,110,9,c.ink,False)
            c.rect(15,y+2,round(fraction(levels[i])*106),5)
            if peaks[i]>0:
                x=15+round(fraction(peaks[i])*105)
                for yy in range(y+1,y+8):c.p[yy*128+x]^=1
            if peaks[i]>=1:c.rect(124,y+2,2,5)
        if state['mixer_field']!=2:
            for x,caption in ((14,'-60'),(73,'-24'),(96,'-12'),(119,'0')):
                c.text(x,46,caption,126-x,font='regular5')
        c.field(('LEVEL','PAN','OUTPUT')[state['mixer_field']],state['mixer_value'])
    if state.get('kind') in ('PATTERN','SCENE'):
        c.rect(1,24,126,39,c.bg)
        c.text(4,26,f'{state["kind"]} {state["selected"]:02} BANK {state["bank"]}',120)
        c.text(4,37,state['position'] if state['playing'] else 'STOP',44)
        c.rect(48,36,76,6,c.ink,False);c.rect(50,38,round(state['progress']*72),2)
        c.field('LENGTH',f'{state["length"]/16:g} BAR')
    c.message(state['message']);return c.finish()


def utility(app,legacy,envelope=None):
    """All V1 workflow branches remain available; replace chrome, not actions.

    Rich legacy content (relink, naming, RAM, export, MIDI learn, etc.) remains
    intact until handled by a dedicated data-driven layout below.
    """
    from app.ui_context import nav_preview,pinned,visible_message
    c=Canvas();c.pinned=pinned(app);c.p[:]=legacy;c.rect(1,1,126,22,c.bg)
    c.header(app.softkeys(),app.active_softkeys())
    if app.page=='LIVE FX':
        from app.live_fx import LIVE_FX
        # This workspace replaces the legacy body completely. Reusing its
        # pixels leaves old Sound labels underneath the scrolling FX list.
        c=Canvas();c.pinned=pinned(app);c.header(app.softkeys(),app.active_softkeys())
        c.title('LIVE FX',('PUNCH','FLEX','KNOB')[app.live_fx_mode])
        names=LIVE_FX[1:]+('OFF',)
        first=max(0,min(app.live_fx_pad-1,len(names)-3))
        c.rows([('>' if first+i==app.live_fx_pad else '')+f'{i+first+1:02} {names[i+first]}' for i in range(3)],y=27,step=8)
        c.field(f'DEPTH {app.live_fx_depth}%',LIVE_FX[app.live_fx_current])
        c.message(visible_message(app));return c.finish()
    if app.page=='AUTOSAMPLER':
        app.auto_setup();c=Canvas();c.header(app.softkeys())
        state=app.auto_status;status=state.get('state','IDLE');label,value=app.auto_rows()[app.auto_field]
        c.title('AUTO',f'{app.auto_field+1}/24')
        c.fitted(3,26,app.auto_config['name'] or 'SET SOUND NAME',122,font='bold5')
        c.fitted(3,35,state.get('message') if status=='ERROR' else status+' '+str(state.get('completed',0))+'/'+str(state.get('total',0)),122)
        c.rect(3,44,122,4,c.ink,False)
        c.rect(4,45,round(120*state.get('completed',0)/max(1,state.get('total',0))),2)
        c.field(label,value);return c.finish()
    if app.page in ('PARAM NAV','SAMPLING NAV'):
        c=Canvas();c.header(app.softkeys(),app.active_softkeys())
        target=nav_preview(app)
        choices=app.parameter_choices() if app.page=='PARAM NAV' else ('RECORD','EDIT','SLICE','ZONE','AUTO')
        index=app.parameter_choice if app.page=='PARAM NAV' else app.sampling_nav
        first=max(0,min(index-1,len(choices)-3))
        c.title('NAV','ENC: MODULE')
        c.rows([('>' if first+i==index else '')+choice for i,choice in enumerate(choices[first:first+3])])
        c.field(target['section'],f'{target["index"]+1}/{target["total"]}')
        c.message(visible_message(app));return c.finish()
    from app.mikro_pages import position,marker
    pages=position(app)
    title={'SAMPLE EDIT':'SAMPLE EDIT','CHOP':'SLICE / '+app.slice_mode,'SAMPLING':'RECORD','ZONE':'ZONE','BROWSE':app.browser.title(),'SETTINGS':app.settings_title()}.get(app.page,app.page)
    if app.page in ('SAMPLE EDIT','CHOP','ZONE','STRETCH'):
        if app.page=='SAMPLE EDIT':title=('PLAY RANGE','SELECTION')[app.range_page]
        elif app.page=='ZONE':
            from app.sampler import ZONE_PAGES
            title='ZONE '+ZONE_PAGES[app.zone_page][0]
        elif app.page=='CHOP':title=('SLICE '+('END' if app.slice_focus_end else 'START')) if app.slice_edit else app.slice_mode+' SLICE'
        detail=app.group_name()+f'{app.pad+1:02}'+(f' {pages[0]+1}/{pages[1]}' if pages else '')
        c.title(title,detail)
    elif app.page in ('SAMPLING','BROWSE'):
        if app.page=='SAMPLING':title='RECORDING' if app.capture_started is not None else 'REC WAIT' if app.capture_armed else 'RECORD'
        c.title(title,' '.join(x for x in (f'{app.group_name()}:{app.pad+1:02}',f'{pages[0]+1}/{pages[1]}' if pages else '') if x))
    else:c.title(title,marker(*pages) if pages else '')
    if app.page in ('MUTE','SOLO'):
        from app.fokus_data import group_status
        c.rect(1,24,126,39,c.bg)
        c.text(3,26,'GROUPS / M:MUTE S:SOLO',122)
        for i,(label,muted,solo,focused,audible) in enumerate(group_status(app)):
            x=2+i*15;c.rect(x,35,14,14,c.ink,muted or solo)
            ink=c.bg if muted or solo else c.ink
            c.text(x+2,37,label,10,ink=ink)
            c.text(x+2,43,'M' if muted else 'S' if solo else '-' if not audible else '',10,ink=ink)
            if focused:c.rect(x,50,14,1)
        c.field('GROUP '+app.group_name(),'MUTED' if app.project['groups'][app.group].get('mute',False) else 'ON')
    elif app.page=='BROWSE':
        c.rect(1,24,126,39,c.bg);entries=app.entries();index=app.browser_index;first=max(0,min(index-1,len(entries)-3))
        c.rows([('>' if first+i==index else '')+app.browser.label(p) for i,p in enumerate(entries[first:first+3])] or ['EMPTY FOLDER'])
        c.field('PADS:TARGET', 'PREH ON' if app.browser.prehear else 'PREH OFF')
    elif app.page in ('PLUGIN BROWSE','PLUGIN MOVE'):
        from app.fokus_data import utility_data
        header,body,_=utility_data(app);c.rect(1,15,126,48,c.bg)
        c.title(header);c.rows(body)
        if app.page=='PLUGIN BROWSE':c.field('SLOT',app.plugin_slot+1)
        else:c.field('TARGET SLOT',app.plugin_move_to+1)
    elif app.page=='INTERFACE MIXER':
        from app.interface_mixer import value_text,db_text
        c.rect(1,24,126,39,c.bg);control=app.interface_control()
        if control:
            c.text(3,27,control['name'],122,font='bold5')
            c.text(3,38,control['direction'].upper()+(' SWITCH' if control['kind']=='switch' else ' LEVEL'),122)
            c.rect(3,46,122,3,c.ink,False)
            c.rect(4,47,round(control['value']/(100 if control['kind']=='level' else 1)*120),1)
            c.text(3,54,value_text(control),50,font='bold5')
            c.text(57,54,db_text(control),68)
        else:c.rows([app.interface_mixer_error or ('NO MIXER CONTROLS' if app.audio else 'NO AUDIO DEVICE')])
    elif app.page=='UPDATE':
        from app.updater import display
        _,body,footer=display(app)
        c.rect(1,24,126,39,c.bg)
        c.rows(body);c.field('OS INCLUDED',str(app.update_status.get('progress',0))+'%' if app.update_status.get('busy') else '')
    elif app.page=='SETTINGS':
        from app.settings_menu import SETTINGS_LABELS
        entries=app.setting_entries();first=max(0,min(app.menu-1,len(entries)-3));c.rect(1,24,126,39,c.bg)
        c.rows([('>' if i==app.menu else '')+SETTINGS_LABELS.get(entries[i],entries[i]) for i in range(first,min(first+3,len(entries)))])
        c.field('LEFT:BACK',f'{app.menu+1}/{len(entries)}')
    elif app.page in ('SAMPLE EDIT','CHOP','ZONE','STRETCH','SAMPLING'):
        # Preserve the cached waveform, live marker and meter pixels above y43.
        from app.ni_display import formatted
        key=value=None
        if app.wave_view():key='ZOOM' if app.view_field==0 else 'SCROLL';value=f'{1<<app.wave_zoom}X' if app.view_field==0 else app.wave_offset
        elif app.page=='SAMPLE EDIT':
            key=('selection_' if app.range_page else '')+('start' if app.sample_field==0 else 'end');value=app.track().get(key,0)
        elif app.page=='ZONE':
            from app.sampler import ZONE_PAGES
            key=ZONE_PAGES[app.zone_page][1][app.zone_field];value=formatted((app.zone() or {}).get(key,0),key)
        elif app.page=='STRETCH':key='LENGTH' if app.sample_field==0 else 'PITCH';value=str(app.track().get('stretch_ratio',100))+'%' if app.sample_field==0 else app.track().get('stretch_pitch',0)
        elif app.page=='SAMPLING':
            fields=app.capture_fields();key=fields[app.capture_field];value=app.capture_source_label() if key=='input' else formatted(app.capture_options()[key],key)
        elif app.slice_edit:
            key=('SLICE','START','END')[app.slice_field];ranges=app.slice_ranges();pair=ranges[min(app.slice_index,len(ranges)-1)] if ranges else (0,0);value=(app.slice_index+1,)+tuple(pair);value=value[app.slice_field]
        else:
            labels,values=app.slice_parameters();i=min(app.slice_field,len(labels)-1);key,value=labels[i],formatted(values[i])
        counts=None
        if app.page=='ZONE':counts=(app.zone_field,len(ZONE_PAGES[app.zone_page][1]))
        elif app.page in ('SAMPLE EDIT','STRETCH'):counts=(app.sample_field,2)
        elif app.page=='SAMPLING':counts=(app.capture_field,len(app.capture_fields()))
        elif app.page=='CHOP':counts=(app.slice_field,3 if app.slice_edit else len(app.slice_parameters()[0]))
        if app.wave_view():counts=(app.view_field,2)
        caption=str(key).replace('_',' ')
        if counts:caption=f'{counts[0]+1}/{counts[1]}: '+caption
        c.rect(1,43,126,20,c.bg);c.field(caption,value)
    c.message(visible_message(app));return c.finish()
