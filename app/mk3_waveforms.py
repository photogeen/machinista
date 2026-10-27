"""MK3-only waveform preparation; PCM work stays in a low-priority worker.

Keep a pad-bank worth of small assets within the existing72MiB PCM budget and
reuse display envelopes during cursor-only refreshes. No application/audio I/O.
"""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import wave
from app.waveform import Envelope
from app.waveform_index import WaveformIndex

class Mk3Waveforms:
    def __init__(self):
        self.worker=ThreadPoolExecutor(max_workers=1,thread_name_prefix='mk3-wave-index')
        self.cache=OrderedDict();self.views=OrderedDict();self.future=None;self.loading_key=None
        self.budget=72*1024*1024;self.revision=0
    def collect(self):
        if self.future is None or not self.future.done():return
        try:result=self.future.result()
        except (OSError,ValueError,wave.Error,EOFError):result=None
        self.cache[self.loading_key]=result;self.future=None;self.revision+=1
        while len(self.cache)>1 and (len(self.cache)>16 or sum(v.nbytes for v in self.cache.values() if v)>self.budget):
            key,_=self.cache.popitem(last=False)
            self.views=OrderedDict((k,v) for k,v in self.views.items() if k[0]!=key)
    def key(self,path):
        if not path:return None
        try:metadata=Path(path).stat()
        except OSError:return None
        return str(path),metadata.st_mtime_ns,metadata.st_size
    def prepare(self,key,path):
        if key in self.cache:self.cache.move_to_end(key)
        elif self.future is None:
            self.loading_key=key;self.future=self.worker.submit(WaveformIndex,path)
    def prefetch(self,path):
        self.collect();key=self.key(path)
        if key is not None:self.prepare(key,path)
    def envelope(self,path,start=0,end=None,columns=120):
        self.collect();key=self.key(path)
        if key is None:return Envelope(0,()) if path else None
        self.prepare(key,path)
        if key not in self.cache:return None
        index=self.cache[key]
        if index is None:return Envelope(0,())
        view=(key,start,end,columns)
        if view not in self.views:
            self.views[view]=index.envelope(start,end,columns)
            if len(self.views)>64:self.views.popitem(last=False)
        else:self.views.move_to_end(view)
        return self.views[view]
    def close(self):self.worker.shutdown(wait=True,cancel_futures=True)
