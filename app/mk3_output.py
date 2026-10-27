"""Coalesced MK3 output; color USB drawing never blocks input dispatch."""
import os
from app.mk2_output import Mk2Output
from app.mk3_usb import DisplayUSB
from app.mk3_frame_encoder import DisplayFrame
from app.mk3_protocol import display_packet,configure_displays

class Mk3Output(Mk2Output):
    def __init__(self,fd,render,settings,product=0x1600,interface=5):
        self.product,self.interface=product,interface
        self.usb=None;self.usb_bytes=self.usb_packets=0;self.performance={};self.display_updates=0
        super().__init__(fd,render,write=lambda fd,data: self.write_hid(fd,data),configure=configure_displays,settings=settings)
    @staticmethod
    def write_hid(fd,data):
        if os.write(fd,data)!=len(data):raise OSError('Short MK3 LED write')
    def changed_frame(self,display,pixels):
        if pixels is None:return
        if isinstance(pixels,DisplayFrame):
            if self.closing:return
            self.usb.send(pixels.packet);self.usb_bytes+=len(pixels.packet);self.usb_packets+=1
            return
        previous=self.last.get(('pixels',display))
        if previous==pixels:return
        # Hardware fallback: complete frame replaces the LCD contents atomically.
        # Rectangle framing is disabled until verified on the physical display.
        if self.closing:return
        packet=display_packet(pixels,display,compress=True)
        self.usb.send(packet);self.usb_bytes+=len(packet);self.usb_packets+=1
        self.last['pixels',display]=pixels
    def run(self):
        import time,threading
        try:
            try:os.setpriority(os.PRIO_PROCESS,threading.get_native_id(),10)
            except (AttributeError,OSError):pass
            self.usb=DisplayUSB(self.product,self.interface)
            while True:
                with self.condition:
                    self.condition.wait_for(lambda:self.closing or self.pending is not None or self.pending_leds is not None or self.settings_pending is not None,timeout=.1)
                    if self.closing:return
                    state,reports,settings=self.pending,self.pending_leds,self.settings_pending
                    if state is None and self.render.needs_refresh:state=self.last_snapshot
                    self.pending=self.pending_leds=self.settings_pending=None
                self.busy_since=time.monotonic()
                try:
                    if settings is not None:self.hardware_values=self.configure(self.fd,settings)
                    if reports is not None:self.leds(reports)
                    if state is not None:
                        started=time.monotonic();frames=self.render(state);rendered=time.monotonic()
                        previous_bytes=self.usb_bytes;previous_packets=self.usb_packets
                        for display,pixels in enumerate(frames):
                            self.changed_frame(display,pixels)
                        self.frames+=1
                        if self.usb_packets>previous_packets:self.display_updates+=1
                        self.performance=dict(display_updates=self.display_updates,render_ms=round((rendered-started)*1000,2),frame_ms=round((time.monotonic()-started)*1000,2),usb_bytes=self.usb_bytes-previous_bytes,usb_packets=self.usb_packets-previous_packets)
                finally:self.busy_since=None
        except Exception as error:
            if not self.closing:self.error=error
        finally:
            if self.usb:self.usb.close()
