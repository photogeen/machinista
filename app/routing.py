"""Acyclic Sound/Group/Master routing with two pre/post sends."""
import copy
from app.audio_ports import port, ports
from app.layout import SOUNDS,GROUP_BASE,MASTER,BUSES,bus_targets

CHANNELS=('INPUT','OUTPUT','GROOVE','MACRO')


def route_defaults(target):
    r={'dest':'PARENT','pan':0,'aux1_dest':'NONE','aux1_level':0,'aux1_pre':False,'aux2_dest':'NONE','aux2_level':0,'aux2_pre':False,'midi_send':False,'midi_target':'NONE','input':'NONE','input_gain':100}
    r.update(target.get('routing',{}));return r


def destination(value,bus):
    if value=='CUE':return -50
    physical=port(value,'OUT')
    if physical:return -100-physical[0] if len(physical)==1 else -2-physical[0]//2
    if value=='NONE':return -99 if bus==MASTER else -1
    if value=='PARENT':return GROUP_BASE+bus//16 if bus<SOUNDS else MASTER if bus<MASTER else -1
    if value=='MASTER':return MASTER
    if value.startswith('GROUP '):return GROUP_BASE+int(value.split()[1])
    if value.startswith('SOUND '):return int(value.split()[1])
    raise ValueError('unknown routing destination')


def build_graph(project):
    nodes=[]
    targets=bus_targets(project)
    for bus,target in targets.items():
        r=route_defaults(target);edges=[]
        for key,lo,hi in (('pan',-100,100),('aux1_level',0,100),('aux2_level',0,100),('input_gain',0,200)):
            if not isinstance(r[key],(int,float)) or not lo<=r[key]<=hi:raise ValueError('invalid routing level')
        if any(type(r[key]) is not bool for key in ('aux1_pre','aux2_pre','midi_send')) or r['input'] not in ('NONE','EXT STEREO','EXT LEFT','EXT RIGHT') and port(r['input'],'IN') is None:raise ValueError('invalid routing switch')
        for field in ('dest','aux1_dest','aux2_dest'):
            dst=destination(r[field],bus)
            if dst==bus or dst>=0 and dst not in targets:raise ValueError('routing cycle or unknown bus')
            if dst>=0:edges.append(dst)
        nodes.append((bus,target,r,edges))
    by_bus={n[0]:n for n in nodes}
    for bus,target,_,_ in nodes:
        for plugin in target.get('plugins',[]):
            source=plugin.get('sidechain','NONE')
            if source=='EXT STEREO':continue
            src=destination(source,bus)
            if src>=0:
                if src==bus or src not in by_bus:raise ValueError('sidechain cycle or unknown bus')
                by_bus[src][3].append(bus)
            elif source!='NONE':raise ValueError('invalid sidechain source')
    indegrees={bus:0 for bus in targets}
    for _,_,_,edges in nodes:
        for dst in set(edges):indegrees[dst]+=1
    from app.virtualjv_multi import internal_destination,rack
    occupied=set()
    for g in project['groups']:
        for track in g['pads']:
            value=track.get('routing',{}).get('midi_target','NONE')
            if value=='NONE':continue
            target=internal_destination(track)
            if target is None or target[0]-GROUP_BASE>=len(project['groups']) or rack(project['groups'][target[0]-GROUP_BASE]) is None:raise ValueError('invalid internal MIDI target')
            if target in occupied:raise ValueError('MIDI channel already assigned')
            occupied.add(target)
    order=[];ready=[i for i,n in indegrees.items() if n==0]
    while ready:
        bus=ready.pop(0);order.append(bus)
        for dst in set(by_bus[bus][3]):
            indegrees[dst]-=1
            if not indegrees[dst]:ready.append(dst)
    if len(order)!=len(targets):raise ValueError('routing cycle')
    return nodes,order


class Routing:
    def init_routing(self):self.channel_field=0;self.groove_field=0;self.channel_page=0;self.input_field=0;self.macro_index=0;self.macro_choice=0
    def channel_fields(self):
        if self.channel_page==0:return ('gain','pan','dest')
        if self.channel_page==1:return ('aux1_dest','aux1_level','aux1_pre')
        if self.channel_page==2:return ('aux2_dest','aux2_level','aux2_pre')
        return ('midi_target','midi_send','note','channel') if self.control_level==2 else ('gain','pan','dest')
    def routing_button(self,name,pressed):
        if not pressed:return False
        if self.page=='INPUT' and name in ('NAV LEFT','NAV RIGHT'):
            self.input_field=int(name=='NAV RIGHT');return True
        if self.page=='MACRO':
            if name in ('NAV LEFT','NAV RIGHT'):self.macro_index=max(0,min(7,self.macro_index+(-1 if name=='NAV LEFT' else 1)));return True
            if name=='F2' and self.shift:self.page='MACRO ASSIGN';self.macro_choice=0;return True
            if name=='F3' and self.shift:self.remember();self.plugin_target().setdefault('macros',{}).pop(str(self.macro_index),None);return True
        if self.page=='MACRO ASSIGN' and name in ('F2','ENTER'):
            choices=self.macro_targets()
            if choices:
                self.remember();self.plugin_target().setdefault('macros',{})[str(self.macro_index)]=dict(choices[self.macro_choice],value=0)
            self.page='MACRO';return True
        if self.page not in ('PAD','CHANNEL'):return False
        if name in ('NAV LEFT','NAV RIGHT'):
            delta=-1 if name=='NAV LEFT' else 1
            if 'NAV' in self.held_buttons:self.channel_page=max(0,min(3 if self.control_level==2 else 2,self.channel_page+delta));self.channel_field=0
            else:self.channel_field=max(0,min(len(self.channel_fields())-1,self.channel_field+delta))
            return True
        return False
    def routing_rotate(self,delta):
        if self.page=='INPUT':
            self.remember();r=self.plugin_target().setdefault('routing',route_defaults(self.plugin_target()))
            if self.input_field==0:
                choices=('NONE','EXT STEREO','EXT LEFT','EXT RIGHT')+ports(self.audio.input_channels if self.audio and self.audio.capture else 0,'IN');index=choices.index(r['input']) if r['input'] in choices else 0;r['input']=choices[max(0,min(len(choices)-1,index+delta))]
            else:r['input_gain']=max(0,min(200,r['input_gain']+delta))
            return True
        if self.page=='MACRO ASSIGN':self.macro_choice=max(0,min(max(0,len(self.macro_targets())-1),self.macro_choice+delta));return True
        if self.page=='MACRO':
            mapping=self.plugin_target().get('macros',{}).get(str(self.macro_index))
            if mapping:
                self.remember();mapping['value']=max(0,min(100,mapping['value']+delta));targets=bus_targets(self.project);target=targets[mapping['bus']]
                plugins=target.get('plugins',[])
                if mapping['slot']<len(plugins):
                    plugin=plugins[mapping['slot']];plugin['controls'][mapping['symbol']]=mapping['min']+(mapping['max']-mapping['min'])*mapping['value']/100
                    self.actions.append(('plugins',(mapping['bus'],copy.deepcopy(plugins))))
            return True
        if self.page not in ('PAD','CHANNEL'):return False
        target=self.plugin_target();key=self.channel_fields()[self.channel_field]
        old=copy.deepcopy(target);self.remember();r=target.setdefault('routing',route_defaults(target))
        from app.virtualjv_multi import internal_destination,rack,channel_choices
        internal=internal_destination(target)
        if key=='channel' and internal:
            bus,_=internal;plugin=rack(self.project['groups'][bus-GROUP_BASE]);values=plugin.get('controls',{})
            part=next((n for n in range(8) if round(values.get(f'p{n+1}_channel',10 if n==7 else n+1))==target.get('channel',1)),None)
            if part is None:self.message='NO PART ON CHANNEL';return True
            choices=channel_choices(plugin,part);index=choices.index(target['channel']);value=choices[max(0,min(len(choices)-1,index+delta))]
            target['channel']=value;values[f'p{part+1}_channel']=value;self.actions.append(('plugins',(bus,copy.deepcopy(self.project['groups'][bus-GROUP_BASE]['plugins']))))
        elif key in ('gain','note','channel'):target[key]=max(1 if key=='channel' else 0,min(16 if key=='channel' else 127 if key=='note' else 100,target.get(key,100 if key=='gain' else 36 if key=='note' else 1)+delta))
        elif key in ('aux1_pre','aux2_pre','midi_send'):r[key]=delta>0
        elif key=='midi_target':
            from app.virtualjv_multi import rack
            choices=('NONE',)+tuple(f'GROUP {i}' for i,g in enumerate(self.project['groups']) if rack(g))
            index=choices.index(r[key]) if r[key] in choices else 0;r[key]=choices[max(0,min(len(choices)-1,index+delta))]
            if r[key]!='NONE':
                owner=int(r[key].split()[1]);plugin=rack(self.project['groups'][owner]);values=plugin.get('controls',{})
                used={t.get('channel',1) for g in self.project['groups'] for t in g['pads'] if t is not target and t.get('routing',{}).get('midi_target')==r[key]}
                free=[round(values.get(f'p{n+1}_channel',10 if n==7 else n+1)) for n in range(8) if round(values.get(f'p{n+1}_channel',10 if n==7 else n+1)) not in used]
                if not free:target.clear();target.update(old);self.message='NO FREE RACK PART';return True
                if target.get('channel',1) not in free:target['channel']=free[0]
        elif key.endswith('dest'):
            choices=('NONE','PARENT','MASTER','CUE')+ports(self.audio.output_channels if self.audio else 0,'OUT')+tuple(f'GROUP {i}' for i in range(len(self.project['groups'])))+tuple(f'SOUND {i}' for i in range(len(self.project['groups'])*16))
            index=choices.index(r[key]) if r[key] in choices else 0;r[key]=choices[max(0,min(len(choices)-1,index+delta))]
        else:r[key]=max(-100 if key=='pan' else 0,min(100,r[key]+delta))
        try:build_graph(self.project)
        except ValueError as error:target.clear();target.update(old);self.message=str(error).upper() if key in ('midi_target','channel') else 'ROUTING CYCLE'
        return True

    def macro_targets(self):
        targets=bus_targets(self.project)
        buses=list(targets) if self.control_level==0 else list(range(self.group*16,self.group*16+16))+[GROUP_BASE+self.group] if self.control_level==1 else [self.group*16+self.pad]
        choices=[]
        for bus in buses:
            for slot,plugin in enumerate(targets[bus].get('plugins',[])):
                meta=self.plugin_metadata(plugin['uri'])
                if meta:
                    for port in meta['ports']:
                        if plugin['uri']=='urn:machinista:ports:virtualjv-multi' and (port['symbol']=='editor_part' or port['symbol'].endswith(('_mixer_gain','_mixer_pan','_mixer_mute'))):continue
                        choices.append(dict(bus=bus,slot=slot,symbol=port['symbol'],min=port['min'],max=port['max'],name=port['name']))
        return choices
