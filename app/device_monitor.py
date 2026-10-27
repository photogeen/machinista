"""Read USB audio/MIDI and mount information outside the sequencer loop."""
from concurrent.futures import ThreadPoolExecutor
import time
from app.devices import discover
from app.browser import mounted_sources

def scan_devices():
    audio,midi=discover()
    return audio,midi,mounted_sources()

class DeviceMonitor:
    def __init__(self,scan=scan_devices):
        self.scan=scan;self.future=None;self.next_scan=0
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='device-scan')
    def poll(self,now=None):
        now=time.monotonic() if now is None else now;result=None
        if self.future is not None and self.future.done():
            future,self.future=self.future,None
            result=future.result()
        if self.future is None and now>=self.next_scan:
            self.future=self.pool.submit(self.scan);self.next_scan=now+1
        return result
    def close(self):self.pool.shutdown(wait=False,cancel_futures=True)
