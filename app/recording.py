"""Mikro REC hold preparation and one-pass Replace recording."""
import copy
import time
from app.timing import RATES

class Recording:
    def init_recording(self):
        self.rec_hold=None;self.record_prepare=False;self.prepare_field=0
        self.replace_context=None;self.replace_old={};self.replace_written=set()

    def cancel_replace(self):
        self.replace_context=None;self.replace_old={};self.replace_written=set()

    def begin_replace(self):
        self.cancel_replace()
        pads={self.pad} if self.keyboard_enabled else self.selected_pads if len(self.selected_pads)>1 else {self.pad}
        self.replace_context=(self.group,self.pattern)
        self.replace_old={key:copy.deepcopy(event) for key,event in self.event_notes().items() if key[0] in pads}
        self.replace_phase=max(0,self.clock_phase)%self.pattern_ticks()

    def recording_button(self,name,pressed):
        if name=='REC' and not pressed:
            hold=self.rec_hold;self.rec_hold=None
            if self.record_prepare:
                self.record_prepare=False;self.page=hold['origin'];self.recording=True
                if hold['count']:self.start_count_in()
                if hold['replace']:self.begin_replace()
                self.message='REPLACE' if hold['replace'] else 'RECORD READY'
            return False
        if not pressed:return False
        if self.record_prepare:
            if name in ('NAV LEFT','NAV RIGHT'):
                self.prepare_field=0 if name=='NAV LEFT' else 1;return True
            if name in ('F1','F2','F3') and self.prepare_field==0:
                self.set_pattern_length((2,4,8)[int(name[1])-1]*16);return True
            if name in ('F1','F2','F3'):return True
            if name in ('MAIN','GROUP','PATTERN','PAD MODE','VIEW','BROWSE','SAMPLING','SCENE','NAV','GRID','NOTE REPEAT'):
                self.record_prepare=False;self.rec_hold=None;self.recording=True
        if name=='REC':
            self.erase_targets.clear()
            if self.count_remaining:
                self.count_remaining=0;self.playing=self.recording=False;self.cancel_replace();self.rec_hold=None
                self.actions.append(('panic',None));self.message='COUNT CANCELLED';return True
            enabled=not self.recording;replace='ERASE' in self.held_buttons
            self.reset_recording_take();self.cancel_replace()
            self.recording=enabled
            if enabled:
                self.rec_hold={'started':time.monotonic(),'origin':self.page,'count':self.shift,'replace':replace}
                if self.shift:self.start_count_in()
                if replace:self.begin_replace()
            else:self.rec_hold=None
            return True
        if name=='ERASE' and self.replace_context is not None:
            self.cancel_replace();self.message='OVERDUB';return True
        if self.page=='STEP' and name in ('MAIN','GROUP','PATTERN','PAD MODE','VIEW','BROWSE','SAMPLING','SCENE','NOTE REPEAT'):
            self.reset_recording_take()
        if self.replace_context is not None and name in ('PLAY','RESTART','TRANSPORT LEFT','TRANSPORT RIGHT','GROUP','MAIN','PATTERN','SCENE','PAD MODE','VIEW','BROWSE','SAMPLING','NAV','SELECT','MUTE','SOLO','GRID','NOTE REPEAT'):
            self.cancel_replace()
        return False

    def record_prepare_tick(self,now):
        if self.rec_hold and not self.record_prepare and 'REC' in self.held_buttons and now-self.rec_hold['started']>=1:
            self.record_prepare=True;self.prepare_field=0;self.page='RECORD PREPARE'
            self.recording=False;self.count_remaining=0;self.cancel_replace()
            self.message=''

    def recording_rotate(self,delta):
        if not self.record_prepare:return False
        if self.prepare_field==0:self.adjust_pattern_length(delta)
        else:
            names=[name for name,_ in RATES];t=self.timing();self.remember()
            t['grid']=names[max(0,min(len(names)-1,names.index(t['grid'])+delta))]
        return True

    def replace_tick(self):
        if self.replace_context is None:return
        if not self.recording or not self.playing or self.replace_context!=(self.group,self.pattern):self.cancel_replace();return
        tick=self.clock_phase%self.pattern_ticks()
        if tick<self.replace_phase:self.cancel_replace();return
        self.replace_phase=tick
        keys=[key for key in self.replace_old if key[1]==tick and key not in self.replace_written]
        for key in keys:
            before=self.event_notes().get(key)
            if before is None:continue
            self.remember_recording_note();self.remove_event(key)
            self.recording_change((self.group,self.pattern,*key),before,None)
        for key in keys:self.replace_old.pop(key,None)
