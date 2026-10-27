"""Isolated, bounded WAV rendering; no live audio devices or project writes."""
import copy
import errno
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import uuid
import wave
from app.audio import AudioBackend
from app.layout import GROUP_BASE,MASTER,bus_targets
from app.note_tokens import NoteTokens
from app.storage import save_json
from app.export_destination import ExportLocation
from app.export_formats import FORMATS,DEPTHS,export_format,verify_audio_export

MODES=('PATTERN','SCENE','SONG')
SOURCES=('MIX','SOUND','GROUP','ALL SOUNDS','ALL GROUPS')
FIELDS=('RANGE','SOURCE','RATE','TAIL','FORMAT','DEPTH','LOOP OPT','NORMALIZE','DESTINATION')
TAILS=(0,1,2,5,10)


def check_cancel(cancel):
    if cancel is not None and cancel.is_set():raise ValueError('EXPORT CANCELED')


def export_spans(app,request):
    mode=request['mode'];group=request['group'];pattern=request['pattern']
    if mode=='PATTERN':
        clips=[None]*len(app.project['groups']);clips[group]=pattern
        return [(clips,app.pattern_ticks(group,pattern))]
    scenes=[request['scene']] if mode=='SCENE' else app.project.get('song',[])
    if not scenes:raise ValueError('SONG IS EMPTY')
    return [(list(app.project['scenes'][scene]),app.scene_steps(scene)*24) for scene in scenes]


def compile_export(app,request,cancel=None):
    """Flatten independent clip loops; reuse the live sampler and modulation encoders."""
    spans=export_spans(app,request);ticks=sum(length for _,length in spans)
    rate=request['rate'];seconds=ticks*60/(app.project['tempo']*96)+request['tail']
    if seconds>3600:raise ValueError('EXPORT LIMIT 60 MIN')
    frames=round(seconds*rate)
    if frames<1:raise ValueError('EMPTY EXPORT')
    plan=['sequence_begin',f'sequence_lane {ticks+request["tail"]*app.project["tempo"]*96/60+384}']
    controls=[];offset=0;hits=0;onset_count=0;control_bytes=0
    encoder=object.__new__(AudioBackend);encoder.tempo=app.project['tempo'];encoder.instrument_tokens=NoteTokens()
    encoder.routing_signature=None;encoder.input_device='-';encoder.desired=encoder.recorder=encoder.capture_pending=encoder.native_capture=None
    app.song_playing=request['mode']=='SONG'
    for song_entry,(clips,duration) in enumerate(spans):
        app.song_bar=song_entry;app.song_phase_origin=offset if request.get('scene_retrigger','ON')!='ON' else 0
        check_cancel(cancel);app.automation_restore()
        app.active_patterns=[p if p is not None else 0 for p in clips];app.active_clips=[p is not None for p in clips]
        app.automation_cache=None
        onsets={};group_solo=any(g.get('solo',False) for g in app.project['groups'])
        for group,pattern in enumerate(clips):
            bank=app.project['groups'][group]
            if pattern is None or bank.get('mute',False) or group_solo and not bank.get('solo',False):continue
            solo=any(t['solo'] for t in bank['pads']);length=app.pattern_ticks(group,pattern)
            for identity,event in sorted(app.event_notes(group,pattern).items()):
                pad,tick=identity[:2]
                if bank['pads'][pad]['mute'] or solo and not bank['pads'][pad]['solo']:continue
                tick=app.groove_position(group,pad,tick,length)
                if request['mode']=='SONG' and request.get('scene_retrigger','ON')!='ON':tick=(tick-offset)%length
                for cycle in range(0,duration,length):
                    at=cycle+tick
                    if at<duration:
                        onset_count+=1
                        if onset_count>16384:raise ValueError('EXPORT NOTE LIMIT')
                        onsets.setdefault(at,[]).append((group,pad,event))
        has_modulation=any(p is not None and any(k.startswith(str(p)+':') for k in g.get('automation',{})) for g,p in zip(app.project['groups'],clips))
        has_modulation=has_modulation or app.song_playing and any(k.startswith(str(song_entry)+':') for k in app.project.get('master_automation',{}))
        times=range(duration) if has_modulation else sorted(set(onsets)|{0})
        for tick in times:
            if tick%512==0:check_cancel(cancel);time.sleep(0)
            app.clock_phase=tick+(offset if request['mode']=='SONG' and request.get('scene_retrigger','ON')!='ON' else 0);app.automation_tick()
            generated=[];encoder.command=generated.append
            # Route reset at each Scene boundary and all actual modulation changes.
            if tick==0 or any(action=='routing_refresh' for action,value in app.actions):encoder.routing(app.project)
            for action,value in app.actions:
                if action=='load':
                    group,pad,track=value;encoder._params(group*16+pad,track)
                    from app.sampler import zones
                    from app.layout import ZONE_BASE
                    for index,zone in enumerate(zones(track)):encoder._params(ZONE_BASE+(group*16+pad)*128+index,track,zone)
                elif action in ('plugins','plugin_controls'):
                    bus,chain=value
                    for slot,plugin in enumerate(chain):
                        metadata=next((p for p in request['metadata'] if p['uri']==plugin['uri']),None)
                        if metadata:
                            for port in metadata['ports']:generated.append(f'plugin_param {bus} {slot} {port["index"]} {plugin.get("controls",{}).get(port["symbol"],port["default"])}')
                elif action=='live_fx':generated.append('live_fx '+' '.join(map(str,value)))
            app.actions.clear()
            frame=round((offset+tick)*rate*60/(app.project['tempo']*96))//256*256
            control_bytes+=sum(len(command) for command in generated)
            if control_bytes>32*1024**2:raise ValueError('EXPORT MODULATION LIMIT')
            controls.extend(f'offline_control {frame} '+json.dumps(command) for command in generated)
            if len(controls)>200000:raise ValueError('EXPORT MODULATION LIMIT')
            for group,pad,event in onsets.get(tick,[]):
                source=app.project['groups'][group]['pads'][pad]
                voices=[{k:v for k,v in event.items() if k!='poly'},*event.get('poly',{}).values()]
                for voice in voices:
                    boundary=ticks-offset-tick if request['mode']=='SONG' and request.get('scene_retrigger','ON')!='ON' else duration-tick
                    gate=max(1,min(boundary,voice.get('length',app.grid_ticks())))
                    plan.append(f'sequence_event {offset+tick} {gate} {voice["probability"]} 0')
                    encoder.command=plan.append
                    for note in voice.get('chord') or [voice.get('note',source.get('note',36+pad))]:
                        semitones=note-source.get('note',36+pad)
                        for slot in app.linked_sounds(group,pad):
                            track=app.project['groups'][group]['pads'][slot]
                            if track.get('source')!='MIDI' or track['sample'] or track.get('plugins') or track.get('routing',{}).get('midi_target','NONE')!='NONE':
                                encoder.hit(group,slot,voice['velocity'],dict(track,gain=100),semitones)
                                hits+=1
                                if hits>16384:raise ValueError('EXPORT NOTE LIMIT')
        offset+=duration
    plan.append('sequence_commit')
    if sum(c.startswith(('hit ','plugin_note ','plugin_note_ch ')) for c in plan)>16384:raise ValueError('EXPORT HIT LIMIT')
    app.automation_restore();app.actions.clear()
    return controls,plan,frames


def export_targets(app,request):
    source=request['source'];group=request['group'];pad=request['pad']
    if source=='MIX':return [(MASTER,'Mix')]
    if source=='SOUND':return [(group*16+pad,f'{app.group_name(group)}-Sound{pad+1:02}')]
    if source=='GROUP':return [(GROUP_BASE+group,f'Group-{app.group_name(group)}')]
    spans=export_spans(app,request);sounds=set()
    for g,bank in enumerate(app.project['groups']):
        sounds.update((g,p) for p,t in enumerate(bank['pads']) if t.get('sample') or t.get('zones') or t.get('plugins'))
    for clips,_ in spans:
        for g,p in enumerate(clips):
            if p is not None:
                for identity,event in app.event_notes(g,p).items():
                    sounds.update((g,slot) for slot in app.linked_sounds(g,identity[0]))
    from app.routing import build_graph
    nodes,_=build_graph(app.project);edges={bus:destinations for bus,target,routing,destinations in nodes}
    reached={g*16+p for g,p in sounds}|{GROUP_BASE+g for g,bank in enumerate(app.project['groups']) if bank.get('plugins')}
    todo=list(reached)
    while todo:
        for destination in edges[todo.pop()]:
            if destination not in reached:reached.add(destination);todo.append(destination)
    if source=='ALL GROUPS':return [(bus,f'Group-{app.group_name(bus-GROUP_BASE)}') for bus in sorted(reached) if GROUP_BASE<=bus<MASTER]
    return [(bus,f'{app.group_name(bus//16)}-Sound{bus%16+1:02}') for bus in sorted(reached) if bus<GROUP_BASE]



def render_export(request,root,cancel=None,progress=None):
    location=None
    try:
        check_cancel(cancel);location=ExportLocation(root,request)
        return _render_export(request,root,cancel,progress,location)
    except OSError as error:
        if error.errno in (errno.EACCES,errno.EPERM,errno.EROFS):raise ValueError('DESTINATION NOT WRITABLE') from error
        if error.errno==errno.ENOSPC:raise ValueError('DESTINATION FULL') from error
        raise
    finally:
        if location is not None:location.close()
        state_dir=Path(request.get('state_dir',Path(root)/'cache'/'absent'))
        if state_dir.parent==Path(root)/'cache'/'export-state' and state_dir.exists():shutil.rmtree(state_dir)


def _render_export(request,root,cancel,progress,location):
    from app.model import Application
    root=Path(root);base=location.base;(root/'cache').mkdir(exist_ok=True)
    temporary=base/('.'+uuid.uuid4().hex);temporary.mkdir()
    report=progress.put if progress is not None else lambda value:None
    try:
        format,bits=export_format(request)
        if any(type(request.get(key,False)) is not bool for key in ('loop_optimize','normalize')):raise ValueError('INVALID EXPORT OPTION')
        with tempfile.TemporaryDirectory(prefix='export-',dir=root/'cache') as directory:
            job=Path(directory);save_json(job/'projects/current.json',request['project']);app=Application(job)
            app.group=request['group'];app.pad=request['pad'];app.pattern=request['pattern'];app.settings['scene_retrigger']=request.get('scene_retrigger','ON')
            targets=export_targets(app,request)
            if not targets:raise ValueError('NO TRACKS TO EXPORT')
            for target in bus_targets(app.project).values():
                if target.get('routing',{}).get('input','NONE')!='NONE':raise ValueError('LIVE INPUT CANNOT EXPORT')
                for plugin in target.get('plugins',[]):
                    if not plugin.get('state') or not Path(plugin['state']).is_file():raise ValueError('PLUGIN STATE FAILED')
            # Estimate decoded sample memory before starting a second host on the Pi.
            assets={}
            for group in app.project['groups']:
                for track in group['pads']:
                    for asset in [track,*track.get('zones',[])]:
                        if asset.get('sample'):
                            path=Path(asset['sample']).resolve()
                            with wave.open(str(path)) as wav:assets[path]=wav.getnframes()*8
            available=next((int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:')),0) if Path('/proc/meminfo').exists() else 2**40
            if sum(assets.values())+128*1024**2>available:raise ValueError('NOT ENOUGH FREE RAM')
            cache_bytes=sum(assets.values())
            if request.get('destination') and shutil.disk_usage(root).free<cache_bytes+16*1024**2:raise ValueError('NOT ENOUGH SD CACHE SPACE')
            report('PREPARING');controls,plan,frames=compile_export(app,request,cancel)
            ticks=sum(duration for _,duration in export_spans(app,request))
            loop_frames=round(ticks*60/(app.project['tempo']*96)*request['rate']) if request.get('loop_optimize') else 0
            final_frames=loop_frames or frames
            processing=request.get('normalize',False) or bool(loop_frames)
            if shutil.disk_usage(base).free<final_frames*2*(bits//8)*len(targets)+(frames*8 if processing else 0)+(0 if request.get('destination') else cache_bytes)+16*1024**2:raise ValueError('NOT ENOUGH FREE SPACE')
            commands=[];encoder=object.__new__(AudioBackend);encoder.command=commands.append
            encoder.root=job;encoder.cache=job/'pcm';encoder.cache.mkdir();encoder.loaded={};encoder.plugin_chains={};encoder.plugin_metadata=request['metadata'];encoder.sample_rate=request['rate'];encoder.tempo=app.project['tempo'];encoder.instrument_tokens=NoteTokens()
            encoder.routing_signature=None;encoder.input_device='-';encoder.desired=encoder.recorder=encoder.capture_pending=encoder.native_capture=None
            def invalid(message):raise ValueError(message)
            encoder.on_message=invalid
            for g,group in enumerate(app.project['groups']):
                for p,track in enumerate(group['pads']):
                    check_cancel(cancel)
                    if track['sample'] or track.get('zones'):encoder.load(g,p,track)
            for bus,target in bus_targets(app.project).items():
                if target.get('plugins'):encoder.plugins(bus,target['plugins'])
            encoder.routing(app.project)
            prefix=['offline_rate '+str(request['rate']),*commands,*controls]
            results=[]
            for index,(bus,label) in enumerate(targets):
                check_cancel(cancel);location.verify();report(f'RENDER {index+1}/{len(targets)}')
                from app.virtualjv_multi import internal_destination
                destination=internal_destination(app.project['groups'][bus//16]['pads'][bus%16]) if bus<GROUP_BASE else None
                render_bus=destination[0] if destination else bus
                selected_plan=plan
                if destination:
                    selected_plan=[]
                    for command in plan:
                        if command.startswith(('hit ','plugin_note ','plugin_note_ch ','external_note ','click ')):
                            fields=command.split()
                            if fields[0]!='plugin_note_ch' or int(fields[1])!=destination[0] or int(fields[2])!=destination[1] or int(fields[5])!=bus:continue
                        selected_plan.append(command)
                initial=[*prefix,*selected_plan,'sequence_seek 0 1',f'sequence_transport {app.project["tempo"]} 1 0 0']
                path=temporary/(label+('.wav' if format=='WAV' else '.aiff'));script='\n'.join([*initial,'render_start '+json.dumps(str(path))+f' {frames} {render_bus} {bits} {format} {loop_frames} {int(request.get("normalize",False))} {app.project["tempo"]} {ticks/384}','quit',''])
                process=subprocess.Popen(['nice','-n','19',str(root/'build/audio_engine'),'--offline-render'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                try:
                    started=time.monotonic();first=True
                    while True:
                        check_cancel(cancel);location.verify()
                        try:
                            output,error=process.communicate(script if first else None,timeout=.2);break
                        except subprocess.TimeoutExpired:
                            first=False
                            if time.monotonic()-started>max(120,frames/request['rate']*3):raise ValueError('EXPORT TIMED OUT')
                    if process.returncode:raise ValueError('EXPORT ENGINE FAILED')
                    events=[json.loads(line) for line in output.splitlines() if line.startswith('{')]
                    if any(e.get('status') in ('error','memory_limit') for e in events):raise ValueError('EXPORT ENGINE ERROR')
                    result=next((e for e in reversed(events) if e.get('kind')=='export'),None)
                    if result is None or result['status']!='finished' or result['frames']!=final_frames or result.get('overflow'):raise ValueError('EXPORT INCOMPLETE')
                    verify_audio_export(path,format,bits,request['rate'],final_frames)
                    with path.open('rb') as rendered:os.fsync(rendered.fileno())
                    results.append(dict(file=path.name,bus=bus,peak=result['peak'],gain=result.get('gain',1)))
                finally:
                    if process.poll() is None:process.kill();process.communicate()
            check_cancel(cancel)
            save_json(temporary/'Export.json',dict(format='Machinista-audio-export',version=2,container=format,bits=bits,encoding='float' if bits==32 else 'PCM',project=app.project['name'],mode=request['mode'],source=request['source'],rate=request['rate'],frames=final_frames,render_frames=frames,tempo=app.project['tempo'],bars=ticks/384,loop_optimize=request.get('loop_optimize',False),normalize=request.get('normalize',False),tail=request['tail'],files=results,external_midi='not rendered',modulation='256-frame blocks'))
        location.verify()
        name=request['project']['name']+'-'+request['mode'].title()
        for number in range(1,10000):
            destination=base/f'{name}-{number:03}'
            if not destination.exists():
                temporary.rename(destination)
                descriptor=os.open(base,os.O_RDONLY)
                try:os.fsync(descriptor)
                finally:os.close(descriptor)
                report('EXPORT DONE');return location.result(destination.name)
        raise ValueError('EXPORT FOLDER LIMIT')
    finally:
        if temporary.exists():shutil.rmtree(temporary)
        state_dir=Path(request.get('state_dir',root/'cache'/'absent'))
        if state_dir.parent==root/'cache'/'export-state' and state_dir.exists():shutil.rmtree(state_dir)


class AudioExport:
    def init_export(self):
        self.export_mode=0;self.export_source=0;self.export_rate=48000;self.export_tail=2;self.export_field=0
        self.export_busy=False;self.export_status='';self.export_result='';self.export_kind='AUDIO';self.export_midi_source=1;self.export_groove=False;self.export_format='WAV';self.export_bits=16;self.export_loop=False;self.export_normalize=False;self.export_destination=None;self.export_result_device='SD CARD'
    def open_export(self,kind='AUDIO'):
        self.export_kind=kind;self.page='EXPORT';self.export_field=0
    def export_fields(self):
        return ('RANGE','SOURCE','TIMING','DESTINATION') if self.export_kind=='MIDI' else FIELDS
    def export_destinations(self):
        return [None]+[dict(path=str(s.path),identity=s.identity,name=s.name,read_only=s.read_only) for s in self.browser.sources if s.identity]
    def export_destination_label(self):
        if self.export_destination is None:return 'SD CARD'
        current=next((d for d in self.export_destinations() if d and (d['path'],d['identity'])==(self.export_destination['path'],self.export_destination['identity'])),None)
        return (current['name']+(' (RO)' if current['read_only'] else '')) if current else 'USB REMOVED'
    def rotate_export_destination(self,delta):
        choices=self.export_destinations()
        key=lambda d:(d['path'],d['identity']) if d else None
        index=next((i for i,d in enumerate(choices) if key(d)==key(self.export_destination)),0)
        self.export_destination=choices[max(0,min(len(choices)-1,index+delta))]
    def export_value(self):
        if self.export_fields()[self.export_field]=='DESTINATION':return self.export_destination_label()
        mode=MODES[self.export_mode]+(f' {self.group_name()} P{self.pattern+1:02}' if self.export_mode==0 else f' {self.scene+1:02}' if self.export_mode==1 else '')
        if self.export_kind=='MIDI':
            source=('SOUND','GROUP','ALL GROUPS')[self.export_midi_source]
            if self.export_midi_source<2:source+=' '+self.group_name()+(f':{self.pad+1:02}' if self.export_midi_source==0 else '')
            return (mode,source, 'GROOVE' if self.export_groove else 'GRID')[self.export_field]
        source=SOURCES[self.export_source]+(f' {self.group_name()}:{self.pad+1:02}' if self.export_source==1 else f' {self.group_name()}' if self.export_source==2 else '')
        return (mode,source,str(self.export_rate),('WRAP ' if self.export_loop else '')+str(self.export_tail)+' SEC',self.export_format,str(self.export_bits)+(' FLOAT' if self.export_bits==32 else ' BIT'),'ON' if self.export_loop else 'OFF','ON' if self.export_normalize else 'OFF')[self.export_field]
    def export_request(self):
        if self.playing or self.recording or self.capture_started is not None or self.capture_armed:self.message='STOP RECORD/PLAY FIRST';return
        if self.export_busy:self.message='EXPORT BUSY';return
        if self.export_destination is not None:
            if self.export_destination_label()=='USB REMOVED':self.message='USB REMOVED';return
            if any(d and (d['path'],d['identity'])==(self.export_destination['path'],self.export_destination['identity']) and d['read_only'] for d in self.export_destinations()):self.message='USB READ ONLY';return
        self.export_result_device=self.export_destination_label()
        project=self.project_for_save()
        request=dict(destination=copy.deepcopy(self.export_destination),project=project,mode=MODES[self.export_mode],source=SOURCES[self.export_source],rate=self.export_rate,tail=self.export_tail,format=self.export_format,bits=self.export_bits,loop_optimize=self.export_loop,normalize=self.export_normalize,group=self.group,pad=self.pad,pattern=self.pattern,scene=self.scene,scene_retrigger=self.settings['scene_retrigger'])
        if self.export_kind=='MIDI':
            request.update(source=('SOUND','GROUP','ALL GROUPS')[self.export_midi_source],groove=self.export_groove)
            self.actions.append(('midi_export',request));self.export_busy=True;self.export_status='PREPARING';self.message='';return
        request['chains']={bus:(bus,target.get('plugins',[])) for bus,target in bus_targets(project).items() if target.get('plugins')}
        self.actions.append(('audio_export',request));self.export_busy=True;self.export_status='PREPARING';self.message=''
    def export_button(self,name,pressed):
        if self.export_busy and pressed and name in ('PLAY','REC','RESTART'):
            self.message='STOP EXPORT FIRST';return True
        if self.page=='EXPORT DONE' and pressed:
            if name=='F1':self.page='PROJECT MANAGE'
            elif name in ('F3','ENTER'):self.page='EXPORT';self.message=''
            return name in ('F1','F2','F3','ENTER')
        if self.page!='EXPORT' or not pressed:return False
        if name=='F1':
            if self.export_busy:self.actions.append(('export_cancel',None));self.export_status='CANCELING'
            else:self.page='PROJECT MANAGE'
            return True
        if self.export_busy:return name in ('F2','F3','ENTER','ENCODER PUSH','NAV LEFT','NAV RIGHT')
        if name in ('F3','ENTER'):self.export_request();return True
        if name in ('NAV LEFT','NAV RIGHT'):
            self.export_field=max(0,min(len(self.export_fields())-1,self.export_field+(-1 if name=='NAV LEFT' else 1)));return True
        return name=='F2'
    def export_rotate(self,delta):
        if self.page!='EXPORT':return False
        if self.export_busy:return True
        if self.export_fields()[self.export_field]=='DESTINATION':self.rotate_export_destination(delta)
        elif self.export_field==0:self.export_mode=max(0,min(2,self.export_mode+delta))
        elif self.export_kind=='MIDI':
            if self.export_field==1:self.export_midi_source=max(0,min(2,self.export_midi_source+delta))
            else:self.export_groove=delta>0
        elif self.export_field==1:self.export_source=max(0,min(4,self.export_source+delta))
        elif self.export_field==2:self.export_rate=48000 if delta>0 else 44100
        elif self.export_field==3:self.export_tail=TAILS[max(0,min(4,TAILS.index(self.export_tail)+delta))]
        elif self.export_field==4:self.export_format=FORMATS[max(0,min(1,FORMATS.index(self.export_format)+delta))]
        elif self.export_field==5:self.export_bits=DEPTHS[max(0,min(2,DEPTHS.index(self.export_bits)+delta))]
        elif self.export_field==6:self.export_loop=delta>0
        else:self.export_normalize=delta>0
        return True
