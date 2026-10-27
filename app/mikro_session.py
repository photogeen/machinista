"""Optional legacy surface session, independent of the shared audio engine."""
import os
from pathlib import Path
import subprocess
import threading
from app.branding import BootSplash,boot_frame
from app.controller_output import ControllerOutput
from app.connection_health import output_stalled,ReaderWatch,surface_status


def model_for_path(path):
    try:data=(Path('/sys/class/hidraw')/Path(path).name/'device/uevent').read_text()
    except OSError:return 'mikro'
    return 'mikro_mk2' if 'HID_ID=0003:000017CC:00001200' in data else 'mikro'

class MikroSession:
    def __init__(self,root,app,inputs,open_device,pack,send,configure,path=None):
        self.root,self.app,self.inputs=Path(root),app,inputs
        self.model='mikro';self.channels=None
        self.open_device,self.pack,self.send,self.configure=open_device,pack,send,configure
        self.path=path;self.process=self.output=None;self.fd=None;self.next_scan=0
        self.cleanup=[];self.frames=0;self.max_ms=0.;self.total_ms=0.
        self.last_frame=self.last_leds=None
        self.boot=BootSplash();self.reader_watch=ReaderWatch(report_limit=5)

    def lost(self,streams):
        self.reader_watch.stop()
        self.inputs.disconnect('mikro')
        process,output,fd=self.process,self.output,self.fd
        self.process=self.output=None;self.fd=None
        if process:
            streams.pop(process.stdout,None);process.stdout.close()
        def cleanup():
            try:
                if process:
                    if process.poll() is None:process.terminate()
                    try:process.wait(timeout=.5)
                    except subprocess.TimeoutExpired:process.kill();process.wait(timeout=.5)
                if output:
                    output.close();output.thread.join();self.frames+=output.frames
                    self.max_ms=max(self.max_ms,output.max_ms);self.total_ms+=output.total_ms
            finally:
                if fd is not None:os.close(fd)
        if any(x is not None for x in (process,output,fd)):
            self.cleanup=[t for t in self.cleanup if t.is_alive()]
            thread=threading.Thread(target=cleanup,name='mikro-cleanup',daemon=True)
            self.cleanup.append(thread);thread.start()

    def poll(self,now,streams):
        if self.boot.expired(now):self.dismiss_boot()
        if self.process and (self.process.poll() is not None or self.output.error or output_stalled(self.output,now) or self.reader_watch.expired(now)):
            print('Mikro disconnected; audio continues '+str(surface_status(self,now)),flush=True);self.lost(streams);self.next_scan=now+2
        if self.process or now<self.next_scan:return
        self.next_scan=now+2
        self.cleanup=[t for t in self.cleanup if t.is_alive()]
        if self.cleanup:return
        paths=[self.path] if self.path else []
        if not self.path:
            for hid in sorted(Path('/sys/class/hidraw').glob('hidraw*')):
                try:
                    if any(token in (hid/'device/uevent').read_text() for token in ('HID_ID=0003:000017CC:00001110','HID_ID=0003:000017CC:00001200')):paths.append(str(Path('/dev')/hid.name))
                except OSError:continue
        for path in paths:
            try:
                mk2=model_for_path(path)=='mikro_mk2'
                if mk2:
                    from app.mikro_mk2_protocol import open_device,send
                    from tools.mikro_leds import load_pad_channels
                    self.fd=open_device(path)
                    self.channels=load_pad_channels(self.root/'captures/mikro-mk1-pad-led-map.json')
                else:self.fd=self.open_device(path);send=self.send
                self.model='mikro_mk2' if mk2 else 'mikro';self.app.mikro_model=self.model
                self.output=ControllerOutput(self.fd,self.pack,send,self.configure)
                self.apply_settings()
                self.boot.start(now)
                if self.last_leds or self.last_frame:
                    self.output.submit(boot_frame(128),self.encode_leds(self.last_leds or self.last_frame[1]))
                if self.last_leds:self.output.submit_leds(self.encode_leds(self.last_leds))
                self.process=subprocess.Popen([str(self.root/'build/mikro_monitor'),'--live',path,'0'],stdout=subprocess.PIPE)
                self.reader_watch.start(now)
                os.set_blocking(self.process.stdout.fileno(),False);streams[self.process.stdout]=b''
                print(('Mikro MK2' if mk2 else 'Mikro MK1')+' connected: '+path,flush=True);return
            except (OSError,ValueError) as error:
                print('Mikro connect: '+str(error),flush=True);self.lost(streams)

    def submit(self,*args):
        self.last_frame=tuple(bytes(arg) for arg in args)
        try:
            if self.output and not self.output.error:self.output.submit(boot_frame(128) if self.boot.active() else args[0],self.encode_leds(args[1]))
        except OSError:pass  # poll handles the optional session failure.
    def dismiss_boot(self):
        self.boot.dismiss()
        try:
            if self.output and not self.output.error and self.last_frame:self.output.submit(self.last_frame[0],self.encode_leds(self.last_frame[1]))
        except OSError:pass
    def submit_leds(self,*args):
        self.last_leds=bytes(args[0])
        try:
            if self.output and not self.output.error:self.output.submit_leds(self.encode_leds(args[0]))
        except OSError:pass
    def encode_leds(self,leds):
        if self.model!='mikro_mk2':return leds
        from app.mikro_mk2_protocol import led_report
        return led_report(leds,self.channels,self.app.button_led_map,self.app.group)
    def apply_settings(self):
        from app.controller_settings import mikro_display_settings
        self.display_settings(*mikro_display_settings(self.app))
    def display_settings(self,*args):
        try:
            if self.output and not self.output.error:self.output.display_settings(*args)
        except OSError:pass
    def close(self,streams):
        self.lost(streams)
        for thread in self.cleanup:thread.join(timeout=2)
