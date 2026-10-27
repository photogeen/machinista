"""Pattern modulation lanes; playback values are transient, saved bases are stable."""
import bisect
import copy
import math
import time
from app.layout import SOUNDS,GROUP_BASE,MASTER,bus_targets
from app.sampler import DEFAULTS as SAMPLER_DEFAULTS,SAMPLER_PAGES
from app.routing import route_defaults,build_graph

def lane_key(pattern,descriptor):return ':'.join(map(str,(pattern,*descriptor)))

def validate_automation(project):
    targets=bus_targets(project)
    song_lengths=[]
    for scene in project.get('song',[]):
        automatic=max((len(project['groups'][g]['patterns'][pat][0]) for g,pat in enumerate(project['scenes'][scene]) if pat is not None),default=16)
        song_lengths.append(project.get('scene_lengths',{}).get(str(scene),automatic))
    scopes=[(g.get('automation',{}),[len(p[0]) for p in g['patterns']],False) for g in project['groups']]
    scopes.append((project.get('master_automation',{}),song_lengths,True))
    for lanes,lengths,master in scopes:
        if not isinstance(lanes,dict) or len(lanes)>2048:raise ValueError('invalid automation lanes')
        for name,lane in lanes.items():
            try:pattern,bus,kind,slot,key=name.split(':',4);pattern,bus,slot=int(pattern),int(bus),int(slot)
            except (ValueError,AttributeError):raise ValueError('invalid automation identity')
            if master and bus!=MASTER:raise ValueError('invalid master automation target')
            if not 0<=pattern<len(lengths) or bus not in targets or kind not in ('sampler','routing','value','plugin','fx'):raise ValueError('invalid automation target')
            if kind=='sampler' and (bus>=SOUNDS or key not in SAMPLER_DEFAULTS):raise ValueError('invalid sampler automation')
            if kind=='routing' and key not in route_defaults({}):raise ValueError('invalid route automation')
            if kind=='value' and key not in ('gain','note','channel'):raise ValueError('invalid value automation')
            if kind=='plugin' and (not 0<=slot<16 or not key):raise ValueError('invalid plugin automation')
            if kind=='fx' and (not GROUP_BASE<=bus<MASTER or slot!=-1 or key!='state'):raise ValueError('invalid performance FX automation')
            if not isinstance(lane,dict) or not isinstance(lane.get('points'),dict) or len(lane['points'])>98304:raise ValueError('invalid automation data')
            if 'enabled' in lane and type(lane['enabled']) is not bool:raise ValueError('invalid automation enable')
            numeric_bounds={'gain':(0,100),'note':(0,127),'channel':(1,16)} if kind=='value' else {'pan':(-100,100),'aux1_level':(0,100),'aux2_level':(0,100),'input_gain':(0,200)} if kind=='routing' else {}
            if key in numeric_bounds:
                lo,hi=numeric_bounds[key]
                if any(type(v) not in (int,float) or not math.isfinite(v) or not lo<=v<=hi for v in [lane.get('base'),*lane['points'].values()]):raise ValueError('invalid automation range')
            if kind=='fx' and any(type(v) is not int or not 0<=v<6144 for v in [lane.get('base'),*lane['points'].values()]):raise ValueError('invalid performance FX value')
            if kind=='sampler':
                spec=next(field for _,fields in SAMPLER_PAGES for field in fields if field[0]==key);_,_,default,bounds=spec
                for value in [lane.get('base')]+list(lane['points'].values()):
                    valid=value in bounds if isinstance(default,str) or type(default) is bool or key=='polyphony' else type(value) in (int,float) and bounds[0]<=value<=bounds[1]
                    if not valid:raise ValueError('invalid automated sampler value')
            for tick,value in lane['points'].items():
                if not str(tick).isdigit() or not 0<=int(tick)<(98304 if master else lengths[pattern]*24) or not isinstance(value,(str,int,float,bool)) or isinstance(value,(int,float)) and not math.isfinite(value):raise ValueError('invalid automation point')

class Automation:
    def init_automation(self):
        self.automation_bases={};self.automation_written=set();self.automation_cache=None
        self.midi_last_touched=None;self.midi_learning=None;self.midi_map_index=0;self.midi_gesture=None;self.midi_touch_until={}
        self.modulation_rotating=False;self.modulation_anchor=None;self.modulation_context=None
    def automation_descriptor(self):
        bus=self.plugin_bus()
        if self.page=='LIVE FX':return (GROUP_BASE+self.group,'fx',-1,'state')
        if self.page=='MIXER' and self.mixer_field<2:return (self.mixer_bus(),'value' if self.mixer_field==0 else 'routing',-1,'gain' if self.mixer_field==0 else 'pan')
        if self.page=='SAMPLER':return (self.group*16+self.pad,'sampler',-1,self.sampler_parameter()[0])
        if self.page=='PLUGIN' and self.plugin_selected() and self.plugin_controls():
            port=self.plugin_controls()[self.plugin_param]
            if not port.get('profile_action'):return (bus,'plugin',self.plugin_slot,port['symbol'])
        if self.page in ('PAD','CHANNEL'):
            key=self.channel_fields()[self.channel_field];return (bus,'value' if key in ('gain','note','channel') else 'routing',-1,key)
        if self.page=='MACRO':
            m=self.plugin_target().get('macros',{}).get(str(self.macro_index))
            if m:return (m['bus'],'plugin',m['slot'],m['symbol'])
        return None
    def automation_value(self,descriptor,project=None):
        bus,kind,slot,key=descriptor;target=bus_targets(project or self.project)[bus]
        if kind=='fx':return self.live_fx_pack()
        if kind=='sampler':return target.get('sampler',{}).get(key,SAMPLER_DEFAULTS[key])
        if kind=='routing':return route_defaults(target)[key]
        if kind=='value':return target.get(key,100 if key=='gain' else 36 if key=='note' else 1)
        plugin=target.get('plugins',[])[slot];return plugin.get('controls',{}).get(key,0)
    def automation_set(self,descriptor,value,project=None,notify=True):
        bus,kind,slot,key=descriptor;project=project or self.project;target=bus_targets(project)[bus]
        if kind=='fx':
            if project is not self.project or self.live_fx_manual_override():return
            mode,packed=divmod(int(value),2048);effect,velocity=divmod(packed,128)
            self.live_fx_mode=mode
            self.live_fx_send(effect,velocity,mode=mode,pressed=bool(effect))
            return
        if kind=='sampler':target.setdefault('sampler',{})[key]=value
        elif kind=='routing':
            r=target.setdefault('routing',route_defaults(target));old=r[key];r[key]=value
            try:build_graph(project)
            except ValueError:r[key]=old;return
        elif kind=='value':target[key]=value
        else:
            if slot>=len(target.get('plugins',[])):return
            target['plugins'][slot].setdefault('controls',{})[key]=value
        if notify:
            if kind=='sampler':self.actions.append(('load',(bus//16,bus%16,copy.deepcopy(target))))
            elif kind=='plugin':self.actions.append(('plugin_controls',(bus,copy.deepcopy(target.get('plugins',[])))))
            else:self.actions.append(('routing_refresh',None))
    def capture_automation(self,descriptor,before,after):
        if before==after or not self.playing or not getattr(self,'automation_capture',self.shift) or self.count_remaining:return
        master=descriptor[0]==MASTER
        if master and not self.song_playing:self.message='MASTER REC: PLAY SONG';return
        owner=-1 if master else self.group
        pattern=self.song_bar if master else self.pattern
        length=self.scene_steps(self.project['song'][pattern])*24 if master else self.pattern_ticks()
        tick=max(0,self.clock_phase-(getattr(self,'song_phase_origin',0) if master else 0))%length;key=lane_key(pattern,descriptor)
        lanes=self.project.setdefault('master_automation',{}) if master else self.project['groups'][self.group].setdefault('automation',{})
        if key not in lanes and len(lanes)>=2048:self.message='AUTOMATION LIMIT';return
        previous=lanes.get(key);base=self.automation_bases.get(descriptor,before)
        metadata={k:copy.deepcopy(v) for k,v in (previous or {'base':before}).items() if k!='points'}
        tick_key=str(tick)
        prior=dict(exists=previous is not None,present=previous is not None and tick_key in previous['points'],point=copy.deepcopy(previous['points'].get(tick_key)) if previous else None,metadata=metadata,base_value=base)
        lane=lanes.setdefault(key,{'base':base,'points':{}})
        if descriptor[1]=='plugin':lane['uri']=bus_targets(self.project)[descriptor[0]]['plugins'][descriptor[2]]['uri']
        lane['points'][str(tick)]=after;self.automation_bases.setdefault(descriptor,before)
        after_state=dict(exists=True,present=True,point=after,metadata={k:copy.deepcopy(v) for k,v in lane.items() if k!='points'},base_value=base)
        self.modulation_change(owner,key,tick_key,descriptor,prior,after_state)
        self.automation_written.add(descriptor);self.automation_cache=None;self.dirty=True;self.message='MODULATION REC'
    def automation_tick(self):
        signature=(id(self.project),self.revision,tuple(self.active_patterns),tuple(self.active_clips),self.song_playing,self.song_bar)
        if self.automation_cache is None or self.automation_cache[0]!=signature:
            active=[]
            for group,pattern in enumerate(self.active_patterns):
                if not self.active_clips[group]:continue
                for name,lane in self.project['groups'][group].get('automation',{}).items():
                    pat,bus,kind,slot,key=name.split(':',4)
                    if int(pat)!=pattern:continue
                    points=sorted((int(tick),value) for tick,value in lane['points'].items() if int(tick)<self.pattern_ticks(group,pattern))
                    active.append((group,pattern,(int(bus),kind,int(slot),key),lane,points,[p[0] for p in points]))
            if self.song_playing and self.song_bar<len(self.project.get('song',[])):
                for name,lane in self.project.get('master_automation',{}).items():
                    pat,bus,kind,slot,key=name.split(':',4)
                    if int(pat)!=self.song_bar:continue
                    points=sorted((int(t),v) for t,v in lane['points'].items() if int(t)<self.scene_steps(self.project['song'][self.song_bar])*24)
                    active.append((-1,self.song_bar,(int(bus),kind,int(slot),key),lane,points,[p[0] for p in points]))
            self.automation_cache=(signature,active)
        active_descriptors={item[2] for item in self.automation_cache[1] if item[3].get('enabled',True)}
        for descriptor in list(self.automation_bases):
            if descriptor not in active_descriptors and (descriptor[0]==MASTER or descriptor not in self.automation_written):
                self.automation_set(descriptor,self.automation_bases.pop(descriptor))
        for group,pattern,descriptor,lane,points,positions in self.automation_cache[1]:
            if not lane.get('enabled',True) or self.midi_touch_until.get(descriptor,0)>time.monotonic():continue
            if not points or (self.shift or getattr(self,'mk2_auto',False)) and descriptor==self.automation_descriptor():continue
            if descriptor[1]=='plugin':
                slots=bus_targets(self.project)[descriptor[0]].get('plugins',[])
                if descriptor[2]>=len(slots) or slots[descriptor[2]]['uri']!=lane.get('uri'):continue
            tick=(self.clock_phase-(getattr(self,'song_phase_origin',0) if group==-1 else 0))%(self.scene_steps(self.project['song'][pattern])*24 if group==-1 else self.pattern_ticks(group,pattern));index=bisect.bisect_right(positions,tick)-1
            value=lane['base'] if index<0 else points[index][1]
            if descriptor[1]!='fx' and 0<=index<len(points)-1 and type(value) in (int,float) and type(points[index+1][1]) in (int,float):
                a,b=points[index],points[index+1];value=a[1]+(b[1]-a[1])*(tick-a[0])/(b[0]-a[0]);value=round(value) if type(a[1]) is int else round(value,4)
            current=self.automation_value(descriptor)
            self.automation_bases.setdefault(descriptor,current)
            if value!=current:
                self.automation_set(descriptor,value)
                if descriptor[1]=='sampler' or descriptor[1]=='value' and descriptor[3] in ('note','channel'):self.native_sequence_serial=getattr(self,'native_sequence_serial',0)+1
    def automation_restore(self):
        for descriptor,value in self.automation_bases.items():
            try:self.automation_set(descriptor,value)
            except (KeyError,IndexError):pass
        self.automation_bases.clear();self.automation_written.clear();self.automation_cache=None
    def project_for_save(self):
        result=copy.deepcopy(self.project)
        for descriptor,value in self.automation_bases.items():
            try:self.automation_set(descriptor,value,result,False)
            except (KeyError,IndexError):pass
        return result
    def copy_automation(self,source_group,source_pattern,target_group,target_pattern,source_pad=None,target_pad=None):
        lanes=self.project['groups'][source_group].get('automation',{});target=self.project['groups'][target_group].setdefault('automation',{})
        additions={}
        for name,lane in list(lanes.items()):
            pat,bus,kind,slot,key=name.split(':',4);bus=int(bus)
            if int(pat)!=source_pattern:continue
            if source_pad is not None and bus!=source_group*16+source_pad:continue
            if source_group*16<=bus<source_group*16+16:bus=target_group*16+(target_pad if source_pad is not None else bus%16)
            elif bus==GROUP_BASE+source_group:bus=GROUP_BASE+target_group
            additions[lane_key(target_pattern,(bus,kind,int(slot),key))]=copy.deepcopy(lane)
        prefix=str(target_pattern)+':'
        for name in list(target):
            if name.startswith(prefix) and (source_pad is None or int(name.split(':')[1])==target_group*16+target_pad):del target[name]
        target.update(additions);self.automation_cache=None

    def clear_automation(self):
        bus=self.mixer_bus() if self.page=='MIXER' else self.plugin_bus();self.automation_restore();self.remember()
        group=self.project if bus==MASTER else self.project['groups'][self.group];field='master_automation' if bus==MASTER else 'automation'
        prefix=str(self.song_bar if self.song_playing else self.song_index)+':' if bus==MASTER else str(self.pattern)+':'
        group[field]={k:v for k,v in group.get(field,{}).items() if not (k.startswith(prefix) and int(k.split(':')[1])==bus)}
        self.automation_cache=None;self.message='MODULATION CLEARED'
