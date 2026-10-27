"""Bounded, isolated display encoder. No ctypes/native code in the UI process."""
import os,select,subprocess,time
from pathlib import Path
from dataclasses import dataclass

@dataclass(frozen=True)
class DisplayFrame:
    packet: bytes

class FrameEncoder:
    def __init__(self,path=None):
        path=Path(path) if path else Path(__file__).resolve().parents[1]/'build/mk3_frame_encoder'
        self.process=subprocess.Popen([str(path)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,bufsize=0,close_fds=True)
        os.set_blocking(self.process.stdin.fileno(),False);os.set_blocking(self.process.stdout.fileno(),False)
    def encode(self,rgb,display,invert=False,timeout=.5):
        if len(rgb)!=480*272*3 or display not in (0,1):raise ValueError('Invalid native MK3 image')
        request=memoryview(bytes((display,int(bool(invert)),0,0))+rgb);sent=0;result=bytearray();size=None;deadline=time.monotonic()+timeout
        while size is None or len(result)<size+4:
            remaining=deadline-time.monotonic()
            if remaining<=0 or self.process.poll() is not None:raise OSError('MK3 encoder timeout or exit')
            reads,writes,_=select.select([self.process.stdout], [self.process.stdin] if sent<len(request) else [],[],remaining)
            if writes:
                try:sent+=os.write(self.process.stdin.fileno(),request[sent:])
                except BlockingIOError:pass
            if reads:
                try:data=os.read(self.process.stdout.fileno(),65536)
                except BlockingIOError:continue
                if not data:raise OSError('MK3 encoder closed')
                result.extend(data)
                if size is None and len(result)>=4:
                    size=int.from_bytes(result[:4],'big')
                    if not 32<=size<=261148:raise OSError('Invalid MK3 encoder length')
        if len(result)!=size+4:raise OSError('Invalid MK3 encoder framing')
        packet=bytes(result[4:])
        header=bytes((0x84,0,display,0x60,0,0,0,0,0,0,0,0,1,0xe0,1,0x10))
        if packet[:16]!=header or packet[-8:]!=bytes.fromhex('0300000040000000'):raise OSError('Invalid MK3 full frame')
        return DisplayFrame(packet)
    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:self.process.wait(timeout=.2)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait()
        self.process.stdin.close();self.process.stdout.close()
