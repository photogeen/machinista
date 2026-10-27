"""Scrollable group and pitch grids over the existing pattern/event model."""
import copy


class PatternEditor:
    def init_pattern_editor(self):
        self.grid_follow = True
        self.grid_voice = None
        self.grid_notes = False
        self.grid_step = 0
        self.grid_note = self.track().get('note', 36)
        self.grid_selected = set()
        self.grid_context = (self.group,self.pattern)
        self.grid_field = 0
        self.grid_range_anchor=None;self.grid_selection_range=None

    def grid_events(self):
        return self.project['groups'][self.group]['events']

    def grid_length(self):
        return self.step_cell_count()

    def grid_key(self, row, step):
        return f'{self.pattern}:{row}:{step}'

    def grid_cell_notes(self,row,cell,pitch=None):
        start=cell*self.grid_ticks();end=min(self.pattern_ticks(),start+self.grid_ticks())
        notes={key:event for key,event in self.event_notes().items() if key[0]==row and start<=key[1]<end}
        if pitch is not None:
            notes={key:event for key,event in notes.items() if event.get('note',self.project['groups'][self.group]['pads'][row].get('note',36+row))==pitch}
        return notes

    def grid_event(self, row, step):
        notes=self.grid_cell_notes(row,step)
        return notes[min(notes)] if notes else {'velocity':100,'probability':100}

    def grid_pitch(self, row, step):
        return self.grid_event(row, step).get('note', self.project['groups'][self.group]['pads'][row].get('note',36+row))

    def grid_present(self, row, step):return bool(self.grid_cell_notes(row,step))

    def grid_cursor_candidates(self):
        return set(self.grid_cell_notes(self.pad,self.grid_step,self.grid_note if self.grid_notes else None))

    def grid_cursor_targets(self):
        candidates=self.grid_cursor_candidates()
        return {self.grid_voice} if self.grid_voice in candidates else candidates

    def cycle_grid_voice(self,delta):
        self.pause_grid_follow();candidates=sorted(self.grid_cursor_candidates())
        if not candidates:return
        old=candidates.index(self.grid_voice) if self.grid_voice in candidates else (-1 if delta>0 else 0)
        self.grid_voice=candidates[(old+delta)%len(candidates)];self.grid_selected.clear()


    def grid_cursor_present(self):return bool(self.grid_cursor_targets())

    def grid_targets(self):
        if self.grid_context != (self.group,self.pattern):
            self.grid_selected.clear();self.grid_voice=None;self.grid_context=(self.group,self.pattern)
        all_notes=self.event_notes()
        self.grid_selected={key for key in self.grid_selected if key in all_notes}
        return self.grid_selected or self.grid_cursor_targets()

    def follow_pattern_grid(self):
        visible=self.page in ('PATTERN GRID','GRID EDIT') or self.page=='VIEW NAV' and self.view_target=='PAT'
        if not self.grid_follow or not visible or not self.playing:return
        if self.pattern!=self.active_patterns[self.group] or not self.active_clips[self.group]:return
        count=max(1,self.view_count)
        self.view_first=(self.phase_cell()//count)*count

    def follow_step_view(self,phase=None):
        if phase is None and not self.playing:return
        if self.page=='STEP' and self.follow and self.pattern==self.active_patterns[self.group] and self.active_clips[self.group]:
            phase=max(0,self.clock_phase if phase is None else phase)%self.pattern_ticks()
            self.bank=phase//self.grid_ticks()//16

    def step_playhead_x(self):
        if not self.playing or self.pattern!=self.active_patterns[self.group] or not self.active_clips[self.group]:return None
        phase=max(0,self.clock_phase)%self.pattern_ticks()
        offset=phase-self.bank*16*self.grid_ticks()
        return 2+int(offset*8/self.grid_ticks()) if 0<=offset<16*self.grid_ticks() else None

    def pattern_playhead_x(self):
        # STOP holds clock_phase; keep the transport position visible in Events.
        if self.pattern!=self.active_patterns[self.group] or not self.active_clips[self.group]:return None
        phase=max(0,self.clock_phase)%self.pattern_ticks()
        offset=phase-self.view_first*self.grid_ticks();span=self.view_count*self.grid_ticks()
        return 29+int(offset*96/span) if 0<=offset<span else None

    def toggle_grid_follow(self):
        self.grid_follow=not self.grid_follow
        self.follow_pattern_grid()

    def pause_grid_follow(self):
        if self.grid_follow:
            self.grid_step=max(self.view_first,min(self.grid_step,min(self.grid_length()-1,self.view_first+self.view_count-1)))
        self.grid_follow=False

    def ensure_grid_view(self):
        if self.grid_step<self.view_first:self.view_first=self.grid_step
        elif self.grid_step>=self.view_first+self.view_count:self.view_first=self.grid_step-self.view_count+1

    def open_pattern_grid(self):
        self.grid_step=min(self.event_step*24//self.grid_ticks(),self.grid_length()-1)
        self.grid_note=self.grid_pitch(self.pad,self.grid_step)
        if self.keyboard_enabled:
            self.grid_notes=True
            if not self.grid_present(self.pad,self.grid_step):
                note=self.step_input_note()
                notes=self.performance_notes(0)
                self.grid_note=note if note is not None else notes[0] if notes else self.keyboard_root
        self.grid_selected.clear();self.grid_voice=None
        self.grid_context=(self.group,self.pattern)
        self.mode_origins.pop('PATTERN',None)
        self.ensure_grid_view()
        self.page='PATTERN GRID'
        self.follow_pattern_grid()

    def edit_grid_event(self):
        targets=self.grid_targets()
        if targets and not (targets & self.grid_cursor_targets()):
            identity=sorted(targets)[0];self.pad,tick=identity[:2];self.grid_step=tick//self.grid_ticks()
            self.grid_note=self.event_notes()[identity].get('note',self.track().get('note',36+self.pad))
        if not targets:
            tick=self.grid_step*self.grid_ticks()
            from app.polyphony import note_id,event_key
            event={'velocity':self.velocity_value,'probability':100,'_id':note_id()}
            if self.grid_notes:event['note']=self.grid_note
            key=event_key(self.pad,tick,event)
            if not self.note_capacity([key]):self.message='NOTE LIMIT';return
            self.remember();self.put_event(key,event)
        self.grid_field=0;self.page='GRID EDIT'

    def delete_grid_events(self):
        targets=self.grid_targets()
        if not targets:return
        self.remember()
        for key in targets:self.remove_event(key)
        self.grid_selected.clear();self.page='PATTERN GRID'

    def change_grid_events(self, delta):
        targets=self.grid_targets()
        if not targets:return
        if delta:self.pause_grid_follow()
        all_notes=self.event_notes()
        if self.grid_field==0:
            from app.timing import RATES
            unit=dict(RATES)[self.timing()['nudge']] if self.shift else self.grid_ticks()
            delta*=unit
            delta=max(-min(key[1] for key in targets),min(self.pattern_ticks()-1-max(key[1] for key in targets),delta))
            if not delta:return
            destination={(key[0],key[1]+delta,*key[2:]) for key in targets}
            if any(key in all_notes and key not in targets for key in destination):
                self.message='TARGET OCCUPIED';return
            if not self.note_capacity(destination,targets):self.message='NOTE LIMIT';return
            payload={(key[0],key[1]+delta,*key[2:]):copy.deepcopy(all_notes[key]) for key in targets}
            self.remember()
            for key in targets:self.remove_event(key)
            for key,event in payload.items():self.put_event(key,event)
            self.grid_selected=destination
            identity=sorted(destination)[0];self.pad,tick=identity[:2];self.grid_step=tick//self.grid_ticks()
        else:
            field=('step','note','velocity','probability','length')[self.grid_field]
            self.remember()
            for identity in targets:
                row,tick=identity[:2];event=copy.deepcopy(all_notes[identity])
                old=event.get('note',self.project['groups'][self.group]['pads'][row].get('note',36+row)) if field=='note' else event.get(field,self.grid_ticks() if field=='length' else 100)
                event[field]=max(1 if field in ('velocity','length') else 0,min(self.pattern_ticks() if field=='length' else 100 if field=='probability' else 127,old+delta))
                self.put_event(identity,event)
            if self.grid_notes:
                identity=sorted(targets)[0];row,tick=identity[:2]
                self.grid_note=self.event_notes()[identity].get('note',self.track().get('note',36+self.pad))

    def grid_range_context(self):
        return (self.project_generation,self.group,self.pattern,self.grid_notes,self.pad)

    def begin_grid_range(self):
        self.pause_grid_follow()
        self.grid_range_anchor=(self.grid_range_context(),self.grid_step)
        unit=self.grid_ticks()
        self.grid_selection_range=(self.grid_step*unit,min(self.pattern_ticks(),(self.grid_step+1)*unit))

    def extend_grid_range(self,delta):
        if self.grid_range_anchor is None or self.grid_range_anchor[0]!=self.grid_range_context():self.begin_grid_range()
        anchor=self.grid_range_anchor[1]
        self.grid_step=max(0,min(self.grid_length()-1,self.grid_step+delta))
        unit=self.grid_ticks();start=min(anchor,self.grid_step)*unit;end=min(self.pattern_ticks(),(max(anchor,self.grid_step)+1)*unit)
        self.grid_selection_range=(start,end)
        self.grid_selected={key for key,event in self.event_notes().items()
            if key[0]==self.pad and key[1]<end and key[1]+max(1,event.get('length',unit))>start}
        self.grid_voice=None;self.ensure_grid_view()

    def pattern_editor_button(self,name,pressed):
        if name in ('SELECT','EVENT RANGE SELECT'):
            if not pressed and self.grid_range_anchor is not None:
                self.grid_range_anchor=None;self.grid_selection_range=None;return True
            if pressed and not self.shift and self.page in ('PATTERN GRID','GRID EDIT'):
                self.begin_grid_range();return True
        if not pressed:return False
        if self.page=='PATTERN' and name=='ENTER':
            self.open_pattern_grid();return True
        if self.page not in ('PATTERN GRID','GRID EDIT'):return False
        if self.shift and name=='F1':
            self.toggle_grid_follow();return True
        if self.shift and name=='ERASE':return True
        if name=='PATTERN':
            self.grid_selected.clear();self.page='PATTERN';return True
        if name in ('NAV LEFT','NAV RIGHT'):
            delta=-1 if name=='NAV LEFT' else 1
            if self.shift and self.page=='PATTERN GRID':
                self.cycle_grid_voice(delta);return True
            if self.page=='GRID EDIT':self.grid_field=max(0,min(4,self.grid_field+delta))
            else:
                self.pause_grid_follow();self.grid_step=max(0,min(self.grid_length()-1,self.grid_step+delta));self.ensure_grid_view()
            return True
        if self.page=='GRID EDIT':
            if name in ('F1','F3','ENTER','ENCODER PUSH'):
                self.page='PATTERN GRID';return True
            if name in ('F2','ERASE'):
                self.confirm('DELETE SELECTED?',self.delete_grid_events);return True
            return False
        if name=='F1':
            self.grid_notes=not self.grid_notes
            self.grid_note=self.grid_pitch(self.pad,self.grid_step)
            return True
        if name=='F2' and self.shift:
            self.pause_grid_follow();items={key for key in self.event_notes() if not self.grid_notes or key[0]==self.pad}
            self.grid_selected=set() if items<=self.grid_selected else items
            return True
        if name=='F2':
            self.pause_grid_follow()
            if self.grid_cursor_present():
                items=self.grid_cursor_targets()
                if items<=self.grid_selected:self.grid_selected-=items
                else:self.grid_selected|=items
            return True
        if name in ('F3','ENTER','ENCODER PUSH'):
            self.pause_grid_follow();self.edit_grid_event();return True
        if name=='ERASE':
            if self.grid_targets():self.confirm('DELETE SELECTED?',self.delete_grid_events)
            return True
        return False

    def pattern_editor_rotate(self,delta):
        if self.page in ('PATTERN GRID','GRID EDIT') and self.grid_range_anchor is not None and self.held_buttons.intersection(('SELECT','EVENT RANGE SELECT')):
            self.extend_grid_range(delta);return True
        if self.page=='GRID EDIT':self.change_grid_events(delta);return True
        if self.page!='PATTERN GRID':return False
        self.pause_grid_follow();self.grid_voice=None
        if self.shift:
            if self.grid_notes:self.grid_note=max(0,min(127,self.grid_note+delta))
            else:self.pad=max(0,min(15,self.pad+delta))
        else:self.grid_step=max(0,min(self.grid_length()-1,self.grid_step+delta));self.ensure_grid_view()
        return True

    def pattern_editor_pad(self,slot):
        if self.page not in ('PATTERN GRID','GRID EDIT'):return False
        if self.shift and slot in (4,5):
            self.quantize_pattern(100 if slot==4 else 50);return True
        if self.shift and slot in (0,1,2,3):
            self.undo_action(redo=slot in (1,3),step=slot in (2,3));return True
        if self.page=='GRID EDIT':self.page='PATTERN GRID'
        self.pad=slot
        if self.grid_notes:self.grid_note=self.grid_pitch(self.pad,self.grid_step)
        return True

    def pattern_editor_softkeys(self):
        if self.page=='PATTERN GRID':
            if self.shift:return ('FOLLOW','ALL','EDIT')
            return ('GROUP','MARK','EDIT') if not self.grid_notes else ('NOTES','MARK','EDIT')
        if self.page=='GRID EDIT':return ('FOLLOW' if self.shift else 'BACK','DELETE','DONE')
        return None
