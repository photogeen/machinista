#!/usr/bin/env python3
"""Guided Mikro MK2 LED verification; isolated from project and audio commands."""
import argparse,fcntl,json,os,select,signal,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.mikro_mk2_protocol import open_device,send,BUTTON_LEDS,PAD_SLOTS
from mikro_feedback import text,frame_reports

PHYSICAL={'MAIN':'CONTROL','ENTER':'MAIN','TRANSPORT LEFT':'STEP LEFT','TRANSPORT RIGHT':'STEP RIGHT'}

def stages():
    result=[dict(kind='button',control=name,index=index,color='RED' if name=='GROUP' else 'WHITE') for name,index in BUTTON_LEDS.items()]
    result += [dict(kind='button',control='GROUP',index=8+i,color=color) for i,color in ((1,'GREEN'),(2,'BLUE'))]
    result += [dict(kind='pad',control=slot,index=30+raw*3+channel,color=color) for color,channel in (('RED',0),('GREEN',1),('BLUE',2)) for raw,slot in enumerate(PAD_SLOTS)]
    return result

def run(path,output,seconds):
    stopped=False
    def stop(*_):
        nonlocal stopped
        stopped=True
    for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,stop)
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    with (ROOT/'build/surface.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        fd=open_device(path);process=None;steps=stages();position=0;pending=None;buffer=b''
        def show(lines):
            pixels=bytearray(8192)
            for row,line in enumerate(lines):text(pixels,2,2+row*12,line,1)
            for packet in frame_reports(pixels):send(fd,packet)
        try:
            process=subprocess.Popen([str(ROOT/'build/mikro_monitor'),'--live',path,'0'],stdout=subprocess.PIPE)
            os.set_blocking(process.stdout.fileno(),False)
            with output.open('w') as log:
                def record(row):log.write(json.dumps(row)+'\n');log.flush()
                def prompt():
                    nonlocal pending
                    pending=None;step=steps[position]
                    report=bytearray(79);report[0]=128;report[1+step['index']]=72;send(fd,report)
                    label='PAD '+str(step['control']+1) if step['kind']=='pad' else PHYSICAL.get(step['control'],step['control'])
                    show(['MK2 LED CHECK',f'{position+1}/{len(steps)} '+step['color'],label,'PRESS LIT CONTROL','NO LIGHT: PUSH KNOB'])
                    record(dict(prompt=True,stage=position,**step));print(f'{position+1}/{len(steps)} {label} {step["color"]}',flush=True)
                record(dict(started=True,hardware='17cc:1200',total=len(steps)));prompt();deadline=time.monotonic()+seconds
                while position<len(steps) and time.monotonic()<deadline and not stopped:
                    if process.poll() is not None:raise RuntimeError('input monitor stopped')
                    if not select.select([process.stdout],[],[],.1)[0]:continue
                    chunk=os.read(process.stdout.fileno(),65536)
                    if not chunk:raise RuntimeError('input monitor disconnected')
                    buffer+=chunk
                    while b'\n' in buffer and position<len(steps):
                        line,buffer=buffer.split(b'\n',1);event=json.loads(line);kind=event.get('kind');name=event.get('name')
                        if kind=='button' and event['value'] or kind=='pad_on':
                            if pending is None:pending=('button' if kind=='button' else 'pad',name)
                        elif pending and ((kind=='button' and not event['value'] and pending==('button',name)) or (kind=='pad_off' and pending==('pad',name))):
                            step=steps[position];expected='PAD_'+str(step['control']+1) if step['kind']=='pad' else step['control']
                            skipped=pending==('button','ENCODER PUSH');matched=not skipped and pending==(step['kind'],expected)
                            record(dict(stage=position,expected=expected,observed=pending[1],observed_kind=pending[0],matched=matched,skipped=skipped,color=step['color'],index=step['index']))
                            position+=1
                            if position<len(steps):prompt()
                record(dict(completed=position,total=len(steps),cancelled=stopped))
                show(['CHECK COMPLETE' if position==len(steps) else 'CHECK STOPPED',f'{position}/{len(steps)}','RESULTS SAVED','RETURN TO CHAT'])
                print(json.dumps(dict(completed=position,total=len(steps))),flush=True)
        finally:
            try:send(fd,bytes([128])+bytes(78))
            finally:
                if process:
                    process.terminate()
                    try:process.wait(timeout=2)
                    except subprocess.TimeoutExpired:process.kill();process.wait()
                    process.stdout.close()
                os.close(fd)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('path');p.add_argument('--output',default=str(ROOT/'captures/mikro-mk2/led-verification.jsonl'));p.add_argument('--seconds',type=int,default=1800);a=p.parse_args()
    run(a.path,a.output,a.seconds)
