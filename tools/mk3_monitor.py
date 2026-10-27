#!/usr/bin/env python3
"""Independent MK3 HID reader, bounded reports, no audio/display work or GIL sharing."""
import os,sys,select,time,json,signal
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.mk3_protocol import Decoder,open_device

def run(path,product=0x1600):
 stopped=False
 def stop(*_):
  nonlocal stopped
  stopped=True
 for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,stop)
 decoder=Decoder();fd=open_device(path,read_only=True,product=product);last=last_pad=reports=rejected=pads=0;health=0
 try:
  while not stopped:
   readable=select.select([fd],[],[],.05)[0]
   if readable:
    for _ in range(64):
     try:data=os.read(fd,64)
     except BlockingIOError:break
     if not data:raise OSError('MK3 disconnected')
     stamp=time.monotonic_ns();last=stamp;reports+=1
     if len(data) not in (42,64) or data[0] not in (1,2):rejected+=1;continue
     if data[0]==2:pads+=1;last_pad=stamp
     for event in decoder.decode(data):event['monotonic_ns']=stamp;print(json.dumps(event),flush=True)
   now=time.monotonic_ns()
   if now-health>=500000000:
    print(json.dumps(dict(kind='reader_health',reports=reports,rejected=rejected,monotonic_ns=now,last_report_ns=last,pad_reports=pads,last_pad_report_ns=last_pad)),flush=True);health=now
 finally:os.close(fd)
if __name__=='__main__':run(sys.argv[1],int(sys.argv[2]) if len(sys.argv)>2 else 0x1600)
