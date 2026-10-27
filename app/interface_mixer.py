"""Selected-device ALSA simple mixer. All hardware I/O runs in one worker.

No stored defaults are applied on discovery. ALSA owns these hardware values;
channel gains are linked when edited, while switches are separate controls.
"""
import os
import math
import queue
import re
import subprocess
import threading
from pathlib import Path
from app.devices import usb_identity, hat_identity


def context(device):
    return (device.key,device.playback) if device else None


def verified_card(device):
    if not device:raise ValueError('NO AUDIO DEVICE')
    match=re.fullmatch(r'plughw:(\d+),(\d+)',device.playback)
    if not match:raise ValueError('UNSUPPORTED AUDIO DEVICE')
    card,pcm=match.groups()
    identity=usb_identity(Path('/sys/class/sound')/f'card{card}'/'device') if device.transport=='USB' else hat_identity(Path('/proc/asound')/f'card{card}')
    if not identity or device.key!=f'{identity[0]}:pcm{pcm}' or not (Path('/proc/asound')/f'card{card}'/f'pcm{pcm}p').exists():
        raise ValueError('AUDIO DEVICE CHANGED')
    return card


def parse_controls(contents):
    result=[]
    for block in re.split(r"(?=^Simple mixer control )",contents,flags=re.M):
        header=re.match(r"Simple mixer control '(.*)',(\d+)\n",block)
        if not header:continue
        name,index=header.groups()
        # amixer's simple ID accepts quoted names; don't construct an ambiguous ID.
        if "'" in name and '"' in name:continue
        caps=re.search(r'^\s*Capabilities: (.*)$',block,re.M)
        if not caps:continue
        caps=caps[1].split()
        for direction,prefix in (('Playback','p'),('Capture','c')):
            volume=prefix+'volume' in caps or 'volume' in caps
            switch=prefix+'switch' in caps or 'switch' in caps
            limit_line=re.search(r'^\s*Limits: (.*)$',block,re.M)
            limits=re.search(direction+r'\s+(-?\d+)\s+-\s+(-?\d+)',limit_line[1]) if limit_line else None
            if not limits and limit_line:limits=re.fullmatch(r'(-?\d+)\s+-\s+(-?\d+)',limit_line[1])
            step=max(1,math.ceil(100/max(1,int(limits[2])-int(limits[1])))) if limits else 1
            channels=[]
            for line in block.splitlines():
                # Channel names may contain spaces; volume/switch brackets follow.
                match=re.match(r'^\s+([^:]+):\s+(?:(Playback|Capture)\s+)?(-?\d+)?\s*((?:\[[^\]]*\]\s*)+)$',line)
                if not match or match[2] and match[2]!=direction:continue
                percent=re.search(r'\[(\d+)%\]',match[4]);db=re.search(r'\[([^\]]*dB)\]',match[4]);state=re.search(r'\[(on|off)\]',match[4])
                channels.append((match[1].strip(),int(percent[1]) if percent else None,db[1] if db else '',state[1] if state else None))
            if not channels:continue
            for kind,available in (('level',volume),('switch',switch)):
                values=[c[1] if kind=='level' else c[3]=='on' for c in channels if c[1 if kind=='level' else 3] is not None]
                if not available or not values:continue
                result.append(dict(id=(name,int(index),direction,kind),name=name+(f' {int(index)+1}' if index!='0' else ''),direction=direction,kind=kind,
                                   value=round(sum(values)/len(values)) if kind=='level' else int(all(values)),
                                   step=step if kind=='level' else 1,values=values,db=tuple(c[2] for c in channels if c[2]) if kind=='level' else ()))
    return result


def value_text(control):
    if control['kind']=='switch':return 'ON' if control['value'] else 'OFF'
    values=control.get('values',[control['value']]);lo,hi=min(values),max(values)
    return f'{lo} - {hi}%' if lo!=hi else f'{control["value"]}%'


def db_text(control):
    values=tuple(dict.fromkeys(control.get('db',())))
    if len(values)<2:return ''.join(values)
    try:return '/'.join(f'{float(value[:-2]):g}' for value in values)+'dB'
    except ValueError:return ' / '.join(values)


def run(device,*args):
    card=verified_card(device)
    output=subprocess.run(['amixer','-c',card,*args],check=True,timeout=2,text=True,
                          stdout=subprocess.PIPE,stderr=subprocess.PIPE,env={**os.environ,'LC_ALL':'C'}).stdout
    verified_card(device)
    return output


def read_controls(device):
    return parse_controls(run(device,'scontents'))


def set_control(device,identifier,value):
    name,index,direction,kind=identifier
    quote='"' if "'" in name else "'"
    simple_id=f'{quote}{name}{quote},{index}'
    value=max(0,min(100 if kind=='level' else 1,int(value)))
    # The direction modifier keeps capture and playback on the same simple
    # control independent. Switch edits never implicitly change volume.
    target=f'{value}%' if kind=='level' else ('on' if value else 'off')
    run(device,'sset',simple_id,direction.lower(),target)


class InterfaceMixer:
    def __init__(self):
        self.condition=threading.Condition();self.device=None;self.revision=0
        self.pending={};self.scan=False;self.stopped=False;self.next_scan=0
        self.results=queue.SimpleQueue()
        self.thread=threading.Thread(target=self._run,name='interface-mixer',daemon=True);self.thread.start()

    def update(self,device,now,visible):
        with self.condition:
            if context(device)!=context(self.device):
                self.device=device;self.revision+=1;self.pending.clear();self.scan=False;self.next_scan=0
            if visible and device and now>=self.next_scan:
                self.scan=True;self.next_scan=now+2;self.condition.notify()

    def submit(self,device,identifier,value):
        with self.condition:
            if context(device)!=context(self.device) or not device:return
            self.revision+=1;self.pending[tuple(identifier)]=value;self.condition.notify()

    def _run(self):
        while True:
            with self.condition:
                self.condition.wait_for(lambda:self.stopped or self.scan or self.pending)
                if self.stopped:return
                device,revision=self.device,self.revision
                pending=self.pending;self.pending={};self.scan=False
            error='';controls=[]
            try:
                for identifier,value in pending.items():set_control(device,identifier,value)
                controls=read_controls(device)
            except ValueError as exc:error=str(exc)
            except (OSError,subprocess.SubprocessError):error='MIXER UNAVAILABLE'
            self.results.put((context(device),revision,controls,error))

    def poll(self):
        latest=None
        while not self.results.empty():
            result=self.results.get()
            if result[:2]==(context(self.device),self.revision):latest=result
        return latest

    def close(self):
        with self.condition:self.stopped=True;self.condition.notify()
        self.thread.join(timeout=.1)
