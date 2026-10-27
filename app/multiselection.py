"""Mikro Select/Quiet focus and parameter mirroring (manual PDF164-169)."""
import copy
from app.layout import GROUP_BASE,MASTER,bus_targets
from app.routing import route_defaults,build_graph
from app.groove import settings as groove_settings

GROUP_PADS=(12,13,14,15,8,9,10,11)

class MultiSelection:
    def init_multiselection(self):
        self.selection_project=self.project
        self.sound_selections={}
        self.selected_groups={self.group}
        self.selection_level=2
        self.selection_group=self.group
        self.selection_focus=self.pad

    def sync_selection(self):
        if self.selection_project is not self.project:
            self.init_multiselection();self.selected_pads={self.pad}
        if self.selection_group!=self.group:
            if self.group not in self.selected_groups:self.selected_groups={self.group}
            self.sound_selections[self.selection_group]=(self.pad if not hasattr(self,'selection_focus') else self.selection_focus,set(self.selected_pads))
            focus,selected=self.sound_selections.get(self.group,(0,{0}))
            self.pad=focus;self.selected_pads=set(selected);self.selection_group=self.group;self.selection_focus=self.pad
        if self.pad!=self.selection_focus and self.pad not in self.selected_pads:self.selected_pads={self.pad}
        self.selected_pads.intersection_update(range(16));self.selected_pads.add(self.pad)
        self.selected_groups.intersection_update(range(len(self.project['groups'])));self.selected_groups.add(self.group)
        self.selection_focus=self.pad

    def select_sound(self,slot,multi=False):
        self.sync_selection();self.selection_level=2;self.selected_groups={self.group}
        if multi:
            if slot!=self.pad:
                if slot in self.selected_pads:self.selected_pads.remove(slot)
                else:self.selected_pads.add(slot)
        else:
            if slot not in self.selected_pads:self.selected_pads={slot}
            changed=slot!=self.pad;was_slice=self.slice_keyboard()
            self.pad=slot
            if changed:
                if self.slice_keyboard():self.keyboard_root=0
                elif was_slice:self.keyboard_root=self.performance()['root']
                if self.control_level==2 and self.page in ('SAMPLER','PLUGIN','AUDIO LOOP'):
                    # A new Sound owns a different source and effect chain.
                    # Never carry the previous pad's sampler page into a synth.
                    from app.audio_loop import is_audio_sound
                    self.plugin_slot=self.plugin_param=0
                    self.parameter_kind='PLUG-IN';self.parameter_choice=0
                    self.page=('AUDIO LOOP' if is_audio_sound(self.track()) else 'SAMPLER') if self.sampler_slot_present() else 'PLUGIN'
                    self.remember_control_view()
        self.selection_focus=self.pad
        self.sound_selections[self.group]=(self.pad,set(self.selected_pads))

    def select_group(self,index,multi=False):
        self.sync_selection()
        if not 0<=index<len(self.project['groups']):return
        self.selection_level=1
        if multi:
            if index!=self.group:
                if index in self.selected_groups:self.selected_groups.remove(index)
                else:self.selected_groups.add(index)
        else:
            if index not in self.selected_groups:self.selected_groups={index}
            self.group=index;self.sync_selection()
            self.group_bank=self.group//8;self.pattern=self.active_patterns[self.group]
            self.pattern_bank=self.pattern//16;self.keyboard_root=0 if self.slice_keyboard() else self.performance()['root']

    def selection_pad(self,slot):
        if self.page=='GROUP' and self.mode_origins.get('GROUP')=='SELECT' and not self.shift:
            if slot in GROUP_PADS:self.select_group(self.group_bank*8+GROUP_PADS.index(slot),self.select_multi)
            return True
        if self.page=='SELECT' and not self.shift:
            self.select_sound(slot,self.select_multi);return True
        return False

    def selection_buses(self,level):
        self.sync_selection()
        if level==0:return [MASTER]
        if level==1:return [GROUP_BASE+i for i in sorted(self.selected_groups)] if self.selection_level==1 else [GROUP_BASE+self.group]
        return [self.group*16+i for i in sorted(self.selected_pads)] if self.selection_level==2 else [self.group*16+self.pad]

    def selection_parameter(self):
        """path, default, numeric bounds (None means discrete), level, URI guard."""
        level=self.mixer_level if self.page=='MIXER' else self.control_level
        if self.page=='SAMPLER':
            key,_,default,bounds=self.sampler_parameter()
            return ('sampler',key),default,None if isinstance(default,(str,bool)) or key=='polyphony' else bounds,2,'SAMPLER'
        if self.page=='PLUGIN' and self.plugin_selected() and self.plugin_controls():
            port=self.plugin_controls()[self.plugin_param];plugin=self.plugin_selected()
            if port.get('profile_action'):return None
            return ('plugins',self.plugin_slot,'controls',port['symbol']),port['default'],None if port.get('toggle') else (port['min'],port['max']),level,plugin['uri']
        if self.page=='PAD CONFIG' and not self.keyboard_enabled and self.pad_field<5:
            key=('choke_group','choke_mode','link_group','link_mode','note')[self.pad_field]
            return (key,), 'MASTER' if key.endswith('mode') else 36+self.pad if key=='note' else 0,None,2,None
        if self.page=='GROOVE':
            key=('amount','cycle','invert')[self.groove_field]
            return ('groove',key),groove_settings(self.plugin_target())[key],(0,100) if key=='amount' else None,level,None
        if self.page=='MACRO' and self.plugin_target().get('macros',{}).get(str(self.macro_index)):
            return ('macros',str(self.macro_index),'value'),0,(0,100),level,'MACRO'
        if self.page=='INPUT':key='input' if self.input_field==0 else 'input_gain'
        elif self.page in ('PAD','CHANNEL'):key=self.channel_fields()[self.channel_field]
        elif self.page=='MIXER':key=('gain','pan','dest')[self.mixer_field]
        else:return None
        if key in ('gain','note','channel'):return (key,),100 if key=='gain' else 36+self.pad if key=='note' else 1,(0,100) if key=='gain' else None,level,None
        return ('routing',key),route_defaults(self.plugin_target() if self.page!='MIXER' else self.mixer_target())[key],{'pan':(-100,100),'input_gain':(0,200),'aux1_level':(0,100),'aux2_level':(0,100)}.get(key),level,None

    @staticmethod
    def selection_value(target,path,default):
        for key in path:
            if isinstance(target,list):
                if key>=len(target):return default
                target=target[key]
            else:
                if key not in target:return default
                target=target[key]
        return target

    @staticmethod
    def selection_set(target,path,value):
        for key in path[:-1]:
            target=target[key] if isinstance(target,list) else target.setdefault(key,{})
        target[path[-1]]=value

    def rotate(self,delta):
        self.sync_selection();spec=self.selection_parameter()
        if spec is None:return self.rotate_single(delta)
        path,default,bounds,level,guard=spec
        capture=bool(self.automation_descriptor())
        focus=self.mixer_bus() if self.page=='MIXER' else self.group*16+self.pad if self.page in ('SAMPLER','PAD CONFIG') else self.plugin_bus()
        targets=bus_targets(self.project);peers=[]
        before=self.selection_value(targets[focus],path,default)
        for bus in self.selection_buses(level):
            if bus==focus:continue
            target=targets[bus];chain=target.get('plugins',[])
            if guard=='SAMPLER' and chain and chain[0].get('kind')=='INSTRUMENT':continue
            if guard=='MACRO' and str(self.macro_index) not in target.get('macros',{}):continue
            if guard and guard not in ('SAMPLER','MACRO') and (path[1]>=len(chain) or chain[path[1]]['uri']!=guard):continue
            peers.append((bus,self.selection_value(target,path,default)))
        self.rotate_single(delta)
        after=self.selection_value(targets[focus],path,default)
        if before==after:return
        for bus,old in peers:
            value=after if bounds is None else max(bounds[0],min(bounds[1],round(old+after-before,6)))
            target=targets[bus]
            self.selection_set(target,path,value)
            if path[0]=='routing':
                try:build_graph(self.project)
                except ValueError:self.selection_set(target,path,old);self.message='SELECTION ROUTING CYCLE';continue
            descriptor=None
            if path[0]=='sampler':descriptor=(bus,'sampler',-1,path[1]);self.actions.append(('load',(bus//16,bus%16,copy.deepcopy(target))))
            elif path[0]=='plugins':descriptor=(bus,'plugin',path[1],path[-1]);self.actions.append(('plugin_controls',(bus,copy.deepcopy(target['plugins']))))
            elif path[0]=='routing':descriptor=(bus,'routing',-1,path[1]);self.actions.append(('routing_refresh',None))
            elif path[0] in ('gain','note','channel'):descriptor=(bus,'value',-1,path[0]);self.actions.append(('load',(bus//16,bus%16,copy.deepcopy(target)))) if bus<GROUP_BASE else None
            elif self.page=='PAD CONFIG':self.actions.append(('load',(bus//16,bus%16,copy.deepcopy(target))))
            if path[0]=='macros':
                mapping=target['macros'][str(self.macro_index)];mapped=targets[mapping['bus']];chain=mapped.get('plugins',[])
                if mapping['slot']<len(chain):
                    descriptor=(mapping['bus'],'plugin',mapping['slot'],mapping['symbol']);old=self.automation_value(descriptor)
                    value=mapping['min']+(mapping['max']-mapping['min'])*value/100
                    self.automation_set(descriptor,value)
            if descriptor and capture:
                saved=(self.group,self.pattern)
                if GROUP_BASE<=bus<MASTER:self.group=bus-GROUP_BASE;self.pattern=self.active_patterns[self.group]
                try:self.capture_automation(descriptor,old,value)
                finally:self.group,self.pattern=saved
