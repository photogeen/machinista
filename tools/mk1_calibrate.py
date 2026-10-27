#!/usr/bin/env python3
"""Guided, isolated full-MK1 hardware mapping. No engine/project access."""
import argparse,json,sys,time,threading,queue,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.mk1_usb import Mk1USB
from app.mk1_protocol import *
from app.lcd_font import FONTS

PHYSICAL={'ALL':'SNAP','AUTO':'AUTO WRITE','RESTART':'RESTART / LOOP'}

def frame(lines):
    pixels=bytearray(255*64)
    for y,value in zip((3,16,29,42,55),lines):
        x=4
        for c in str(value).upper():
            glyph=FONTS['regular7'].get(c,FONTS['regular7']['?'])
            for dy,row in enumerate(glyph):
                for dx,bit in enumerate(row):
                    if bit=='1' and x+dx<253:pixels[(y+dy)*255+x+dx]=1
            x+=len(glyph[0])+1
    return pack_frame(pixels)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--start',type=int,default=0);parser.add_argument('--seconds',type=int,default=900);parser.add_argument('--stage',choices=('inputs','leds'),default='inputs')
    args=parser.parse_args()
    if not 1<=args.seconds<=1800:parser.error('seconds must be 1..1800')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with Mk1USB() as usb,args.output.open('a') as log:
        stop=threading.Event();events=queue.Queue(maxsize=20000);lock=threading.Lock();errors=[]
        def record(event):
            with lock:log.write(json.dumps(event)+'\n');log.flush()
        def reader(ep):
            try:
                while not stop.is_set():
                    data=usb.read(ep,20)
                    if data:
                        item=dict(time_ns=time.monotonic_ns(),ep=ep,hex=data.hex())
                        record(item)
                        try:events.put_nowait((item["time_ns"],ep,data))
                        except queue.Full:raise OSError('calibration input queue full')
            except Exception as error:errors.append(str(error));stop.set()
        threads=[threading.Thread(target=reader,args=(ep,)) for ep in (129,132)]
        for t in threads:t.start()
        def show(left,right):
            for display,lines in enumerate((left,right)):
                for packet in frame_packets(display,frame(lines)):usb.write(8,packet)
        def light(name=None):
            values={'BACKLIGHT':92}
            if name:values[name]=100
            for packet in led_packets(values):usb.write(1,packet)
        try:
            for d in (0,1):
                for packet in init_packets(d):usb.write(8,packet);time.sleep(.02)
            usb.write(1,bytes((11,255,2,5)));light()
            # Hardware names on MK1 differ from the logical engine bindings.
            button_order=['CONTROL','STEP','BROWSE','SAMPLING','PAGE LEFT','PAGE RIGHT','ALL','AUTO']+[f'DISPLAY {i}' for i in range(1,9)]+[f'GROUP {x}' for x in 'ABCDEFGH']+['RESTART','TRANSPORT LEFT','TRANSPORT RIGHT','GRID','PLAY','REC','ERASE','SHIFT','NOTE REPEAT','SCENE','PATTERN','PAD MODE','NAVIGATE','DUPLICATE','SELECT','SOLO','MUTE']
            stages=([('button',name) for name in button_order]+[('encoder',str(i)) for i in range(1,9)]+[('encoder',name) for name in ('VOLUME','SWING','TEMPO')]+[('pad',str(i)) for i in range(1,17)]) if args.stage=='inputs' else [('led',name) for name in LED_NAMES if name and name!='BACKLIGHT']
            if not 0<=args.start<len(stages):parser.error('start outside calibration stages')
            index=args.start;previous=set();pressed=None;used_bits=set();baseline=None;changes={};stage_start=time.monotonic();pad_peak={};encoder_samples=[];pad_released=None
            def prompt():
                nonlocal stage_start,baseline,changes,pad_peak,encoder_samples,pad_released
                stage_start=time.monotonic();baseline=None;changes={};pad_peak={};encoder_samples=[];pad_released=None
                kind,name=stages[index];label=PHYSICAL.get(name,name)
                if kind=='encoder':
                    show(['MK1 INPUT CHECK',f'{index+1}/{len(stages)}: ENCODER '+label,'TURN CLOCKWISE','THEN PRESS TOP BUTTON 8'],['ENCODER MAPPING','TURN ONLY THIS KNOB','STOP TURNING, THEN NEXT','TOP BUTTON 8 = NEXT'])
                    light('DISPLAY 8')
                elif kind=='led':
                    light(name)
                    show(['MK1 LED CHECK',f'{index+1}/{len(stages)}','PRESS THE LIT CONTROL',label],['ONE LIGHT AT A TIME','PRESS AND RELEASE','NO AUDIO WILL PLAY','MATCH: '+label])
                else:
                    light()
                    show(['MK1 INPUT CHECK',f'{index+1}/{len(stages)}: '+kind.upper(),'PRESS '+label,'THEN RELEASE'],['FOLLOW LEFT DISPLAY','ONE CONTROL AT A TIME','NO AUDIO WILL PLAY','MACHINISTA'])
                record(dict(stage=index,kind=kind,expected=name,prompt=True))
                print(f'{index+1}/{len(stages)} {kind} {name}',flush=True)
            prompt();deadline=time.monotonic()+args.seconds
            while time.monotonic()<deadline and index<len(stages) and not stop.is_set():
                try:stamp,ep,data=events.get(timeout=.1)
                except queue.Empty:continue
                if stamp/1e9<stage_start+.25:continue
                kind,name=stages[index];advance=False;observation=None
                if ep==129 and data[0]==2 and len(data)>=23:
                    pairs=[tuple(data[1+i*2:3+i*2]) for i in range(11)]
                    if kind=='encoder':
                        if baseline is None:baseline=pairs
                        encoder_samples.append(data.hex())
                        for i,(a,b) in enumerate(pairs):
                            distance=abs(a-baseline[i][0])+abs(b-baseline[i][1])
                            changes[i]=max(changes.get(i,0),distance)
                if ep==129 and data[0]==4 and len(data)>=7:
                    current={i for i in range(42) if data[1+i//8]&(1<<(i%8))}
                    down=current-previous;up=previous-current;previous=current
                    if down and pressed is None:pressed=min(down)
                    if pressed is not None and pressed in up:
                        bit=pressed;pressed=None
                        if time.monotonic()-stage_start<.15:continue
                        if kind=='button' and bit not in used_bits:
                            observation=dict(raw_button=bit);used_bits.add(bit);advance=True
                        elif kind=='encoder' and bit==32 and changes and max(changes.values())>=12:
                            observation=dict(raw_encoder=max(changes,key=changes.get),distances=changes,samples=encoder_samples);advance=True
                        elif kind=='led' and not is_pad_led(name):
                            observation=dict(raw_button=bit,decoded=BUTTONS[bit]);advance=True
                if ep==132 and len(data)==64 and (kind=='pad' or kind=='led' and is_pad_led(name)):
                    current={}
                    for raw,pressure in pad_samples(data):
                        pad_peak[raw]=max(pad_peak.get(raw,0),pressure)
                        current[raw]=pressure
                    if pad_peak and max(pad_peak.values())>200:
                        raw=max(pad_peak,key=pad_peak.get)
                        if current.get(raw,0)<60:
                            if pad_released is None:pad_released=stamp/1e9
                            if stamp/1e9-pad_released>=.06:
                                observation=dict(raw_pad=raw,logical=PAD_SLOTS[raw]+1,peak=pad_peak[raw]);advance=True
                        else:pad_released=None
                if advance:
                    record(dict(stage=index,kind=kind,expected=name,observed=observation))
                    index+=1
                    if index<len(stages):prompt()
            if errors:raise OSError('; '.join(errors))
            if index==len(stages):
                show(['MK1 CHECK COMPLETE',args.stage.upper(),'THANK YOU'],['MACHINISTA','ALL STEPS RECORDED','CONTINUE IN CHAT'])
                record(dict(complete=True,stage=args.stage,count=index));print('COMPLETE',flush=True)
            else:record(dict(incomplete=True,next_stage=index));print('INCOMPLETE',flush=True)
        finally:
            try:usb.write(1,bytes((11,0,0,0)));time.sleep(.05)
            except OSError:pass
            stop.set()
            for t in threads:t.join()
if __name__=='__main__':main()
