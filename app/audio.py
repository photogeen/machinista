"""Control the native sampler and disk-based ALSA recording away from the UI."""
from app.note_tokens import NoteTokens
from app.layout import SOUNDS,GROUP_BASE,MASTER,PREVIEW,CLICK,ZONE_BASE,bus_targets
import array
import json
import os
import re
from pathlib import Path
import signal
import subprocess
import struct
import tempfile
import sys
import time
import wave
from app.sampler import DEFAULTS, zones
from app.audio_ports import port, cue_sound
from app.routing import build_graph, destination


def convert_sample(track, output):
    with wave.open(track['sample'], 'rb') as wav:
        channels, width, rate = wav.getnchannels(), wav.getsampwidth(), wav.getframerate()
        start, end = track['start'], min(track['end'], wav.getnframes())
        if start >= end or (end-start)*8 > 64*1024*1024:
            raise ValueError('empty sample or sample exceeds 64 MB decoded limit')
        if channels not in (1, 2) or width not in (1, 2, 3, 4):
            raise ValueError('unsupported WAV format')
        wav.setpos(start)
        raw = wav.readframes(end-start)
    if width in (1, 2, 4):
        values = array.array({1:'B',2:'h',4:'i'}[width]);values.frombytes(raw)
        if width > 1 and sys.byteorder != 'little':values.byteswap()
        numbers = ((v-128)/128 for v in values) if width == 1 else (v/(1 << (width*8-1)) for v in values)
    else:
        numbers = (int.from_bytes(raw[i:i+3],'little',signed=True)/(1 << 23) for i in range(0,len(raw),3))
    floats = array.array('f', numbers) if channels == 2 else array.array('f', (v for number in numbers for v in (number,number)))
    if sys.byteorder != 'little':
        floats.byteswap()
    Path(output).write_bytes(floats.tobytes())
    return rate


def repair_recording_header(path):
    """Finalize oversized arecord RIFF/data lengths using actual PCM bytes on disk."""
    path=Path(path);size=path.stat().st_size
    with path.open('r+b') as stream:
        if stream.read(4)!=b'RIFF':return False
        stream.seek(8)
        if stream.read(4)!=b'WAVE':return False
        offset=12;alignment=1
        while offset+8<=size:
            stream.seek(offset);kind,length=struct.unpack('<4sI',stream.read(8))
            if kind==b'fmt ':
                data=stream.read(min(length,16))
                if len(data)>=14:alignment=struct.unpack_from('<H',data,12)[0] or 1
            if kind==b'data':
                actual=min(length,size-offset-8);actual-=actual%alignment
                if length==actual:return False
                stream.seek(offset+4);stream.write(struct.pack('<I',actual))
                stream.seek(4);stream.write(struct.pack('<I',size-8))
                stream.flush();os.fsync(stream.fileno());return True
            offset+=8+length+(length%2)
    return False


def reserve_recording_path(folder):
    """Reserve the next readable recording name without overwriting a file."""
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    numbers=[int(match.group(1)) for path in folder.glob('Sample*.wav')
             if (match:=re.fullmatch(r'Sample([0-9]+)\.wav',path.name))]
    number=max(numbers,default=0)+1
    while True:
        path=folder/f'Sample{number:02}.wav'
        try:fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        except FileExistsError:number+=1;continue
        os.close(fd);return path


class AudioBackend:
    def __init__(self, root, on_message, sample_rate=48000, buffer_frames=0):
        self.root = Path(root)
        self.cache = self.root/'cache'
        self.cache.mkdir(exist_ok=True)
        self.on_message = on_message
        self.engine = subprocess.Popen([str(self.root/'build/audio_engine')],
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        self.recorder = None
        self.native_capture=None;self.native_cancel=False;self.capture_peak=0
        self.capture_pending=None
        self.record_path = None
        self.record_target = None
        self.desired = None
        self.sample_rate = sample_rate
        self.buffer_frames = buffer_frames
        self.loaded = {};self.wave_preview=None
        self.instrument_tokens=NoteTokens()
        self.tempo=120
        self.plugin_chains={}
        self.routing_signature=None
        self.input_device=None;self.sampling_input=False;self.monitor_source=0;self.meter_source=-99
        self.plugin_metadata=json.loads(subprocess.check_output([str(self.root/'build/audio_engine'),'--plugins'],text=True,timeout=15))
        self.record_errors = None

    def command(self, text):
        if text=='panic':self.instrument_tokens.clear()
        if self.engine.poll() is not None:
            raise OSError('audio engine exited')
        self.engine.stdin.write(text+'\n')
        self.engine.stdin.flush()

    def device(self, device, sample_rate=None, buffer_frames=None):
        self.stop_capture()
        self.desired = device
        if sample_rate is not None and sample_rate!=self.sample_rate:
            self.sample_rate=sample_rate
            self.plugin_chains.clear()
        if buffer_frames is not None:self.buffer_frames=buffer_frames
        self.command('device '+json.dumps(device.playback if device else '-', ensure_ascii=False)+f' {self.sample_rate} {getattr(self, "buffer_frames", 0)} {device.output_channels if device else 2} {device.input_channels if device and device.capture else 2}')

    def _load_asset(self,slot,track):
        try:self._load_available_asset(slot,track)
        except (OSError,ValueError,wave.Error,EOFError):
            self.command(f'clear {slot}');self.loaded.pop(slot,None)
            self.on_message('SAMPLE MISSING/INVALID')

    def _load_available_asset(self,slot,track):
        if slot==PREVIEW:self.wave_preview=None
        if not track.get('sample'):
            self.command(f'clear {slot}');self.loaded.pop(slot,None);return
        source=Path(track['sample']);stat=source.stat()
        signature=(str(source.resolve()),stat.st_mtime_ns,stat.st_size)
        if self.loaded.get(slot)!=signature:
            shared=next((other for other,key in self.loaded.items() if key==signature),None)
            if shared is not None:self.command(f'assign {slot} {shared}')
            else:
                ready=track.get('_ready_pcm')
                if ready and tuple(ready[0])==signature:
                    _,path,rate=ready
                else:
                    with wave.open(str(source),'rb') as wav:frames=wav.getnframes()
                    path=self.cache/f'pad-{slot}.f32'
                    rate=convert_sample(dict(track,start=0,end=frames),path)
                self.command(f'load {slot} {rate} '+json.dumps(str(path),ensure_ascii=False))
            self.loaded[slot]=signature
        self.command(f'range {slot} {track["start"]} {track["end"]}')

    def _params(self,slot,track,zone=None,velocity=127):
        p=dict(DEFAULTS,**track.get('sampler',{}));z=zone or {}
        attack=p['attack']/1000
        values=[('ONESHOT','AHD','ADSR').index(p['type']),attack,p['hold']/1000,p['decay']/1000,p['sustain']/100,p['release']/1000,
                ('OFF','LP2','BP2','HP2','EQ').index(p['filter']),max(20,min(20000,p['cutoff']*2**(p['vel_cutoff']/100*(velocity/127-1)*4))),p['resonance']/100,p['drive']/100,max(-1,min(1,(p['pan']+z.get('pan',0))/100)),1 if p['polyphony']=='LEGATO' else p['polyphony'],p['bits'],int(p['reverse']),int(z.get('loop',False)),z.get('loop_start',0),z.get('loop_end',0),int(z.get('xfade',0)),
                p['mod_attack']/1000,p['mod_decay']/1000,p['mod_pitch'],p['mod_cutoff']/100,p['mod_pan']/100,(p['lfo_rate'] if p['lfo_sync']=='FREE' else getattr(self,'tempo',120)/60/({'1/1':4,'1/2':2,'1/4':1,'1/8':.5,'1/16':.25,'1/32':.125,'1/8T':1/3,'1/16T':1/6}[p['lfo_sync']])),('SINE','TRI','RECT','SAW','RANDOM').index(p['lfo_shape']),p['lfo_pitch'],p['lfo_cutoff']/100,p['lfo_pan']/100,p['glide']/1000,p['bend'],p['comp']/100,p['sr']/100,p['eq_gain'],p['eq_width'],int(p['polyphony']=='LEGATO'),track.get('choke_group',0),int(track.get('choke_mode','MASTER')=='SLAVE'),z.get('attack',0)/1000,z.get('decay',0)/1000,p['wheel_pitch'],p['wheel_cutoff']/100,p['wheel_pan']/100,p['lfo_phase']/360,p['tune']]
        self.command('params '+str(slot)+' '+' '.join(str(v) for v in values))

    def load(self,group,pad,track):
        slot=PREVIEW if group<0 else group*16+pad
        if not track.get('sample'):
            self._load_asset(slot,track)
            for index in range(128):
                mapped=ZONE_BASE+slot*128+index
                if mapped in self.loaded:self.command(f'clear {mapped}');self.loaded.pop(mapped,None)
            return
        self._load_asset(slot,track);self._params(slot,track)
        if group>=0:
            items=zones(track)
            for index in range(len(items),128):
                mapped=ZONE_BASE+slot*128+index
                if mapped in self.loaded:self.command(f'clear {mapped}');self.loaded.pop(mapped,None)
            for index,zone in enumerate(items):
                mapped=ZONE_BASE+slot*128+index
                asset=dict(zone,_ready_pcm=track['_ready_pcm']) if track.get('_ready_pcm') else zone
                self._load_asset(mapped,asset);self._params(mapped,track,zone)

    def slice_preview(self,track,token=None):
        velocity=max(1,min(127,track.get('_preview_velocity',127)))
        self.load(-1,0,dict(track,zones=[],sampler={},choke_group=0))
        gain=velocity/127
        self.command(f'preview {token} {gain:.6f}' if token is not None else f'hit {PREVIEW} {gain:.6f}')

    def stretch_preview(self,track,velocity):
        self.command(f'load {PREVIEW} {track["_preview_rate"]} '+json.dumps(track['_preview_pcm'],ensure_ascii=False))
        self.loaded.pop(PREVIEW,None)
        self.wave_preview=track.get('_wave_source')
        self.command(f'range {PREVIEW} {track["start"]} {track["end"]}')
        self._params(PREVIEW,track)
        self.command(f'hit {PREVIEW} {velocity/127*.5:.6f}')

    def hit(self,group,pad,velocity,track,semitones=0,voice_token=0):
        from app.audio_loop import is_audio_sound
        if is_audio_sound(track) and getattr(self,'loop_transport_running',False):return
        slot=PREVIEW if group<0 else group*16+pad;note=round(track.get('note',36+pad)+semitones)
        from app.virtualjv_multi import internal_destination
        internal=internal_destination(track) if group>=0 else None
        if internal is not None:
            if not hasattr(self,'internal_note_bindings'):self.internal_note_bindings={};self.internal_tokens=NoteTokens()
            destination,channel=internal;key=(slot,note,voice_token)
            self.internal_note_bindings[key]=(destination,channel,note);self.internal_tokens.start((destination,channel,note),(slot,voice_token))
            if not hasattr(self,'internal_attack_sources'):self.internal_attack_sources={}
            self.internal_attack_sources.setdefault((destination,channel,note),[]).append(slot)
            self.command(f'plugin_note_ch {destination} {channel} {note} {velocity} {slot}');return
        chain=track.get('plugins',[])
        if chain and chain[0].get('kind')=='INSTRUMENT':
            if not hasattr(self,'instrument_tokens'):self.instrument_tokens=NoteTokens()
            self.instrument_tokens.start((slot,note),voice_token)
            self.command(f'plugin_note {slot} {note} {velocity}');return
        p=dict(DEFAULTS,**track.get('sampler',{}))
        gain=track['gain']/100*(1-p['vel_volume']/100+p['vel_volume']/100*velocity/127)
        items=zones(track) if group>=0 else []
        if items:
            for index,z in enumerate(items):
                if z['key_lo']<=note<=z['key_hi'] and z['vel_lo']<=velocity<=z['vel_hi']:
                    mapped=ZONE_BASE+slot*128+index
                    self._params(mapped,track,z,velocity)
                    first=z['start']+round((z['end']-z['start']-1)*p['vel_start']/100*velocity/127)
                    self.command(f'range {mapped} {first} {z["end"]}')
                    pitch=2**((note-z['root']+z.get('tune',0))/12)
                    mapped=ZONE_BASE+slot*128+index
                    self.command(f'hit {mapped} {gain*z.get("gain",100)/100:.6f} {pitch:.8f} {note} {voice_token}')
        else:self.command(f'hit {slot} {gain:.6f} {2**((semitones)/12):.8f} {note} {voice_token}')

    def note_off(self,group,pad,note=None,voice_token=None):
        slot=PREVIEW if group<0 else group*16+pad
        if self.release_internal(slot,note,voice_token):return
        suffix='' if voice_token is None else f' {voice_token}'
        self.command(f'off {slot} {note if note is not None else -1}'+suffix)
        if not hasattr(self,'instrument_tokens'):self.instrument_tokens=NoteTokens()
        count=1 if note is None else self.instrument_tokens.release_count((slot,note),voice_token)
        for _ in range(count):
            self.command(f'plugin_note {slot} {note if note is not None else -1} 0')
        if note is None:
            for key in list(self.instrument_tokens.active):
                if key[0]==slot:self.instrument_tokens.release_count(key)
        for index in range(128):
            mapped=ZONE_BASE+slot*128+index
            if mapped in self.loaded:self.command(f'off {mapped} {note if note is not None else -1}'+suffix)

    def release_internal(self,slot,note=None,token=None):
        bindings=getattr(self,'internal_note_bindings',{})
        matched=[key for key in bindings if key[0]==slot and (note is None or key[1]==note) and (token is None or key[2]==token)]
        for key in matched:
            destination,channel,pitch=bindings.pop(key)
            if self.internal_tokens.release_count((destination,channel,pitch),(slot,key[2])):
                sources=self.internal_attack_sources.pop((destination,channel,pitch),[slot])
                for source in sources:self.command(f'plugin_note_ch {destination} {channel} {pitch} 0 {source}')
        return bool(matched)

    def internal_control_targets(self,group,pad,current=None):
        slot=group*16+pad
        targets={(d,ch) for key,(d,ch,_) in getattr(self,'internal_note_bindings',{}).items() if key[0]==slot}
        if current:targets.add(current)
        return sorted(targets) if targets else [(slot,None)]

    @staticmethod
    def input_code(value):
        physical=port(value,'IN')
        if physical:return 10+physical[0] if len(physical)==1 else 100+physical[0]//2
        return ('NONE','EXT STEREO','EXT LEFT','EXT RIGHT').index(value)

    def output_settings(self, settings):
        def pair(value):
            physical=port(value,'OUT')
            return physical[0] if physical and len(physical)==2 else -100-physical[0] if physical else -1
        self.command(f'output_map {pair(settings.get("main_output","OUT 1/2"))} {pair(settings.get("cue_output","OFF"))} {settings.get("cue_level",100)/100}')

    def routing(self,project):
        nodes,order=build_graph(project)
        lines=[]
        for bus,target,r,edges in nodes:
            muted=target.get('audio_mute',False) or bus>=GROUP_BASE and bus<MASTER and target.get('mute',False)
            if bus<GROUP_BASE:
                bank=project['groups'][bus//16]
                muted=(muted or target.get('mute',False) or bank.get('mute',False)) and not cue_sound(project,bus//16,bus%16)
            elif r['dest']=='CUE':muted=False
            gain=0 if muted else target.get('gain',100)/100
            # Gate sends too: a pre-fader send deliberately bypasses gain.
            fields=[bus,gain,r['pan']/100,destination(r['dest'],bus),destination(r['aux1_dest'],bus),0 if muted else r['aux1_level']/100,int(r['aux1_pre']),destination(r['aux2_dest'],bus),0 if muted else r['aux2_level']/100,int(r['aux2_pre']),self.input_code(r['input']),r['input_gain']/100]
            lines.append(' '.join(str(v) for v in fields))
        device=self.desired.capture if self.desired and (any(r['input']!='NONE' or any(p.get('sidechain')=='EXT STEREO' for p in t.get('plugins',[])) for _,t,r,_ in nodes) or self.native_capture and self.native_capture['source']<0 or getattr(self,'sampling_input',False)) and not self.recorder and not self.capture_pending else '-'
        device=device or '-'
        if device!=self.input_device:self.command('input_device '+json.dumps(device));self.input_device=device
        from app.virtualjv_multi import internal_destination,rack,BY_SYMBOL
        mappings={};mix={}
        for group_index,group in enumerate(project['groups']):
            plugin=rack(group)
            if plugin:
                for part in range(8):
                    for suffix,value in (('mixer_gain',100),('mixer_pan',0),('mixer_mute',0)):
                        mix[(GROUP_BASE+group_index,BY_SYMBOL[f'p{part+1}_{suffix}']['index'])]=value
        for bus,track,r,edges in nodes:
            if bus>=SOUNDS:continue
            internal=internal_destination(track)
            if internal is None:continue
            mappings[bus]=internal;destination_bus,channel=internal
            plugin=rack(project['groups'][destination_bus-GROUP_BASE]);values=plugin.get('controls',{})
            source_group=project['groups'][bus//16]
            muted=track.get('audio_mute',False) or track.get('mute',False) or source_group.get('mute',False)
            for part in range(8):
                if round(values.get(f'p{part+1}_channel',10 if part==7 else part+1))!=channel+1:continue
                for suffix,value in (('mixer_gain',round(track.get('gain',100))),('mixer_pan',round(r['pan']*64/100)),('mixer_mute',int(bool(muted)))):
                    mix[(destination_bus,BY_SYMBOL[f'p{part+1}_{suffix}']['index'])]=max(-64,min(63,value)) if suffix=='mixer_pan' else value
        old=getattr(self,'internal_routes',{})
        for bus,destination_value in old.items():
            if mappings.get(bus)!=destination_value:self.release_internal(bus)
        self.internal_routes=mappings
        previous=getattr(self,'internal_mix_values',{})
        for key,value in mix.items():
            if previous.get(key)!=value:self.command(f'plugin_param {key[0]} 0 {key[1]} {value}')
        self.internal_mix_values=mix
        signature=(tuple(lines),tuple(order))
        if signature!=self.routing_signature:
            self.command('routing '+str(len(order))+' '+' '.join(str(i) for i in order)+' '+' '.join(lines));self.routing_signature=signature

    def plugins(self,bus,chain):
        signature=(self.sample_rate,tuple((p['uri'],p.get('state')) for p in chain))
        uris=tuple(p['uri'] for p in chain)
        changed_chain=self.plugin_chains.get(bus)!=signature
        if not hasattr(self,'plugin_control_values'):self.plugin_control_values={}
        if changed_chain:
            self.plugin_control_values={k:v for k,v in self.plugin_control_values.items() if k[0]!=bus}
            self.internal_mix_values={k:v for k,v in getattr(self,'internal_mix_values',{}).items() if k[0]!=bus}
            self.command('plugins '+str(bus)+' '+' '.join(json.dumps(uri) for uri in uris));self.plugin_chains[bus]=signature
            for index,plugin in enumerate(chain):
                if plugin.get('state') and Path(plugin['state']).is_file():self.command(f'plugin_restore {bus} {index} '+json.dumps(plugin['state'],ensure_ascii=False))
        for index,plugin in enumerate(chain):
            if plugin['uri']=='urn:machinista:instrument:synth':
                from app.synth_library import asset
                if not hasattr(self,'synth_wave_values'):self.synth_wave_values={}
                for osc,row in plugin.get('synth_waves',{}).items():
                    if osc not in ('1','2','3','4'):continue
                    path=asset(self.root,row['id']);key=(bus,index,int(osc))
                    if path.is_file() and (changed_chain or self.synth_wave_values.get(key)!=row['id']):
                        self.command(f'synth_wave {bus} {index} {int(osc)-1} '+json.dumps(str(path)))
                        self.synth_wave_values[key]=row['id']
            source=plugin.get('sidechain','NONE');sc=-1 if source=='NONE' else -2 if source=='EXT STEREO' else destination(source,bus)
            self.command(f'plugin_sidechain {bus} {index} {sc}')
            metadata=next((p for p in self.plugin_metadata if p['uri']==plugin['uri']),None)
            if metadata:
                for port in metadata['ports']:
                    value=plugin.get('controls',{}).get(port['symbol'],port['default'])
                    if plugin['uri'] in ('urn:machinista:ports:virtualjv-multi','urn:machinista:instrument:synth'):
                        from app.virtualjv_multi import MIXER_SUFFIXES
                        if port['symbol'].endswith(MIXER_SUFFIXES):continue
                        key=(bus,index,port['index'])
                        if self.plugin_control_values.get(key)==value:continue
                        self.plugin_control_values[key]=value
                    self.command(f'plugin_param {bus} {index} {port["index"]} {value}')
            self.command(f'plugin_bypass {bus} {index} {int(plugin.get("bypass",False))}')

    def save_plugin_state(self,project):
        targets=bus_targets(project)
        for bus,target in targets.items():
            for index,plugin in enumerate(target.get('plugins',[])):
                if plugin.get('state'):self.command(f'plugin_save {bus} {index} '+json.dumps(str(Path(plugin['state']).parent)))

    def click(self, accent, level):
        self.command(f'click {int(accent)} {level/100:.6f}')

    @staticmethod
    def capture_source(options):
        if options['source']=='INTERNAL' and options['input'].startswith('SOUND '):
            _,group,pad=options['input'].split();return int(group)*16+int(pad)
        if options['source']=='INTERNAL':return MASTER if options['input']=='MASTER' else GROUP_BASE+int(options['input'].split()[1])
        if options['source']=='EXT LEFT':return -2
        if options['source']=='EXT RIGHT':return -3
        value=options.get('input','IN 1')
        if options['source']=='EXT MONO':
            if value.endswith(' L'):return -2
            if value.endswith(' R'):return -3
            return -2000-port(value,'IN')[0]
        if value=='IN 1':return -1
        return -1000-port(value,'IN')[0]

    def sampling_io(self,options,visible):
        source=self.capture_source(options)
        monitoring=source if source<0 and options['monitor'] else 0
        self.sampling_input=source<0 and (visible or monitoring!=0)
        if monitoring!=self.monitor_source:self.command(f'monitor_source {monitoring}');self.monitor_source=monitoring
        metering=source if visible else -99
        if metering!=self.meter_source:self.command(f'meter_source {metering}');self.meter_source=metering
        return self.sampling_input

    def start_native_capture(self,device,target,options,tempo):
        if self.recorder or self.capture_pending or self.native_capture:self.on_message('ALREADY RECORDING');return
        source=GROUP_BASE+target[0] if options['source']=='GROUP' else MASTER if options['source']=='MASTER' else self.capture_source(options)
        path=reserve_recording_path(self.root/'samples/recordings');mode='SYNC' if options['mode']=='LOOP' else options['mode']
        frames=min(8388608,round(options['bars']*4*60/tempo*self.sample_rate)) if mode=='SYNC' and options['bars']!='FREE' else 8388608
        self.native_capture={'source':source,'target':target,'path':path,'mode':mode,'triggered':mode!='SYNC'};self.native_cancel=False
        if source<0:
            self.command('input_device '+json.dumps(device));self.input_device=device
        self.command('record_start '+json.dumps(str(path),ensure_ascii=False)+f' {source} {int(mode=="DETECT")} {int(mode=="SYNC")} {options["threshold"]} {frames} {int(options["monitor"])}')
    def native_record_event(self,event):
        if self.native_capture is None:return None
        self.capture_peak=event.get('peak',0)
        if event['status'] not in ('finished','error'):return None
        capture=self.native_capture;self.native_capture=None
        if self.native_cancel or event['status']=='error' or not event.get('frames'):
            capture['path'].unlink(missing_ok=True);return None
        return capture['target'],capture['path']

    def external_capture_tick(self,app):
        # External MIDI clock still owns the fallback transport. Internal
        # playback uses sample-exact Recorder.feed_transport exclusively.
        capture=self.native_capture
        if app.settings['midi_sync']=='IN' and capture and capture.get('mode')=='SYNC' and not capture.get('triggered') and app.playing and app.clock_phase%384<4:
            self.command('record_trigger');capture['triggered']=True

    def capture(self,device,target):
        if self.recorder or self.capture_pending:
            self.on_message('ALREADY RECORDING');return
        self.capture_pending=(device,target)
        self.command('input_device "-"');self.input_device='-';self.command('capture_barrier')

    def begin_capture(self):
        if self.capture_pending is None:return
        device,target=self.capture_pending;self.capture_pending=None
        if self.recorder:
            self.on_message('ALREADY RECORDING')
            return
        folder = self.root/'samples/recordings'
        folder.mkdir(parents=True, exist_ok=True)
        self.record_path = reserve_recording_path(folder)
        self.record_target = target
        self.record_errors = tempfile.TemporaryFile()
        self.recorder = subprocess.Popen(['arecord', '-q', '-D', device, '-f', 'S16_LE',
                                          '-r', str(self.sample_rate), '-c', '2', '--buffer-time=500000', '--period-time=100000',
                                          '-t', 'wav', str(self.record_path)], stderr=self.record_errors)
        self.on_message('SAMPLING RECORDING')

    def stop_capture(self):
        self.capture_pending=None
        if self.native_capture:
            self.command('record_stop');return None
        if not self.recorder:
            return None
        process = self.recorder
        self.recorder = None
        if process.poll() is None:
            process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            self.record_errors.close();self.record_errors=None
            self.on_message('RECORD STOP FAILED')
            return None
        self.record_errors.seek(0)
        error = self.record_errors.read()
        self.record_errors.close();self.record_errors=None
        if error:print(error.decode(errors='replace'),file=sys.stderr)
        repair_recording_header(self.record_path)
        try:
            with wave.open(str(self.record_path), 'rb') as wav:
                if wav.getnframes() == 0:
                    raise ValueError('empty recording')
        except (OSError, EOFError, wave.Error, ValueError):
            self.on_message('RECORD FAILED')
            if error:
                print(error.decode(errors='replace'), file=sys.stderr)
            return None
        self.on_message('RECORD XRUN' if b'overrun' in error.lower() else 'RECORD SAVED')
        return self.record_target, self.record_path

    def close(self):
        self.stop_capture()
        if self.engine.poll() is None:
            try:
                self.command('quit')
            except OSError:
                pass  # systemd may already have stopped the audio worker.
        try:
            self.engine.stdin.close()
        except OSError:
            pass
        try:
            self.engine.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.engine.kill()
            self.engine.wait()
        self.engine.stdout.close()
