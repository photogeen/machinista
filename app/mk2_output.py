"""Optional MK2 output worker: coalesced snapshots, native dual-screen reports.

The renderer receives an immutable application snapshot. Packing, rendering and
nonblocking HID writes happen here, never inside the audio dispatch loop.
"""
import errno
import os
import threading
import time
from app.mk2_protocol import display_reports,send


class Mk2Output:
    def __init__(self,fd,render,write=send,configure=None,settings=None):
        self.fd,self.render,self.write=fd,render,write
        self.configure=configure;self.hardware_values=None;self.settings_pending=dict(settings or {}) if configure else None
        self.condition=threading.Condition()
        self.pending=None;self.pending_leds=None;self.closing=False;self.error=None
        self.last={};self.frames=0;self.revision=0;self.last_snapshot=None
        self.busy_since=None
        self.thread=threading.Thread(target=self.run,name='mk2-output',daemon=True)
        self.thread.start()

    def submit(self,snapshot):
        # Caller creates an immutable snapshot; no live Application is passed.
        with self.condition:
            if self.closing or self.error:return False
            if snapshot==self.last_snapshot:return True
            self.last_snapshot=snapshot
            self.pending=snapshot;self.revision+=1;self.condition.notify()
        return True

    def submit_leds(self,reports):
        with self.condition:
            if self.closing or self.error:return False
            self.pending_leds=tuple(bytes(r) for r in reports);self.condition.notify()
        return True

    def display_settings(self,values):
        with self.condition:
            if self.closing or self.error:return False
            self.settings_pending=dict(values);self.condition.notify()
        return True

    def changed(self,report,key):
        if self.last.get(key)==report:return
        deadline=time.monotonic()+.25
        while True:
            try:self.write(self.fd,report);break
            except BlockingIOError as error:
                if error.errno not in (errno.EAGAIN,errno.EWOULDBLOCK) or time.monotonic()>=deadline:raise
                with self.condition:
                    if self.closing:return
                    self.condition.wait(.002)
        self.last[key]=report

    def leds(self,reports):
        for report in reports:self.changed(report,(report[0],))

    def run(self):
        try:
            try:os.setpriority(os.PRIO_PROCESS,threading.get_native_id(),10)
            except (AttributeError,OSError):pass
            while True:
                with self.condition:
                    self.condition.wait_for(lambda:self.closing or self.pending is not None or self.pending_leds is not None or self.settings_pending is not None,timeout=.1)
                    if self.closing:return
                    snapshot,leds,revision=self.pending,self.pending_leds,self.revision
                    if snapshot is None and getattr(self.render,'needs_refresh',False):snapshot=self.last_snapshot
                    self.pending=self.pending_leds=None
                    settings=self.settings_pending;self.settings_pending=None
                self.busy_since=time.monotonic()
                try:
                    if settings is not None:self.hardware_values=self.configure(self.fd,settings)
                    if leds is not None:self.leds(leds)
                    if snapshot is None:continue
                    left,right=self.render(snapshot)
                    for display,pixels in enumerate((left,right)):
                        if bytes(pixels)==self.last.get(('pixels',display)):continue
                        for index,report in enumerate(display_reports(pixels,display)):
                            with self.condition:
                                if self.closing:return
                                # Finish this bounded frame even if newer state arrives.
                                # Otherwise continuous updates can starve every chunk.
                                leds=self.pending_leds;self.pending_leds=None
                            if leds is not None:self.leds(leds)
                            self.changed(report,(report[0],index))
                        else:
                            self.last['pixels',display]=bytes(pixels)
                            continue
                        break
                    self.frames+=1
                finally:self.busy_since=None
        except Exception as error:
            self.error=error  # Session manager disconnects only this controller.

    def close(self):
        with self.condition:
            self.closing=True;self.pending=self.pending_leds=None;self.condition.notify_all()
        self.thread.join(timeout=.5)
