"""Optional MK2 session. Disconnect never terminates the shared engine."""
import json
from collections import deque
import os
from pathlib import Path
import subprocess
import threading
import time
from app.mk2_protocol import open_device
from app.mk2_output import Mk2Output
from app.connection_health import output_stalled,ReaderWatch,surface_status
from app.mk2_settings import configure_displays
from app.controller_settings import seed_mk2_settings
from app.mk2_surface import Mk2Surface
from app.mk2_encoders import quantum,CHOICE_TRAVEL
from app.mk2_display import snapshot,leds
from app.controller_renderer import ProcessRenderer as Mk2Renderer


class Mk2Session:
    source='mk2'
    surface_type=Mk2Surface
    def __init__(self,root,app,inputs,channels):
        self.root,self.app,self.inputs,self.channels=Path(root),app,inputs,channels
        self.surface=self.surface_type(app,inputs)
        self.process=self.output=self.renderer=None;self.fd=None
        self.buffer=b'';self.next_scan=self.next_frame=self.next_led=0
        self.cleanup=[]
        self.input_lags=deque(maxlen=128)
        self.encoder_remainders={}
        self.encoder_context=None;self.reader_watch=ReaderWatch(report_limit=5)

    def disconnect(self):
        self.reader_watch.stop()
        self.surface.disconnect()
        process,output,renderer,fd=self.process,self.output,self.renderer,self.fd
        self.process=self.output=self.renderer=None;self.fd=None
        def cleanup():
            try:
                if process:
                    if process.poll() is None:process.terminate()
                    try:process.wait(timeout=.5)
                    except subprocess.TimeoutExpired:process.kill();process.wait(timeout=.5)
                    process.stdout.close()
                    if process.stdin:process.stdin.close()
                if output:
                    output.close()
                    if output.thread.is_alive() and isinstance(renderer,Mk2Renderer):renderer.close()
                    output.thread.join()  # Detached worker owns fd until it exits.
                if renderer:renderer.close()
            finally:
                if fd is not None:os.close(fd)
        if any(x is not None for x in (process,output,renderer,fd)):
            self.cleanup=[t for t in self.cleanup if t.is_alive()]
            thread=threading.Thread(target=cleanup,name='mk2-cleanup',daemon=True)
            self.cleanup.append(thread);thread.start()
        self.buffer=b''
        self.encoder_remainders.clear();self.encoder_context=None

    def connect(self,now):
        self.next_scan=now+2
        self.cleanup=[t for t in self.cleanup if t.is_alive()]
        if self.cleanup:return
        for hid in sorted(Path('/sys/class/hidraw').glob('hidraw*')):
            try:
                if 'HID_ID=0003:000017CC:00001140' not in (hid/'device/uevent').read_text():continue
                path=str(Path('/dev')/hid.name)
                self.fd=open_device(path);self.renderer=Mk2Renderer(startup=True)
                self.output=Mk2Output(self.fd,self.renderer,configure=configure_displays,settings=self.app.settings['controllers']['mk2'])
                self.process=subprocess.Popen([str(self.root/'build/mk2_monitor'),'--live',path,'0'],stdout=subprocess.PIPE)
                self.reader_watch.start(now)
                os.set_blocking(self.process.stdout.fileno(),False)
                self.next_frame=self.next_led=0
                print('Maschine MK2 connected: '+path,flush=True);return
            except Exception as error:
                print('MK2 connect: '+str(error),flush=True);self.disconnect()

    def poll(self,now):
        if not self.process:
            if now>=self.next_scan:self.connect(now)
            return
        try:
            if output_stalled(self.output,now):raise OSError('MK2 output timeout; reconnecting')
            if self.process.poll() is not None or self.output.error:
                raise OSError('MK2 disconnected' if not self.output.error else str(self.output.error))
            if type(self.output.hardware_values) is dict:seed_mk2_settings(self.app,self.output.hardware_values,self.source)
            try:chunk=os.read(self.process.stdout.fileno(),65536)
            except BlockingIOError:chunk=None
            if chunk==b'':raise OSError('MK2 input closed')
            if chunk:self.buffer+=chunk
            if len(self.buffer)>1024*1024:raise OSError('MK2 input backlog')
            deadline=time.monotonic()+.002
            for _ in range(64):
                if b'\n' not in self.buffer:break
                if time.monotonic()>deadline:break
                line,self.buffer=self.buffer.split(b'\n',1)
                event=json.loads(line)
                if self.reader_watch.receive(event,time.monotonic()):continue
                kind=event['kind'];a=self.app
                if kind in ('button','encoder','pad_on') and self.renderer:self.renderer.dismiss_boot()
                if kind=='encoder':
                    # Drain a continuous turn before expensive project/history
                    # edits. Never combine across reversals, knobs, pads or keys:
                    # those boundaries carry ordering and clamp semantics.
                    for _ in range(512):
                        if b'\n' not in self.buffer or time.monotonic()>deadline:break
                        following,remaining=self.buffer.split(b'\n',1)
                        next_event=json.loads(following)
                        if (next_event.get('kind')!='encoder' or
                            next_event.get('raw_control')!=event['raw_control'] or
                            next_event['value']*event['value']<=0):break
                        self.buffer=remaining
                        event['value']+=next_event['value']
                        event['monotonic_ns']=next_event.get('monotonic_ns',0)
                a.input_timestamp=event.get('monotonic_ns',0)/1e9 or None
                try:
                    if self.handle_event(event):pass
                    elif kind=='button':self.surface.button(event['name'],bool(event['value']))
                    elif kind=='encoder':self.rotate_raw(event['raw_control'],event['value'])
                    elif kind.startswith('pad_'):
                        slot=int(event['name'].split('_')[-1])-1
                        if kind=='pad_on':
                            self.inputs.pad_on(self.source,slot,a.pad_velocity(event['value'],self.source))
                            if a.input_timestamp:self.input_lags.append(max(0,(time.monotonic()-a.input_timestamp)*1000))
                        elif kind=='pad_off':self.inputs.pad_off(self.source,slot)
                        elif kind=='pad_pressure':self.inputs.pad_pressure(self.source,slot,a.pad_velocity(event['value'],self.source))
                finally:a.input_timestamp=None
            if self.reader_watch.expired(now):raise OSError('MK2 reader/USB scan timeout '+str(surface_status(self,now)))
        except Exception as error:
            print('MK2 session: '+str(error),flush=True)
            self.disconnect();self.next_scan=now+2

    def handle_event(self,event):return False

    def rotate_raw(self,index,delta):
        # The eight smooth knobs count 0..999; master counts 0..15.
        # Preserve sub-step travel across reports, but never across bindings.
        if index==0:
            self.surface.rotate(index,delta);return
        if not 1<=index<=8:raise ValueError('invalid MK2 encoder')
        fields=self.surface.fields()
        resolutions=tuple(quantum(self.surface,f) for f in fields)
        selected=self.app.plugin_selected() if self.app.page=='PLUGIN' else None
        selectors=(self.app.plugin_slot,selected['uri'],selected.get('controls',{}).get('bank'),selected.get('controls',{}).get('rhythm')) if selected else None
        context=(self.app.page,self.app.group,self.app.pad,self.app.shift,self.app.control_level,selectors,
                 tuple(None if f is None else (f.label,f.attributes) for f in fields),resolutions)
        travel=resolutions[index-1]
        if fields[index-1] is None and index==8 and self.app.page in ('BROWSE','PLUGIN BROWSE'):travel=CHOICE_TRAVEL
        if context!=self.encoder_context:
            self.encoder_remainders.clear();self.encoder_context=context
        remainder=self.encoder_remainders.get(index,0)
        if remainder*delta<0:remainder=0  # Reversing must respond immediately.
        total=remainder+delta
        steps=(abs(total)//travel)*(1 if total>=0 else -1)
        self.encoder_remainders[index]=total-steps*travel
        if steps:self.surface.rotate(index,steps)

    def display_settings(self):
        if self.output:self.output.display_settings(self.app.settings['controllers']['mk2'])

    def update(self,now):
        if not self.output:return
        try:
            if now>=self.next_led:
                self.output.submit_leds(leds(self.surface,self.channels,now));self.next_led=now+.05
            if now>=self.next_frame:
                self.output.submit(snapshot(self.surface));self.next_frame=now+.05
        except Exception as error:
            print('MK2 display snapshot: '+str(error),flush=True)
            self.disconnect();self.next_scan=now+2

    def close(self):
        self.disconnect()
        for thread in self.cleanup:thread.join(timeout=2)
