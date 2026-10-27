#!/usr/bin/env python3
"""Record physical MK1 button LED channels without guessing MK2 addresses."""
import fcntl
import json
import os
from pathlib import Path
import select
import subprocess
import time
from mikro_feedback import open_mk1,send,text,frame_reports
from mikro_settings import configure_backlight
from mikro_leds import load_pad_channels
ROOT=Path(__file__).resolve().parent.parent

def main():
    path='/dev/hidraw0'
    pads=set(load_pad_channels(ROOT/'captures/mikro-mk1-pad-led-map.json').values())
    indices=[i for i in range(60) if i not in pads and i != 36]
    mapping={'MAIN':36}; rows=[]; pending=None; position=0
    with (ROOT/'build/surface.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        fd=open_mk1(path);configure_backlight(fd,100)
        process=subprocess.Popen([str(ROOT/'build/mikro_monitor'),'--live',path,'600'],stdout=subprocess.PIPE)
        buffer=b''
        try:
            while position<len(indices):
                index=indices[position]
                report=bytearray([0x80]+[0]*60);report[index+1]=24;send(fd,report)
                pixels=bytearray(8192);text(pixels,2,3,'BUTTON LED MAP',2)
                text(pixels,2,21,f'{position+1}/{len(indices)} LED {index}',1)
                text(pixels,2,35,'PRESS THE LIT BUTTON',1)
                text(pixels,2,47,'NO LIGHT: PRESS KNOB',1)
                for r in frame_reports(pixels):send(fd,r)
                print(f'LED {index} WAITING',flush=True)
                while True:
                    if not select.select([process.stdout],[],[],2)[0]:
                        if process.poll() is not None: raise RuntimeError('input worker stopped')
                        continue
                    chunk=os.read(process.stdout.fileno(),65536)
                    if not chunk: raise RuntimeError('input worker disconnected')
                    buffer+=chunk;advance=False
                    while b'\n' in buffer:
                        line,buffer=buffer.split(b'\n',1);event=json.loads(line)
                        if event['kind']!='button':continue
                        if event['value'] and pending is None:
                            pending=event['name']
                        elif not event['value'] and event['name']==pending:
                            name=pending;pending=None
                            if name!='ENCODER PUSH':mapping[name]=index
                            rows.append({'payload_index':index,'button':None if name=='ENCODER PUSH' else name})
                            print(f'LED {index} = {name}',flush=True)
                            advance=True
                    if advance:break
                position+=1
            output={'buttons':mapping,'observations':rows,'hardware':'17cc:1110 MK1'}
            (ROOT/'captures/mikro-mk1-button-led-map.json').write_text(json.dumps(output,indent=2)+'\n')
            pixels=bytearray(8192);text(pixels,2,15,'LED MAP SAVED',2)
            for r in frame_reports(pixels):send(fd,r)
            print('CALIBRATION COMPLETE',flush=True)
        finally:
            process.terminate();process.wait(timeout=3);os.close(fd)

if __name__=='__main__':main()
