"""96-PPQ pattern positions, quantization, swing and transport count-in."""
import copy
import math
import random
import time
from app.polyphony import note_id,event_key

PPQ=96
BASE=24
RATES=(('1/1',384),('1/2',192),('1/4',96),('1/8',48),('1/16',24),('1/32',12),('1/64',6),
       ('1/4T',64),('1/8T',32),('1/16T',16),('1/32T',8))
DEFAULTS={'grid':'1/16','grid_on':True,'nudge':'1/16','swing':0,'strength':100,'target':'GROUP',
          'metro':False,'metro_level':35,'count_bars':1,'record_quantize':True}


def validate_timing(project):
    t=project.get('timing',{})
    if not isinstance(t,dict):raise ValueError('invalid timing settings')
    for key in ('grid','nudge'):
        if key in t and t[key] not in dict(RATES):raise ValueError('invalid grid')
    for key in ('grid_on','metro','record_quantize'):
        if key in t and type(t[key]) is not bool:raise ValueError('invalid timing switch')
    for key in ('swing','strength','metro_level'):
        if key in t and (type(t[key]) is not int or not 0<=t[key]<=100):raise ValueError('invalid timing amount')
    if t.get('count_bars',1) not in (1,2,4) or t.get('target','GROUP') not in ('GROUP','SOUND'):
        raise ValueError('invalid recording settings')
    for group in project['groups']:
        extra=group.get('extra_events',{})
        if not isinstance(extra,dict):raise ValueError('invalid extra events')
        for key,event in extra.items():
            try:pat,pad,tick=map(int,key.split(':'))
            except (ValueError,AttributeError):raise ValueError('invalid event position')
            if not (0<=pat<len(group['patterns']) and 0<=pad<16 and 0<=tick<len(group['patterns'][pat][pad])*BASE and tick%BASE):
                raise ValueError('invalid fine event position')
            if not isinstance(event,dict) or type(event.get('velocity')) is not int or not 1<=event['velocity']<=127 or type(event.get('probability')) is not int or not 0<=event['probability']<=100:
                raise ValueError('invalid fine event properties')
            if 'note' in event and (type(event['note']) is not int or not 0<=event['note']<=127):raise ValueError('invalid fine event note')


class Timing:
    def tap_tempo(self):
        now=getattr(self,'input_timestamp',None)
        if now is None:now=time.monotonic()
        if self.taps and (now<=self.taps[-1] or now-self.taps[-1]>2):self.taps=[]
        if self.taps and now-self.taps[-1]<.06:return
        self.taps=(self.taps+[now])[-5:]
        if len(self.taps)>1:
            tempo=round(60*(len(self.taps)-1)/(self.taps[-1]-self.taps[0]),2)
            self.remember()
            self.project['tempo']=max(40,min(240,tempo))
        self.message=f'TAP {self.project["tempo"]:.2f} BPM'

    def init_timing(self):
        self.project.setdefault('timing',{})
        for key,value in DEFAULTS.items():self.project['timing'].setdefault(key,value)
        for group in self.project['groups']:group.setdefault('extra_events',{})
        self.grid_tab=2;self.grid_field=0;self.record_field=0
        self.clock_phase=-1;self.count_remaining=0;self.count_phase=0
        self.clock_schedule_key=None;self.clock_schedule=[]
        self.clock_last=None
        self.recording_undo=None;self.record_live_skip=set()
        self.note_snapshot_cache={}
        self.poly_cache={}
        self.event_voice_counter=0

    def timing(self):return self.project['timing']
    def grid_ticks(self):return dict(RATES)[self.timing()['grid']] if self.timing()['grid_on'] else 1
    def pattern_ticks(self,group=None,pattern=None):
        group=self.group if group is None else group;pattern=self.pattern if pattern is None else pattern
        return self.pattern_steps(group,pattern)*BASE
    def step_cell_count(self):return math.ceil(self.pattern_ticks()/self.grid_ticks())
    def clock_interval(self):return 60/self.project['tempo']/PPQ
    def phase_cell(self):return max(0,self.clock_phase)%self.pattern_ticks()//self.grid_ticks()

    def pattern_position(self):
        tick=max(0,self.clock_phase)%self.pattern_ticks()
        return f'{tick//384+1}:{tick%384//96+1}:{tick%96//24+1}'

    def transport_title(self):
        if self.count_remaining:return 'COUNT IN'
        status='REPL' if self.playing and self.recording and self.replace_context is not None else 'REC' if self.playing and self.recording else 'ARM' if self.recording else 'PLAY' if self.playing else 'STOP'
        bar=max(0,self.clock_phase)%self.pattern_ticks()//384+1
        return f'{status} P{self.pattern+1:02} {bar}/{self.pattern_steps()/16:g} BAR'

    def notes(self,group=None,pattern=None):
        group=self.group if group is None else group;pattern=self.pattern if pattern is None else pattern
        data=self.project['groups'][group]
        cached=self.note_snapshot_cache.get((group,pattern))
        if cached is not None and cached[0]==self.revision:return dict(cached[1])
        result={}
        for pad,lane in enumerate(data['patterns'][pattern]):
            for step,on in enumerate(lane[:self.pattern_steps(group,pattern)]):
                if on:result[(pad,step*BASE)]=data['events'].get(f'{pattern}:{pad}:{step}',{'velocity':100,'probability':100})
        for key,event in data['extra_events'].items():
            pat,pad,tick=map(int,key.split(':'))
            if pat==pattern and tick<self.pattern_ticks(group,pattern):result[(pad,tick)]=event
        self.note_snapshot_cache[(group,pattern)]=(self.revision,result)
        return dict(result)

    def put_note(self,pad,tick,event,group=None,pattern=None):
        self.poly_cache.clear()
        self.erase_index.clear()
        group=self.group if group is None else group;pattern=self.pattern if pattern is None else pattern
        data=self.project['groups'][group]
        self.note_snapshot_cache.pop((group,pattern),None);self.clock_schedule_key=None
        if tick%BASE:
            data['extra_events'][f'{pattern}:{pad}:{tick}']=copy.deepcopy(event)
        else:
            data['patterns'][pattern][pad][tick//BASE]=True
            data['events'][f'{pattern}:{pad}:{tick//BASE}']=copy.deepcopy(event)

    def remove_note(self,pad,tick,group=None,pattern=None):
        self.poly_cache.clear()
        self.erase_index.clear()
        group=self.group if group is None else group;pattern=self.pattern if pattern is None else pattern
        data=self.project['groups'][group]
        self.note_snapshot_cache.pop((group,pattern),None);self.clock_schedule_key=None
        if tick%BASE:data['extra_events'].pop(f'{pattern}:{pad}:{tick}',None)
        else:
            data['patterns'][pattern][pad][tick//BASE]=False
            data['events'].pop(f'{pattern}:{pad}:{tick//BASE}',None)

    def notes_in_cell(self,pad,cell):
        start=cell*self.grid_ticks();end=min(self.pattern_ticks(),start+self.grid_ticks())
        return {(row,tick):event for (row,tick),event in self.notes().items() if row==pad and start<=tick<end}

    def quantize_pattern(self,strength=None,targets=None):
        if not self.timing()['grid_on']:
            self.message='STEP GRID OFF';return
        strength=self.timing()['strength'] if strength is None else strength
        all_notes=self.event_notes()
        if targets is not None:selected=set(targets)
        elif (self.page in ('PATTERN GRID','GRID EDIT') or (self.page=='OPTIONS' and self.mode_origins.get('GRID') in ('PATTERN GRID','GRID EDIT'))) and self.grid_selected:
            selected=self.grid_targets()
        else:selected={key for key in all_notes if self.timing()['target']=='GROUP' or key[0]==self.pad}
        if not selected:self.message='NO EVENTS';return
        unit=self.grid_ticks();length=self.pattern_ticks()
        moved={}
        for identity in sorted(selected):
            row,tick=identity[:2]
            snapped=((tick+unit//2)//unit)*unit
            target=(tick+round((snapped-tick)*strength/100))%length
            key=(row,target,*identity[2:])
            if key in moved or (key in all_notes and key not in selected):
                self.message='QUANTIZE COLLISION';return
            moved[key]=copy.deepcopy(all_notes[identity])
        if not self.note_capacity(moved,selected):self.message='NOTE LIMIT';return
        self.remember()
        for key in selected:self.remove_event(key)
        for key,event in moved.items():self.put_event(key,event)
        if self.grid_selected:self.grid_selected=set(moved)
        self.message=f'QUANTIZED {strength}%'

    def remember_recording_note(self):
        # One independent Undo snapshot for the take, not one per press/release.
        if not self.undo or self.undo[-1] is not self.recording_undo:
            self.remember();self.recording_undo=self.undo[-1]
        else:
            self.redo.clear();self.revision+=1;self.dirty=True

    def reset_recording_take(self):
        self.recording_undo=None;self.record_live_skip.clear();self.modulation_anchor=None;self.modulation_context=None

    def record_pad_note(self,pad,velocity,note=None,delay=0):
        stamp=getattr(self,'input_timestamp',None)
        stamp=time.monotonic() if stamp is None else stamp
        if self.count_remaining:
            # Input is drained before pending UI clock ticks. Judge the count-in
            # boundary by the hardware timestamp, not by that stale UI state.
            if self.clock_last is None or not self.count_phase:return
            boundary=self.clock_last+(self.count_remaining+1)*self.clock_interval()
            if stamp<boundary-1e-9:return
            position=round((stamp-boundary)/self.clock_interval())
        else:
            if not self.playing or not self.recording:return
            position=max(0,self.clock_phase)
            # Before tick zero, clock_last can still belong to a previous take.
            if self.clock_phase>=0 and self.clock_last is not None:
                position+=round((stamp-self.clock_last)/self.clock_interval())
        length=self.pattern_ticks();tick=max(0,position)%length
        if self.timing()['record_quantize'] and self.timing()['grid_on']:
            unit=self.grid_ticks();tick=(((tick+unit//2)//unit)*unit)%length
        tick=(tick+round(delay/self.clock_interval()))%length
        event={'velocity':velocity,'probability':100,'length':self.grid_ticks()}
        if note is not None:event['note']=note
        existing=self.event_notes();key=None
        if note is None:
            key=next((k for k,v in existing.items() if k[:2]==(pad,tick) and v.get('note',self.project['groups'][self.group]['pads'][pad].get('note',36+pad))==self.project['groups'][self.group]['pads'][pad].get('note',36+pad)),None)
        if key is None:
            if sum(k[:2]==(pad,tick) for k in existing)>=128:self.message='NOTE LIMIT';return
            event['_id']=note_id();key=event_key(pad,tick,event)
        elif len(key)>2:event['_id']=key[2]
        before=copy.deepcopy(existing.get(key))
        self.remember_recording_note()
        # Recording into an empty scene must create an audible clip, too.
        self.active_patterns[self.group]=self.pattern;self.active_clips[self.group]=True
        self.project['scenes'][self.scene][self.group]=self.pattern
        created=self.project['groups'][self.group]['pattern_created']
        if self.pattern not in created:created.append(self.pattern)
        self.put_event(key,event)
        reference=(self.group,self.pattern,*key)
        self.recording_change(reference,before,event)
        self.replace_written.add(key)
        skip=(self.group,self.pattern,pad,event.get('_id',tick))
        if self.clock_phase<0 or getattr(self,'native_sequence',False) and self.clock_phase==0 or tick>max(0,self.clock_phase)%length:self.record_live_skip.add(skip)
        else:self.record_live_skip.discard(skip)
        self.last_recorded=reference
        if getattr(self,'recorded_press',None) is not None:self.recorded_press.append(reference)

    def start_count_in(self):
        self.reset_recording_take()
        self.count_remaining=self.timing()['count_bars']*384;self.count_phase=0
        self.playing=self.recording=False;self.step=-1;self.clock_phase=-1
        self.actions.extend([('panic',None),('restart',None)])
        self.message='COUNT IN'

    def emit_note(self,group,pad,event):
        if getattr(self,'native_sequence',False):return
        if event.get('poly'):
            self.emit_note(group,pad,{k:v for k,v in event.items() if k!='poly'})
            for voice in event['poly'].values():self.emit_note(group,pad,voice)
            return
        data=self.project['groups'][group];track=data['pads'][pad]
        group_solo=any(g.get('solo',False) for g in self.project['groups'])
        if not self.active_clips[group]:return
        from app.audio_ports import cue_sound
        if not cue_sound(self.project,group,pad):
            if data.get('mute',False) or (group_solo and not data.get('solo',False)):return
            if track['mute'] or (any(t['solo'] for t in data['pads']) and not track['solo']):return
        if random.randrange(100)>=event['probability']:return
        pitches=event.get('chord') or [event.get('note',track.get('note',36+pad))]
        for note in pitches:
            self.event_voice_counter+=1;token=self.event_voice_counter
            self.actions.append(('voice_token',token))
            if 'note' in event or event.get('chord'):self.actions.append(('event_hit',(group,pad,event['velocity'],note)))
            else:self.actions.append(('hit',(group,pad,event['velocity'])))
            self.actions.append(('note_gate',(group,pad,note,event.get('length',self.grid_ticks()),token)))
        if group==self.group:self.flash_until[pad]=time.monotonic()+0.08

    def swing_position(self,tick,length):
        # Stretch the first eighth and compress the second without crossing a beat.
        beat,phase=divmod(tick,96);delay=24*self.timing()['swing']/100
        shifted=phase*(48+delay)/48 if phase<48 else 48+delay+(phase-48)*(48-delay)/48
        return min(length-1,beat*96+min(95,round(shifted)))

    def clock_tick(self,now=None,emit=True):
        self.clock_last=time.monotonic() if now is None else now
        if self.count_remaining:
            if emit and self.count_phase%96==0:
                self.actions.append(('click',(self.count_phase%384==0,self.timing()['metro_level'])))
                total=self.timing()['count_bars']*4
                self.message=f'COUNT {self.count_phase//96+1}/{total}'
            self.count_phase+=1;self.count_remaining-=1
            if not self.count_remaining:
                self.playing=self.recording=True;self.step=-1;self.clock_phase=-1;self.message='RECORDING'
                if getattr(self,'native_clock_enabled',False):self.native_sequence=self.settings['midi_sync']!='IN'
            return
        if not self.playing:return
        if self.pending_scene is not None and self.settings['perform_grid']!='SCENE':
            grid={'IMMEDIATE':1,'1 BAR':384,'1/2':192,'1/4':96,'1/8':48,'1/16':24}[self.settings['perform_grid']]
            if (self.clock_phase+1)%grid==0:
                self.activate_scene(self.pending_scene);self.pending_scene=None
                if self.settings['scene_retrigger']=='ON':
                    self.step=-1;self.clock_phase=-1;self.song_phase_origin=0;self.native_transport_revision=getattr(self,'native_transport_revision',0)+1
        self.clock_phase=self.clock_phase+1 if getattr(self,'native_sequence',False) else (self.clock_phase+1)%98304
        if self.clock_phase%BASE==0:
            self.tick(emit=False)
            if not self.playing:return
            self.clock_phase=self.step*BASE
        self.replace_tick()
        self.erase_tick()
        if emit:self.automation_tick()
        self.follow_step_view()
        self.follow_pattern_grid()
        if emit and not getattr(self,'native_sequence',False) and self.timing()['metro'] and self.clock_phase%96==0:
            self.actions.append(('click',(self.clock_phase%384==0,self.timing()['metro_level'])))
        key=(self.revision,tuple(self.active_patterns),self.timing()['swing'])
        if key!=self.clock_schedule_key:
            self.clock_schedule=[]
            for group,pat in enumerate(self.active_patterns):
                length=self.pattern_ticks(group,pat);schedule={}
                for identity,event in self.event_notes(group,pat).items():
                    pad,tick=identity[:2]
                    schedule.setdefault(self.groove_position(group,pad,tick,length),[]).append((pad,event))
                self.clock_schedule.append((length,schedule))
            self.clock_schedule_key=key
        for group,(length,schedule) in enumerate(self.clock_schedule):
            tick=self.clock_phase%length
            for pad,event in schedule.get(tick,[]):
                key=(group,self.active_patterns[group],pad,event.get('_id',tick))
                if key in self.record_live_skip:
                    # Native plan publication follows UI tick processing. Keep
                    # the initial skip until that plan can exclude tick zero.
                    if not getattr(self,'native_sequence',False) or self.clock_phase>0:self.record_live_skip.discard(key)
                elif emit:self.emit_note(group,pad,event)

    def timing_button(self,name,pressed):
        if not pressed:return False
        if self.shift and name=='PLAY':
            self.remember();self.timing()['metro']=not self.timing()['metro']
            self.message='METRONOME ON' if self.timing()['metro'] else 'METRONOME OFF';return True
        if self.shift and name=='REC':self.start_count_in();return True
        if self.shift and name=='GRID':self.page='RECORD SETTINGS';return True
        if self.count_remaining and name in ('PLAY','REC','RESTART'):
            self.count_remaining=0;self.playing=self.recording=False
            self.actions.append(('panic',None));self.message='COUNT CANCELLED';return True
        if self.page=='RECORD SETTINGS':
            if name=='F1':
                self.remember();self.timing()['metro']=not self.timing()['metro'];return True
            if name=='F2':self.start_count_in();return True
            if name in ('F3','ENTER'):self.page=self.control_home();return True
            if name in ('NAV LEFT','NAV RIGHT'):
                self.record_field=max(0,min(2,self.record_field+(-1 if name=='NAV LEFT' else 1)));return True
        if self.page=='OPTIONS':
            if name in ('F1','F2','F3'):
                self.grid_tab=int(name[1])-1;self.grid_field=0;return True
            if name in ('NAV LEFT','NAV RIGHT'):
                self.grid_field=max(0,min((2,0,3)[self.grid_tab],self.grid_field+(-1 if name=='NAV LEFT' else 1)));return True
            if name in ('ENTER','ENCODER PUSH') and self.grid_tab==0:self.quantize_pattern();return True
        return False

    def timing_rotate(self,delta):
        t=self.timing()
        if self.page=='OPTIONS':
            if self.grid_tab==1:
                self.remember();t['swing']=max(0,min(100,t['swing']+delta))
                if 'groove' in self.project:self.project['groove']['amount']=t['swing']
            elif self.grid_tab==0:
                if self.grid_field==0:
                    self.remember();t['strength']=max(0,min(100,t['strength']+delta))
                elif self.grid_field==1:
                    self.remember();t['target']='SOUND' if delta>0 else 'GROUP'
                else:return True
            else:
                if self.grid_field==3:
                    if delta:self.remember();t['record_quantize']=delta>0
                    return True
                old=self.grid_ticks();self.remember()
                if self.grid_field==1:t['grid_on']=delta>0
                else:
                    field='grid' if self.grid_field==0 else 'nudge'
                    index=next(i for i,(name,_) in enumerate(RATES) if name==t[field])
                    t[field]=RATES[max(0,min(len(RATES)-1,index+delta))][0]
                self.bank=min((self.step_cell_count()-1)//16,max(0,self.bank*16*old//self.grid_ticks()//16))
                self.grid_selected.clear()
            return True
        if self.page=='RECORD SETTINGS':
            self.remember()
            if self.record_field==0:t['metro_level']=max(0,min(100,t['metro_level']+delta))
            elif self.record_field==1:
                values=(1,2,4);t['count_bars']=values[max(0,min(2,values.index(t['count_bars'])+delta))]
            else:t['record_quantize']=delta>0
            return True
        return False
