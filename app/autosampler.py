"""Autosampler plan and nonblocking capture state machine for the live engine."""
import array
import copy
import json
import math
import os
from pathlib import Path
import secrets
import shutil
import time
import wave
from app.sound_library import mapping,name,folders,tags,RESERVE
from app.sampler import default_zone


def number(value,lo,hi,integer=False):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not lo<=value<=hi or integer and type(value) is not int:raise ValueError('Invalid autosampler parameter.')
    return value


def configuration(value):
    if type(value.get('trim',True)) is not bool:raise ValueError('Invalid trim setting.')
    result=dict(value);name(value.get('name'));folders(value.get('folder',''));tags(value.get('tags',[]))
    lo=number(value.get('low',48),0,127,True);hi=number(value.get('high',84),lo,127,True);step=number(value.get('step',12),1,24,True)
    velocities=value.get('velocities',[100])
    if not isinstance(velocities,list) or not 1<=len(velocities)<=8:raise ValueError('Use 1–8 velocity layers.')
    velocities=sorted(set(number(v,1,127,True) for v in velocities))
    notes=list(range(lo,hi+1,step))
    if notes[-1]!=hi:notes.append(hi)
    if len(notes)*len(velocities)>128:raise ValueError('Maximum 128 recorded zones.')
    result.update(low=lo,high=hi,step=step,velocities=velocities,hold=number(value.get('hold',2),.05,30),tail=number(value.get('tail',1),0,10),gap=number(value.get('gap',.2),.05,5),channel=number(value.get('channel',1),1,16,True))
    if result.get('source') not in ('EXTERNAL','LV2'):raise ValueError('Choose External MIDI or the current LV2 Sound.')
    tasks=[]
    for note in notes:
        for i,velocity in enumerate(velocities):tasks.append(dict(root=note,velocity=velocity,vel_lo=1 if i==0 else (velocities[i-1]+velocity)//2+1,vel_hi=127 if i==len(velocities)-1 else (velocity+velocities[i+1])//2))
    return result,mapping(tasks)


def finish_bundle(library,config,tasks,paths):
    rows=[];clipped=0;silent=0
    for task,path in zip(tasks,paths):
        with wave.open(str(path),'rb') as wav:
            frames=wav.getnframes();width=wav.getsampwidth();channels=wav.getnchannels()
            if frames<1 or width!=2:raise ValueError('An autosampler recording is empty or invalid.')
            start=0;first=None;peak=0;offset=0
            while True:
                raw=wav.readframes(16384)
                if not raw:break
                values=array.array('h');values.frombytes(raw)
                if __import__('sys').byteorder!='little':values.byteswap()
                for i in range(0,len(values),channels):
                    level=max(abs(v) for v in values[i:i+channels]);peak=max(peak,level)
                    if first is None and level>=33:first=offset+i//channels
                offset+=len(values)//channels
            if peak>=32760:clipped+=1
            if first is None:silent+=1
            if config.get('trim',True) and first is not None:start=max(0,first-round(wav.getframerate()*.002))
        row=default_zone(dict(sample=str(path),start=start,end=frames,note=task['root']))
        row.update({key:task[key] for key in ('root','key_lo','key_hi','vel_lo','vel_hi')});row['asset']={'capture':str(path)};rows.append(row)
    if silent==len(tasks):raise ValueError('All recordings are silent. Check the audio input and MIDI routing.')
    draft=dict(name=config['name'],folder=config.get('folder',''),tags=config.get('tags',[]),zones=rows,sampler={'type':'ADSR','attack':0,'decay':250,'sustain':100,'release':150,'polyphony':16})
    def opened(ref):
        path=Path(ref['capture'])
        if path not in paths or path.is_symlink():raise ValueError('Invalid recording asset.')
        return path.open('rb')
    result=library.save(draft,opened);shutil.rmtree(paths[0].parent);return dict(sound=result,clipped=clipped,silent=silent)


class AutoSampler:
    def __init__(self,root,app,audio,midi,pool,library):
        self.root=Path(root);self.app=app;self.audio=audio;self.midi=midi;self.pool=pool;self.library=library
        self.active=False;self.state={'state':'IDLE'};self.future=None;self.own_fd=None;self.borrowed=False;self.index=0;self.paths=[];self.note_on=False
    def start(self,value,now):
        if self.active or self.future:raise ValueError('Autosampler is busy.')
        if self.app.playing or self.app.recording or self.audio.native_capture or self.audio.recorder or self.audio.capture_pending:raise ValueError('Stop playback and recording first.')
        if not self.app.audio:raise ValueError('No audio interface is active.')
        cfg,tasks=configuration(value);self.config=cfg;self.tasks=tasks
        if (cfg['hold']+cfg['tail'])*self.audio.sample_rate*8>64*1024**2:raise ValueError('Recording duration exceeds the zone limit.')
        self.group,self.pad=self.app.group,self.app.pad;self.generation=self.app.project_generation;self.revision=self.app.revision;self.device=self.app.audio.key
        self.track=copy.deepcopy(self.app.track());self.token=(1<<59)+int.from_bytes(os.urandom(6),'little')
        if cfg['source']=='LV2':
            if not self.track.get('plugins') or self.track['plugins'][0]['kind']!='INSTRUMENT':raise ValueError('Select a Sound with an LV2 instrument first.')
            self.source=self.group*16+self.pad
        else:
            if not self.app.audio.capture:raise ValueError('This interface has no audio input.')
            from app.audio import AudioBackend
            from app.audio_ports import port
            source=cfg.get('input','IN 1/2');parsed=port(source,'IN')
            if not parsed or max(parsed)>=self.app.audio.input_channels:raise ValueError('Audio input is not available.')
            self.source=AudioBackend.capture_source(dict(source='EXT MONO' if len(parsed)==1 else 'EXT STEREO',input=source))
            output=next((d for d in self.app.midi_devices if d.key==cfg.get('midi_out')),None)
            if output is None:raise ValueError('Select an available MIDI output.')
            if output.path in self.midi.ports:self.own_fd=self.midi.ports[output.path];self.borrowed=True
            else:self.own_fd=os.open(output.path,os.O_WRONLY|os.O_NONBLOCK|os.O_APPEND|os.O_NOCTTY);self.borrowed=False
        estimated=round(len(tasks)*(cfg['hold']+cfg['tail'])*self.audio.sample_rate*4)
        if estimated>512*1024**2:self.close_midi();raise ValueError('This session exceeds the 512 MiB Sound limit.')
        if shutil.disk_usage(self.root/'samples').free<estimated*2+RESERVE:self.close_midi();raise OSError('Not enough free storage for this session.')
        work=self.root/'samples/.autosampler';work.mkdir(exist_ok=True)
        if work.is_symlink():self.close_midi();raise ValueError('Invalid recording storage.')
        self.work=work/secrets.token_hex(16);self.work.mkdir();self.paths=[];self.index=0;self.active=True;self.app.autosampling=True;self.cancelled=False;self.note_on=False
        self.audio.native_capture=dict(source=self.source,autosampler=True)
        self.app.actions.append(('panic',None));self.stage='GAP';self.deadline=now+max(.25,cfg['gap']);self.next_status=0;self.peak=0
        self.state=dict(state='RECORDING',completed=0,total=len(tasks),note=tasks[0]['root'],velocity=tasks[0]['velocity'],peak=0,estimated_seconds=len(tasks)*(cfg['hold']+cfg['tail']+cfg['gap']))
    def send_note(self,on):
        task=self.tasks[self.index];note=task['root'];velocity=task['velocity'] if on else 0
        if self.config['source']=='LV2':
            if on:self.audio.hit(self.group,self.pad,velocity,dict(self.track,gain=100),note-self.track.get('note',36+self.pad),self.token)
            else:self.audio.note_off(self.group,self.pad,note,self.token)
        elif self.own_fd is not None:
            data=bytes([(0x90 if on else 0x80)|(self.config['channel']-1),note,velocity])
            if os.write(self.own_fd,data)!=3:raise OSError('MIDI note transmission failed.')
        self.note_on=on
    def close_midi(self):
        if self.own_fd is not None and not self.borrowed:
            try:os.close(self.own_fd)
            except OSError:pass
        self.own_fd=None;self.borrowed=False
    def cancel(self,reason='Cancelled'):
        if not self.active:return
        self.cancelled=True;self.failure=reason
        try:
            if self.note_on:self.send_note(False)
        except OSError:self.note_on=False
        finally:
            self.audio.command('record_stop');self.stage='CANCELLING';self.deadline=time.monotonic()+5
    def event(self,event,now):
        if not self.active or event.get('kind')!='native_record':return False
        self.peak=max(self.peak,event.get('peak',0));self.state['peak']=event.get('peak',0)
        if event['status']=='error':self.failure=event.get('detail','Recording failed.');self.cancelled=True;self.finish(False);return True
        if event['status']=='waiting' and self.stage=='ARMING':
            self.audio.command('record_trigger');self.send_note(True);self.stage='HELD';self.deadline=now+self.config['hold']
        elif event['status']=='finished':
            if self.stage=='GAP':return True
            if self.note_on:self.send_note(False)
            if self.cancelled:self.finish(False)
            elif self.stage not in ('HELD','TAIL'):self.failure='Recording ended unexpectedly.';self.finish(False)
            else:
                expected=round((self.config['hold']+self.config['tail'])*self.audio.sample_rate)
                if event.get('frames',expected)<max(1,expected-512):self.failure='Recording was interrupted.';self.finish(False);return True
                self.paths.append(self.path);self.index+=1;self.state['completed']=self.index
                if self.index==len(self.tasks):self.finish(True)
                else:self.stage='GAP';self.deadline=now+self.config['gap']
        return True
    def finish(self,success):
        self.active=False;self.app.autosampling=False;self.audio.native_capture=None;self.close_midi()
        if success:
            self.state['state']='SAVING';self.future=self.pool.submit(finish_bundle,self.library,self.config,self.tasks,list(self.paths))
        else:
            self.state.update(state='CANCELLED' if self.failure=='Cancelled' else 'ERROR',message=self.failure)
            # Private failed takes remain recoverable; never publish a partial Sound.
            self.state['recovery']=str(self.work)
    def tick(self,now):
        if self.future and self.future.done():
            try:
                result=self.future.result();self.state.update(state='DONE',sound=result['sound']['id'],message='Sound saved.',clipped=result['clipped'],silent=result['silent'])
                # Private takes were removed by the asset worker after publication.
            except Exception as e:self.state.update(state='ERROR',message=str(e),recovery=str(self.work))
            self.future=None
        if not self.active:return
        try:
            if self.stage!='CANCELLING' and (self.generation!=self.app.project_generation or self.revision!=self.app.revision or self.app.playing or self.app.recording or not self.app.audio or self.app.audio.key!=self.device):self.cancel('Project, source or audio device changed.')
            if self.stage!='GAP' and now>=self.next_status:self.audio.command('record_status');self.next_status=now+.05
            if self.stage=='GAP' and now>=self.deadline:
                task=self.tasks[self.index];self.state.update(note=task['root'],velocity=task['velocity']);self.path=self.work/f'Note{task["root"]:03}_Vel{task["velocity"]:03}.wav'
                frames=max(1,round((self.config['hold']+self.config['tail'])*self.audio.sample_rate))
                self.audio.command('record_start '+json.dumps(str(self.path))+f' {self.source} 0 1 -60 {frames} 0');self.stage='ARMING';self.deadline=now+5
            elif self.stage=='HELD' and now>=self.deadline:self.send_note(False);self.stage='TAIL';self.deadline=now+self.config['tail']+5
            elif self.stage in ('ARMING','TAIL','CANCELLING') and now>=self.deadline:
                self.failure='Recorder timeout.';self.audio.command('record_stop');self.finish(False)
        except (OSError,ValueError,KeyError) as e:
            try:self.cancel(str(e))
            except OSError:self.failure=str(e);self.finish(False)
