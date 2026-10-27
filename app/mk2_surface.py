"""Maschine MK2 controls over the shared engine, without Mikro key aliases.

Bindings are also the display's parameter columns; an encoder can only edit
the parameter shown directly above it. NI MK2 manual PDF52,216,289-299,787ff.
"""
from dataclasses import dataclass
from app.controller_settings import on_controller,DEVICE_PAGES,DISPLAY_PAGES,change_display,save_display
from app.preferences import PREFERENCES
import copy
import wave
from pathlib import Path
from app.navigation import CONTROL_PAGES
from app.sampler import ZONE_PAGES
from app.surface import TEMPORARY,PROCESSING
from app.ni_display import formatted,plugin_value,name


@dataclass(frozen=True)
class Field:
    label:str
    value:str
    attributes:tuple


class Mk2Surface:
    source='mk2'
    def __init__(self,app,inputs):
        self.app,self.inputs=app,inputs
        self.held=set();self.master_mode=None;self.auto_locked=False;self.pad_page=0
        self.tap_tempo_held=False
        self.event_select_key=False;self.event_select_moved=False
        self.utility_bank=0
        self.auto_page=app.page
        self.master_page=None
        self.zone_subpage=self.slice_subpage=0
        self.sampler_subpage=0

    def sync(self):
        if self.master_mode and self.app.page!=self.master_page:self.master_mode=None;self.master_page=None
        if self.auto_locked and self.app.page!=self.auto_page:
            self.auto_locked=False;self.app.mk2_auto='AUTO' in self.held

    def tap(self,name):
        # Synthetic action, not an owned physical key. It must still execute if
        # the other surface is holding a similarly named Mikro softkey.
        held=name in self.app.held_buttons
        self.app.button(name,True)
        if not held:self.app.button(name,False)

    def scope(self,index):
        a=self.app
        if a.page=='MIXER':a.mixer_level=index;return
        if a.page not in CONTROL_PAGES:a.page=a.control_home()
        a.button(f'F{index+1}',True);a.button(f'F{index+1}',False)

    def property(self,kind,delta=0):
        a=self.app;a.parameter_kind=kind
        if delta==0:
            a.parameter_choice=0 if kind=='PLUG-IN' else int(a.control_level>0)
        else:
            choices=a.parameter_choices()
            if kind=='PLUG-IN':current=0 if a.page=='SAMPLER' else a.plugin_slot+int(a.sampler_slot_present())
            else:current=choices.index({'PAD':'OUTPUT','CHANNEL':'OUTPUT','INPUT':'INPUT','GROOVE':'GROOVE','MACRO':'MACRO'}.get(a.page,'OUTPUT'))
            a.parameter_choice=max(0,min(len(choices)-1,current+delta))
        a.page=a.parameter_destination();a.remember_control_view()

    def select_chain(self,delta,allow_add=False):
        """Master arrows visit loaded slots; F8 also retains ADD PLUGIN."""
        a=self.app;offset=int(a.sampler_slot_present())
        count=len(a.plugin_target().get('plugins',[]))+offset
        current=0 if a.page in ('SAMPLER','AUDIO LOOP') else a.plugin_slot+offset
        target=max(0,min(count if allow_add else count-1,current+delta))
        if (count or allow_add) and (target!=current or allow_add and not count):
            a.parameter_kind='PLUG-IN';a.parameter_choice=target
            a.plugin_param=0;a.page=a.parameter_destination();a.remember_control_view()

    def chain_right_label(self):
        from app.mono_instrument_icons import overview
        item=overview(self.app)
        return '>' if item and item['right'] else 'ADD PLUG'

    def page_state(self):
        a=self.app
        if a.page=='AUTOSAMPLER':
            a.auto_setup();base=1 if a.capture_options()['source']=='INTERNAL' else 2;return base+a.auto_field//8,base+3
        if a.page=='SAMPLER':
            from app.fokus import enabled
            if enabled():return a.sampler_page+int(a.sampler_page>2)+(min(1,self.sampler_subpage) if a.sampler_page==2 else 0),7
            return a.sampler_page,6
        if a.page in ('PAD','CHANNEL'):return a.channel_page,4 if a.control_level==2 else 3
        if a.page=='PLUGIN':return a.plugin_param//8,max(1,(len(a.plugin_controls())+7)//8)
        if a.page=='ZONE':
            counts=[(len(keys)+1)//2 for _,keys in ZONE_PAGES]
            return sum(counts[:a.zone_page])+min(self.zone_subpage,counts[a.zone_page]-1),sum(counts)
        if a.page=='SAMPLE EDIT':return a.range_page,2
        if a.page=='SAMPLING':return a.capture_section,4 if a.capture_options()['source']=='INTERNAL' else 5
        if a.page=='CHOP':return (0,1) if a.slice_edit else (min(self.slice_subpage,2),3)
        if a.page=='PAD CONFIG':return min(self.pad_page,2 if a.keyboard_enabled and a.keyboard_chord_mode()=='CUSTOM' else 0 if a.keyboard_enabled else 1),3 if a.keyboard_enabled and a.keyboard_chord_mode()=='CUSTOM' else 1 if a.keyboard_enabled else 2
        if a.page=='MIXER':return (a.pad//8,2) if a.mixer_level==2 else (a.group//8,max(1,(len(a.project['groups'])+7)//8)) if a.mixer_level==1 else (0,1)
        if a.page=='INTERFACE MIXER':return a.interface_mixer_index,max(1,len(a.interface_mixer_controls))
        if a.page=='SYSTEM':
            from app.system_info import system_page_count
            total=system_page_count(a.system_stats,'mk2')
            a.system_index=min(a.system_index,total-1)
            return a.system_index,total
        if a.page=='EXPORT' and not a.export_busy:
            total=max(1,(len(a.export_fields())+7)//8)
            return min(self.utility_bank,total-1),total
        return 0,1

    def channel_page_path(self):
        a=self.app
        if a.page not in ('PAD','CHANNEL','INPUT','GROOVE','MACRO'):return ()
        return ((('INPUT',0),) if a.control_level else ())+tuple(('CHANNEL',i) for i in range(4 if a.control_level==2 else 3))+(('GROOVE',0),('MACRO',0))

    def held_mode(self):
        # A held mode only owns PIN while its own workspace is still visible.
        for physical in self.held:
            mode={'NAVIGATE':'VIEW'}.get(physical,physical)
            if mode in TEMPORARY and (self.app.page==TEMPORARY[mode] or
                    mode=='NOTE REPEAT' and self.app.page=='ARP'):
                return mode
        return None

    def page_directions(self):
        if self.app.shift and self.app.page in ('SCENE','PATTERN','GROUP'):
            bank=getattr(self.app,{'SCENE':'scene_bank','PATTERN':'pattern_bank','GROUP':'group_bank'}[self.app.page])
            return bank>0,bank<63
        if self.app.page=='CHOP' and self.app.slice_edit:return True,True
        path=self.channel_page_path()
        if path:
            a=self.app;current=('CHANNEL' if a.page=='PAD' else a.page,a.channel_page if a.page in ('PAD','CHANNEL') else 0)
            index=path.index(current) if current in path else -1
            return index>0,index+1<len(path)
        index,total=self.page_state();return index>0,index+1<total

    def change_page(self,delta):
        if self.app.shift and self.app.page in ('SCENE','PATTERN','GROUP'):
            self.app.bank_button('NAV LEFT' if delta<0 else 'NAV RIGHT',True);return
        if self.app.page=='CHOP' and self.app.slice_edit:
            self.app.focus_slice_boundary(delta>0);return
        path=self.channel_page_path()
        if path:
            a=self.app;current=('CHANNEL' if a.page=='PAD' else a.page,a.channel_page if a.page in ('PAD','CHANNEL') else 0)
            current_index=path.index(current) if current in path else -1
            if current_index<0 and delta<0:return
            target,index=path[max(0,min(len(path)-1,current_index+delta))]
            a.page=target
            if target=='CHANNEL':a.channel_page=index;a.channel_field=0
            elif target=='INPUT':a.input_field=0
            elif target=='GROOVE':a.groove_field=0
            else:a.macro_index=0
            a.parameter_kind='CHNL';a.parameter_choice=a.parameter_choices().index({'CHANNEL':'OUTPUT'}.get(target,target))
            a.remember_control_view();return
        a=self.app;index,total=self.page_state();index=max(0,min(total-1,index+delta))
        if a.page in ('SAMPLING','AUTOSAMPLER'):
            base=1 if a.capture_options()['source']=='INTERNAL' else 2
            if index>=base:a.open_sampling_page('AUTOSAMPLER');a.auto_field=(index-base)*8
            else:a.page='SAMPLING';a.capture_section=index
            return
        if a.page=='SAMPLER':
            from app.fokus import enabled
            if enabled():
                a.sampler_page=2 if index==3 else index-int(index>3)
                self.sampler_subpage=1 if index==3 else 0;a.sampler_field=0;return
        if a.page=='ZONE':
            for page,(_,keys) in enumerate(ZONE_PAGES):
                count=(len(keys)+1)//2
                if index<count:a.zone_page=page;self.zone_subpage=index;a.zone_field=index*2;return
                index-=count
        if a.page=='CHOP':
            self.slice_subpage=index;return
        attrs={'SAMPLER':'sampler_page','PAD':'channel_page','CHANNEL':'channel_page','ZONE':'zone_page','SAMPLE EDIT':'range_page','SAMPLING':'capture_section','CHOP':'slice_section'}
        if a.page in attrs:setattr(a,attrs[a.page],index)
        elif a.page=='PLUGIN':a.plugin_param=index*8
        elif a.page=='PAD CONFIG':self.pad_page=index
        elif a.page=='SYSTEM':a.system_index=index
        elif a.page=='INTERFACE MIXER':a.interface_mixer_index=index
        elif a.page=='EXPORT':self.utility_bank=index;a.export_field=index*8
        elif a.page=='MIXER':a.mixer_button('NAV LEFT' if delta<0 else 'NAV RIGHT',True)
        elif a.page in ('PATTERN GRID','GRID EDIT','STEP','SONG','EVENT'):self.tap('NAV LEFT' if delta<0 else 'NAV RIGHT')

    def waveform_source(self):
        a=self.app;t=a.track()
        return (a.zone() or t) if a.page=='ZONE' else t.get('slice_source',t) if a.page=='CHOP' else t

    def waveform_window(self):
        a=self.app;source=self.waveform_source()
        key=(a.group,a.pad,source.get('sample'))
        if getattr(self,'waveform_key',None)!=key:
            self.waveform_key=key;a.wave_zoom=a.wave_offset=0
            a.wave_sample=a.track()['sample']
            # Viewport belongs to the asset, not its editable playback range.
            # Read the header once on source entry, never on each encoder step.
            self.waveform_frames=max(0,source.get('end',0))
            if source.get('sample'):
                try:
                    with wave.open(source['sample'],'rb') as wav:self.waveform_frames=wav.getnframes()
                except (OSError,EOFError,wave.Error):pass
        frames=self.waveform_frames
        first,last=a.wave_bounds(frames)
        return source.get('sample'),first,last

    def rotate_waveform(self,field,delta):
        a=self.app;source=self.waveform_source()
        if not source.get('sample'):a.message='NO SAMPLE';return
        for _ in range(min(128,abs(delta))):
            _,first,last=self.waveform_window();size=last-first;frames=self.waveform_frames
            if field==0:
                old=a.wave_zoom;zoom=max(0,min(16,old+(1 if delta>0 else -1)))
                new_size=max(min(120,frames),frames>>zoom)
                if new_size==size:break
                a.wave_zoom=zoom
                if a.page=='CHOP':
                    ranges=a.slice_ranges();start,end=ranges[min(a.slice_index,len(ranges)-1)] if ranges else (0,frames)
                    anchor=(start+end)//2
                elif a.page=='ZONE':
                    keys=ZONE_PAGES[a.zone_page][1];key=keys[min(a.zone_field,len(keys)-1)]
                    anchor=source.get(key,first+size//2) if key in ('start','end','loop_start','loop_end') else first+size//2
                else:
                    key=('selection_' if a.range_page else '')+('start' if a.sample_field==0 else 'end')
                    anchor=source.get(key,0 if a.sample_field==0 else frames)
                if not first<=anchor<=last:anchor=first+size//2
                a.wave_offset=max(0,min(frames-new_size,anchor-new_size//2))
            else:a.wave_offset+=(-1 if delta<0 else 1)*max(1,size//60)
        self.waveform_window()

    @on_controller('mk2')
    def fields(self):
        self.sync()
        a=self.app;result=[None]*8
        def field(column,label,value,**attrs):result[column]=Field(label,('ON' if value else 'OFF') if type(value) is bool else str(value),tuple(attrs.items()))
        if a.page=='LIVE FX':
            field(0,'DEPTH',str(a.live_fx_depth)+'%',_utility=True)
            return tuple(result)
        if a.page=='AUTOSAMPLER':
            rows=a.auto_rows();base=a.auto_field//8*8
            for col,(label,value) in enumerate(rows[base:base+8]):
                if label:field(col,label,value,_auto=base+col)
            return tuple(result)
        if a.page in DEVICE_PAGES:
            values=a.settings['controllers'][self.source]
            for col,key,label in ((0,'brightness','BRIGHT.'),(1,'pad_sensitivity','PAD SENS'),(2,'contrast_left','CNTR. L'),(3,'contrast_right','CNTR. R'),(4,'pad_curve','PAD CURVE'),(5,'invert','INVERT')):
                value=values[key];field(col,label,value if value is not None else 100 if key=='brightness' else 42,_controller_key=key)
        elif a.page=='VIEW NAV':
            return tuple(result)
        elif a.wave_view():
            field(0,'ZOOM',a.wave_zoom,_wave=0);field(1,'SCROLL',a.wave_offset,_wave=1)
            return tuple(result)
        from app.codec_levels import CONTROLS,MUTES
        if a.page in (*CONTROLS,*MUTES):
            if a.page in CONTROLS:
                key,_,_,_=CONTROLS[a.page];field(0,a.page,a.settings[key],_utility=True)
            else:
                key,_=MUTES[a.page];field(0,'MUTE',a.settings[key],_dac_mute=a.page)
        if a.page=='BLUETOOTH MIDI':
            field(0,'DEVICE',a.bluetooth_index+1,_bluetooth=True)
        elif a.page=='SAMPLER':
            values=a.track().get('sampler',{})
            placements=(('polyphony','glide','bend',None,None,None,None,None),
                        ('tune',None,'reverse','type','attack','hold','decay',None),
                        ('comp','drive','sr','bits','filter','cutoff','resonance',None),
                        ('mod_attack','mod_decay',None,None,'mod_pitch','mod_cutoff','mod_pan',None),
                        ('lfo_shape','lfo_rate','lfo_sync','lfo_phase','lfo_pitch','lfo_cutoff','lfo_pan',None),
                        ('vel_volume','vel_cutoff','vel_start','pan','wheel_pitch','wheel_cutoff','wheel_pan',None))
            visible=a.sampler_fields();layout=list(placements[a.sampler_page])
            if a.sampler_page==1:
                kind=values.get('type','ONESHOT')
                layout[4:]=['attack','decay','sustain','release'] if kind=='ADSR' else ['attack','hold','decay',None]
            if a.sampler_page==2 and values.get('filter')=='EQ':layout[6:]=['eq_gain','eq_width']
            from app.fokus import enabled
            if enabled() and a.sampler_page==2:
                layout=['eq_width',None,None,None,None,None,None,None] if self.sampler_subpage else ['comp','drive','sr','bits','filter','cutoff','resonance','eq_gain']
            for column,key in enumerate(layout):
                for i,(k,label,default,_) in enumerate(visible):
                    if k==key:field(column,label,formatted(values.get(k,default),k),sampler_field=i)
        elif a.page in ('PAD','CHANNEL'):
            from app.routing import route_defaults
            target=a.plugin_target();r=route_defaults(target)
            fields=a.channel_fields()
            order=('dest',None,'gain','pan') if a.channel_page==0 else fields
            for column,key in enumerate(order):
                if key in fields:field(column,{'gain':'LEVEL','dest':'DEST.','midi_target':'INTERNAL TO','midi_send':'EXT MIDI'}.get(key,key.replace('_',' ')),formatted(target.get(key,100 if key=='gain' else 0) if key in ('gain','note','channel') else r[key],key),channel_field=fields.index(key))
        elif a.page=='INPUT':
            from app.routing import route_defaults
            r=route_defaults(a.plugin_target());field(0,'SOURCE',r['input'],input_field=0);field(1,'GAIN',formatted(r['input_gain'],'input_gain'),input_field=1)
        elif a.page=='GROOVE':
            from app.groove import settings
            values=settings(a.plugin_target(),a.timing()['swing'] if a.control_level==0 else 0)
            for i,key in enumerate(('amount','cycle','invert')):field(i,key,formatted(values[key],key),groove_field=i)
        elif a.page=='MACRO':
            macros=a.plugin_target().get('macros',{})
            for i in range(8):
                m=macros.get(str(i));field(i,m['name'] if m else f'MACRO {i+1}',str(m['value'])+'%' if m else '-',macro_index=i)
        elif a.page=='PLUGIN':
            ports=a.plugin_controls();plugin=a.plugin_selected();first=a.plugin_param//8*8
            from app.virtualjv_controls import URI
            for i,p in enumerate(ports[first:first+8]):
                value=plugin['controls'].get(p['symbol'],p['default'])
                numeric=(p.get('profile_action') or plugin['uri']==URI and p['symbol'] in ('bank','program') or plugin['uri']=='urn:machinista:ports:virtualjv-multi' and p['symbol'].endswith(('_bank','_program')))
                caption='PATCH' if numeric and (p['symbol']=='program' or p['symbol'].endswith('_program')) else p['name']
                field(i,caption,str(round(value)+1) if p.get('profile_action') and p['profile_action'] not in ('ducktor_source','synth_wave') else str(round(value)) if numeric and p.get('profile_action') not in ('ducktor_source','synth_wave') else plugin_value(p,value),plugin_param=first+i)
        elif a.page=='SAMPLING':
            values=a.capture_options()
            for i,key in enumerate(a.capture_fields()):field(i,key,a.capture_source_label() if key=='input' else values[key],capture_field=i)
        elif a.page in ('AUDIO LOOP','BOUNCE TO PAD'):
            for i,(label,value) in enumerate(a.audio_tool_fields()):field(i,label,value,_sample_tool=i)
        elif a.page=='SAMPLE EDIT':
            t=a.track();prefix='selection_' if a.range_page else ''
            field(0,'START',t.get(prefix+'start',t['start']),sample_field=0);field(1,'END',t.get(prefix+'end',t['end']),sample_field=1)
        elif a.page=='STRETCH':
            field(0,'LENGTH',str(a.track().get('stretch_ratio',100))+'%',sample_field=0)
            field(1,'PITCH',a.track().get('stretch_pitch',0),sample_field=1)
        elif a.page=='CHOP':
            if a.slice_edit:
                ranges=a.slice_ranges();start,end=ranges[min(a.slice_index,len(ranges)-1)] if ranges else (0,0)
                field(0,'START',start,slice_field=1);field(1,'END',end,slice_field=2)
            else:
                section=a.slice_section;a.slice_section=0
                try:labels,values=a.slice_parameters()
                finally:a.slice_section=section
                entries=[(label,value,0,i) for i,(label,value) in enumerate(zip(labels,values))]
                if a.slice_mode=='DETECT':entries.append(('ZERO-X','ON' if a.slice_zero else 'OFF',1,0))
                first=min(self.slice_subpage,2)*2
                for col,(label,value,section,index) in enumerate(entries[first:first+2]):field(col,label,value,slice_section=section,slice_field=index)
        elif a.page=='SLICE TARGET':
            field(0,'PATTERN',a.slice_pattern,slice_target_field=0);field(1,'MONO',a.slice_options()['mono'],slice_target_field=1)
            field(2,'GROUP',a.group_name(a.slice_target_group),_target_group=True)
            field(3,'TARGET','GROUP' if a.slice_target_sound is None else a.slice_target_sound+1,_target_sound=True)
        elif a.page=='ZONE':
            z=a.zone()
            if z:
                keys=ZONE_PAGES[a.zone_page][1];first=min(self.zone_subpage,(len(keys)-1)//2)*2
                for col,key in enumerate(keys[first:first+2]):field(col,key.replace('_',' '),z[key],zone_field=first+col)
        elif a.page=='PAD CONFIG':
            if a.keyboard_enabled:
                p=a.performance()
                keys=a.keyboard_fields()
                if a.keyboard_chord_mode()=='CUSTOM':
                    indices=(0,1,2,3,4,5,6,7) if self.pad_page==0 else (8,9,10) if self.pad_page==1 else (11,12,13)
                else:indices=range(len(keys))
                for i,index in enumerate(indices):
                    key=keys[index];value=a.keyboard_value(key)
                    if a.slice_keyboard():field(i,'FIRST SLICE',a.keyboard_root+1,pad_field=index);continue
                    if key in ('root','edit_note','edit_input') and isinstance(value,int):value=formatted(value,'note')
                    field(i,{'chord_type':'PRESET' if p['chord_mode']=='CUSTOM' else 'TYPE','custom_bank':'PAD BANK','strum':'STRUM MS','human_time':'TIME RAND','velocity_spread':'VEL SPREAD','velocity_direction':'VEL DIR','human_velocity':'VEL RAND'}.get(key,key),value,pad_field=index)
            elif self.pad_page:
                field(0,'FIXED VEL',a.velocity_value,velocity_value=a.velocity_value)
                field(1,'BASE KEY',formatted(a.track().get('note',36),'note'),pad_field=4)
            else:
                for i,key in enumerate(('choke_group','choke_mode','link_group','link_mode')):field(i,key.replace('_',' '),a.track().get(key,'MASTER' if key.endswith('mode') else 0),pad_field=i)
        elif a.page in ('NOTE REPEAT','ARP'):
            from app.performance import ARP_DEFAULTS
            for i,key in enumerate(ARP_DEFAULTS):
                value=a.project['repeat_presets'][a.repeat_bank*2+a.repeat_preset] if key=='rate' else a.project['arp'][key]
                field(i,key,('1/'+str(value)) if key=='rate' else value,arp_field=i)
        elif a.page=='OPTIONS':
            t=a.timing()
            rows={0:((0,'strength',0),(1,'target',1)),1:((0,'swing',0),),2:((0,'grid',0),(1,'grid_on',1),(2,'nudge',2))}[a.grid_tab]
            for col,key,index in rows:
                field(col,key.replace('_',' '),str(t[key])+'%' if key in ('swing','strength') else t[key],grid_tab=a.grid_tab,grid_field=index)
            if a.grid_tab==2:field(4,'REC QUANT','ON' if t['record_quantize'] else 'OFF',_record_quant=True)
        elif a.page=='RECORD SETTINGS':
            t=a.timing()
            for col,key,index in ((0,'metro_level',0),(3,'count_bars',1),(4,'record_quantize',2)):
                field(col,key.replace('_',' '),t[key],record_field=index)
        elif a.page=='RECORD PREPARE':
            field(3,'LENGTH',f'{a.pattern_steps()/16:g} BAR',prepare_field=0)
            field(1,'GRID',a.timing()['grid'],prepare_field=1)
        elif a.page in ('STEP','PATTERN'):
            field(0,'LENGTH',f'{a.pattern_steps()/16:g} BAR',_length=True)
            field(1,'GRID',a.timing()['grid'],_grid=True)
            if a.page=='STEP':field(2,'BASE KEY',a.step_input_note() or a.track().get('note',36),_pitch=True);field(3,'VELOCITY',a.velocity_value,_velocity=True)
        elif a.page in ('PATTERN GRID','GRID EDIT'):
            targets=a.grid_targets();events=a.event_notes();event=events[min(targets)] if targets else {}
            tick=min(targets)[1] if targets else a.grid_step*a.grid_ticks()
            field(0,'EVENT',a.grid_step+1,_event_index=True)
            field(1,'SOUND',a.pad+1,_row=True)
            field(2,'PROBABILITY',str(event.get('probability',100))+'%',_event_edit=3)
            for col,label,value,index in ((4,'POSITION',tick,0),(5,'LENGTH',event.get('length',a.grid_ticks()),4),(6,'PITCH',event.get('note',a.track().get('note',36)),1),(7,'VELOCITY',event.get('velocity',100),2)):
                field(col,label,value,_event_edit=index)
        elif a.page=='MIXER':
            first=0 if a.mixer_level==0 else a.group//8*8 if a.mixer_level==1 else a.pad//8*8
            from app.routing import route_defaults
            for i in range(1 if a.mixer_level==0 else 8):
                index=first+i
                if a.mixer_level==1 and index>=len(a.project['groups']):break
                t=a.project if a.mixer_level==0 else a.project['groups'][index] if a.mixer_level==1 else a.project['groups'][a.group]['pads'][index]
                key=('gain','pan','dest')[a.mixer_field]
                field(i,'MASTER' if a.mixer_level==0 else f'GROUP {index+1}' if a.mixer_level==1 else a.sound_name(t,empty=f'SOUND {index+1}'),t.get('gain',100) if key=='gain' else route_defaults(t)[key],_mixer=index)
        elif a.page=='EXPORT' and not a.export_busy:
            fields=a.export_fields();old=a.export_field
            try:
                first=min(self.utility_bank,(len(fields)-1)//8)*8
                for column,i in enumerate(range(first,min(first+8,len(fields)))):
                    a.export_field=i;field(column,fields[i],a.export_value(),export_field=i)
            finally:a.export_field=old
        elif a.page=='PROJECT NAME':
            value=a.name_value.ljust(32)
            field(0,'LETTER',value[a.name_cursor] if value[a.name_cursor]!=' ' else '_',_utility=True)
            field(1,'CURSOR',a.name_cursor+1,_name_cursor=True)
        elif a.page=='INTERFACE MIXER':
            from app.interface_mixer import value_text
            control=a.interface_control()
            if control:
                field(0,'CONTROL',a.interface_mixer_index+1,_hardware_select=True)
                field(1,'SWITCH' if control['kind']=='switch' else 'LEVEL',value_text(control),_hardware_level=True)
        elif a.page=='MACRO ASSIGN':field(0,'TARGET',a.macro_choice+1,_utility=True)
        elif a.page=='PLUGIN MOVE':field(0,'TARGET SLOT',a.plugin_move_to+1,_utility=True)
        elif a.page in PREFERENCES and a.page not in DEVICE_PAGES:
            key,_,_=PREFERENCES[a.page]
            value=a.settings[key]
            field(0,'OFFSET' if a.page=='MIDI OFFSET' else 'VALUE',str(value)+(' MS' if a.page=='MIDI OFFSET' else ''),_utility=True)
        if a.page in ('SAMPLE EDIT','CHOP','ZONE'):
            self.waveform_window()
            field(2,'ZOOM',f'{1<<a.wave_zoom}X',_mk2_wave=0)
            field(3,'SCROLL',a.wave_offset,_mk2_wave=1)
        if not any(result) and a.page not in ('VIEW NAV','SAMPLING NAV','PARAM NAV','CONFIRM','SELECT','MUTE','SOLO'):
            # Utility workflows keep their established master-encoder action;
            # expose it explicitly above E1 rather than eight blank cells.
            selection={'SETTINGS':a.menu,'BROWSE':a.browser_index,'PLUGIN BROWSE':a.plugin_browser_index+1,'PROJECT LOAD':a.project_choice,'PROJECT MANAGE':a.manage_index,'PRESET LOAD':a.preset_index,'MISSING SAMPLES':a.missing_index,'RELINK RESULTS':a.relink_index,'MIDI LEARN':a.midi_map_index,'SONG AUTO':a.midi_map_index,'SONG':a.song_index,'SCENE OPTIONS':a.scene_options_index}
            values={'AUDIO BUFFER':'AUTO' if not a.settings['audio_buffer'] else str(a.settings['audio_buffer'])+' FR',
                    'AUDIO RATE':str(a.settings['sample_rate'])+' HZ','MIDI CHANNEL':a.settings['midi_channel'],
                    'TEMPO':f'{a.project["tempo"]:.2f}', 'SCENE':str(a.scene_steps()/16)+' BAR',
                    'MAIN OUTPUT':a.settings['main_output'],'CUE OUTPUT':a.settings['cue_output'],'CUE LEVEL':str(a.settings['cue_level'])+'%',
                    'PLUGIN DELAY':'ON' if a.settings['plugin_delay'] else 'OFF', 'PLUGIN SC':(a.plugin_selected() or {}).get('sidechain','NONE')}
            if a.page in ('AUDIO','MIDI IN','MIDI OUT'):
                key={'AUDIO':'audio','MIDI IN':'midi_in','MIDI OUT':'midi_out'}[a.page]
                devices=a.audio_devices if key=='audio' else a.midi_devices
                value=next((d.name for d in devices if d.key==a.settings[key]),a.settings[key])
                field(0,'DEVICE',value,_utility=True)
            elif a.page in selection:field(0,'SELECT',selection[a.page]+1,_utility=True)
            elif a.page in values:field(0,a.page,values[a.page],_utility=True)
        return tuple(result)

    @on_controller('mk2')
    def rotate(self,index,delta):
        self.sync()
        a=self.app
        if not delta:return
        if a.page in ('PATTERN GRID','GRID EDIT') and index in (0,1,5) and a.grid_range_anchor is not None and a.held_buttons.intersection(('SELECT','EVENT RANGE SELECT')):
            self.event_select_moved=True
            a.extend_grid_range(delta);return
        if index==0:
            if a.page in DEVICE_PAGES:a.rotate(delta);return
            if self.master_mode:
                origin=a.page;page={'VOLUME':'CHANNEL','SWING':'GROOVE','TEMPO':'TEMPO'}[self.master_mode]
                saved={key:getattr(a,key) for key in ('channel_field','channel_page','groove_field','control_level','pad','sampler_page','sampler_field','encoder_held')}
                held_group=any(n.startswith('GROUP ') for n in self.held)
                held_pad=any(source==self.source for source,_ in self.inputs.pads)
                a.control_level=1 if held_group else 2 if held_pad else 0
                a.page=page;a.channel_field=0;a.channel_page=0;a.groove_field=0
                a.automation_capture=self.auto_locked or 'AUTO' in self.held
                try:
                    if self.master_mode=='TEMPO' and a.control_level:
                        targets=range(16) if a.control_level==1 else (a.pad,)
                        a.page='SAMPLER';a.control_level=2;a.sampler_page=1
                        for pad in targets:
                            a.pad=pad
                            if not a.sampler_slot_present():continue
                            a.sampler_field=next(i for i,f in enumerate(a.sampler_fields()) if f[0]=='tune')
                            a.rotate_single(delta*(.01 if a.shift else 1))
                    else:a.rotate_single(delta)
                finally:
                    a.page=origin;del a.automation_capture
                    for key,value in saved.items():setattr(a,key,value)
            elif a.page=='CHOP' and a.slice_edit:
                a.slice_field=0;a.rotate(delta)
            elif a.page not in CONTROL_PAGES+('MIXER','STEP','PATTERN'):a.rotate(delta)
            else:
                for _ in range(min(32,abs(delta))):a.seek_transport('TRANSPORT RIGHT' if delta>0 else 'TRANSPORT LEFT')
            return
        binding=self.fields()[index-1]
        if binding is None:
            if index==8 and a.page in ('BROWSE','PLUGIN BROWSE'):a.rotate(delta)
            return
        attrs=dict(binding.attributes)
        if '_record_quant' in attrs:
            if delta:a.remember();a.timing()['record_quantize']=delta>0
            return
        if '_auto' in attrs:a.auto_adjust(attrs['_auto'],delta);return
        if '_hardware_select' in attrs:a.select_interface_control(delta);return
        if '_hardware_level' in attrs:a.interface_level(delta);return
        if '_dac_mute' in attrs:a.set_dac_mute(attrs['_dac_mute'],delta>0);return
        if '_utility' in attrs:a.rotate(delta);return
        if '_name_cursor' in attrs:a.name_cursor=max(0,min(31,a.name_cursor+delta));return
        if '_target_group' in attrs:
            a.slice_target_group=max(0,min(len(a.project['groups'])-1,a.slice_target_group+delta))
            a.group_bank=a.slice_target_group//8;a.slice_target_sound=None;return
        if '_target_sound' in attrs:
            index=-1 if a.slice_target_sound is None else a.slice_target_sound
            index=max(-1,min(15,index+delta));a.slice_target_sound=None if index<0 else index;return
        if '_bluetooth' in attrs:a.settings_rotate(delta);return
        if '_controller_key' in attrs:
            key=attrs['_controller_key'];values=a.settings['controllers'][self.source]
            if key in ('pad_sensitivity','pad_curve'):
                origin=a.page;a.page='PAD SENS' if key=='pad_sensitivity' else 'PAD CURVE'
                try:a.preferences_rotate(delta)
                finally:a.page=origin
            elif key=='invert':
                if delta:save_display(a,key,delta>0)
            else:
                value=values[key] if values[key] is not None else 100 if key=='brightness' else 42
                save_display(a,key,max(0,min(100,value+delta)))
            return
        if '_mk2_wave' in attrs:
            self.rotate_waveform(attrs['_mk2_wave'],delta);return
        if '_view' in attrs:
            target,field=attrs['_view'];a.view_target=target;a.view_field=field;a.navigation_rotate(delta);return
        if '_wave' in attrs:
            a.wave_selected=True;a.view_field=attrs['_wave'];a.rotate(delta);return
        if '_event_index' in attrs:
            origin=a.page;a.page='PATTERN GRID'
            try:a.rotate(delta)
            finally:a.page=origin
            return
        if '_row' in attrs:
            if a.grid_notes:a.grid_note=max(0,min(127,a.grid_note+delta))
            else:a.select_sound(max(0,min(15,a.pad+delta)))
            return
        if '_event_edit' in attrs:
            a.grid_field=attrs['_event_edit']
            a.change_grid_events(delta);return
        if '_sample_tool' in attrs:a.audio_tool_field=attrs['_sample_tool'];a.audio_tool_rotate(delta);return
        if '_length' in attrs:a.adjust_pattern_length(delta);return
        if '_velocity' in attrs or 'velocity_value' in attrs:a.velocity_value=max(1,min(127,a.velocity_value+delta));return
        if '_pitch' in attrs:
            note=a.step_input_note() or a.track().get('note',36+a.pad);a.remember_step_input(a.group,a.pad,max(0,min(127,note+delta)));return
        if '_grid' in attrs:
            from app.timing import RATES
            choices=[x[0] for x in RATES];a.remember();a.timing()['grid']=choices[max(0,min(len(choices)-1,choices.index(a.timing()['grid'])+delta))];return
        if '_mixer' in attrs:
            focus=(a.group,a.pad)
            if a.mixer_level==1:a.group=attrs['_mixer']
            elif a.mixer_level==2:a.pad=attrs['_mixer']
            a.automation_capture=self.auto_locked or 'AUTO' in self.held
            try:a.rotate_single(delta)
            finally:a.group,a.pad=focus;del a.automation_capture
            return
        for key,value in attrs.items():setattr(a,key,value)
        old_fine=a.encoder_held
        a.encoder_held=a.shift
        a.automation_capture=self.auto_locked or 'AUTO' in self.held
        try:a.rotate(delta)
        finally:a.encoder_held=old_fine;del a.automation_capture

    @on_controller('mk2')
    def button(self,name,pressed):
        import time
        a=self.app
        if pressed and time.monotonic()<getattr(a,'update_lock_until',0):return
        self.sync()
        if pressed:
            if name in self.held:return
            self.held.add(name)
            if name=='NOTE REPEAT' and a.shift:
                self.tap_tempo_held=True
                self.inputs.button(self.source,'TAP',True)
                return
            if name in ('CONTROL','STEP','BROWSE','SAMPLING','NAVIGATE','SCENE','PATTERN','PAD MODE','SELECT','MUTE','SOLO','NOTE REPEAT') or name.startswith('DISPLAY '):
                self.master_mode=None;self.master_page=None
        else:
            if name not in self.held:return
            self.held.discard(name)
            if name=='NOTE REPEAT' and self.tap_tempo_held:
                self.tap_tempo_held=False
                self.inputs.button(self.source,'TAP',False)
                return
        if name=='DISPLAY 1':
            if pressed and a.page in ('PATTERN GRID','GRID EDIT') and not a.shift:
                self.event_select_key=True;self.event_select_moved=False
                self.inputs.button(self.source,'EVENT RANGE SELECT',True);return
            if not pressed and self.event_select_key:
                self.event_select_key=False
                self.inputs.button(self.source,'EVENT RANGE SELECT',False)
                if not self.event_select_moved and a.page in ('PATTERN GRID','GRID EDIT'):self.softkey(0)
                return
        if name.startswith('DISPLAY '):
            if pressed:self.softkey(int(name.split()[1])-1)
            return
        if name.startswith('GROUP '):
            if pressed:
                index=a.group_bank*8+ord(name[-1])-65
                if index<len(a.project['groups']):
                    if a.page=='SLICE TARGET':a.slice_target_group=index;a.slice_target_sound=None
                    elif a.page in ('MUTE','SOLO'):
                        a.remember();target=a.project['groups'][index];key=a.page.lower();target[key]=not target.get(key,False)
                    else:a.select_group(index,multi=a.page=='SELECT' and a.select_multi)
            return
        if name in ('PAGE LEFT','PAGE RIGHT'):
            if pressed:self.change_page(-1 if name.endswith('LEFT') else 1)
            return
        if name=='CONTROL':
            if pressed:
                if a.page=='LIVE FX':a.close_live_fx()
                if a.shift:a.open_settings()
                else:a.main_controls=False;a.page=a.control_home()
            return
        if name=='STEP':
            if pressed:
                if a.page=='LIVE FX':a.close_live_fx()
                a.page=a.control_home() if a.page=='STEP' else 'STEP'
            return
        if name in ('VOLUME','SWING','TEMPO'):
            if pressed:
                self.master_mode=None if self.master_mode==name else name
                if self.master_mode and a.page in DEVICE_PAGES:a.page=a.control_home()
                self.master_page=a.page if self.master_mode else None
            return
        if name=='AUTO':
            if pressed:
                if a.shift:self.auto_locked=not self.auto_locked;self.auto_page=a.page
                elif self.auto_locked:self.auto_locked=False
                a.message='AUTO WRITE' if self.auto_locked or 'AUTO' in self.held else ''
            a.mk2_auto=self.auto_locked or 'AUTO' in self.held
            if not a.mk2_auto and a.message=='AUTO WRITE':a.message=''
            return
        if name=='ALL':
            if pressed:
                if a.shift:a.save()
                elif a.page in ('PATTERN GRID','GRID EDIT'):
                    events=set(a.event_notes())
                    a.grid_selected=set() if events and events.issubset(a.grid_selected) else events
                else:
                    a.sync_selection();a.selection_level=2
                    a.selected_pads={a.pad} if len(a.selected_pads)==16 else set(range(16))
                    a.sound_selections[a.group]=(a.pad,set(a.selected_pads))
                    a.message='ALL 16 SOUNDS SELECTED' if len(a.selected_pads)==16 else 'FOCUSED SOUND ONLY'
            return
        if self.source in ('mk1','mk2') and name in ('MASTER LEFT','MASTER RIGHT') and a.page in ('SAMPLER','PLUGIN','AUDIO LOOP') and not a.shift:
            if pressed:self.select_chain(-1 if name.endswith('LEFT') else 1)
            return
        mapped={'NAVIGATE':'VIEW','MASTER LEFT':'NAV LEFT','MASTER RIGHT':'NAV RIGHT','MASTER PUSH':'ENCODER PUSH'}.get(name,name)
        self.inputs.button(self.source,mapped,pressed)

    def repeat_active_keys(self):
        a=self.app;rate=a.project['repeat_presets'][a.repeat_bank*2+a.repeat_preset]
        return ({1} if a.repeat_locked else set()) | ({2} if a.arp_hold else set()) | ({3} if a.project['arp']['division']!='NORMAL' else set()) | {4+i for i,value in enumerate((8,16,32,64)) if value==rate}

    @on_controller('mk2')
    def softkeys(self):
        a=self.app;p=a.page
        if p in ('MIDI LEARN','SONG AUTO','SCENE OPTIONS'):return tuple(a.softkeys())+('','','','','')
        if p=='OPTIONS':return ('PIN' if self.held_mode() else 'BACK','SWING','GRID','QUANT','','','','APPLY' if a.grid_tab==0 else '')
        if p in ('SCENE','MUTE','SOLO','DUPLICATE'):
            keys=list(a.softkeys())+['']*5
            if self.held_mode():keys[3]=keys[0];keys[0]='PIN'
            if p=='SCENE':keys[6:8]=['BANK-','BANK+']
            return tuple(keys)
        if p=='AUTOSAMPLER':return ('RECORD','SETUP','OUTPUT','VELOCITY','NAME','FOLDER','CANCEL','START')
        if p=='AUDIO LOOP':return ('BACK','','','','','','<',self.chain_right_label())
        if p=='BOUNCE TO PAD':return ('BACK','','','','','','CANCEL' if a.capture_armed or a.capture_started is not None else '', 'STOP' if a.capture_started is not None else 'WAIT' if a.capture_armed else 'START')
        if p=='BLUETOOTH MIDI':return ('ON/OFF','PAIR','SCAN','BACK','CONNECT','DISCONN','','')
        if p=='VIEW NAV':return ('PIN','IDEAS','SONG','MIXER','BROWSE','EVENTS','LIVE FX','BACK')
        if p=='LIVE FX':return ('PUNCH','FLEX','KNOB','','DEPTH-','DEPTH+','OFF','BACK')
        if p in DEVICE_PAGES:return ('BACK','RESET','','','','','','')
        from app.codec_levels import dac_context
        if dac_context(a):return ('HP MUTE','SP MUTE','','BACK','','','','')
        from app.settings_menu import SETTINGS_VIEWS
        if p=='UPDATE':return ('CHECK','INSTALL','','BACK','BETA','RELEASE','','')
        if p in SETTINGS_VIEWS:return ('RESET' if a.shift and p in PREFERENCES else 'AUDIO','MIDI','SYSTEM','BACK','','','','')
        if a.wave_view():return ('PIN','WAVE','LIVE FX','','ZOOM-','ZOOM+','SCROLL-','SCROLL+')
        if p=='MACRO' and a.shift:return ('','ASSIGN','CLEAR','','CHANNEL','PLUG-IN','<','>')
        if p=='PLUGIN' and a.shift:return ('COPY','PASTE','MOVE','','BYPASS','BROWSE','REMOVE','')
        if p=='PLUGIN' and (a.plugin_selected() or {}).get('uri') in ('urn:machinista:ports:virtualjv','urn:machinista:ports:virtualjv-multi'):return ('MASTER','GROUP','SOUND','RESET PG','CHANNEL','PLUG-IN','<',self.chain_right_label())
        if p in CONTROL_PAGES:return ('MASTER','GROUP','SOUND','AUDIO' if p=='SAMPLER' else '', 'CHANNEL','PLUG-IN','<',self.chain_right_label() if p in ('SAMPLER','PLUGIN') else '>')
        if p in ('SAMPLING','SAMPLE EDIT','CHOP','ZONE','STRETCH','SLICE TARGET'):
            if p=='SLICE TARGET':return ('','','BANK-','BANK+','SINGLE','','CANCEL','APPLY')
            if p=='SAMPLING' and a.shift:return ('RECORD','EDIT','SLICE','ZONE','BOUNCE','AUDIO','','DELETE')
            right={'SAMPLING':a.capture_actions(),
                'SAMPLE EDIT':('<','>','SETTINGS' if PROCESSING[a.process_index]=='STRETCH' else '', 'APPLY'),
                'STRETCH':('','','CANCEL','APPLY'),
                'CHOP':('EDIT','SPLIT','REMOVE','DEL ALL') if a.slice_edit and not a.slice_single_apply else ('EDIT','','APPL.TO','APPLY'),
                'ZONE':('REMOVE','ADD','PREV','NEXT'),'SLICE TARGET':('SINGLE','','CANCEL','APPLY')}[p]
            return ('RECORD','EDIT','SLICE','ZONE')+right
        if p=='PAD CONFIG' and a.keyboard_enabled and a.keyboard_chord_mode()=='CUSTOM' and self.pad_page==2:return ('PIN' if self.held_mode() else 'PAD','KEYBOARD','16 VEL','FIX VEL','LEARN','INV-','INV+','')
        if p=='PAD CONFIG':return ('PIN' if self.held_mode() else 'PAD','KEYBOARD','16 VEL','FIX VEL','BANK-' if a.keyboard_enabled and a.slice_keyboard() else 'OCT-','BANK+' if a.keyboard_enabled and a.slice_keyboard() else 'OCT+','SEMI-','SEMI+')
        if p=='STEP':return ('PIN','','DOUBLE','FIX VEL','FOLLOW','','<','>')
        if p=='PATTERN':return ('PIN','REMOVE','DOUBLE','DUPL','EDITOR','','<','>')
        if p in ('PATTERN GRID','GRID EDIT'):
            selected=bool(a.grid_cursor_targets() & a.grid_selected)
            edit='DONE' if p=='GRID EDIT' else 'EDIT' if a.grid_targets() else 'ADD NOTE'
            return ('SELECTED' if selected else 'SELECT',edit,'FOLLOW','','UP','DOWN','ALL','NONE')
        if p=='MIXER':return ('MASTER','GROUP','SOUND','','LEVEL','PAN','ROUTE','RESET')
        if p=='BROWSE':return ('BACK','FIND' if a.shift else '','','PREHEAR','','','','LOAD')
        if p=='SELECT':return ('PIN','EVENTS','BANK-','BANK+','ALL','NONE','','MULTI')
        if p in ('NOTE REPEAT','ARP'):return ('PIN','LOCK','HOLD',a.project['arp']['division'], '1/8','1/16','1/32','1/64')
        keys=a.softkeys() or ('','','')
        return tuple(keys)+('','','','','')

    @on_controller('mk2')
    def softkey(self,index):
        a=self.app;p=a.page
        if p in ('AUDIO LOOP','BOUNCE TO PAD'):
            if index==0:a.audio_tool_button('F1',True)
            elif p=='AUDIO LOOP' and index in (6,7):self.select_chain(-1 if index==6 else 1,allow_add=True)
            elif p=='BOUNCE TO PAD' and index in (6,7):a.audio_tool_button('F2' if index==6 else 'F3',True)
            return
        if p=='SAMPLING' and a.shift and index in (4,5,7):
            self.tap({4:'F1',5:'F2',7:'F3'}[index]);return
        if p=='AUTOSAMPLER':
            a.auto_setup()
            if index==0:a.page='SAMPLING';a.capture_section=0
            elif index in (1,2,3):a.auto_field=(index-1)*8
            elif index in (4,5):a.auto_name('name' if index==4 else 'folder')
            elif index==6:a.auto_command=('cancel',None)
            elif index==7:a.auto_start()
            return
        if p=='BLUETOOTH MIDI':
            from app.bluetooth_midi import command
            if index==3:a.open_settings('MIDI')
            elif index in (0,1,2,4,5):command(a,{0:'off' if a.bluetooth_status.get('enabled') else 'on',1:'pair',2:'scan',4:'connect',5:'disconnect'}[index])
            return
        mode=self.held_mode()
        if p=='VIEW NAV':
            if index==0:a.pin_view()
            elif index==7:
                a.view_origin=a.view_entry;a.page=a.view_entry
            elif index in (1,2,3,4,5,6):
                a.select_view({1:'SCENE',2:'SONG',3:'MIXER',4:'BROWSE',5:'PATTERN GRID',6:'LIVE FX'}[index])
                # Keep Navigate held; releasing shows the selected view.
                if 'NAVIGATE' not in self.held:a.activate_view()
            return
        if p=='LIVE FX':
            if index<3:self.tap(f'F{index+1}')
            elif index in (4,5):a.live_fx_button('NAV LEFT' if index==4 else 'NAV RIGHT',True)
            elif index==6:a.live_fx_off()
            elif index==7:a.close_live_fx()
            return
        if p in DEVICE_PAGES:
            if index==0:a.settings_back()
            elif index==1:
                shifted=a.shift;a.shift=True
                try:a.settings_button('F1',True)
                finally:a.shift=shifted
            return
        from app.codec_levels import dac_context
        if dac_context(a):
            if index<2:a.settings_button(f'F{index+1}',True)
            elif index==3:a.settings_back()
            return
        from app.settings_menu import SETTINGS_VIEWS
        if p=='UPDATE':
            from app.updater import command
            if index in (0,1):command(a,'check' if index==0 else 'install')
            elif index in (4,5):command(a,'channel','beta' if index==4 else 'release')
            elif index==3:a.open_settings('SYSTEM')
            return
        if p in SETTINGS_VIEWS and index==3:a.settings_back();return
        if p=='OPTIONS':
            if index==0:
                if mode:self.tap('MAIN')
                else:a.page=a.mode_origins.get('GRID',a.control_home())
            elif index in (1,2,3):a.grid_tab={1:1,2:2,3:0}[index];a.grid_field=0
            elif index==7 and a.grid_tab==0:
                shifted=a.shift;a.shift=False
                try:self.tap('ENTER')
                finally:a.shift=shifted
            return
        if p=='SCENE' and index in (6,7):a.ensure_scene_bank(max(0,a.scene_bank+(-1 if index==6 else 1)));return
        if p in ('SCENE','MUTE','SOLO','DUPLICATE','OPTIONS') and index==3 and mode:
            self.tap('F1');return
        if index==0 and mode:
            self.tap('MAIN');return
        if a.wave_view():
            if index==1:a.wave_selected=True
            elif index==2:a.open_live_fx()
            elif index in (4,5,6,7):
                a.wave_selected=True;a.wave_control({4:1,5:5,6:0,7:2}[index])
            return
        if p=='MACRO' and a.shift and index in (1,2):
            a.routing_button('F2' if index==1 else 'F3',True);return
        if p=='PLUGIN' and a.shift:
            if index<3:a.plugins_button(f'F{index+1}',True)
            elif index in (4,5,6):
                a.shift=False
                try:a.plugins_button(f'F{index-3}',True)
                finally:a.shift=True
            return
        if p=='PLUGIN' and index==3 and a.virtualjv_reset(True):return
        if p in CONTROL_PAGES:
            if p=='SAMPLER' and index==3:a.audio_loop_setup()
            elif index<3:self.scope(index)
            elif index in (4,5):self.property('CHNL' if index==4 else 'PLUG-IN')
            elif index in (6,7):
                if self.source in ('mk1','mk2') and p in ('SAMPLER','PLUGIN'):self.select_chain(-1 if index==6 else 1,allow_add=True)
                else:self.property('PLUG-IN' if p in ('SAMPLER','PLUGIN') else 'CHNL',-1 if index==6 else 1)
            return
        if p in ('SAMPLING','SAMPLE EDIT','CHOP','ZONE','STRETCH','SLICE TARGET'):
            if p=='SLICE TARGET':
                if index in (2,3):
                    bank=max(0,min((len(a.project['groups'])-1)//8,a.slice_target_group//8+(-1 if index==2 else 1)))
                    a.slice_target_group=bank*8+a.slice_target_group%8;a.group_bank=bank;a.slice_target_sound=None
                elif index in (4,6,7):self.tap({4:'F1',6:'F2',7:'F3'}[index])
                return
            if index<4:
                if p=='SLICE TARGET':self.tap('F2')
                a.open_sampling_page(('SAMPLING','SAMPLE EDIT','CHOP','ZONE')[index]);return
            if p=='SAMPLING':
                if index==4:self.tap('F1')
                elif index==5:
                    if a.capture_started is not None or a.capture_armed:self.tap('F2')
                    elif a.track().get('sample'):
                        old=a.shift;a.shift=True
                        try:self.tap('F3')
                        finally:a.shift=old
                elif a.capture_actions()[index-4]:self.tap('F2' if index==6 else 'F3')
            elif p=='SAMPLE EDIT':
                if index in (4,5):self.tap('F1' if index==4 else 'F3')
                elif index==7 or index==6 and PROCESSING[a.process_index]=='STRETCH':self.tap('F2')
            elif p=='STRETCH':self.tap('F2' if index==7 else 'F3')
            elif p=='ZONE':
                if index==4:
                    old=a.shift;a.shift=True
                    try:self.tap('F3')
                    finally:a.shift=old
                else:self.tap({5:'F3',6:'F1',7:'F2'}[index])
            elif p=='SLICE TARGET':self.tap({4:'F1',6:'F2',7:'F3'}.get(index,'F2'))
            elif p=='CHOP':
                if a.shift and index in (6,7):a.slice_bank=max(0,min((len(a.slice_ranges())-1)//16,a.slice_bank+(-1 if index==6 else 1)));return
                if index==4:self.tap('F1')
                elif a.slice_edit and not a.slice_single_apply:
                    if index==5:self.tap('F2')
                    else:
                        old=a.shift;a.shift=index==7
                        try:self.tap('F3')
                        finally:a.shift=old
                elif index in (6,7):self.tap('F2' if index==6 else 'F3')
            return
        if p=='PAD CONFIG':
            if a.keyboard_enabled and a.keyboard_chord_mode()=='CUSTOM' and self.pad_page==2 and index>=4:
                if index in (4,5,6):a.chord_edit({4:'LEARN',5:'INVERT DOWN',6:'INVERT UP'}[index])
                return
            if index==0:a.keyboard_enabled=False;a.velocities16=False;self.pad_page=0
            elif index==1:a.keyboard_enabled=not a.keyboard_enabled;a.velocities16=False;self.pad_page=0
            elif index==2:a.velocities16=not a.velocities16;a.keyboard_enabled=False
            elif index==3:a.fixed_velocity=not a.fixed_velocity
            elif index>=4:
                step=16 if a.keyboard_enabled and a.slice_keyboard() else 12
                a.keyboard_root=max(0,min(127,a.keyboard_root+(-step if index==4 else step if index==5 else -1 if index==6 else 1)))
                if not a.slice_keyboard():a.performance()['root']=a.keyboard_root
            return
        if p=='MIXER':
            if index<3:a.mixer_level=index
            elif index in (4,5,6):a.mixer_field=index-4
            elif index==7:a.reset_mixer_peaks()
            return
        if p=='STEP':
            if index==2:self.tap('F2')
            elif index==3:self.tap('F3')
            elif index==4:self.tap('F1')
            elif index in (6,7):self.tap('NAV LEFT' if index==6 else 'NAV RIGHT')
            return
        if p=='PATTERN':
            if index in (1,2,3):self.tap({1:'F3',2:'F1',3:'F2'}[index])
            elif index==4:self.tap('ENTER')
            elif index in (6,7):a.ensure_pattern_bank(max(0,a.pattern_bank+(-1 if index==6 else 1)))
            return
        if p in ('PATTERN GRID','GRID EDIT'):
            if index==0:
                origin=a.page;a.page='PATTERN GRID'
                try:self.tap('F2')
                finally:a.page=origin
            elif index==1:self.tap('ENTER')
            elif index==2:a.toggle_grid_follow()
            elif index in (4,5):
                delta=1 if index==4 else -1
                if a.grid_notes:a.grid_note=max(0,min(127,a.grid_note+delta))
                else:a.select_sound(max(0,min(15,a.pad+delta)))
            elif index==6:a.grid_selected=set(a.event_notes())
            elif index==7:a.grid_selected.clear()
            return
        if p=='BROWSE':
            if index==0:self.tap('F1')
            elif index==1 and a.shift:self.tap('F2')
            elif index==3:self.tap('F3')
            elif index==7:self.tap('ENTER')
            return
        if p=='SELECT':
            if index==1:self.tap('F2')
            elif index in (2,3):a.ensure_group_bank(max(0,a.group_bank+(-1 if index==2 else 1)))
            elif index==4:a.selected_pads=set(range(16))
            elif index==5:a.selected_pads={a.pad}
            elif index==7:a.select_multi=not a.select_multi
            return
        if p in ('NOTE REPEAT','ARP'):
            if index==1:a.repeat_locked=not a.repeat_locked
            elif index==2:a.arp_hold=not a.arp_hold;a.project['arp']['hold']=a.arp_hold
            elif index==3:
                a.remember();choices=('NORMAL','TRIPLET','DOTTED');old=a.project['arp']['division']
                a.project['arp']['division']=choices[(choices.index(old)+1)%len(choices)]
            elif index>=4:
                a.remember();a.repeat_bank=(index-4)//2;a.repeat_preset=(index-4)%2
                rate=(8,16,32,64)[index-4]
                a.project['repeat_presets'][index-4]=rate;a.project['arp']['rate']=rate
            return
        if index<3:self.tap(f'F{index+1}')

    def master_feedback(self):
        self.sync()
        if not self.master_mode:return None
        a=self.app
        level=1 if any(n.startswith('GROUP ') for n in self.held) else 2 if any(source==self.source for source,_ in self.inputs.pads) else 0
        target=a.project if level==0 else a.project['groups'][a.group] if level==1 else a.track()
        scope='MASTER' if level==0 else f'GROUP {a.group+1}' if level==1 else f'SOUND {a.pad+1}'
        mode=self.master_mode
        if mode=='VOLUME':value=formatted(target.get('gain',100 if level<2 else 80),'gain')
        elif mode=='SWING':
            from app.groove import settings
            value=str(settings(target,a.timing()['swing'] if level==0 else 0)['amount'])+'%'
        else:
            mode='TUNE' if level else 'TEMPO'
            value=f"{target.get('sampler',{}).get('tune',0):.2f} ST" if level else f"{a.project['tempo']:.2f} BPM"
        return scope+' '+mode,value

    def disconnect(self):
        self.event_select_key=False;self.event_select_moved=False
        self.tap_tempo_held=False
        self.inputs.disconnect(self.source);self.held.clear();self.app.mk2_auto=False;self.auto_locked=False;self.master_mode=None;self.master_page=None
