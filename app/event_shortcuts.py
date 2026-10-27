"""NI 2.x SHIFT-pad event commands and explicit Sound reset."""
import copy
from app.navigation import CONTROL_PAGES

EVENT_PAGES=CONTROL_PAGES+('PAD CONFIG','KEYBOARD','CHORD','ARP','STEP','PATTERN','PATTERN GRID','GRID EDIT','EVENT','SELECT','MUTE','SOLO','NOTE REPEAT','SCENE','BROWSE','SAMPLING','SAMPLE EDIT','CHOP','ZONE')

class EventShortcuts:
    def init_event_shortcuts(self):self.event_clipboard=None
    def event_shortcut_targets(self):
        notes=self.event_notes()
        if self.grid_context!=(self.group,self.pattern):
            self.grid_selected.clear();self.grid_context=(self.group,self.pattern)
        self.grid_selected.intersection_update(notes)
        if self.grid_selected:return set(self.grid_selected)
        keyboard=self.keyboard_enabled or self.page in ('KEYBOARD','CHORD','ARP') or self.page in ('PATTERN GRID','GRID EDIT') and self.grid_notes
        return {key for key in notes if not keyboard or key[0]==self.pad}
    def focused_sound_events(self):
        """Sound-level Clear/Copy never inherit selections from other pads."""
        return {key for key in self.event_notes() if key[0]==self.pad}
    def select_sound_events(self,slot):
        notes=self.event_notes()
        if self.grid_context!=(self.group,self.pattern):self.grid_selected.clear();self.grid_context=(self.group,self.pattern)
        if self.keyboard_enabled:
            pitches=set(self.performance_notes(slot))
            keys={key for key,event in notes.items() if key[0]==self.pad and event.get('note',self.track().get('note',36+self.pad)) in pitches}
        else:keys={key for key in notes if key[0]==slot}
        if keys and keys<=self.grid_selected:self.grid_selected-=keys
        else:self.grid_selected|=keys
        self.message=f'{len(self.grid_selected)} NOTES SELECTED'
    def move_shortcut_events(self,delta=0,transpose=0):
        keys=self.event_shortcut_targets();notes=self.event_notes()
        if not keys:self.message='NO EVENTS';return
        if delta:
            delta=max(-min(key[1] for key in keys),min(self.pattern_ticks()-1-max(key[1] for key in keys),delta))
            destination={(key[0],key[1]+delta,*key[2:]) for key in keys}
            if any(k in notes and k not in keys for k in destination):self.message='TARGET OCCUPIED';return
            if not self.note_capacity(destination,keys):self.message='NOTE LIMIT';return
        else:destination=set(keys)
        if transpose:
            pitches=[notes[k].get('note',self.project['groups'][self.group]['pads'][k[0]].get('note',36+k[0])) for k in keys]
            transpose=max(-min(pitches),min(127-max(pitches),transpose))
        if not delta and not transpose:return
        payload=[]
        for identity in keys:
            r,t=identity[:2];event=copy.deepcopy(notes[identity])
            if transpose:event['note']=event.get('note',self.project['groups'][self.group]['pads'][r].get('note',36+r))+transpose
            payload.append(((r,t+delta,*identity[2:]),event))
        self.remember()
        for key in keys:self.remove_event(key)
        for key,event in payload:self.put_event(key,event)
        if self.grid_selected:self.grid_selected=destination
        self.message='NOTES TRANSPOSED' if transpose else 'NOTES NUDGED'
    def copy_shortcut_events(self,focused=False):
        keys=self.focused_sound_events() if focused else self.event_shortcut_targets();notes=self.event_notes()
        if not keys:self.event_clipboard=None;self.message='NO EVENTS';return
        self.event_clipboard={'scope':'SOUND' if focused else 'EVENTS','notes':[(key[0],key[1],copy.deepcopy(notes[key])) for key in sorted(keys)],'group':self.group,'pattern':self.pattern,'focus':self.pad,'position':self.event_paste_position()}
        self.message=f'{len(keys)} NOTES COPIED'
    def event_paste_position(self):
        return self.grid_step*self.grid_ticks() if self.page in ('PATTERN GRID','GRID EDIT') else max(0,self.clock_phase)
    def paste_shortcut_events(self):
        clip=self.event_clipboard
        if not clip:self.message='COPY FIRST';return
        position=self.event_paste_position();first=min(t for r,t,e in clip['notes'])
        changed_focus=(self.group,self.pad)!=(clip['group'],clip['focus'])
        changed_position=position!=clip['position']
        if clip.get('scope')=='SOUND':
            # Copy a pad's phrase at its original Pattern times, even while playing.
            offset=0;row_offset=self.pad-clip['focus']
        else:
            offset=position-first if changed_position else 0 if self.playing or changed_focus or self.pattern!=clip['pattern'] else self.grid_ticks()
            row_offset=self.pad-min(r for r,t,e in clip['notes']) if changed_focus else 0
        payload=[(r+row_offset,t+offset,copy.deepcopy(e)) for r,t,e in clip['notes']]
        if any(not 0<=r<16 or not 0<=t<self.pattern_ticks() for r,t,e in payload):self.message='PASTE OUT OF RANGE';return
        notes=self.event_notes()
        if any((r,t) in notes for r,t,e in payload if '_id' not in e):self.message='TARGET OCCUPIED';return
        from app.polyphony import note_id,event_key
        for r,t,event in payload:
            if '_id' in event or any(key[:2]==(r,t) for key in notes):event['_id']=note_id()
        if not self.note_capacity([event_key(r,t,e) for r,t,e in payload]):self.message='NOTE LIMIT';return
        self.remember()
        selected=set()
        for r,t,event in payload:
            key=event_key(r,t,event);self.put_event(key,event);selected.add(key)
        self.grid_selected=selected;self.grid_context=(self.group,self.pattern)
        self.message=f'{len(payload)} NOTES PASTED'
    def reset_sound_slot(self,slot):
        self.sync_selection()
        slots=sorted(self.selected_pads) if self.selection_level==2 and slot in self.selected_pads else [slot]
        focus=self.pad
        self.automation_restore();self.remember();self.selection_batch=True
        try:
            for selected in slots:self.reset_single_sound(selected)
        finally:self.selection_batch=False
        self.pad=focus if focus in slots else slot
        self.message=f"{len(slots)} SOUNDS RESET"

    def reset_single_sound(self,slot):
        from app.model import new_project
        channel=self.project['groups'][self.group]['pads'][slot].get('channel',1)
        self.automation_restore();self.remember();bus=self.group*16+slot
        self.plugin_reindex(bus,{})
        for group in self.project['groups']:
            group['automation']={k:v for k,v in group.get('automation',{}).items() if int(k.split(':')[1])!=bus}
        track=copy.deepcopy(new_project()['groups'][0]['pads'][slot]);track.update(source='SAMPLE',note=36+slot,channel=1)
        self.project['groups'][self.group]['pads'][slot]=track
        self.record_history.pop((self.group,slot),None);self.record_cursor.pop((self.group,slot),None)
        self.pad=slot;self.zone_index=self.slice_index=self.slice_bank=0;self.flash_until.pop(slot,None)
        self.actions.extend([('sound_reset',(self.group,slot,channel)),('load',(self.group,slot,copy.deepcopy(track))),('plugins',(bus,[]))]);self.message=f'SOUND {slot+1:02} RESET'
    def event_shortcut_pad(self,slot):
        if not self.shift or self.page not in EVENT_PAGES:return False
        if 'ERASE' in self.held_buttons:
            if 'GROUP' in self.held_buttons:self.message='RELEASE GROUP TO RESET SOUND'
            else:self.reset_sound_slot(slot)
            return True
        if 'SELECT' in self.held_buttons:
            self.select_sound_events(slot);return True
        if slot in (0,1,2,3):self.undo_action(redo=slot in (1,3),step=slot in (2,3))
        elif slot in (4,5):self.quantize_pattern(100 if slot==4 else 50,targets=self.event_shortcut_targets())
        elif slot in (6,7):
            from app.timing import RATES
            self.move_shortcut_events(delta=(-1 if slot==6 else 1)*dict(RATES)[self.timing()['nudge']])
        elif slot==8:
            keys=self.focused_sound_events()
            if keys:
                self.remember()
                for key in keys:self.remove_event(key)
                self.grid_selected.difference_update(keys);self.message=f'{len(keys)} NOTES CLEARED'
            else:self.message='NO EVENTS'
        elif slot==9:self.clear_automation()
        elif slot==10:self.copy_shortcut_events(focused=True)
        elif slot==11:self.paste_shortcut_events()
        else:self.move_shortcut_events(transpose={12:-1,13:1,14:-12,15:12}[slot])
        return True
