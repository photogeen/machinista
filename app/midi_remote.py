"""Project-local MIDI CC learn for existing engine parameter identities."""
import copy
import math
import time
from app.layout import MASTER, GROUP_BASE, bus_targets
from app.sampler import SAMPLER_PAGES


def validate_midi_mappings(project):
    mappings=project.get('midi_mappings',{})
    if not isinstance(mappings,dict) or len(mappings)>1920:raise ValueError('invalid MIDI mappings')
    targets=bus_targets(project)
    for name,item in mappings.items():
        try:channel,cc=map(int,name.split(':'));bus,kind,slot,key=item['descriptor']
        except (ValueError,TypeError,KeyError):raise ValueError('invalid MIDI mapping')
        if not 0<=channel<16 or not 0<=cc<120 or cc==64 or bus not in targets or kind not in ('sampler','value','routing','plugin') or type(slot) is not int or not isinstance(key,str):raise ValueError('invalid MIDI mapping target')
        choices=item.get('choices')
        if choices is not None:
            if not isinstance(choices,list) or not 2<=len(choices)<=64 or any(not isinstance(v,(str,int,float,bool)) for v in choices):raise ValueError('invalid MIDI choices')
        elif any(type(item.get(k)) not in (int,float) or not math.isfinite(item[k]) for k in ('min','max')) or item['max']<=item['min']:raise ValueError('invalid MIDI range')
        if kind=='sampler':
            if bus>=GROUP_BASE or not any(key==f[0] for _,fields in SAMPLER_PAGES for f in fields):raise ValueError('invalid MIDI sampler')
        if kind=='value' and key not in ('gain','note','channel'):raise ValueError('invalid MIDI value')
        if kind=='routing' and key not in ('pan','aux1_level','aux2_level','input_gain'):raise ValueError('invalid MIDI route')
        if kind=='plugin' and (not 0<=slot<16 or not isinstance(item.get('uri'),str)):raise ValueError('invalid MIDI plugin')


class MidiRemote:
    def midi_parameter_spec(self,descriptor):
        bus,kind,slot,key=descriptor
        if bus not in bus_targets(self.project):return None
        result=dict(descriptor=list(descriptor),name=key.upper())
        if kind=='sampler':
            field=next((f for _,fields in SAMPLER_PAGES for f in fields if f[0]==key),None)
            if field is None:return None
            _,label,default,bounds=field;result['name']=label
            if type(default) in (str,bool) or key=='polyphony':result['choices']=list(bounds)
            else:result.update(min=bounds[0],max=bounds[1],integer=type(default) is int)
        elif kind=='plugin':
            chain=bus_targets(self.project)[bus].get('plugins',[])
            if not 0<=slot<len(chain):return None
            metadata=self.plugin_metadata(chain[slot]['uri'])
            field=next((f for f in metadata['ports'] if f['symbol']==key),None) if metadata else None
            if not field or field['max']<=field['min']:return None
            result.update(min=field['min'],max=field['max'],integer=field.get('integer',False),log=field.get('log',False),uri=chain[slot]['uri'])
            if field.get('toggle'):result['choices']=[field['min'],field['max']]
        else:
            bounds={'gain':(0,100),'note':(0,127),'channel':(1,16)} if kind=='value' else {'pan':(-100,100),'aux1_level':(0,100),'aux2_level':(0,100),'input_gain':(0,200)}
            if key not in bounds:return None
            result.update(min=bounds[key][0],max=bounds[key][1],integer=True)
        return result

    def midi_remote_button(self,name,pressed):
        if self.page=='SONG' and self.shift and name=='F3':
            if pressed:self.page='SONG AUTO';self.midi_map_index=0
            return True
        if self.page not in ('MIDI LEARN','SONG AUTO'):return False
        if not pressed:return name in ('F1','F2','F3','ENTER','ENCODER PUSH','MAIN','NAV LEFT','NAV RIGHT')
        if name in ('F1','MAIN','ENTER'):
            self.midi_learning=None
            if self.page=='SONG AUTO':self.page='SONG'
            else:self.open_settings('MIDI')
        elif name=='F2':
            if self.page=='SONG AUTO':
                row=self.remote_selected()
                if row:
                    self.automation_restore();self.remember();row[1]['enabled']=not row[1].get('enabled',True);self.automation_cache=None
            else:
                touched=self.midi_last_touched
                spec=self.midi_parameter_spec(touched[1]) if touched and touched[0]==self.project_generation else None
                if not spec:self.message='TOUCH A PARAMETER FIRST'
                else:self.midi_learning=(self.project_generation,spec);self.message='MOVE MIDI CC'
        elif name=='F3':
            row=self.remote_selected()
            if row:
                field='master_automation' if self.page=='SONG AUTO' else 'midi_mappings';key=row[0]
                def remove():
                    self.automation_restore();self.remember();self.project.get(field,{}).pop(key,None);self.automation_cache=None;self.message='REMOVED'
                self.confirm('REMOVE AUTOMATION?' if field=='master_automation' else 'REMOVE MIDI MAPPING?',remove)
        return True

    def remote_rows(self):
        return sorted(self.project.get('master_automation' if self.page=='SONG AUTO' else 'midi_mappings',{}).items())

    def remote_selected(self):
        rows=self.remote_rows();self.midi_map_index=max(0,min(self.midi_map_index,len(rows)-1))
        return rows[self.midi_map_index] if rows else None

    def midi_remote_rotate(self,delta):
        if self.page not in ('MIDI LEARN','SONG AUTO'):return False
        self.midi_map_index=max(0,min(max(0,len(self.remote_rows())-1),self.midi_map_index+delta));return True

    def midi_remote_display(self):
        if self.page not in ('MIDI LEARN','SONG AUTO'):return None
        row=self.remote_selected()
        if self.midi_learning and self.page=='MIDI LEARN':body=[self.midi_learning[1]['name'],'MOVE MIDI CC','F1 CANCEL']
        elif not row:body=['NO AUTOMATION' if self.page=='SONG AUTO' else 'NO MIDI MAPPINGS','SHIFT + ENCODER IN SONG' if self.page=='SONG AUTO' else 'TOUCH PARAM THEN F2','']
        elif self.page=='SONG AUTO':
            entry,bus,kind,slot,key=row[0].split(':',4);body=[f'POS {int(entry)+1} {key.upper()}',f'{len(row[1]["points"])} POINTS','ENABLED' if row[1].get('enabled',True) else 'DISABLED']
        else:
            channel,cc=map(int,row[0].split(':'));body=[f'CH {channel+1} CC {cc}',row[1]['name'],f'{self.midi_map_index+1}/{len(self.remote_rows())} MAPPINGS']
        return self.page,body,'ENC SELECT'

    def midi_remote_event(self,status,data):
        if status&0xf0!=0xb0 or len(data)!=2 or data[0]==64 or data[0]>=120:return False
        cc,value=data;identity=f'{status&15}:{cc}'
        if not 0<=value<=127:return False
        if self.midi_learning and self.page!='MIDI LEARN':self.midi_learning=None
        if self.midi_learning:
            generation,spec=self.midi_learning;self.midi_learning=None
            if generation!=self.project_generation:return False
            self.remember();self.project.setdefault('midi_mappings',{})[identity]=copy.deepcopy(spec);self.message='MIDI LEARNED';return True
        mapping=self.project.get('midi_mappings',{}).get(identity)
        if not mapping:return False
        descriptor=tuple(mapping['descriptor']);spec=self.midi_parameter_spec(descriptor)
        if not spec or mapping.get('uri')!=spec.get('uri'):self.message='MIDI TARGET MISSING';return True
        if 'choices' in spec:after=spec['choices'][min(len(spec['choices'])-1,value*len(spec['choices'])//128)]
        else:
            lo,hi=spec['min'],spec['max'];fraction=value/127
            after=lo*(hi/lo)**fraction if spec.get('log') and lo>0 else lo+(hi-lo)*fraction
            if spec.get('integer'):after=round(after)
        before=self.automation_value(descriptor)
        if before==after:return True
        now=time.monotonic();record=self.playing and self.recording and not self.count_remaining and (descriptor[0]!=MASTER or self.song_playing)
        if record:
            old_group,old_pattern,old_shift=self.group,self.pattern,self.shift
            bus=descriptor[0]
            if bus!=MASTER:self.group=bus-GROUP_BASE if bus>=GROUP_BASE else bus//16;self.pattern=self.active_patterns[self.group]
            self.shift=True
            try:
                self.remember_modulation();self.automation_set(descriptor,after);self.capture_automation(descriptor,before,after)
            finally:self.modulation_rotating=False;self.group,self.pattern,self.shift=old_group,old_pattern,old_shift
        else:
            gesture=(self.project_generation,identity)
            if not self.midi_gesture or self.midi_gesture[0]!=gesture or now-self.midi_gesture[1]>.4:self.remember()
            self.midi_gesture=(gesture,now)
            self.automation_set(descriptor,after)
            if descriptor in self.automation_bases:self.automation_bases[descriptor]=after
        self.midi_touch_until[descriptor]=now+.3
        if descriptor[1]=='sampler' or descriptor[1]=='value' and descriptor[3] in ('note','channel'):self.native_sequence_serial=getattr(self,'native_sequence_serial',0)+1
        self.dirty=True
        return True

    def song_automation_remap(self,index,delete=False):
        self.automation_restore();lanes={}
        for key,lane in self.project.get('master_automation',{}).items():
            entry,rest=key.split(':',1);entry=int(entry)
            if delete and entry==index:continue
            if entry>=index:entry+=-1 if delete else 1
            lanes[f'{entry}:{rest}']=lane
        self.project['master_automation']=lanes;self.automation_cache=None
