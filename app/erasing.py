"""Mikro event erasure: held pads, Select shortcut and stopped Locate."""
import copy
import time
from app.performance import PARAMETER_PLAY_PAGES

ERASE_PAGES=('PAD','PAD CONFIG','MIXER','KEYBOARD','CHORD','ARP','SELECT','NOTE REPEAT','PATTERN GRID','GRID EDIT','EVENT')+PARAMETER_PLAY_PAGES
GROUP_SLOTS=(12,13,14,15,8,9,10,11)

class Erasing:
    def init_erasing(self):self.erase_targets={};self.erase_index={}
    def erase_target(self,slot):
        if 'GROUP' in self.held_buttons:
            if slot not in GROUP_SLOTS:return None
            group=self.group_bank*8+GROUP_SLOTS.index(slot)
            return group,self.active_patterns[group],set(range(16)),None
        if self.page not in ERASE_PAGES:return None
        keyboard=self.keyboard_enabled or self.page in ('KEYBOARD','CHORD','ARP')
        return self.group,self.pattern,{self.pad if keyboard or self.velocities16 else slot},set(self.performance_notes(slot)) if keyboard else None
    def erase_events(self,target,positions=None):
        group,pattern,pads,pitches=target;changed=0
        schedule_valid=self.clock_schedule_key==(self.revision,tuple(self.active_patterns),self.timing()['swing'])
        schedule=self.clock_schedule[group][1] if schedule_valid else None
        index=None
        if positions is None:events=self.event_notes(group,pattern).items()
        else:
            key=(group,pattern,self.revision);index=self.erase_index.get(key)
            if index is None:
                index={};length=self.pattern_ticks(group,pattern)
                for identity,event in self.event_notes(group,pattern).items():
                    pad,tick=identity[:2]
                    index.setdefault(self.groove_position(group,pad,tick,length),[]).append((identity,event))
                self.erase_index[key]=index
                while len(self.erase_index)>8:self.erase_index.pop(next(iter(self.erase_index)))
            events=[item for position in positions for item in index.get(position,())]
        for identity,event in events:
            pad,tick=identity[:2]
            if pad not in pads:continue
            after=None
            if pitches is not None:
                notes=event.get('chord',[event.get('note',self.project['groups'][group]['pads'][pad].get('note',36+pad))])
                remaining=[n for n in notes if n not in pitches]
                if len(remaining)==len(notes):continue
                if remaining:
                    after=copy.deepcopy(event);after['note']=remaining[0]
                    if len(remaining)>1:after['chord']=remaining
                    else:after.pop('chord',None)
            self.remember_recording_note()
            self.put_event(identity,after,group,pattern)
            self.recording_change((group,pattern,*identity),event,after)
            due=self.groove_position(group,pad,tick,self.pattern_ticks(group,pattern))
            if index is not None:
                index[due]=[(key,value) for key,value in index.get(due,()) if key!=identity]
                if after is not None:index[due].append((identity,after))
                if not index[due]:index.pop(due)
            if schedule is not None and self.active_patterns[group]==pattern:
                schedule[due]=[(row,value) for row,value in schedule.get(due,()) if not (row==pad and value is event)]
                if after is not None:schedule[due].append((pad,after))
                if not schedule[due]:schedule.pop(due)
            self.record_live_skip.discard((group,pattern,pad,event.get('_id',tick)));changed+=1
        if changed and schedule_valid:
            self.clock_schedule_key=(self.revision,tuple(self.active_patterns),self.timing()['swing'])
        if changed and index is not None:self.erase_index[(group,pattern,self.revision)]=index
        if changed:self.message='ERASING'
        return changed
    def erase_pad(self,slot):
        if self.shift or 'ERASE' not in self.held_buttons:return False
        target=self.erase_target(slot)
        if target is None:return False
        if 'SELECT' in self.held_buttons or self.page=='SELECT':
            self.erase_events(target);self.message='EVENTS ERASED';return True
        self.erase_targets[slot]=target
        self.erase_tick()
        return True
    def erase_tick(self):
        if not self.playing or self.shift or 'ERASE' not in self.held_buttons:return
        for slot,target in list(self.erase_targets.items()):
            group,pattern,_,_=target
            if slot not in self.held_pads or self.active_patterns[group]!=pattern:
                self.erase_targets.pop(slot,None);continue
            self.erase_events(target,{self.clock_phase%self.pattern_ticks(group,pattern)})
    def erasing_button(self,name,pressed):
        if name=='ERASE':
            self.erase_targets.clear();self.reset_recording_take()
            if pressed and not self.shift:
                for slot in self.held_pads:
                    target=self.erase_target(slot)
                    if target is not None:self.erase_targets[slot]=target
                self.erase_tick()
        elif (name=='GROUP' and not pressed) or (pressed and name in ('SHIFT','REC','PLAY','RESTART','MAIN','PATTERN','SCENE','PAD MODE','VIEW','BROWSE','SAMPLING','NAV','SELECT','MUTE','SOLO','GRID','NOTE REPEAT')):
            self.erase_targets.clear()
        if pressed and not self.playing and not self.shift and 'ERASE' in self.held_buttons and name in ('TRANSPORT LEFT','TRANSPORT RIGHT'):
            self.erase_locate(name);self.transport_repeat[name]=time.monotonic()+.25;return True
        return False
    def erase_locate(self,name):
        direction=-1 if name=='TRANSPORT LEFT' else 1;length=self.pattern_ticks()
        start=max(0,self.clock_phase)%length;distance=self.grid_ticks()
        positions={(start+direction*i)%length for i in range(1,distance+1)}
        pads=set(self.selected_pads) if len(self.selected_pads)>1 else {self.pad}
        self.erase_events((self.group,self.pattern,pads,None),positions)
        self.clock_phase=(start+direction*distance)%length;self.step=self.clock_phase//24
        self.actions.append(('panic',None))
