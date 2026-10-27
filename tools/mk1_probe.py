#!/usr/bin/env python3
"""Isolated MK1 display/input check; does not access Machinista project/audio."""
import argparse,json,sys,time,threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.mk1_protocol import pack_frame,frame_packets,init_packets,led_packets,buttons
from app.mk1_usb import Mk1USB

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--seconds',type=int,default=15)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if not 1<=args.seconds<=900:parser.error('seconds must be 1..900')
    from app.lcd_font import FONTS
    def text(p,x,y,value):
        for c in value.upper():
            glyph=FONTS['regular7'].get(c,FONTS['regular7']['?'])
            for dy,row in enumerate(glyph):
                for dx,bit in enumerate(row):
                    if bit=='1' and x+dx<255:p[(y+dy)*255+x+dx]=1
            x+=len(glyph[0])+1
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with Mk1USB() as usb,args.output.open('w') as log:
        stop=threading.Event();lock=threading.Lock();errors=[]
        def reader(endpoint):
            try:
                while not stop.is_set():
                    report=usb.read(endpoint,20)
                    if not report:continue
                    event=dict(time_ns=time.monotonic_ns(),endpoint=endpoint,length=len(report),hex=report.hex())
                    if report[0]==4 and len(report)>=7:event['buttons']=sorted(buttons(report))
                    with lock:log.write(json.dumps(event)+'\n');log.flush()
            except Exception as error:errors.append(str(error));stop.set()
        threads=[threading.Thread(target=reader,args=(ep,)) for ep in (0x81,0x84)]
        for thread in threads:thread.start()
        try:
            for display in (0,1):
                for packet in init_packets(display):usb.write(8,packet);time.sleep(.02)
                image=bytearray(255*64)
                for x in range(255):image[x]=image[63*255+x]=1
                for y in range(64):image[y*255]=image[y*255+254]=1
                text(image,8,5,'Machinista / MK1')
                text(image,8,22,'LEFT DISPLAY' if display==0 else 'RIGHT DISPLAY')
                text(image,8,43,'USB TEST - NO AUDIO')
                for packet in frame_packets(display,pack_frame(image)):usb.write(8,packet)
            usb.write(1,bytes((11,255,2,5)))
            for packet in led_packets({'BACKLIGHT':92}):usb.write(1,packet)
            print('MK1 displays written; recording USB inputs',flush=True)
            deadline=time.monotonic()+args.seconds
            while time.monotonic()<deadline and not stop.is_set():stop.wait(.05)
            if errors:raise OSError('; '.join(errors))
        finally:
            try:usb.write(1,bytes((11,0,0,0)));time.sleep(.05)
            except OSError:pass
            stop.set()
            for thread in threads:thread.join()
        print('MK1 check complete; USB handle released on exit',flush=True)
if __name__=='__main__':main()
