"""MK3 dedicated controls share the proven eight-knob engine bindings."""
import copy
from app.mk2_surface import Mk2Surface,Field
from app.controller_settings import on_controller

class Mk3Surface(Mk2Surface):
    source='mk3'
    def __init__(self,*args):
        super().__init__(*args);self.strip_mode=None;self.strip_value=0;self.touched=set()
    @on_controller('mk3')
    def button(self,name,pressed):
        import time
        a=self.app
        if pressed and time.monotonic()<getattr(a,'update_lock_until',0):return
        if name=='FOLLOW':
            if pressed and name not in self.held and not getattr(self,'follow_grid',False):
                self.follow_grid=a.shift
            if getattr(self,'follow_grid',False):
                if pressed and 'GRID' not in self.held:a.grid_tab=2;a.grid_field=0
                shifted=a.shift;a.shift=False
                try:return super().button('GRID',pressed)
                finally:
                    a.shift=shifted
                    if not pressed:self.follow_grid=False
        if name=='TAP':
            if pressed:
                if name in self.held:return
                self.held.add(name);self.tap_binding='METRONOME' if a.shift else 'TAP'
                if self.tap_binding=='METRONOME':a.timing_button('PLAY',True)
                else:self.inputs.button(self.source,'TAP',True)
            else:
                if name not in self.held:return
                self.held.discard(name)
                if getattr(self,'tap_binding',None)=='TAP':self.inputs.button(self.source,'TAP',False)
                self.tap_binding=None
            return
        if name in ('MASTER LEFT','MASTER RIGHT','MASTER UP','MASTER DOWN') and a.page in ('SAMPLER','PLUGIN','AUDIO LOOP'):
            if pressed:
                if name in self.held:return
                self.held.add(name)
                offset=int(a.sampler_slot_present());count=len(a.plugin_target().get('plugins',[]))+offset
                current=0 if a.page in ('SAMPLER','AUDIO LOOP') else a.plugin_slot+offset
                delta=-1 if name in ('MASTER LEFT','MASTER UP') else 1
                target=max(0,min(count-1,current+delta))
                if count and target!=current:
                    a.parameter_kind='PLUG-IN';a.parameter_choice=target
                    a.plugin_param=0;a.page=a.parameter_destination();a.remember_control_view()
                    self.chain_motion=(getattr(self,'chain_motion',(0,''))[0]+1,name)
            else:self.held.discard(name)
            return
        if name.endswith(' TOUCH'):
            if pressed:self.touched.add(name)
            else:self.touched.discard(name)
            return
        if name in ('LOCK','CHANNEL','PLUG-IN','MIXER','ARRANGER','SETTINGS','FILE','KEYBOARD','CHORDS','FIXED VEL','EVENTS','PERFORM','MACRO','FOLLOW','STOP','PITCH','MOD','NOTES','MASTER UP','MASTER DOWN'):
            if pressed:
                if name in self.held:return
                self.held.add(name)
            else:self.held.discard(name);return
            self.master_mode=None
            if a.page=='LIVE FX' and (name in ('CHANNEL','PLUG-IN','MIXER','ARRANGER','SETTINGS','KEYBOARD','CHORDS','EVENTS','MACRO') or name=='FILE' and not a.shift):
                # Clear owners and record the OFF state before leaving, without
                # restoring an origin that could invert a workspace toggle.
                a.live_fx_off()
                if self.strip_mode=='PERFORM':self.strip_mode=None
            if name=='LOCK':self.lock_parameters()
            elif name in ('CHANNEL','PLUG-IN'):self.property('CHNL' if name=='CHANNEL' else 'PLUG-IN')
            elif name=='MIXER':a.page=a.control_home() if a.page=='MIXER' else 'MIXER'
            elif name=='ARRANGER':a.page=a.control_home() if a.page=='SONG' else 'SONG'
            elif name=='SETTINGS':
                if a.page=='SETTINGS':a.page=a.control_home()
                else:a.open_settings()
            elif name=='FILE':a.save() if a.shift else setattr(a,'page','PROJECT')
            elif name=='KEYBOARD':
                a.keyboard_enabled=not a.keyboard_enabled;a.velocities16=False
                a.page='PAD CONFIG' if a.keyboard_enabled else a.control_home()
            elif name=='CHORDS':
                a.remember();a.keyboard_enabled=True;a.velocities16=False
                p=a.performance();p['chord_mode']='OFF' if a.keyboard_chord_mode()!='OFF' else 'CUSTOM'
                a.page='PAD CONFIG';self.pad_page=0
            elif name=='FIXED VEL':a.fixed_velocity=not a.fixed_velocity
            elif name=='EVENTS':a.open_pattern_grid()
            elif name=='PERFORM':
                self.strip_mode=None if self.strip_mode=='PERFORM' else 'PERFORM'
                if a.page!='LIVE FX':a.open_live_fx()
            elif name=='MACRO':a.page=a.control_home() if a.page=='MACRO' else 'MACRO'
            elif name=='FOLLOW':
                if a.page in ('PATTERN GRID','GRID EDIT'):a.grid_follow=not a.grid_follow
                else:a.follow=not a.follow
            elif name=='STOP':
                if a.playing:self.tap('PLAY')
            elif name in ('PITCH','MOD','NOTES'):
                if self.strip_value:self.strip(0)
                self.strip_mode=None if self.strip_mode==name else name
            elif name in ('MASTER UP','MASTER DOWN'):
                if a.page in ('PATTERN GRID','GRID EDIT'):
                    a.pause_grid_follow();a.grid_voice=None
                    if a.grid_notes:a.grid_note=max(0,min(127,a.grid_note+(1 if name=='MASTER UP' else -1)))
                    else:a.pad=max(0,min(15,a.pad+(1 if name=='MASTER UP' else -1)))
                else:self.rotate(0,-1 if name=='MASTER UP' else 1)
            return
        if name in ('PAGE LEFT','PAGE RIGHT','MASTER LEFT','MASTER RIGHT') and a.page=='CHOP':
            if pressed:
                if name in self.held:return
                self.held.add(name)
                if a.shift:
                    a.slice_edit=False;self.change_page(1 if name.endswith('RIGHT') else -1)
                elif a.slice_ranges():
                    if not a.slice_edit and a.live_chop_started is not None:a.stop_live_chop()
                    a.slice_edit=True;a.focus_slice_boundary(name.endswith('RIGHT'))
            else:self.held.discard(name)
            return
        if name=='VARIATION':
            if pressed:self.variation_binding='GRID' if a.shift else 'NAVIGATE'
            binding=getattr(self,'variation_binding','NAVIGATE');shifted=a.shift
            # SHIFT chooses the binding; it must not turn GRID into SHIFT+GRID.
            a.shift=False
            try:return super().button(binding,pressed)
            finally:a.shift=shifted
        return super().button(name,pressed)
    def softkeys(self):
        keys=super().softkeys()
        if self.app.page=='OPTIONS':keys=keys[:2]+('GRID',)+keys[3:]
        return keys

    def fields(self):
        return super().fields()

    @on_controller('mk3')
    def rotate(self,index,delta):
        import time
        a=self.app
        if time.monotonic()<getattr(a,'update_lock_until',0):return
        return super().rotate(index,delta)

    def page_directions(self):
        if self.app.page=='CHOP' and self.app.slice_ranges():return True,True
        return super().page_directions()

    def strip(self,value):
        self.strip_value=value
        if self.strip_mode=='PITCH':
            bend=8192 if value==0 else round((value-1)*16383/1023)
            self.app.actions.append(('controller_midi',(0xe0,(bend&127,bend>>7))))
        elif self.strip_mode=='MOD':
            if value:self.app.actions.append(('controller_midi',(0xb0,(1,round((value-1)*127/1023)))))
        elif self.strip_mode=='PERFORM':
            before=self.app.live_fx_pack();velocity=round(value*127/1024)
            self.app.live_fx_send(self.app.live_fx_pad+1 if self.app.live_fx_pad<15 else 0,velocity,pressed=bool(value))
            self.app.live_fx_record(before,self.app.live_fx_pack())
        elif self.strip_mode=='NOTES':
            # Glissando through the same keyboard mapping as the physical pads.
            slot=min(15,max(0,(value-1)*16//1024)) if value else None
            old=getattr(self,'strip_pad',None)
            if old!=slot:
                if old is not None:self.inputs.pad_off(self.source+'-strip',old)
                if slot is not None:self.inputs.pad_on(self.source+'-strip',slot,100)
                self.strip_pad=slot
    def disconnect(self):
        self.inputs.disconnect(self.source+'-strip');super().disconnect()

    def lock_parameters(self):
        """A/B performance parameters only; never restore notes, files or plug-in slots."""
        a=self.app
        targets=[a.project]+[v for g in a.project['groups'] for v in [g]+g['pads']]
        stored=getattr(self,'lock_state',None)
        if stored is None or stored[0]!=a.project_generation:
            data=[]
            for target in targets:
                values={k:copy.deepcopy(target[k]) for k in ('gain','sampler','routing','macros') if k in target}
                plugins=tuple((v['uri'],copy.deepcopy(v.get('controls',{})),v.get('bypass',False)) for v in target.get('plugins',[]))
                data.append((values,plugins))
            self.lock_state=(a.project_generation,data);a.message='PARAMETERS LOCKED';return
        a.remember()
        for target,(values,plugins) in zip(targets,stored[1]):
            for key,value in values.items():target[key]=copy.deepcopy(value)
            for current,(uri,controls,bypass) in zip(target.get('plugins',[]),plugins):
                if current['uri']==uri:current['controls']=copy.deepcopy(controls);current['bypass']=bypass
        self.lock_state=None;a.dirty=True;a.message='LOCK RESTORED'
