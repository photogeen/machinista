"""Compact Group slots and all cross-bus references after NI Group deletion."""
import copy
from app.layout import GROUP_BASE,MASTER,bus_targets
from app.routing import route_defaults
from app.performance import PERFORMANCE_DEFAULTS

GROUP_SLOTS=(12,13,14,15,8,9,10,11)

def blank_group():
    from app.model import new_project
    group=copy.deepcopy(new_project()['groups'][0])
    group.update(events={},extra_events={},automation={},pattern_created=[],pattern_lengths={},performance=copy.deepcopy(PERFORMANCE_DEFAULTS))
    for pad,track in enumerate(group['pads']):track.update(source='SAMPLE',note=36+pad,channel=1)
    return group

def group_used(group):
    if group.get('name') or group.get('plugins') or group.get('macros') or group.get('automation') or group.get('gain',100)!=100 or group.get('mute') or group.get('solo'):return True
    if group.get('events') or group.get('extra_events') or any(p!=0 for p in group.get('pattern_created',[])):return True
    if route_defaults(group)!=route_defaults({}) or group.get('groove',{}).get('amount',0) or group.get('performance',{}) not in ({},PERFORMANCE_DEFAULTS,{**PERFORMANCE_DEFAULTS,'root':36}):return True
    if any(any(any(lane) for lane in pattern) for pattern in group['patterns']):return True
    return any(t.get('sample') or t.get('plugins') or t.get('name') or t.get('zones') or t.get('sampler') or t.get('source','SAMPLE')!='SAMPLE' or t.get('macros') or t.get('gain',80)!=80 or t.get('note',36+p)!=36+p or t.get('channel',1)!=1 or route_defaults(t)!=route_defaults({}) for p,t in enumerate(group['pads']))

def compact_group(project,index):
    result=copy.deepcopy(project);old_count=len(result['groups'])
    result['groups'].pop(index)
    for scene in result['scenes']:scene.pop(index)
    # Preserve empty buses which other Groups deliberately route into.
    referenced=set()
    for target in bus_targets(project).values():
        for value in [*target.get('routing',{}).values(),*(p.get('sidechain','NONE') for p in target.get('plugins',[]))]:
            if isinstance(value,str) and value.startswith(('GROUP ','SOUND ')):
                number=int(value.split()[1]);referenced.add(number if value.startswith('GROUP ') else number//16)
        for macro in target.get('macros',{}).values():
            value=macro['bus'];referenced.add(value-GROUP_BASE if GROUP_BASE<=value<MASTER else value//16 if value<GROUP_BASE else -1)
    for group in project['groups']:
        for name,lane in group.get('automation',{}).items():
            value=int(name.split(':')[1]);referenced.add(value-GROUP_BASE if GROUP_BASE<=value<MASTER else value//16 if value<GROUP_BASE else -1)
            for value in [lane.get('base'),*lane.get('points',{}).values()]:
                if isinstance(value,str) and value.startswith(('GROUP ','SOUND ')):
                    number=int(value.split()[1]);referenced.add(number if value.startswith('GROUP ') else number//16)
    for item in project.get('midi_mappings',{}).values():
        value=item['descriptor'][0];referenced.add(value-GROUP_BASE if GROUP_BASE<=value<MASTER else value//16 if value<GROUP_BASE else -1)
    sampling=project.get('sampling',{})
    if sampling.get('source')=='INTERNAL' and sampling.get('input','').startswith('GROUP '):referenced.add(int(sampling['input'].split()[1]))
    referred_new={old-(old>index) for old in referenced if old!=index}
    while len(result['groups'])>8 and not any(group_used(g) for g in result['groups'][-(len(result['groups'])%8 or 8):]):
        count=len(result['groups'])%8 or 8
        if len(result['groups'])-count<8:break
        first=len(result['groups'])-count
        if any(i>=first for i in referred_new) or any(any(clip is not None for clip in scene[first:]) for scene in result['scenes']):break
        del result['groups'][-count:]
        for scene in result['scenes']:del scene[-count:]
    while len(result['groups'])<8 or len(result['groups'])%8:
        result['groups'].append(blank_group())
        for scene in result['scenes']:scene.append(None)
    count=len(result['groups'])
    def group_index(old):
        new=old-(old>index)
        return None if old==index or old>=old_count or new>=count else new
    def bus(old):
        if old==MASTER:return MASTER
        if old>=GROUP_BASE:
            new=group_index(old-GROUP_BASE);return GROUP_BASE+new if new is not None else None
        new=group_index(old//16);return new*16+old%16 if new is not None else None
    def route(value):
        if value.startswith('GROUP '):
            new=group_index(int(value.split()[1]));return f'GROUP {new}' if new is not None else 'NONE'
        if value.startswith('SOUND '):
            new=bus(int(value.split()[1]));return f'SOUND {new}' if new is not None else 'NONE'
        return value
    for target in bus_targets(result).values():
        routing=target.get('routing',{})
        for key in ('dest','aux1_dest','aux2_dest','midi_target'):
            if key in routing:routing[key]=route(routing[key])
        for plugin in target.get('plugins',[]):
            if 'sidechain' in plugin:plugin['sidechain']=route(plugin['sidechain'])
        for key,macro in list(target.get('macros',{}).items()):
            new=bus(macro['bus'])
            if new is None:del target['macros'][key]
            else:macro['bus']=new
    for group in result['groups']:
        lanes={}
        for key,lane in group.get('automation',{}).items():
            pattern,old,kind,slot,field=key.split(':',4);new=bus(int(old))
            if new is None:continue
            if kind=='routing' and field in ('dest','aux1_dest','aux2_dest'):
                lane['base']=route(lane['base']);lane['points']={t:route(v) for t,v in lane['points'].items()}
            lanes[':'.join((pattern,str(new),kind,slot,field))]=lane
        if 'automation' in group:group['automation']=lanes
    for key,item in list(result.get('midi_mappings',{}).items()):
        new=bus(item['descriptor'][0])
        if new is None:del result['midi_mappings'][key]
        else:item['descriptor'][0]=new
    sampling=result.get('sampling',{})
    if sampling.get('source')=='INTERNAL' and sampling.get('input','').startswith('GROUP '):
        value=route(sampling['input']);sampling['input']='MASTER' if value=='NONE' else value
    return result,group_index

class GroupDelete:
    def undo_action(self,redo=False,step=False):
        source,destination=(self.redo,self.undo) if redo else (self.undo,self.redo)
        saved=source[-1] if source else None
        table=getattr(self,'group_delete_history',{})
        entry=table.get(id(saved));entry=entry if entry and entry[0] is saved else None
        current=copy.deepcopy((self.record_history,self.record_cursor,self.group)) if entry else None
        before=self.project;super().undo_action(redo=redo,step=step)
        if entry and self.project is not before:
            snapshot=destination[-1];table[id(snapshot)]=(snapshot,*current)
            self.record_history,self.record_cursor=copy.deepcopy(entry[1:3])
            self.group=min(entry[3],len(self.project['groups'])-1);self.group_bank=self.group//8;self.activate_scene(self.scene)
            self.note_snapshot_cache.clear();self.erase_index.clear();self.clock_schedule_key=None
            self.keyboard_root=self.performance()['root']
        keep={id(s) for s in self.undo+self.redo}
        self.group_delete_history={key:value for key,value in table.items() if key in keep}

    def group_delete_pad(self,slot):
        if not (self.shift and 'ERASE' in self.held_buttons and 'GROUP' in self.held_buttons):return False
        if slot not in GROUP_SLOTS:return True
        index=self.group_bank*8+GROUP_SLOTS.index(slot)
        if index>=len(self.project['groups']):return True
        if self.capture_started is not None or self.capture_armed:self.message='STOP RECORDING FIRST';return True
        self.sync_selection()
        indices=sorted(self.selected_groups) if self.selection_level==1 and index in self.selected_groups else [index]
        self.actions.append(('group_delete',dict(operation='DELETE_GROUP',index=index,indices=indices,generation=self.project_generation,revision=self.revision)))
        self.message='DELETING GROUP';return True
    def finish_group_delete(self,request):
        if request['generation']!=self.project_generation or request['revision']!=self.revision:
            self.message='GROUP CHANGED: CANCELED';return
        self.automation_restore()
        self.stop_live_chop();self.duplicate_source=None
        for bus,chain in request.get('chains',{}).items():bus_targets(self.project)[bus]['plugins']=copy.deepcopy(chain)
        result=self.project;remap={i:i for i in range(len(result['groups']))}
        for index in sorted(request.get('indices',[request['index']]),reverse=True):
            if index>=len(result['groups']):continue
            result,translate=compact_group(result,index)
            remap={old:translate(new) if new is not None else None for old,new in remap.items()}
        mapping=lambda old:remap.get(old)
        from app.model import validate_project
        validate_project(result);self.remember()
        if not hasattr(self,'group_delete_history'):self.group_delete_history={}
        keep={id(s) for s in self.undo+self.redo}
        self.group_delete_history={k:v for k,v in self.group_delete_history.items() if k in keep}
        snapshot=self.undo[-1];history,cursor=copy.deepcopy((self.record_history,self.record_cursor))
        self.group_delete_history[id(snapshot)]=(snapshot,history,cursor,self.group)
        old_group=self.group;self.project=result
        self.project_generation+=1;self.group=mapping(old_group)
        used=[i for i,g in enumerate(result['groups']) if group_used(g)]
        if self.group is None:self.group=next((i for i in used if i>=request['index']),used[-1] if used else 0)
        if not used:self.group=0
        self.group_bank=self.group//8;self.pad=min(self.pad,15);self.selected_pads={self.pad}
        self.activate_scene(self.scene);self.keyboard_root=self.performance()['root']
        self.note_snapshot_cache.clear();self.clock_schedule_key=None;self.erase_index.clear();self.erase_targets.clear()
        self.automation_cache=None;self.control_views.clear();self.grid_selected.clear();self.grid_context=(self.group,self.pattern)
        self.record_history={(mapping(g),pad):value for (g,pad),value in self.record_history.items() if mapping(g) is not None}
        self.record_cursor={(mapping(g),pad):value for (g,pad),value in self.record_cursor.items() if mapping(g) is not None}
        self.live_notes.clear();self.cancel_replace();self.reset_recording_take()
        self.repeat_pads.clear();self.arp_notes.clear();self.performance_lights.clear();self.flash_until.clear()
        self.bank=self.event_step=self.zone_index=self.slice_index=self.slice_bank=0
        self.actions.extend([('panic',None),('reload',None)]);self.message='GROUP DELETED'
        return True
