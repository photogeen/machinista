"""Web-side Sound editor jobs and trusted sample asset resolution."""
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
import copy
import json
from pathlib import Path
import threading
from app.sound_library import SoundLibrary,MAX_JSON,folders,worker_priority
from app.sound_runtime import request

class Sounds:
    def __init__(self,library):
        self.library=library;self.store=SoundLibrary(library.root);self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='web-sounds',initializer=worker_priority);self.future=None;self.last={'state':'IDLE'};self.sequence=0;self.guard=threading.Lock()
    def runtime(self):
        try:return request(self.library.root,'status')
        except (OSError,ValueError):return {'available':False,'busy':False,'message':'Controller engine unavailable.'}
    def status(self):
        with self.guard:
            if self.future and self.future.done():
                try:result=self.future.result();self.last={'state':'DONE','id':result['id'],'message':'Sound saved.','sequence':self.sequence}
                except Exception as e:self.last={'state':'ERROR','message':str(e),'sequence':self.sequence}
                self.future=None
        return dict(**self.store.scan(),job=self.last,busy=self.future is not None)
    @contextmanager
    def asset(self,ref):
        if not isinstance(ref,dict):raise ValueError('Invalid sample reference.')
        if 'sound' in ref:
            with self.store.opened_asset(ref['sound'],ref.get('path')) as stream:yield stream
        elif 'source' in ref:
            source=self.library.source(ref['source'])
            from app.web_server import filename
            filename(ref.get('name',''))
            if Path(ref['name']).suffix.lower()!='.wav':raise ValueError('Use WAV samples; MP3 uploads are converted in Sample Library.')
            import os,stat
            with self.library.directory(source,ref.get('path','')) as fd:child=os.open(ref['name'],os.O_RDONLY|os.O_NOFOLLOW,dir_fd=fd)
            with os.fdopen(child,'rb') as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):raise ValueError('Not a sample file.')
                yield stream
        elif 'current' in ref:
            # Never trust arbitrary client filesystem paths. The reference must
            # match a zone in the engine's fresh selected-Sound snapshot.
            context=self.runtime();zones=context.get('zones',[]);p=ref['current']
            if not any(z.get('sample')==p for z in zones):raise ValueError('Current Sound changed; refresh it.')
            with self.library.projects.opened(p,self.library.projects.roots()+[self.library.root/'presets',self.library.root/'cache']) as stream:yield stream
        else:raise ValueError('Invalid sample reference.')
    def info(self,ref):
        import wave
        with self.asset(ref) as stream,wave.open(stream,'rb') as wav:
            return dict(frames=wav.getnframes(),rate=wav.getframerate(),channels=wav.getnchannels(),width=wav.getsampwidth())
    def save(self,draft):
        if not self.library.upload_lock.acquire(blocking=False):raise BlockingIOError('Another upload or save is in progress.')
        with self.guard:
            if self.future is not None:self.library.upload_lock.release();raise BlockingIOError('A Sound save is already in progress.')
            self.sequence+=1;self.last={'state':'SAVING','message':'Collecting samples.','sequence':self.sequence}
            def work():
                try:return self.store.save(copy.deepcopy(draft),self.asset)
                finally:self.library.upload_lock.release()
            self.future=self.pool.submit(work)
        return {'ok':True}
    def current(self):
        context=self.runtime()
        if not context.get('available'):raise ValueError('Controller engine unavailable.')
        if context['plugins']:raise ValueError('Save current Sound / LV2 patch first, then edit its saved zones to preserve the plug-in strip.')
        result=dict(name=context['name'],folder='',tags=[],sampler=context['sampler'],zones=copy.deepcopy(context['zones']),plugins=context['plugins'],context=context)
        for zone in result['zones']:zone['asset']={'current':zone.pop('sample')}
        return result
    def command(self,operation,value):return request(self.library.root,operation,**value)
