"""MIDI input owns each live attack until its matching release, across focus changes."""
import copy
from app.live_timing import LiveTiming
from collections import deque
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class LiveTarget:
    group: int
    slot: int
    note: int
    channel: int
    external: bool


@dataclass(frozen=True)
class LiveBinding:
    token: int
    targets: tuple
    recorded: tuple=()
    started: float=0
    generation: int=0


class MidiPerformance:
    MAX_HELD=2048

    def __init__(self,app,audio,midi):
        self.app,self.audio,self.midi=app,audio,midi
        self.timing=LiveTiming();self.bindings={};self.sustained={};self.sustain=set()
        # Separate from pad/gate tokens (small positive integers) and native
        # sequencer tokens (bit63). Never reuse tokens after panic/project load.
        self.serial=1<<61;self.held=0;self.generation=app.project_generation

    def tick(self,now):
        if getattr(self.app,'autosampling',False):self.panic();return
        if self.generation!=self.app.project_generation:
            self.panic();self.generation=self.app.project_generation
        self.timing.tick(now)

    def release_binding(self,binding):
        self.timing.cancel(binding.token)
        if binding.generation==self.app.project_generation:
            elapsed=(getattr(self.app,'input_timestamp',None) or time.monotonic())-binding.started
            for reference,delay in binding.recorded:self.app.finish_chord_recording(reference,elapsed,delay)
        for target in binding.targets:
            self.audio.note_off(target.group,target.slot,target.note,binding.token)
            if target.external:self.midi.note_off(target.note,target.channel,binding.token)
        self.held-=1

    def release(self,note,channel=0):
        key=(channel,note);queue=self.bindings.get(key)
        if not queue:return
        binding=queue.popleft()
        if not queue:self.bindings.pop(key,None)
        if channel in self.sustain:self.sustained.setdefault(key,[]).append(binding)
        else:self.release_binding(binding)

    def panic(self):
        for bindings in (self.bindings,self.sustained):
            for queue in bindings.values():
                for binding in queue:self.release_binding(binding)
            bindings.clear()
        self.sustain.clear();self.held=0;self.timing.clear()

    def control_targets(self,channel):
        # Snapshot routing at note-on. A later Link/Base Key/MIDI Channel change
        # must not redirect held notes or their control/release messages.
        app=self.app;track=app.track()
        targets={(app.group,app.pad,track['channel'],track.get('source')=='MIDI' or track.get('routing',{}).get('midi_send',False))}
        for bindings in (self.bindings,self.sustained):
            for (source,_),queue in bindings.items():
                if source==channel:
                    for binding in queue:
                        targets.update((t.group,t.slot,t.channel,t.external) for t in binding.targets)
        return targets

    def event(self,status,data):
        if getattr(self.app,'autosampling',False):return
        app,audio,midi=self.app,self.audio,self.midi;kind=status&0xf0;channel=status&15
        if self.generation!=app.project_generation:
            self.panic();self.generation=app.project_generation
        if app.midi_remote_event(status,data):return
        if kind==0x90 and data[1]>0:
            note,velocity=data
            keyboard=app.keyboard_enabled or app.track().get('routing',{}).get('midi_target','NONE')!='NONE' or bool(app.track().get('plugins') and app.track()['plugins'][0].get('kind')=='INSTRUMENT')
            slot=app.pad if keyboard else note-36
            if not 0<=slot<16:return
            if self.held>=self.MAX_HELD:
                self.panic();app.message='MIDI LIVE LIMIT';return
            group=app.group;track=app.project['groups'][group]['pads'][slot]
            self.serial+=1;token=self.serial;targets=[];recorded=[];started=getattr(app,'input_timestamp',None) or time.monotonic()
            learning=app.chord_learn_event(note,True,channel)
            custom=keyboard and app.performance()['chord_mode']=='CUSTOM' and not learning
            notes=app.custom_notes(input_note=note) if custom else [note]
            if custom and notes:
                index=next(i for i,row in enumerate(app.performance()['custom']['chords']) if row['input']==note)
                app.performance()['custom_bank']=index//16;app.chord_focus=index%16
            planned=app.chord_plan(notes,velocity) if custom else [(0,note,velocity)]
            for delay,pitch,level in planned:
                app.last_recorded=None;app.record_pad_note(slot,level,pitch,delay=delay)
                if custom and app.last_recorded:recorded.append((app.last_recorded,delay))
                for linked in app.linked_sounds(group,slot):
                    target=copy.deepcopy(app.project['groups'][group]['pads'][linked]);semitones=pitch-track.get('note',36+slot)
                    target_note=max(0,min(127,target.get('note',36+linked)+semitones))
                    external=target.get('source')=='MIDI' or target.get('routing',{}).get('midi_send',False)
                    targets.append(LiveTarget(group,linked,target_note,target['channel'],external))
                    def attack(target=target,linked=linked,target_note=target_note,external=external,level=level,token=token,group=group):
                        if target.get('source')!='MIDI' or target.get('sample') or target.get('plugins') or target.get('routing',{}).get('midi_target','NONE')!='NONE':audio.hit(group,linked,level,dict(target,gain=100),target_note-target.get('note',36+linked),token)
                        if external:midi.hit(linked,level,target_note,target['channel'],duration=None,voice_token=token)
                    if not self.timing.add(delay,token,attack):app.message='CHORD VOICE LIMIT'
            self.bindings.setdefault((channel,note),deque()).append(LiveBinding(token,tuple(targets),tuple(recorded),started,app.project_generation));self.held+=1
            return
        if kind==0x80 or kind==0x90 and data[1]==0:
            app.chord_learn_event(data[0],False,channel);self.release(data[0],channel);return
        targets=self.control_targets(channel)
        if kind==0xb0 and data[0]==64:
            was=channel in self.sustain
            if data[1]>=64:self.sustain.add(channel)
            else:self.sustain.discard(channel)
            if was and channel not in self.sustain:
                for key in list(self.sustained):
                    if key[0]==channel:
                        for binding in self.sustained.pop(key):self.release_binding(binding)
        if kind==0xb0 and data[0] in (120,123):self.panic();app.actions.append(('panic',None));return
        if kind in (0xb0,0xc0,0xd0,0xe0,0xa0):
            seen_audio=set();seen_external=set()
            for group,slot,output_channel,external in targets:
                bus=group*16+slot
                from app.virtualjv_multi import internal_destination
                internal=internal_destination(app.project['groups'][group]['pads'][slot])
                destinations=audio.internal_control_targets(group,slot,internal) if internal or isinstance(getattr(audio,'internal_note_bindings',None),dict) and audio.internal_note_bindings else [(bus,None)]
                for destination,target_channel in destinations:
                    key=(destination,target_channel)
                    if key in seen_audio:continue
                    seen_audio.add(key)
                    audio.command('plugin_midi '+str(destination)+' '+str(kind)+' '+' '.join(map(str,data))+(' 0' if len(data)==1 else '')+(' '+str(target_channel) if target_channel is not None else ''))
                if internal is None and (bus,'sampler') not in seen_audio:
                    seen_audio.add((bus,'sampler'))
                    if kind==0xe0:audio.command(f'bend {bus} {(((data[1]<<7)|data[0])-8192)/8192}')
                    if kind==0xb0 and data[0]==1:audio.command(f'wheel {bus} {data[1]/127}')
                if external and output_channel not in seen_external:
                    seen_external.add(output_channel);midi.send(bytes([kind|(output_channel-1),*data]))
            if kind==0xd0:
                for group,slot,_,_ in targets:
                    if group==app.group:app.repeat_velocities[slot]=max(1,data[0])
            elif kind==0xa0:
                for binding in self.bindings.get((channel,data[0]),()):
                    for target in binding.targets:
                        if target.group==app.group:app.repeat_velocities[target.slot]=max(1,data[1])
