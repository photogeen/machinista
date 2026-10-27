"""Scale-aware pad notes and configurable repeat/arpeggio generation."""
import copy
import math
import time
from app.chords import PLAY_DEFAULTS,DIRECTIONS,normalize,validate_play,plan

SCALES={
 'CHROMATIC':tuple(range(12)),'MAJOR':(0,2,4,5,7,9,11),'MINOR':(0,2,3,5,7,8,10),'HARMONIC MINOR':(0,2,3,5,7,8,11),
 'MAJOR PENTA':(0,2,4,7,9),'MINOR PENTA':(0,3,5,7,10),'BLUES':(0,3,5,6,7,10),'JAPANESE':(0,2,3,7,8),'FREYGISH':(0,1,4,5,7,8,10),
 'GYPSY':(0,2,3,6,7,8,11),'FLAMENCO':(0,1,4,5,7,8,11),'ALTERED':(0,1,3,4,6,8,10),'WHOLE TONE':(0,2,4,6,8,10),'HALF-WHOLE':(0,1,3,4,6,7,9,10),'WHOLE-HALF':(0,2,3,5,6,8,9,11)}
CHORDS={'OCTAVE':(0,12),'PERFECT 4':(0,5),'PERFECT 5':(0,7),'MAJOR':(0,4,7),'MINOR':(0,3,7),'SUS 4':(0,5,7),'MAJOR 7':(0,4,7,11),'MINOR 7':(0,3,7,10),'DOM 7':(0,4,7,10),'DOM 9':(0,4,7,10,14),'MIN 7B5':(0,3,6,10),'DIM 7':(0,3,6,9),'AUGMENTED':(0,4,8),'QUARTAL':(0,5,10,15),'TRICHORD':(0,5,11)}
DIATONIC={'OCTAVE':(0,7),'1-3':(0,2),'1-5':(0,4),'1-3-5':(0,2,4),'1-4-5':(0,3,4),'1-3-5-7':(0,2,4,6),'1-4-7':(0,3,6)}
PARAMETER_PLAY_PAGES=('SAMPLER','PLUGIN','CHANNEL','INPUT','GROOVE','MACRO','MIDI TRACK','TEMPO')
EDITOR_PLAY_PAGES=('PATTERN GRID','GRID EDIT','EVENT')
RATES=(1,2,4,8,16,32,64,128)
PERFORMANCE_DEFAULTS={'scale':'CHROMATIC','chord_mode':'OFF','chord_type':'MAJOR','root':60}
ARP_DEFAULTS={'rate':16,'division':'NORMAL','gate':100,'dynamic':100,'type':'UP','octaves':1,'sequence':0,'hold':False}


def scale_note(root,scale,index):
    octave,degree=divmod(index,len(scale));return root+octave*12+scale[degree]


class Performance:
    def init_performance(self):
        self.performance_field=0;
        self.step_input_notes={};self.chord_presets=();self.chord_focus=0;self.chord_stroke=0;self.chord_offsets={};self.chord_voice=0;self.chord_learning=None;self.chord_learn_notes=set();self.chord_learn_held=set()
        for group in self.project['groups']:
            settings=group.setdefault('performance',copy.deepcopy(PERFORMANCE_DEFAULTS))
            for key,value in PERFORMANCE_DEFAULTS.items():settings.setdefault(key,value)
        self.keyboard_root=0 if self.slice_keyboard() else self.performance()['root']
        self.arp_field=0;self.repeat_bank=0;self.arp_played=[];self.performance_lights=set();self.repeat_velocities={}
        self.project.setdefault('arp',copy.deepcopy(ARP_DEFAULTS));self.project.setdefault('repeat_presets',[8,16,32,64])
    def performance(self):return self.project['groups'][self.group].setdefault('performance',copy.deepcopy(PERFORMANCE_DEFAULTS))
    def slice_keyboard(self):
        track=self.track()
        return bool(track.get('slice_source') and track.get('slice_committed') and track.get('zones') and track.get('source','SAMPLE')=='SAMPLE')

    def keyboard_chord_mode(self):
        return 'OFF' if self.slice_keyboard() else self.performance()['chord_mode']
    def remember_step_input(self,group,pad,note):
        track=self.project['groups'][group]['pads'][pad]
        self.step_input_notes[group,pad]=(self.project_generation,track,track.get('sample'),track.get('note',36+pad),note)

    def step_input_note(self):
        track=self.track();saved=self.step_input_notes.get((self.group,self.pad))
        if saved and saved[0]==self.project_generation and saved[1] is track and saved[2]==track.get('sample') and saved[3]==track.get('note',36+self.pad):return saved[4]
        return None
    def keyboard_fields(self):
        if self.slice_keyboard():return ('root',)
        base=('root','scale','chord_mode','chord_type')
        return base+('custom_bank','strum','direction','human_time','velocity_spread','velocity_direction','human_velocity','edit_voice','edit_note','edit_input') if self.performance()['chord_mode']=='CUSTOM' else base
    def keyboard_value(self,key):
        p=self.performance()
        row=self.chord_row()
        if key=='edit_voice':return self.chord_voice+1
        if key=='edit_note':return row['notes'][min(self.chord_voice,len(row['notes'])-1)] if row else '-'
        if key=='edit_input':return row['input'] if row else '-'
        if key=='root':return self.keyboard_root
        if key=='chord_type' and p['chord_mode']=='CUSTOM':return p.get('custom',{}).get('name','IMPORT IN WEB UI')
        if key=='custom_bank':return p.get(key,0)+1
        if key in PLAY_DEFAULTS:return p.get('play',{}).get(key,PLAY_DEFAULTS[key])
        return p[key]
    def chord_row(self):
        p=self.performance();rows=p.get('custom',{}).get('chords',[]);index=p.get('custom_bank',0)*16+self.chord_focus
        return rows[index] if 0<=index<len(rows) else None
    def chord_edit(self,operation):
        row=self.chord_row()
        if not row:self.message='SELECT AN ASSIGNED CHORD PAD';return
        if operation=='LEARN':
            if self.chord_learning is not None:self.chord_learning=None;self.message='LEARN CANCELLED';return
            self.chord_learning=(self.project_generation,self.group,self.performance().get('custom'),row)
            self.chord_learn_notes=set();self.chord_learn_held=set();self.message='PLAY MIDI CHORD / RELEASE TO SAVE';return
        if operation in ('INVERT DOWN','INVERT UP'):
            if len(row['notes'])<2:self.message='CHORD NEEDS TWO NOTES';return
            from app.chords import invert_chord
            up=operation=='INVERT UP'
            try:inverted=invert_chord(row,up)
            except ValueError:self.message='MIDI NOTE LIMIT';return
            self.remember();row.clear();row.update(inverted);self.chord_voice=0
            self.message='INVERSION UP' if up else 'INVERSION DOWN'
            return
        self.remember()
        if operation=='ADD' and len(row['notes'])<32:
            note=next((n for n in range(60,128) if n not in row['notes']),next((n for n in range(60) if n not in row['notes']),0))
            row['notes'].append(note);self.chord_voice=len(row['notes'])-1
        elif operation=='REMOVE' and len(row['notes'])>1:row['notes'].pop(min(self.chord_voice,len(row['notes'])-1));self.chord_voice=max(0,self.chord_voice-1)
    def chord_learn_event(self,note,on,channel):
        context=self.chord_learning
        if context is None:return False
        generation,group,preset,row=context
        if generation!=self.project_generation or group!=self.group or preset is not self.performance().get('custom'):
            self.chord_learning=None;return False
        if on:
            self.chord_learn_held.add((channel,note));self.chord_learn_notes.add(note)
        else:
            self.chord_learn_held.discard((channel,note))
            if not self.chord_learn_held and self.chord_learn_notes:
                shift=self.keyboard_root-preset.get('root',60)
                notes=sorted(n-shift for n in self.chord_learn_notes if 0<=n-shift<=127)
                if notes:self.remember();row['notes']=notes[:32];self.chord_voice=0;self.message='CHORD LEARNED'
                self.chord_learning=None
        return True
    def select_chord_preset(self,delta):
        if not self.chord_presets:self.message='IMPORT CHORDS IN WEB UI';return
        p=self.performance();ids=[r['id'] for r in self.chord_presets];old=p.get('custom_id')
        index=max(0,min(len(ids)-1,(ids.index(old) if old in ids else (-1 if delta>0 else len(ids)))+delta))
        row=self.chord_presets[index];p['custom_id']=row['id'];p['custom']=copy.deepcopy(row['preset']);p['custom_bank']=0
        p['root']=self.keyboard_root=p['custom']['root'];self.chord_focus=0
    def custom_notes(self,input_note=None,slot=None):
        p=self.performance();preset=p.get('custom',{});rows=preset.get('chords',[])
        if slot is not None:
            index=p.get('custom_bank',0)*16+slot
            row=rows[index] if 0<=index<len(rows) else None
        else:row=next((r for r in rows if r['input']==input_note),None)
        shift=self.keyboard_root-preset.get('root',60)
        return [n+shift for n in row['notes'] if 0<=n+shift<=127] if row else []
    def finish_chord_recording(self,reference,elapsed,delay):
        group,pattern=reference[:2];key=reference[2:];event=self.event_notes(group,pattern).get(key)
        if not event:return
        before=copy.deepcopy(event);self.remember_recording_note()
        if elapsed<delay:
            self.remove_event(key,group,pattern);self.recording_change(reference,before,None,merge=True)
        else:
            event=copy.deepcopy(event);event['length']=max(1,min(self.pattern_ticks(group,pattern),round((elapsed-delay)/self.clock_interval())))
            self.put_event(key,event,group,pattern);self.recording_change(reference,before,event,merge=True)
    def chord_plan(self,notes,velocity):
        result=plan(notes,velocity,self.performance().get('play',{}),self.chord_stroke);self.chord_stroke+=1
        return result
    def chord_choices(self):
        if self.performance()['chord_mode']=='SET':return tuple(f'{mode} {i}' for mode in ('MAJOR','MINOR') for i in range(1,9))
        return tuple(CHORDS if self.performance()['scale']=='CHROMATIC' else DIATONIC)
    def performance_notes(self,slot):
        if self.slice_keyboard():
            note=self.keyboard_root+slot
            return [note] if 0<=note<=127 and any(z['key_lo']<=note<=z['key_hi'] for z in self.track()['zones']) else []
        p=self.performance();root=self.keyboard_root;scale=SCALES[p['scale']]
        mode=p['chord_mode'];kind=p['chord_type']
        if self.chord and self.page in ('CHORD','KEYBOARD'):
            mode='HARM';kind='MAJOR' if self.chord==1 else 'MINOR'
        if mode=='CUSTOM':return self.custom_notes(slot=slot)
        if mode=='SET':
            # Own diatonic chord voicings; NI's undocumented chord-set contents are not reproduced.
            if slot>=12:return []
            variants=((0,2,4),(0,2,4,6),(0,1,4),(0,3,4),(0,2,6),(0,2,4,8),(0,2,4,6,8),(0,4,7))
            variant=int(p['chord_type'].split()[-1])-1 if p['chord_type'].split()[-1].isdigit() else 0
            degrees=variants[variant];major=SCALES['MINOR'] if p['chord_type'].startswith('MINOR') else SCALES['MAJOR']
            result=[scale_note(root,major,slot+i) for i in degrees]
        elif mode=='HARM':
            if p['scale']=='CHROMATIC':result=[root+slot+i for i in CHORDS.get(kind,CHORDS['MAJOR'])]
            else:result=[scale_note(root,scale,slot+i) for i in DIATONIC.get(kind,DIATONIC['1-3-5'])]
        else:result=[scale_note(root,scale,slot)]
        return [note for note in result if 0<=note<=127]
    def performance_button(self,name,pressed):
        if not pressed:return False
        if self.page=='PAD CONFIG' and self.keyboard_enabled and self.keyboard_chord_mode()=='CUSTOM' and self.shift and name in ('F1','F2','F3'):
            self.chord_edit({'F1':'LEARN','F2':'INVERT DOWN','F3':'INVERT UP'}[name]);return True
        if self.page=='PAD CONFIG' and name in ('NAV LEFT','NAV RIGHT'):
            self.pad_field=max(0,min(len(self.keyboard_fields())-1 if self.keyboard_enabled else 5,self.pad_field+(-1 if name=='NAV LEFT' else 1)));return True
        if self.page in ('NOTE REPEAT','ARP'):
            if name=='F3' and self.shift:self.repeat_bank=1-self.repeat_bank;return True
            if name in ('F1','F2'):self.repeat_preset=int(name[1])-1;return True
            if name in ('NAV LEFT','NAV RIGHT'):self.arp_field=max(0,min(7,self.arp_field+(-1 if name=='NAV LEFT' else 1)));return True
        return False
    def performance_rotate(self,delta):
        if self.page=='PAD CONFIG':
            self.remember()
            if self.keyboard_enabled:
                p=self.performance();key=self.keyboard_fields()[min(self.pad_field,len(self.keyboard_fields())-1)]
                if key=='root':
                    self.keyboard_root=max(0,min(127,self.keyboard_root+delta))
                    if not self.slice_keyboard():p['root']=self.keyboard_root
                elif key=='chord_type' and p['chord_mode']=='CUSTOM':self.select_chord_preset(delta)
                elif key.startswith('edit_'):
                    row=self.chord_row()
                    if row:
                        if key=='edit_voice':self.chord_voice=max(0,min(len(row['notes'])-1,self.chord_voice+delta))
                        elif key=='edit_note':
                            index=min(self.chord_voice,len(row['notes'])-1);new=max(0,min(127,row['notes'][index]+delta))
                            if new not in row['notes'] or new==row['notes'][index]:row['notes'][index]=new
                        else:
                            value=max(0,min(127,row['input']+delta));rows=p['custom']['chords']
                            if not any(r is not row and r['input']==value for r in rows):row['input']=value
                elif key=='custom_bank':p[key]=max(0,min(max(0,(len(p.get('custom',{}).get('chords',[]))-1)//16),p.get(key,0)+delta))
                elif key in PLAY_DEFAULTS:
                    play=p.setdefault('play',dict(PLAY_DEFAULTS))
                    if key in ('direction','velocity_direction'):play[key]=DIRECTIONS[max(0,min(3,DIRECTIONS.index(play.get(key,'UP'))+delta))]
                    else:play[key]=max(0,min({'strum':500,'human_time':100,'velocity_spread':127,'human_velocity':64}[key],play.get(key,0)+delta))
                else:
                    choices=tuple(SCALES) if key=='scale' else ('OFF','HARM','SET','CUSTOM') if key=='chord_mode' else self.chord_choices()
                    old=p[key];p[key]=choices[max(0,min(len(choices)-1,(choices.index(old) if old in choices else 0)+delta))]
                    if key in ('chord_type','chord_mode'):self.chord=0
            else:
                key=('choke_group','choke_mode','link_group','link_mode','note','fix_velocity')[self.pad_field];t=self.track()
                if key.endswith('mode'):t[key]='SLAVE' if delta>0 else 'MASTER'
                elif key=='fix_velocity':self.fixed_velocity=delta>0
                else:t[key]=max(0,min(8 if key.endswith('group') else 127,t.get(key,0 if key.endswith('group') else 36)+delta))
                self.actions.append(('load',(self.group,self.pad,copy.deepcopy(t))))
            return True
        if self.page not in ('NOTE REPEAT','ARP'):return False
        self.remember();a=self.project['arp'];key=tuple(ARP_DEFAULTS)[self.arp_field]
        if key in ('rate','division','type'):
            if key=='rate':a[key]=self.project['repeat_presets'][self.repeat_bank*2+self.repeat_preset]
            choices=RATES if key=='rate' else ('NORMAL','TRIPLET','DOTTED') if key=='division' else ('UP','DOWN','UPDOWN','PLAYED','CHORD')
            a[key]=choices[max(0,min(len(choices)-1,choices.index(a[key])+delta))]
            if key=='rate':self.project['repeat_presets'][self.repeat_bank*2+self.repeat_preset]=a[key]
        else:
            lo,hi=(0,200) if key=='gate' else (1,200) if key=='dynamic' else (1,8) if key=='octaves' else (0,7) if key=='sequence' else (0,1)
            a[key]=bool(delta>0) if key=='hold' else max(lo,min(hi,a[key]+delta));self.arp_hold=a['hold']
        return True
    def performance_pad(self,slot,velocity):
        if self.shift or 'SELECT' in self.held_buttons:return False
        if self.velocities16 and self.page in ('PAD','PAD CONFIG','MIXER')+PARAMETER_PLAY_PAGES:
            velocity=round(127*(slot+1)/16)
            self.record_pad_note(self.pad,velocity)
            self.actions.append(('hit',(self.group,self.pad,velocity)))
            return True
        if not (self.keyboard_enabled and self.page in ('PAD','PAD CONFIG')+PARAMETER_PLAY_PAGES+EDITOR_PLAY_PAGES or self.page in ('KEYBOARD','CHORD','ARP')):return False
        if self.page=='PAD CONFIG' and self.velocities16:return False
        notes=self.performance_notes(slot)
        if notes:self.chord_focus=slot
        # Keyboard pads audition the current Sound, including while editing its
        # events. Never replace a marked event or the target being edited.
        if notes and self.page=='PATTERN GRID' and not self.grid_selected:
            self.grid_notes=True;self.grid_note=notes[0];self.grid_voice=None
        if self.page=='ARP' or self.repeat_locked:
            if notes:self.remember_step_input(self.group,self.pad,notes[0])
            for note in notes:
                self.arp_notes.add(note)
                if note not in self.arp_played:self.arp_played.append(note)
        else:
            if self.keyboard_chord_mode()=='CUSTOM':
                for delay,note,level in self.chord_plan(notes,velocity):
                    self.record_pad_note(self.pad,level,note,delay=delay)
                    if self.last_recorded:self.chord_offsets[self.last_recorded]=delay
                    self.actions.append(('chord_note',(note,level,self.track()['channel'],delay)))
            else:
                for note in notes:self.record_pad_note(self.pad,velocity,note);self.actions.append(('midi_note',(note,velocity,self.track()['channel'])))
            self.performance_lights.update(notes)
        return True
    def linked_sounds(self,group,pad):
        tracks=self.project['groups'][group]['pads'];source=tracks[pad];link=source.get('link_group',0)
        return [pad]+[i for i,t in enumerate(tracks) if i!=pad and link and t.get('link_group',0)==link] if source.get('link_mode','MASTER')=='MASTER' else [pad]
    def performance_repeat(self,now):
        a=self.project['arp'];presets=self.project['repeat_presets'];rate=presets[self.repeat_bank*2+self.repeat_preset]
        interval=60/self.project['tempo']*4/rate*(2/3 if a['division']=='TRIPLET' else 1.5 if a['division']=='DOTTED' else 1)
        if self.page=='CHOP':return
        arpeggiating=bool(self.arp_notes) and (self.page=='ARP' or self.keyboard_enabled and self.repeat_locked)
        repeating=bool(self.repeat_pads) and (self.page=='NOTE REPEAT' or self.repeat_locked)
        active=arpeggiating or repeating
        if self.playing:
            # Follow transport phase even with no pads held. A new contact
            # between boundaries waits for the next subdivision, never resets it.
            if self.clock_phase<0:return
            tick_seconds=self.clock_interval()
            fraction=max(0,min(1,(now-self.clock_last)/tick_seconds)) if self.clock_last is not None else 0
            phase=self.clock_phase+fraction
            spacing=interval/tick_seconds
            cell=math.floor((phase+1e-8)/spacing)
            key=(getattr(self,'native_transport_revision',0),rate,a['division'])
            previous=getattr(self,'repeat_grid_state',None)
            self.repeat_grid_state=(key,cell)
            if not active:return
            if previous==(key,cell):return
            # Discard missed subdivisions after a stall instead of playing a
            # late catch-up hit. First entry mid-cell also waits for the grid.
            if phase-cell*spacing>1:return
        else:
            self.repeat_grid_state=None
            if not active:self.repeat_next=now;return
            if now<getattr(self,'repeat_next',now):return
            self.repeat_next=now+interval
        # Eight own rhythmic masks; not a claim to reproduce NI's undocumented presets.
        masks=(0xffff,0x5555,0xaaaa,0x7777,0x9249,0x8421,0xf0f0,0x9696)
        step=self.arp_position;self.arp_position+=1
        if not (masks[a['sequence']]>>(step%16))&1:return
        length=max(1,round(interval/self.clock_interval()*a['gate']/100))
        if arpeggiating:
            notes=list(self.arp_played) if a['type']=='PLAYED' else sorted(self.arp_notes)
            notes=[n+12*o for o in range(a['octaves']) for n in notes if n+12*o<=127]
            if a['type']=='DOWN':notes.reverse()
            if a['type']=='UPDOWN' and len(notes)>1:notes+=notes[-2:0:-1]
            chosen=notes if a['type']=='CHORD' else [notes[step%len(notes)]] if notes else []
            for note in chosen:
                self.actions.extend([('midi_note',(note,self.velocity_value,self.track()['channel'])),('note_gate',(self.group,self.pad,note,length))]);self.record_pad_note(self.pad,self.velocity_value,note)
        if repeating:
            for slot in sorted(self.repeat_pads):
                velocity=max(1,min(127,round(self.repeat_velocities.get(slot,self.velocity_value)*a['dynamic']/100)))
                self.actions.extend([('hit',(self.group,slot,velocity)),('note_gate',(self.group,slot,self.project['groups'][self.group]['pads'][slot].get('note',36+slot),length))]);self.flash_until[slot]=now+.08;self.record_pad_note(slot,velocity)


def validate_performance(project):
    for group in project['groups']:
        p=group.get('performance',{})
        if not isinstance(p,dict) or p.get('scale','CHROMATIC') not in SCALES or p.get('chord_mode','OFF') not in ('OFF','HARM','SET','CUSTOM') or type(p.get('root',PERFORMANCE_DEFAULTS['root'])) is not int or not 0<=p.get('root',PERFORMANCE_DEFAULTS['root'])<=127:raise ValueError('invalid performance settings')
        if 'custom' in p:normalize(p['custom'])
        if type(p.get('custom_bank',0)) is not int or not 0<=p.get('custom_bank',0)<=7:raise ValueError('invalid chord bank')
        validate_play(p.get('play',{}))
        for track in group['pads']:
            for key in ('choke_group','link_group'):
                if type(track.get(key,0)) is not int or not 0<=track.get(key,0)<=8:raise ValueError('invalid pad group')
            for key in ('choke_mode','link_mode'):
                if track.get(key,'MASTER') not in ('MASTER','SLAVE'):raise ValueError('invalid pad link mode')
    a=dict(ARP_DEFAULTS,**project.get('arp',{}))
    if a['rate'] not in RATES or a['type'] not in ('UP','DOWN','UPDOWN','PLAYED','CHORD') or a['division'] not in ('NORMAL','TRIPLET','DOTTED'):raise ValueError('invalid arpeggiator')
    for key,lo,hi in (('gate',0,200),('dynamic',1,200),('octaves',1,8),('sequence',0,7)):
        if type(a[key]) is not int or not lo<=a[key]<=hi:raise ValueError('invalid arp '+key)
    if len(project.get('repeat_presets',[8,16,32,64]))!=4 or any(rate not in RATES for rate in project.get('repeat_presets',[])):raise ValueError('invalid repeat presets')
