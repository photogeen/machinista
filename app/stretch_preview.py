"""Offline Stretch audition: coalesce requests, never replace project assets."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import copy
import tempfile
import wave
from app.sample_edit import process_sample
from app.audio import convert_sample

def stretch_parameters(track,context):
    return tuple(context)+(str(track['sample']),track['start'],track['end'],track.get('selection_start',track['start']),track.get('selection_end',track['end']),track.get('stretch_ratio',100),track.get('stretch_pitch',0))

def stretch_key(track,context):
    stat=Path(track['sample']).stat()
    return stretch_parameters(track,context)+(stat.st_mtime_ns,stat.st_size)

def render_stretch_preview(track,folder):
    if track.get('stretch_ratio',100)==100 and track.get('stretch_pitch',0)==0:
        return dict(track,zones=[],sampler={})
    path,frames=process_sample(track,'STRETCH',folder)
    with wave.open(track['sample'],'rb') as wav:delta=frames-wav.getnframes()
    end=track['end']+delta
    if not 0<=track['start']<end<=frames:raise ValueError('empty stretch preview')
    return dict(track,sample=str(path),start=track['start'],end=end,zones=[],sampler={})

def prepare_stretch_preview(track,folder):
    preview=render_stretch_preview(track,folder)
    with wave.open(preview['sample'],'rb') as wav:frames=wav.getnframes()
    with tempfile.NamedTemporaryFile(suffix='.f32',dir=folder,delete=False) as output:path=output.name
    rate=convert_sample(dict(preview,start=0,end=frames),path)
    return dict(preview,_preview_pcm=path,_preview_rate=rate,
                _wave_source=(str(track['sample']),track['start'],track['end'],preview['start'],preview['end']))

class StretchPreview:
    def __init__(self,cache):
        Path(cache).mkdir(parents=True,exist_ok=True)
        self.folder=tempfile.TemporaryDirectory(prefix='stretch-preview-',dir=cache)
        self.worker=ThreadPoolExecutor(max_workers=1,thread_name_prefix='stretch-preview')
        self.pending=None;self.queued=None;self.latest=None;self.cached={}
    def request(self,track,context,velocity):
        key=stretch_key(track,context);self.latest=key
        if key in self.cached:
            self.queued=None;return self.cached[key],velocity
        request=(key,copy.deepcopy(track),velocity)
        if self.pending:self.queued=request
        else:self._start(request)
        return None
    def _start(self,request):
        key,track,velocity=request
        self.pending=(key,velocity,self.worker.submit(prepare_stretch_preview,track,self.folder.name))
    def cancel(self):self.latest=None;self.queued=None
    def active_key(self,track,context):
        return self.latest if self.latest and self.latest[:-2]==stretch_parameters(track,context) else None
    def poll(self,active_key):
        if active_key!=self.latest:self.cancel()
        result=None
        if self.pending and self.pending[2].done():
            key,velocity,future=self.pending;self.pending=None
            try:
                rendered=future.result();self.cached[key]=rendered
                # Files live until engine shutdown; its load commands may still read them.
                while len(self.cached)>4:self.cached.pop(next(iter(self.cached)))
                if key==self.latest:result=(rendered,velocity,None)
            except Exception as error:
                if key==self.latest:result=(None,velocity,error)
            if self.queued:
                request=self.queued;self.queued=None
                if request[0] in self.cached:
                    if request[0]==self.latest:result=(self.cached[request[0]],request[2],None)
                else:self._start(request)
        return result
    def close(self):self.cancel();self.worker.shutdown(wait=True,cancel_futures=True)
    def cleanup(self):self.folder.cleanup()
