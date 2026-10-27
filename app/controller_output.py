"""Coalesced controller output; USB writes must never block sequencer dispatch."""
import threading
import time

class ControllerOutput:
    def __init__(self,fd,pack,send,configure):
        self.fd=fd;self.pack=pack;self.send=send;self.configure=configure
        self.condition=threading.Condition();self.pending=None;self.settings=None;self.pending_leds=None
        self.closing=False;self.error=None;self.last_reports=None;self.last_leds=None
        self.invert=False;self.last_pixels=None
        self.frames=0;self.max_ms=0.;self.total_ms=0.
        self.busy_since=None
        self.thread=threading.Thread(target=self.run,name='controller-output',daemon=True);self.thread.start()
    def check(self):
        if self.error is not None:raise OSError('controller output failed') from self.error
    def submit(self,pixels,leds):
        self.check()
        with self.condition:
            if self.closing:return
            self.pending=(bytes(pixels),bytes(leds));self.pending_leds=bytes(leds);self.condition.notify()
    def submit_leds(self,leds):
        self.check()
        with self.condition:
            if self.closing:return
            self.pending_leds=bytes(leds);self.condition.notify()
    def display_settings(self,brightness,contrast,invert=False):
        self.check()
        with self.condition:
            self.settings=(brightness,contrast,invert);self.condition.notify()
    def run(self):
        try:
            while True:
                with self.condition:
                    self.condition.wait_for(lambda:self.pending is not None or self.settings is not None or self.pending_leds is not None or self.closing)
                    pending,settings,leds=self.pending,self.settings,self.pending_leds;self.pending=self.settings=self.pending_leds=None
                    if self.closing and pending is None and settings is None and leds is None:return
                self.busy_since=time.monotonic()
                try:
                    if settings is not None:
                        self.configure(self.fd,*settings[:2])
                        changed=self.invert!=settings[2];self.invert=settings[2]
                        if pending is None and changed and self.last_pixels is not None:pending=(self.last_pixels,None)
                    if leds is None and pending is not None:leds=pending[1]
                    if leds is not None and leds!=self.last_leds:self.send(self.fd,leds);self.last_leds=leds
                    if pending is None:continue
                    started=time.monotonic();pixels,_=pending
                    self.last_pixels=pixels
                    from app.display_polarity import pixels as polarity
                    reports=self.pack(polarity(pixels,self.invert))
                    for index,report in enumerate(reports):
                        if self.last_reports is None or report!=self.last_reports[index]:self.send(self.fd,report)
                    self.last_reports=reports
                    elapsed=(time.monotonic()-started)*1000
                    self.frames+=1;self.total_ms+=elapsed;self.max_ms=max(self.max_ms,elapsed)
                finally:self.busy_since=None
        except Exception as error:self.error=error
    def close(self):
        with self.condition:self.closing=True;self.condition.notify()
        self.thread.join()
