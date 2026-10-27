"""Headless LV2 slot browser and stable-symbol parameter persistence."""
from app.layout import SOUNDS,GROUP_BASE,MASTER,PREVIEW,CLICK,ZONE_BASE,bus_targets
import copy
import json
import subprocess
import shutil
import uuid
from pathlib import Path
from functools import lru_cache

@lru_cache(maxsize=4)
def scan_plugins(path,stamp):
    return json.loads(subprocess.check_output([path,"--plugins"],timeout=15,text=True))


class Plugins:
    def init_plugins(self):
        self.plugin_catalog=[];self.plugin_slot=0;self.plugin_param=0;self.plugin_filter='EFFECT';self.plugin_browser_index=0
        self.plugin_origin='PAD';self.plugin_clipboard=None;self.plugin_move_to=0
        executable=self.root/'build/audio_engine'
        if executable.exists():
            try:self.plugin_catalog=copy.deepcopy(scan_plugins(str(executable),executable.stat().st_mtime_ns))
            except (OSError,ValueError,subprocess.SubprocessError):self.message='PLUGIN SCAN FAILED'

    def sound_name(self,track=None,empty='EMPTY'):
        from app.sound_names import sound_name
        return sound_name(self,track,empty)

    def plugin_target(self):return self.project if self.control_level==0 else self.project['groups'][self.group] if self.control_level==1 else self.track()
    def plugin_bus(self):return MASTER if self.control_level==0 else GROUP_BASE+self.group if self.control_level==1 else self.group*16+self.pad
    def plugin_items(self):
        from app.virtualjv_multi import URI
        return [p for p in self.plugin_catalog if p['supported'] and p['kind']==self.plugin_filter and (p['kind']!='INSTRUMENT' or (self.control_level==1 and p['uri']==URI) or (self.control_level==2 and p['uri']!=URI))]
    def plugin_metadata(self,uri):return next((p for p in self.plugin_catalog if p['uri']==uri),None)
    def plugin_selected(self):
        slots=self.plugin_target().get('plugins',[])
        return slots[self.plugin_slot] if self.plugin_slot<len(slots) else None
    def plugin_controls(self):
        selected=self.plugin_selected();metadata=self.plugin_metadata(selected['uri']) if selected else None
        if not metadata:return []
        from app.plugin_profiles import controls
        return controls(self,selected,metadata['ports'])
    def plugin_update(self):self.actions.append(('plugins',(self.plugin_bus(),copy.deepcopy(self.plugin_target().get('plugins',[])))))

    def plugin_reindex(self,bus,mapping):
        for target in bus_targets(self.project).values():
            for key,macro in list(target.get('macros',{}).items()):
                if macro.get('bus')==bus:
                    slot=mapping.get(macro['slot'])
                    if slot is None:del target['macros'][key]
                    else:macro['slot']=slot
        for group in self.project['groups']:
            lanes={}
            for name,lane in group.get('automation',{}).items():
                pat,b,kind,slot,key=name.split(':',4)
                if kind=='plugin' and int(b)==bus:
                    new=mapping.get(int(slot))
                    if new is None:continue
                    name=':'.join((pat,b,kind,str(new),key))
                lanes[name]=lane
            group['automation']=lanes
        lanes={}
        for name,lane in self.project.get('master_automation',{}).items():
            pat,b,kind,slot,key=name.split(':',4)
            if kind=='plugin' and int(b)==bus:
                new=mapping.get(int(slot))
                if new is None:continue
                name=':'.join((pat,b,kind,str(new),key))
            lanes[name]=lane
        if 'master_automation' in self.project:self.project['master_automation']=lanes
        for name,item in list(self.project.get('midi_mappings',{}).items()):
            b,kind,slot,key=item['descriptor']
            if kind=='plugin' and b==bus:
                new=mapping.get(slot)
                if new is None:del self.project['midi_mappings'][name]
                else:item['descriptor'][2]=new
        self.midi_last_touched=None;self.midi_learning=None
        self.automation_cache=None

    def request_plugin_transfer(self,operation):
        if not self.plugin_selected():self.message='NO PLUGIN';return
        self.actions.append(('plugin_transfer',dict(operation=operation,bus=self.plugin_bus(),slot=self.plugin_slot,destination=self.plugin_move_to,
            generation=self.project_generation,revision=self.revision,chain=copy.deepcopy(self.plugin_target().get('plugins',[])))))
        self.message='SAVING PLUGIN STATE'

    def finish_plugin_transfer(self,request):
        if request['generation']!=self.project_generation or request['revision']!=self.revision:
            self.message='PLUGIN CHANGED: CANCELED';return
        if request['operation']=='COPY':
            self.plugin_clipboard=copy.deepcopy(request['chain'][request['slot']]);self.message='PLUGIN COPIED';return
        bus=request['bus'];target=bus_targets(self.project)[bus];chain=request['chain'];source=request['slot'];dest=request['destination']
        order=list(range(len(chain)));order.insert(dest,order.pop(source))
        if chain[source]['kind']=='INSTRUMENT' and dest!=0 or any(chain[i]['kind']=='INSTRUMENT' and n!=0 for n,i in enumerate(order)):
            self.message='INSTRUMENT MUST BE FIRST';return
        self.automation_restore();self.remember();target['plugins']=[chain[i] for i in order]
        self.plugin_reindex(bus,{old:new for new,old in enumerate(order)})
        self.plugin_slot=dest;self.plugin_param=0;self.page='PLUGIN';self.actions.append(('plugins',(bus,copy.deepcopy(target['plugins']))));self.message='PLUGIN MOVED'

    def paste_plugin(self):
        if not self.plugin_clipboard:self.message='COPY PLUGIN FIRST';return
        slots=self.plugin_target().get('plugins',[]);plugin=copy.deepcopy(self.plugin_clipboard);dest=min(self.plugin_slot,len(slots))
        if len(slots)>=16:self.message='MAX 16 PLUGINS';return
        if plugin['kind']=='INSTRUMENT' and (not (self.control_level==2 or self.control_level==1 and plugin['uri']=='urn:machinista:ports:virtualjv-multi') or dest!=0) or dest==0 and slots and slots[0]['kind']=='INSTRUMENT':
            self.message='INSTRUMENT MUST BE FIRST';return
        self.actions.append(('plugin_paste',dict(bus=self.plugin_bus(),slot=dest,plugin=plugin,generation=self.project_generation,revision=self.revision)))
        self.message='COPYING PLUGIN STATE'

    def finish_plugin_paste(self,request):
        if request['generation']!=self.project_generation or request['revision']!=self.revision:
            self.message='PLUGIN CHANGED: CANCELED';return
        bus=request['bus'];target=bus_targets(self.project)[bus];slots=target.setdefault('plugins',[]);dest=request['slot']
        self.automation_restore();self.remember();self.plugin_reindex(bus,{i:i+int(i>=dest) for i in range(len(slots))})
        slots.insert(dest,request['plugin']);self.plugin_slot=dest;self.plugin_param=0;self.page='PLUGIN'
        self.actions.append(('plugins',(bus,copy.deepcopy(slots))));self.message='PLUGIN PASTED'

    def plugins_button(self,name,pressed):
        if not pressed:return False
        if self.page=='PLUGIN SC':
            if name in ('F1','MAIN','ENTER','ENCODER PUSH'):self.page='PLUGIN'
            return True
        if self.page=='PLUGIN' and self.shift and name=='ENCODER PUSH' and self.virtualjv_reset(False):return True
        if self.page=='PLUGIN' and self.shift and name=='ENCODER PUSH':
            plugin=self.plugin_selected();meta=self.plugin_metadata(plugin['uri']) if plugin else None
            if meta and meta.get('sidechain'):self.page='PLUGIN SC'
            else:self.message='NO SIDECHAIN INPUT'
            return True
        if self.shift and name=='BROWSE':
            self.plugin_origin=self.page;self.plugin_browser_index=-1 if self.plugin_selected() else 0;self.plugin_filter='EFFECT';self.page='PLUGIN BROWSE';return True
        if self.page=='PLUGIN BROWSE':
            if name=='F1' and self.control_level in (1,2):self.plugin_filter='INSTRUMENT' if self.plugin_filter=='EFFECT' else 'EFFECT';self.plugin_browser_index=0
            elif name=='F3':self.page=self.plugin_origin
            elif name in ('F2','ENTER','ENCODER PUSH'):
                items=self.plugin_items()
                if self.plugin_browser_index==-1:
                    if self.plugin_selected():self.confirm('REMOVE PLUGIN?',self.remove_plugin,origin='PLUGIN')
                    else:self.message='NO PLUGIN'
                    return True
                if not items:self.message='NO COMPATIBLE PLUGINS';return True
                metadata=items[min(self.plugin_browser_index,len(items)-1)]
                self.remember();slots=self.plugin_target().setdefault('plugins',[])
                slot=0 if metadata['kind']=='INSTRUMENT' else self.plugin_slot
                if slot>=16:self.message='MAX 16 PLUGINS';return True
                plugin={'uri':metadata['uri'],'kind':metadata['kind'],'bypass':False,'controls':{p['symbol']:p['default'] for p in metadata['ports']}}
                if slot<len(slots):slots[slot]=plugin
                else:slots.append(plugin);slot=len(slots)-1
                if metadata['kind']=='INSTRUMENT' and self.control_level==2 and self.track().get('routing',{}).get('midi_target','NONE')!='NONE':self.track()['routing']['midi_target']='NONE'
                self.plugin_slot=slot;self.plugin_param=0;self.page='PLUGIN'
                if metadata['uri']=='urn:machinista:ports:virtualjv-multi':
                    from app.virtualjv_multi import link_empty_pads
                    linked=link_empty_pads(self);self.message=f'RACK: {linked} PADS LINKED'
                self.plugin_update()
            return True
        if self.page=='PLUGIN MOVE':
            if name=='F2':self.page='PLUGIN'
            elif name in ('F3','ENTER','ENCODER PUSH'):self.request_plugin_transfer('MOVE')
            return True
        if self.page not in ('PLUGIN','PLUGIN SLOTS'):return False
        if self.shift and name in ('F1','F2','F3'):
            if name=='F1':self.request_plugin_transfer('COPY')
            elif name=='F2':self.paste_plugin()
            elif self.plugin_selected():self.plugin_move_to=self.plugin_slot;self.page='PLUGIN MOVE'
            return True
        if name in ('NAV LEFT','NAV RIGHT'):
            if 'NAV' in self.held_buttons:self.plugin_slot=max(0,min(len(self.plugin_target().get('plugins',[])),self.plugin_slot+(-1 if name=='NAV LEFT' else 1)));self.plugin_param=0
            else:self.plugin_param=max(0,min(max(0,len(self.plugin_controls())-1),self.plugin_param+(-1 if name=='NAV LEFT' else 1)))
            return True
        if name=='F1':
            selected=self.plugin_selected()
            if selected:self.remember();selected['bypass']=not selected.get('bypass',False);self.plugin_update()
            return True
        if name=='F2':self.plugin_origin='PLUGIN';self.plugin_browser_index=0;self.page='PLUGIN BROWSE';return True
        if name=='F3':
            selected=self.plugin_selected()
            if selected:self.confirm('REMOVE PLUGIN?',self.remove_plugin,origin='PLUGIN')
            return True
        return False

    def virtualjv_reset(self,page=True):
        from app.virtualjv_controls import URI,SPEC_BY_SYMBOL
        selected=self.plugin_selected()
        if not selected or selected['uri'] not in (URI,'urn:machinista:ports:virtualjv-multi'):return False
        controls=self.plugin_controls();first=self.plugin_param//8*8 if page else self.plugin_param
        ports=controls[first:first+8 if page else first+1];edits=[p for p in ports if p['symbol'] in SPEC_BY_SYMBOL or 'reset_value' in p]
        if not edits:return False
        self.remember()
        for p in edits:selected['controls'][p['symbol']]=p['reset_value'] if 'reset_value' in p else SPEC_BY_SYMBOL[p['symbol']]['default']
        self.plugin_update();self.message='PAGE RESET' if page else 'PARAM RESET';return True

    def remove_plugin(self):
        if self.plugin_selected():
            self.automation_restore();self.remember();slots=self.plugin_target()['plugins'];old=self.plugin_slot
            if slots[old]['uri']=='urn:machinista:ports:virtualjv-multi':
                destination=f'GROUP {self.group}'
                for group in self.project['groups']:
                    for track in group['pads']:
                        if track.get('routing',{}).get('midi_target')==destination:track['routing']['midi_target']='NONE'
            self.plugin_reindex(self.plugin_bus(),{i:i-int(i>old) for i in range(len(slots)) if i!=old})
            slots.pop(old);self.plugin_slot=max(0,old-1);self.plugin_param=0;self.plugin_update()
            self.message='PLUGIN REMOVED'

    def plugins_rotate(self,delta):
        if self.page=='PLUGIN SC':
            from app.routing import build_graph
            selected=self.plugin_selected()
            choices=('NONE','EXT STEREO')+tuple(f'GROUP {i}' for i in range(len(self.project['groups'])))+tuple(f'SOUND {i}' for i in range(len(self.project['groups'])*16))
            current=selected.get('sidechain','NONE');index=choices.index(current) if current in choices else 0
            value=choices[max(0,min(len(choices)-1,index+delta))]
            if value!=current:
                self.remember();selected['sidechain']=value
                try:build_graph(self.project)
                except ValueError:selected['sidechain']=current;self.message='SIDECHAIN CYCLE';return True
                self.plugin_update()
            return True
        if self.page=='PLUGIN MOVE':self.plugin_move_to=max(0,min(len(self.plugin_target().get('plugins',[]))-1,self.plugin_move_to+delta));return True
        if self.page=='PLUGIN BROWSE':self.plugin_browser_index=max(-1,min(max(-1,len(self.plugin_items())-1),self.plugin_browser_index+delta));return True
        if self.page=='PLUGIN SLOTS':self.plugin_slot=max(0,min(len(self.plugin_target().get('plugins',[])),self.plugin_slot+delta));self.plugin_param=0;return True
        if self.page!='PLUGIN':return False
        controls=self.plugin_controls()
        if controls:
            port=controls[min(self.plugin_param,len(controls)-1)];selected=self.plugin_selected()
            if port.get('synth_inactive'):self.message='NOT USED BY THIS WAVE';return True
            from app.plugin_profiles import rotate
            if rotate(self,selected,port,delta):return True
            self.remember()
            old=selected['controls'].get(port['symbol'],port['default'])
            if port.get('preset_parameter') and old<=-999:old=port.get('preset_value',max(port['min'],min(port['max'],0)))
            from app.plugin_units import normalized,advance,advance_cents
            if port.get('choices'):
                choices=[v for v,_ in port['choices']]
                index=min(range(len(choices)),key=lambda i:abs(choices[i]-old))
                value=choices[max(0,min(len(choices)-1,index+delta))]
            elif port.get('toggle'):value=1 if delta>0 else 0
            elif port.get('unit')=='cents':value=advance_cents(port,old,delta,self.encoder_held)
            elif normalized(port):value=advance(port,old,delta,self.encoder_held)
            elif port.get('log') and port['min']>0:value=max(port['min'],old)*(port['max']/port['min'])**(delta/(1000 if self.encoder_held else 100))
            else:value=old+delta*(port.get('step',1) if port.get('integer') else (port['max']-port['min'])/(1000 if self.encoder_held else 100))
            selected['controls'][port['symbol']]=max(port['min'],min(port['max'],round(value) if port.get('integer') else value))
            from app.virtualjv_controls import URI,clamp_preset
            if selected['uri']==URI and port['symbol'] in ('bank','program','rhythm'):
                from app.virtualjv_controls import reset_edits
                reset_edits(selected)
                if port['symbol'] in ('bank','rhythm'):clamp_preset(self.root,selected)
            if selected['uri']=='urn:machinista:ports:virtualjv-multi':
                from app.virtualjv_multi import changed
                changed(self,selected,port,old)
            self.plugin_update()
        return True


def validate_plugins(target,instrument=False,group=False):
    slots=target.get('plugins',[])
    if not isinstance(slots,list) or len(slots)>16:raise ValueError('invalid plugin chain')
    import math
    for index,plugin in enumerate(slots):
        if not isinstance(plugin,dict) or not isinstance(plugin.get('uri'),str) or not plugin['uri'] or plugin.get('kind') not in ('EFFECT','INSTRUMENT') or (plugin['kind']=='INSTRUMENT' and (index!=0 or not (instrument and plugin['uri']!='urn:machinista:ports:virtualjv-multi' or group and plugin['uri']=='urn:machinista:ports:virtualjv-multi'))):raise ValueError('invalid plugin')
        if not isinstance(plugin.get('sidechain','NONE'),str):raise ValueError('invalid sidechain source')
        if type(plugin.get('bypass',False)) is not bool or not isinstance(plugin.get('controls',{}),dict):raise ValueError('invalid plugin state')
        if any(not isinstance(k,str) or not isinstance(v,(float,int)) or not math.isfinite(v) for k,v in plugin.get('controls',{}).items()):raise ValueError('invalid plugin control')
        if 'synth_waves' in plugin:
            import re
            waves=plugin['synth_waves']
            if plugin['uri']!='urn:machinista:instrument:synth' or not isinstance(waves,dict) or len(waves)>4:raise ValueError('invalid synth assets')
            for osc,row in waves.items():
                if osc not in ('1','2','3','4') or not isinstance(row,dict) or not isinstance(row.get('id'),str) or not re.fullmatch('[0-9a-f]{32}',row['id']) or not isinstance(row.get('name'),str) or len(row['name'])>160:raise ValueError('invalid synth asset')
                if 'frames' in row and (type(row['frames']) is not int or not 1<=row['frames']<=256):raise ValueError('invalid synth frame count')
        if 'profile_preset' in plugin:
            preset=plugin['profile_preset']
            if not isinstance(preset,dict) or not isinstance(preset.get('bank'),str) or len(preset['bank'])>128 or type(preset.get('program')) is not int or not 0<=preset['program']<(512 if plugin['uri']=='urn:machinista:instrument:synth' else 256) or not isinstance(preset.get('name'),str) or len(preset['name'])>128:raise ValueError('invalid plugin preset')


def copy_plugin_state(request,root):
    result=copy.deepcopy(request);plugin=result['plugin']
    if plugin.get('state'):
        source=Path(plugin['state'])
        if not source.is_file():raise ValueError('missing copied plugin state')
        directory=Path(root)/'projects'/'plugin-states'/uuid.uuid4().hex
        shutil.copytree(source.parent,directory);plugin['state']=str(directory/'state.ttl')
    return result
