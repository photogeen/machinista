"""Reusable, bounded PCM display index; scrolling never rereads a WAV.

Only the MK2 display worker queries this index. File loading and construction
run in a separate worker; the audio/input dispatcher never receives PCM data.
"""
import array
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
import sys
import threading
import wave
from app.waveform import Envelope


class WaveformIndex:
    block=256

    def __init__(self,path):
        try:os.setpriority(os.PRIO_PROCESS,threading.get_native_id(),10)
        except (AttributeError,OSError):pass
        with wave.open(str(path),'rb') as wav:
            self.width,self.channels,self.frames=wav.getsampwidth(),wav.getnchannels(),wav.getnframes()
            if self.width not in (1,2,3,4) or self.channels not in (1,2) or self.frames>8*1024*1024:
                raise ValueError('unsupported or oversized display sample')
            data=wav.readframes(self.frames)
        self.pcm=array.array({1:'B',2:'h',3:'i',4:'i'}[self.width])
        if self.width==3:
            self.pcm.extend(int.from_bytes(data[i:i+3],'little',signed=True) for i in range(0,len(data),3))
        else:
            self.pcm.frombytes(data)
            if self.width>1 and sys.byteorder!='little':self.pcm.byteswap()
        if len(self.pcm)!=self.frames*self.channels:raise ValueError('truncated display sample')
        self.low=array.array('i');self.high=array.array('i')
        stride=self.block*self.channels
        for i in range(0,len(self.pcm),stride):
            values=self.pcm[i:i+stride];self.low.append(min(values));self.high.append(max(values))

    @property
    def nbytes(self):
        return sum(len(a)*a.itemsize for a in (self.pcm,self.low,self.high))

    def envelope(self,start=0,end=None,columns=120):
        start=max(0,min(self.frames,start));end=self.frames if end is None else max(start,min(self.frames,end))
        peaks=[];c=self.channels;b=self.block
        for column in range(columns):
            first=start+(end-start)*column//columns;last=start+(end-start)*(column+1)//columns
            if first==last:peaks.append((0.0,0.0));continue
            lo=(first+b-1)//b;hi=last//b
            if lo>=hi:
                values=self.pcm[first*c:last*c];minimum,maximum=min(values),max(values)
            else:
                minimum,maximum=min(self.low[lo:hi]),max(self.high[lo:hi])
                edges=self.pcm[first*c:lo*b*c]+self.pcm[hi*b*c:last*c]
                if edges:minimum,maximum=min(minimum,min(edges)),max(maximum,max(edges))
            if self.width==1:minimum-=128;maximum-=128
            divisor=1<<(self.width*8-1);peaks.append((minimum/divisor,maximum/divisor))
        return Envelope(self.frames,tuple(peaks),start,end)


class IndexedWaveforms:
    def __init__(self):
        self.worker=ThreadPoolExecutor(max_workers=1,thread_name_prefix='mk2-wave-index')
        self.cache=OrderedDict();self.future=None;self.loading_key=None
        self.budget=72*1024*1024

    def envelope(self,path,start=0,end=None,columns=120):
        if self.future and self.future.done():
            try:result=self.future.result()
            except (OSError,ValueError,wave.Error,EOFError):result=None
            self.cache[self.loading_key]=result;self.future=None
            while len(self.cache)>1 and (len(self.cache)>2 or sum(v.nbytes for v in self.cache.values() if v)>self.budget):
                self.cache.popitem(last=False)
        if not path:return None
        try:metadata=Path(path).stat()
        except OSError:return Envelope(0,())
        key=(str(path),metadata.st_mtime_ns,metadata.st_size)
        if key in self.cache:
            self.cache.move_to_end(key);index=self.cache[key]
            return index.envelope(start,end,columns) if index else Envelope(0,())
        if self.future is None:
            self.loading_key=key;self.future=self.worker.submit(WaveformIndex,path)
        return None

    def close(self):self.worker.shutdown(wait=True,cancel_futures=True)
