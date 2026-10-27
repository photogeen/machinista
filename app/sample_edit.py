"""Process the selection into a new WAV, preserving unselected material."""
import array
from pathlib import Path
import sys
import time
import wave
import subprocess
import tempfile


def process_sample(track,operation,folder,clipboard=None):
    with wave.open(track['sample'], 'rb') as wav:
        channels,width,rate,total=wav.getnchannels(),wav.getsampwidth(),wav.getframerate(),wav.getnframes()
        start=max(0,track.get('selection_start',track['start']))
        end=min(track.get('selection_end',track['end']),total)
        if channels not in (1,2) or width not in (1,2,3,4) or start>=end or total*channels*width>32*1024*1024:
            raise ValueError('unsupported, empty or oversized sample')
        raw=wav.readframes(total)
    values=[]
    for i in range(0,len(raw),width):
        data=raw[i:i+width]
        values.append((data[0]-128)/128 if width==1 else int.from_bytes(data,'little',signed=True)/(1<<(width*8-1)))
    selected=values[start*channels:end*channels]
    if operation in ('COPY','CUT'):
        if clipboard is None:raise ValueError('clipboard unavailable')
        clip=Path(clipboard);clip.parent.mkdir(parents=True,exist_ok=True)
        clipvalues=array.array('h',[max(-32768,min(32767,round(v*32768))) for v in selected])
        if sys.byteorder!='little':clipvalues.byteswap()
        with wave.open(str(clip),'wb') as w:w.setparams((channels,2,rate,0,'NONE','not compressed'));w.writeframes(clipvalues.tobytes())
        if operation=='COPY':return Path(track['sample']),total
        values=values[:start*channels]+values[end*channels:];selected=[]
    elif operation=='PASTE':
        if clipboard is None:raise ValueError('clipboard empty')
        with wave.open(str(clipboard),'rb') as w:
            if w.getnchannels()!=channels or w.getframerate()!=rate:raise ValueError('clipboard format differs')
            data=array.array('h');data.frombytes(w.readframes(w.getnframes()))
            if sys.byteorder!='little':data.byteswap()
            selected=[v/32768 for v in data]
        values=values[:start*channels]+selected+values[start*channels:]
    elif operation=='DUPLICATE':values=values[:end*channels]+selected+values[end*channels:]
    elif operation=='STRETCH':
        ratio=track.get('stretch_ratio',100)/100
        if not .1<=ratio<=10:raise ValueError('invalid stretch ratio')
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'in.wav';target=Path(temp)/'out.wav'
            data=array.array('h',[max(-32768,min(32767,round(v*32768))) for v in selected])
            if sys.byteorder!='little':data.byteswap()
            with wave.open(str(source),'wb') as w:w.setparams((channels,2,rate,0,'NONE','not compressed'));w.writeframes(data.tobytes())
            subprocess.run(['rubberband','-q','-t',str(ratio),'-p',str(track.get('stretch_pitch',0)),str(source),str(target)],check=True,timeout=120,capture_output=True)
            with wave.open(str(target),'rb') as w:
                data=array.array('h');data.frombytes(w.readframes(w.getnframes()))
                if sys.byteorder!='little':data.byteswap()
                selected=[v/32768 for v in data]
        values=values[:start*channels]+selected+values[end*channels:]
    elif operation=='NORMALIZE':
        peak=max(abs(v) for v in selected)
        if peak:selected=[v/peak for v in selected]
    elif operation=='REVERSE':
        frames=[selected[i:i+channels] for i in range(0,len(selected),channels)]
        selected=[v for frame in reversed(frames) for v in frame]
    elif operation in ('FADE IN','FADE OUT'):
        frames=end-start
        selected=[v*((i//channels)/max(1,frames-1) if operation=='FADE IN' else 1-(i//channels)/max(1,frames-1)) for i,v in enumerate(selected)]
    elif operation=='FIX DC':
        means=[sum(selected[c::channels])/(end-start) for c in range(channels)]
        selected=[v-means[i%channels] for i,v in enumerate(selected)]
    elif operation=='SILENCE':selected=[0.0]*len(selected)
    elif operation!='TRUNCATE':raise ValueError('unsupported processing')
    if operation=='TRUNCATE':values=selected
    elif operation not in ('CUT','PASTE','DUPLICATE','STRETCH'):values=values[:start*channels]+selected+values[end*channels:]
    if not values:raise ValueError('operation would create empty sample')
    output=array.array('h',[max(-32768,min(32767,round(v*32768))) for v in values])
    if sys.byteorder!='little':output.byteswap()
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    path=folder/f'{operation.replace(" ","-")}-{time.time_ns()}.wav'
    with wave.open(str(path),'wb') as wav:
        wav.setnchannels(channels);wav.setsampwidth(2);wav.setframerate(rate);wav.writeframes(output.tobytes())
    return path,len(values)//channels
