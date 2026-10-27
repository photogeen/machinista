"""Full-size MK1: independent USB process, eight knobs and dedicated masters."""
import os,sys,subprocess,time,threading,select
from pathlib import Path
from app.mk2_session import Mk2Session
from app.mk2_surface import Mk2Surface,Field
from app.mk2_display import snapshot,leds
from app.controller_renderer import ProcessRenderer as Mk2Renderer
from app.mk2_protocol import LED_BUTTONS,TRANSPORT,PAD_SLOTS
from app.mk1_protocol import init_packets,frame_packets,pack_frame,led_packets
from app.controller_settings import on_controller

class Mk1Surface(Mk2Surface):
    source='mk1'
    @on_controller('mk1')
    def fields(self):
        fields=list(super().fields());a=self.app
        if not any(fields):
            selection={'SAMPLE DELETE':getattr(a,'sample_delete_index',0),'NAVIGATE':a.nav_index,
                'RELINK BROWSE':a.relink_browser.index if a.relink_browser else 0}
            if a.page in selection:fields[0]=Field('SELECT',str(selection[a.page]+1),(('_utility',True),))
        return tuple(fields)
    def confirm_action(self):
        """Visible alternative to the MK2 master push / ENTER hardware."""
        page=self.app.page
        if page=='SETTINGS':return ('OPEN','ENTER')
        if page=='PLUGIN BROWSE':return ('REMOVE' if self.app.plugin_browser_index<0 else 'LOAD','F2')
        return {'PROJECT LOAD':('LOAD','ENTER'),'PROJECT MANAGE':('OPEN','F2'),
            'PRESET LOAD':('LOAD','F2'),'PROJECT NAME':('OK','F3'),
            'RELINK RESULTS':('SELECT','F2'),'RELINK BROWSE':('OPEN','F2'),
            'SAMPLE DELETE':('OK','ENTER'),'NAVIGATE':('OPEN','F2'),
            'PLUGIN MOVE':('MOVE','F3'),'PLUGIN SC':('BACK','F1'),
            'MACRO ASSIGN':('ASSIGN','ENTER')}.get(page)
    def softkeys(self):
        keys=list(super().softkeys());action=self.confirm_action()
        if action and not keys[7]:keys[7]=action[0]
        if self.app.page=='PLUGIN' and self.app.shift:
            plugin=self.app.plugin_selected()
            meta=self.app.plugin_metadata(plugin['uri']) if plugin else None
            if meta and meta.get('sidechain'):keys[7]='SC INPUT'
        return tuple(keys)
    @on_controller('mk1')
    def softkey(self,index):
        if index==7:
            if self.app.page=='PLUGIN' and self.app.shift and self.softkeys()[7]=='SC INPUT':
                self.app.page='PLUGIN SC';return
            action=self.confirm_action()
            if action and not super().softkeys()[7]:
                # Confirmation is independent of SHIFT (ENTER+SHIFT is tap tempo).
                shifted=self.app.shift;self.app.shift=False
                try:self.tap(action[1])
                finally:self.app.shift=shifted
                return
        return super().softkey(index)
    @on_controller('mk1')
    def rotate(self,index,delta):
        if index<=8:return super().rotate(index,delta)
        if index not in (9,10,11):raise ValueError('invalid MK1 encoder')
        self.master_mode={9:'VOLUME',10:'SWING',11:'TEMPO'}[index]
        self.master_page=self.app.page
        return super().rotate(0,delta)

class Mk1Output:
    def __init__(self,process,renderer,settings):
        self.process,self.render=process,renderer
        self.condition=threading.Condition();self.pending=self.pending_leds=None
        self.settings=dict(settings);self.settings_pending=True;self.last_snapshot=None
        self.hardware_values=None;self.closing=False;self.error=None;self.busy_since=None;self.frames=0;self.last={}
        os.set_blocking(process.stdin.fileno(),False)
        self.thread=threading.Thread(target=self.run,name='mk1-output',daemon=True);self.thread.start()
    def submit(self,state):
        with self.condition:
            if self.closing or self.error:return False
            if state==self.last_snapshot:return True
            self.last_snapshot=state;self.pending=state;self.condition.notify();return True
    def submit_leds(self,reports):
        with self.condition:self.pending_leds=reports;self.condition.notify()
    def display_settings(self,values):
        with self.condition:self.settings=dict(values);self.settings_pending=True;self.condition.notify()
    def send(self,endpoint,packet):
        data=memoryview(f'{endpoint} {packet.hex()}\n'.encode());deadline=time.monotonic()+1
        while data:
            if self.closing:raise InterruptedError('MK1 closing')
            if self.process.poll() is not None:raise OSError('MK1 reader exited')
            try:count=os.write(self.process.stdin.fileno(),data);data=data[count:]
            except BlockingIOError:
                if time.monotonic()>deadline:raise OSError('MK1 USB output backlog')
                select.select([], [self.process.stdin.fileno()],[],.01)
    def output_leds(self,reports):
        mono,group,pad=reports;values={}
        for i,name in enumerate(LED_BUTTONS):values[name]=mono[i+1]
        for i,name in enumerate(TRANSPORT):values[name]=group[49+i]
        for raw,slot in enumerate(PAD_SLOTS):values[f'PAD {slot+1}']=max(pad[1+raw*3:4+raw*3])
        for i,letter in enumerate('ABCDEFGH'):values['GROUP '+letter]=max(group[1+i*6:4+i*6])
        from app.mk1_protocol import LED_NAMES
        values={k:v for k,v in values.items() if k in LED_NAMES}
        values['BACKLIGHT']=round(self.settings.get('brightness',72)*127/100)
        for i,packet in enumerate(led_packets(values)):
            if packet!=self.last.get(('led',i)):self.send(1,packet);self.last['led',i]=packet
    def run(self):
        try:
            try:os.setpriority(os.PRIO_PROCESS,threading.get_native_id(),10)
            except OSError:pass
            self.busy_since=time.monotonic()
            for display in (0,1):
                for packet in init_packets(display):self.send(8,packet);time.sleep(.02)
            self.send(1,bytes((11,1,10,5)))
            self.busy_since=None
            while not self.closing:
                with self.condition:
                    self.condition.wait_for(lambda:self.closing or self.pending is not None or self.pending_leds is not None or self.settings_pending,timeout=.1)
                    if self.closing:return
                    state,reports=self.pending,self.pending_leds;self.pending=self.pending_leds=None
                    changed=self.settings_pending;self.settings_pending=False
                    if state is None and self.render.needs_refresh:state=self.last_snapshot
                self.busy_since=time.monotonic()
                try:
                    if changed:
                        for display,key in enumerate(('contrast_left','contrast_right')):
                            value=round(self.settings.get(key,29)*127/100)
                            self.send(8,bytes((display*2,0,3,0x81,value,2)))
                        self.last={k:v for k,v in self.last.items() if k[0]!='led'}
                    if reports is not None:self.output_leds(reports)
                    if state is not None:
                        for display,pixels in enumerate(self.render(state)):
                            cropped=bytearray(v for y in range(64) for v in pixels[y*256:y*256+255])
                            if cropped==self.last.get(('pixels',display)):continue
                            # Sequential framebuffer protocol: resend entire changed
                            # frame, never skip chunks or replace it halfway through.
                            packed=pack_frame(cropped)
                            if packed==self.last.get(('frame',display)):continue
                            for packet in frame_packets(display,packed):self.send(8,packet)
                            self.last['frame',display]=packed;self.last['pixels',display]=cropped
                        self.frames+=1
                finally:self.busy_since=None
        except Exception as error:
            if not self.closing:self.error=error
    def close(self):
        with self.condition:self.closing=True;self.condition.notify_all()
        self.thread.join(timeout=.5)

class Mk1Session(Mk2Session):
    source='mk1';surface_type=Mk1Surface
    def connect(self,now):
        self.next_scan=now+2
        self.cleanup=[t for t in self.cleanup if t.is_alive()]
        if self.cleanup or not (self.root/'build/mk1_monitor').exists():return
        present=False
        for device in Path('/sys/bus/usb/devices').glob('*'):
            try:
                if (device/'idVendor').read_text().strip()=='17cc' and (device/'idProduct').read_text().strip()=='0808':present=True;break
            except OSError:pass
        if not present:return
        try:
            self.renderer=Mk2Renderer(startup=True)
            self.process=subprocess.Popen([str(self.root/'build/mk1_monitor'),'--midi-manifest',str(self.root/'samples/.mk1-midi.json')],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
            os.set_blocking(self.process.stdout.fileno(),False)
            self.output=Mk1Output(self.process,self.renderer,self.app.settings['controllers']['mk1'])
            self.reader_watch.start(now);self.next_frame=self.next_led=0
            print('Maschine MK1 connected',flush=True)
        except Exception as error:
            print('MK1 connect: '+str(error),flush=True);self.disconnect()
    def rotate_raw(self,index,delta):
        if 1<=index<=8:
            # Analogue MK1 encoders are noisier than the MK2 counters.
            # Three sensor units per MK2 unit gives deliberate, stable travel.
            key=('sensor',index);total=self.encoder_remainders.get(key,0)
            if total*delta<0:total=0
            total+=delta;scaled=int(total/3);self.encoder_remainders[key]=total-scaled*3
            return super().rotate_raw(index,scaled)
        if index not in (9,10,11):return
        key=('master',index);total=self.encoder_remainders.get(key,0)
        if total*delta<0:total=0
        total+=delta;steps=int(total/8);self.encoder_remainders[key]=total-steps*8
        if steps:self.surface.rotate(index,steps)
    def display_settings(self):
        if self.output:self.output.display_settings(self.app.settings['controllers']['mk1'])
