"""Independent notes within one legacy Sound/time cell; stable editor identities."""
import copy
import re
import uuid

def note_id():return uuid.uuid4().hex

def clone_cell(event):
    event=copy.deepcopy(event)
    if '_id' in event:event['_id']=note_id()
    voices={}
    for voice in event.pop('poly',{}).values():
        voice['_id']=note_id();voices[voice['_id']]=voice
    if voices:event['poly']=voices
    return event

def cell_event(project,group,pattern,pad,tick):
    data=project['groups'][group]
    if tick%24:return data['extra_events'].get(f'{pattern}:{pad}:{tick}')
    if not data['patterns'][pattern][pad][tick//24]:return None
    return data['events'].get(f'{pattern}:{pad}:{tick//24}',{'velocity':100,'probability':100})

def event_key(pad,tick,event):return (pad,tick,event['_id']) if '_id' in event else (pad,tick)

def write_event(project,group,pattern,key,event):
    pad,tick=key[:2];cell=copy.deepcopy(cell_event(project,group,pattern,pad,tick))
    identity=key[2] if len(key)>2 else None
    primary=cell is None or identity is None or cell.get('_id')==identity
    extras=cell.pop('poly',{}) if cell else {}
    if primary:
        if event is None:
            if extras:
                first=next(iter(extras));cell=extras.pop(first)
            else:cell=None
        else:cell=copy.deepcopy(event)
    elif event is None:extras.pop(identity,None)
    else:extras[identity]=copy.deepcopy(event)
    if cell is not None:
        if extras:cell['poly']=extras
        else:cell.pop('poly',None)
    data=project['groups'][group]
    stored=f'{pattern}:{pad}:{tick if tick%24 else tick//24}'
    if tick%24:
        if cell is None:data['extra_events'].pop(stored,None)
        else:data['extra_events'][stored]=cell
    else:
        data['patterns'][pattern][pad][tick//24]=cell is not None
        if cell is None:data['events'].pop(stored,None)
        else:data['events'][stored]=cell

def migrate_events(project):
    for group in project['groups']:
        for field in ('events','extra_events'):
            for event in group.get(field,{}).values():
                chord=event.get('chord')
                if chord is not None and (not isinstance(chord,list) or not 1<=len(chord)<=128 or any(type(pitch) is not int or not 0<=pitch<=127 for pitch in chord)):
                    raise ValueError('invalid legacy chord')
                event.setdefault('_id',note_id())
                chord=event.pop('chord',None)
                if chord:
                    event['note']=chord[0];extras=event.setdefault('poly',{})
                    for pitch in chord[1:]:
                        voice=copy.deepcopy({k:v for k,v in event.items() if k not in ('poly','_id')})
                        voice.update(note=pitch,_id=note_id());extras[voice['_id']]=voice

def validate_poly(event):
    voices=event.get('poly',{})
    if not isinstance(voices,dict) or len(voices)>127:raise ValueError('invalid polyphonic notes')
    for voice in [event,*voices.values()]:
        if not isinstance(voice,dict):raise ValueError('invalid polyphonic note')
        if '_id' in voice and (not isinstance(voice['_id'],str) or not re.fullmatch('[a-f0-9]{32}',voice['_id'])):raise ValueError('invalid note identity')
        if type(voice.get('velocity')) is not int or not 1<=voice['velocity']<=127 or type(voice.get('probability')) is not int or not 0<=voice['probability']<=100:raise ValueError('invalid note properties')
        if 'note' in voice and (type(voice['note']) is not int or not 0<=voice['note']<=127):raise ValueError('invalid note pitch')
        if 'length' in voice and (type(voice['length']) is not int or not 1<=voice['length']<=98304):raise ValueError('invalid note length')
    for key,voice in voices.items():
        if voice.get('_id')!=key or key==event.get('_id') or 'poly' in voice or 'chord' in voice:raise ValueError('invalid polyphonic identity')

class Polyphony:
    def event_notes(self,group=None,pattern=None):
        group=self.group if group is None else group;pattern=self.pattern if pattern is None else pattern
        key=(group,pattern,self.revision)
        if key not in self.poly_cache:
            events={}
            for (pad,tick),cell in self.notes(group,pattern).items():
                primary={k:v for k,v in cell.items() if k!='poly'} if cell.get('poly') else cell
                events[event_key(pad,tick,primary)]=primary
                for voice in cell.get('poly',{}).values():events[event_key(pad,tick,voice)]=voice
            self.poly_cache[key]=events
            while len(self.poly_cache)>128:self.poly_cache.pop(next(iter(self.poly_cache)))
        return dict(self.poly_cache[key])
    def note_capacity(self,keys,removed=()):
        occupied=(set(self.event_notes())-set(removed))|set(keys);counts={}
        for key in occupied:
            position=key[:2];counts[position]=counts.get(position,0)+1
        return max(counts.values(),default=0)<=128
    def put_event(self,key,event,group=None,pattern=None):
        group=self.group if group is None else group;pattern=self.pattern if pattern is None else pattern
        write_event(self.project,group,pattern,key,event)
        self.poly_cache.clear();self.erase_index.clear();self.note_snapshot_cache.pop((group,pattern),None);self.clock_schedule_key=None
    def remove_event(self,key,group=None,pattern=None):self.put_event(key,None,group,pattern)
