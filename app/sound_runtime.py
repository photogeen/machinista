"""Same-user local RPC for selected Sound context and exclusive autosampling.

Socket thread only queues bounded requests. The application thread handles
engine commands; copying samples and plug-in states uses a separate worker.
"""
from concurrent.futures import ThreadPoolExecutor
import copy
import json
import os
from pathlib import Path
import queue
import socket
import stat
import threading
import time
from app.sound_library import SoundLibrary,name,folders,tags,worker_priority
from app.autosampler import AutoSampler
from app.presets import preset_snapshot,prepare_preset_state


def request(root,operation,**values):
    path=Path(root)/'samples/.sound-control.sock'
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(8);client.connect(str(path));client.sendall(json.dumps(dict(operation=operation,**values)).encode()+b'\n')
        with client.makefile('rb') as stream:raw=stream.readline(2*1024**2)
    value=json.loads(raw)
    if value.get('error'):raise ValueError(value['error'])
    return value


class SoundRuntime:
    def __init__(self,root,app,audio,midi):
        self.root=Path(root);self.app=app;self.audio=audio;self.midi=midi;self.library=SoundLibrary(root)
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='sound-assets',initializer=worker_priority);self.auto=AutoSampler(root,app,audio,midi,self.pool,self.library)
        self.requests=queue.Queue(8);self.stop=threading.Event();self.future=None;self.future_kind='SAVE';self.load_context=None;self.pending_load=None;self.barrier=None;self.job={'state':'IDLE'};self.snapshot={};self.next_snapshot=0;self.context_key=None;self.context_body={}
        self.path=self.root/'samples/.sound-control.sock'
        if self.path.exists():
            if not stat.S_ISSOCK(self.path.lstat().st_mode) or self.path.lstat().st_uid!=os.getuid():raise ValueError('Invalid Sound runtime socket.')
            self.path.unlink()
        self.socket=socket.socket(socket.AF_UNIX);self.socket.bind(str(self.path));self.path.chmod(0o600);self.socket.listen(4);self.socket.settimeout(.5)
        self.thread=threading.Thread(target=self.serve,name='sound-control',daemon=True);self.thread.start()
    @property
    def busy(self):return self.auto.active or self.auto.future is not None or self.future is not None or self.barrier is not None or self.pending_load is not None
    def serve(self):
        while not self.stop.is_set():
            try:client,_=self.socket.accept()
            except socket.timeout:continue
            except OSError:return
            with client:
                try:
                    if hasattr(socket,'SO_PEERCRED'):
                        import struct
                        _,uid,_=struct.unpack('3i',client.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
                        if uid!=os.getuid():raise PermissionError('Same-user connection required.')
                    client.settimeout(2)
                    with client.makefile('rb') as stream:raw=stream.readline(65537)
                    if len(raw)>65536:raise ValueError('Request too large.')
                    value=json.loads(raw);operation=value.get('operation')
                    if operation=='status':result=copy.deepcopy(self.snapshot)
                    elif operation in ('load','save_current','autosample','cancel','plugin_parameters','synth_edit','update_prepare'):
                        done=queue.Queue(1);self.requests.put_nowait((value,done,time.monotonic()+4));result=done.get(timeout=5)
                    else:raise ValueError('Invalid Sound operation.')
                except Exception as e:result={'error':str(e) or 'Sound runtime unavailable.'}
                try:client.sendall(json.dumps(result).encode()+b'\n')
                except OSError:pass
    def capture_snapshot(self):
        a=self.app;t=a.track()
        return dict(available=True,group=a.group,pad=a.pad,generation=a.project_generation,revision=a.revision,name=a.sound_name(empty='Empty Sound'),
                    zones=copy.deepcopy(__import__('app.sampler',fromlist=['zones']).zones(t)),sampler=copy.deepcopy(t.get('sampler',{})),plugins=[dict(uri=p['uri'],kind=p['kind'],name=(a.plugin_metadata(p['uri']) or {}).get('name',p['uri']),controls=copy.deepcopy(p.get('controls',{})),synth_waves=copy.deepcopy(p.get('synth_waves',{})),profile_preset=copy.deepcopy(p.get('profile_preset',{}))) for p in t.get('plugins',[])],
                    busy=self.busy,playing=a.playing,recording=a.recording,autosampler=copy.deepcopy(self.auto.state),job=copy.deepcopy(self.job),audio=a.audio.name if a.audio else '',inputs=a.audio.input_channels if a.audio else 0,midi_outputs=[dict(id=d.key,name=d.name) for d in a.midi_devices],midi_out=a.settings['midi_out'])
    def poll(self,now,other_busy=False):
        a=self.app
        if self.future and self.future.done():
            try:
                result=self.future.result()
                if self.future_kind=='LOAD':
                    if self.load_context!=(a.project_generation,a.group,a.pad,a.revision):raise ValueError('Selected Sound changed; load cancelled.')
                    if result is None:raise ValueError('Sound not found.')
                    a.request_preset_load(self.library.folder/result['link'],'SOUND',a.group,a.pad);self.pending_load=(self.load_context,result['name'],now,now+60);self.job=dict(state='LOADING',message='Loading Sound on the selected pad.')
                else:self.job=dict(state='DONE',id=result.get('id'),message='Sound saved.');a.message='SOUND SAVED'
            except Exception as e:self.job=dict(state='ERROR',message=str(e));a.message='SOUND SAVE FAILED'
            self.future=None
        self.auto.tick(now)
        a.auto_setup()
        command=a.auto_command;a.auto_command=None
        if command:
            try:
                if command[0]=='cancel':self.auto.cancel()
                else:
                    if self.busy or other_busy:raise ValueError('Finish the current operation first.')
                    self.auto.start(command[1],now)
            except (ValueError,OSError) as error:
                a.message=str(error)
                if not self.busy:self.auto.state={'state':'ERROR','message':str(error)}
        a.auto_status=copy.deepcopy(self.auto.state)
        if self.pending_load:
            context,title,started,deadline=self.pending_load
            if now>deadline or a.playing or a.project_generation!=context[0]:self.job=dict(state='ERROR',message='Sound load cancelled or timed out.');self.pending_load=None
            elif not other_busy and now-started>.2:
                if (a.group,a.pad)==context[1:3] and a.revision!=context[3] and a.track().get('name')==title:self.job=dict(state='LOADED',message='Sound loaded on the selected pad.');self.pending_load=None
                elif a.message!='LOADING PRESET':self.job=dict(state='ERROR',message=a.message or 'Sound could not be loaded.');self.pending_load=None
        for _ in range(4):
            try:value,done,expires=self.requests.get_nowait()
            except queue.Empty:break
            try:
                if now>expires:raise ValueError('Sound request expired; try again.')
                op=value['operation']
                if op=='update_prepare':
                    from app.updater import prepare
                    done.put_nowait(prepare(a,self.busy or other_busy,now));continue
                if now<getattr(a,'update_lock_until',0):raise ValueError('Update is starting. Please wait.')
                if op=='cancel':self.auto.cancel();result={'ok':True}
                else:
                    if self.busy or other_busy:raise ValueError('Finish the current operation first.')
                    if value.get('generation')!=a.project_generation or value.get('group')!=a.group or value.get('pad')!=a.pad or value.get('revision')!=a.revision:raise ValueError('Selected Sound changed. Refresh the current Sound first.')
                    if op=='synth_edit':
                        if self.audio.native_capture or a.capture_armed:raise ValueError('Finish sampling first.')
                        from app.web_synth import apply
                        done.put_nowait(apply(a,value));self.context_key=None
                        continue
                    if a.playing or a.recording or self.audio.native_capture:raise ValueError('Stop playback and recording first.')
                    if op=='load':
                        self.future_kind='LOAD';self.load_context=(a.project_generation,a.group,a.pad,a.revision);self.future=self.pool.submit(self.library.row,value.get('id'));result={'ok':True,'message':'Loading Sound on the selected pad.'}
                    elif op=='save_current':
                        metadata=dict(name=name(value.get('name')),folder=folders(value.get('folder','')),tags=tags(value.get('tags',[])))
                        project,chains=preset_snapshot(a,'SOUND');request=dict(kind='SOUND',name=metadata['name'],project=project,chains=chains)
                        self.barrier=(project,metadata,now+15);prepare_preset_state(self.audio,request,self.root);self.job={'state':'SAVING','message':'Saving plugin state and samples.'};result={'ok':True}
                    elif op=='autosample':self.auto.start(value,now);result={'ok':True}
                    elif op=='plugin_parameters':
                        from app.web_plugin_controls import apply_parameters
                        apply_parameters(a,value);result={'ok':True}

                done.put_nowait(result)
            except Exception as e:done.put_nowait({'error':str(e)})
        if self.barrier and now>self.barrier[2]:self.barrier=None;self.job={'state':'ERROR','message':'Plugin state save timed out.'}
        if now>=self.next_snapshot:
            key=(a.project_generation,a.group,a.pad,a.revision,a.audio,tuple(a.midi_devices),a.settings['midi_out'])
            if key!=self.context_key:
                self.context_body=self.capture_snapshot();self.context_key=key
            self.snapshot=dict(self.context_body,busy=self.busy,playing=a.playing,recording=a.recording,autosampler=copy.deepcopy(self.auto.state),job=copy.deepcopy(self.job));self.next_snapshot=now+.25
    def event(self,event,now):
        try:
            if self.auto.event(event,now):return True
        except (OSError,ValueError) as error:
            self.auto.failure=str(error);self.auto.finish(False);return True
        if event.get('kind')=='state_barrier' and self.barrier:
            project,metadata,_=self.barrier;self.barrier=None;self.future_kind='SAVE';self.future=self.pool.submit(self.library.save_project,project,metadata);return True
        return False
    def close(self):
        if self.auto.active:
            try:self.auto.cancel('Application stopped.')
            except OSError:pass
        self.auto.close_midi();self.stop.set();self.socket.close();self.thread.join(2);self.path.unlink(missing_ok=True);self.pool.shutdown(wait=True,cancel_futures=True)
