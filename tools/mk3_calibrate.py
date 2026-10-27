#!/usr/bin/env python3
"""Isolated guided MK3 control/LED check; never sends audio or project commands."""
import sys,os,json,select,time,signal,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.mk3_protocol import Decoder,open_device,feature,led_reports,display_packet,LED_NAMES,COLOUR_SLOTS,PAD_SLOTS
from app.mk3_usb import DisplayUSB
from app.mk3_graphics import Canvas,ACCENT,INK,MUTED,GROUPS

def run(path,destination,product=0x1600):
 destination=Path(destination);destination.mkdir(parents=True,exist_ok=True);fd=open_device(path,product=product);usb=DisplayUSB(product,6 if product==0x1820 else 5);decoder=Decoder();stopped=False
 def stop(*_):
  nonlocal stopped
  stopped=True
 for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,stop)
 palette=feature(fd,0xfe,208);(destination/'palette.bin').write_bytes(palette)
 for rid in (0xf8,0xf9):(destination/f'feature-{rid:x}.bin').write_bytes(feature(fd,rid,10))
 colours=[]
 for i in range(17):colours.append(tuple(v*2 for v in palette[1+i*12+6:1+i*12+9]))
 def nearest(target):return min(range(1,17),key=lambda i:sum((a-b)**2 for a,b in zip(colours[i],target)))
 steps=[dict(kind='button',name=name,led=i,colour=i in COLOUR_SLOTS) for i,name in enumerate(LED_NAMES)]
 steps += [dict(kind='button',name='MASTER PUSH')]
 steps += [dict(kind='encoder',name='4D ENCODER' if i==0 else f'KNOB {i}',index=i) for i in range(9)]
 steps += [dict(kind='touch',name='MASTER TOUCH')]+[dict(kind='touch',name=f'KNOB {i} TOUCH') for i in range(1,9)]
 steps += [dict(kind='pad',name=f'PAD {slot+1}',slot=slot,led=87+raw) for raw,slot in enumerate(PAD_SLOTS)]
 steps += [dict(kind='pad',name='PAD 1 / '+label,slot=0,led=99,palette=nearest(rgb)) for label,rgb in (('RED',(255,0,0)),('GREEN',(0,255,0)),('BLUE',(0,0,255)))]
 steps += [dict(kind='strip',name='TOUCH STRIP')]
 position=0;pending=None;travel=0;deadline=time.monotonic()+3600
 log=(destination/'verification.jsonl').open('w')
 def record(row):log.write(json.dumps(row)+'\n');log.flush()
 def leds(values):
  for report in led_reports(values):
   if os.write(fd,report)!=len(report):raise OSError('Short MK3 LED write')
 def prompt():
  nonlocal pending,travel
  pending=None;travel=0;step=steps[position];values=[0]*103
  if 'led' in step:values[step['led']]=((step.get('palette',nearest((255,150,62)))<<2)|3) if step.get('colour') or step['kind']=='pad' else 100
  if step['kind']=='strip':values[62:87]=[127]*25
  leds(values)
  for display in (0,1):
   c=Canvas();c.rect(0,0,480,5,ACCENT);c.text(18,16,'Machinista / Maschine+' if product==0x1820 else 'Machinista / MK3',24,True);c.text(18,55,'LEFT DISPLAY' if display==0 else 'RIGHT DISPLAY',16,color=MUTED)
   if display==0:
    c.text(18,95,f'{position+1:02} / {len(steps)}',18,color=ACCENT);c.text(18,128,step['name'],25,True,width=445)
    c.text(18,181,'TURN' if step['kind']=='encoder' else 'TOUCH' if step['kind']=='touch' else 'SLIDE A FINGER' if step['kind']=='strip' else 'PRESS AND RELEASE',18)
   else:
    c.text(18,95,'HARDWARE CHECK',20,True);c.text(18,130,'Follow the left display.',18);c.text(18,162,'LED missing: push 4D encoder.',16,color=MUTED)
    for i,color in enumerate(GROUPS):c.rect(18+i*56,214,48,28,color,radius=4)
   usb.send(display_packet(c.wire(),display))
  state=dict(stage=position,total=len(steps),prompt=step);(destination/'status.json').write_text(json.dumps(state));record(state);print(json.dumps(state),flush=True)
 try:
  record(dict(started=True,stages=len(steps)));prompt()
  while not stopped and position<len(steps) and time.monotonic()<deadline:
   if not select.select([fd],[],[],.1)[0]:continue
   data=os.read(fd,64)
   if not data:raise OSError('MK3 disconnected')
   for event in decoder.decode(data):
    step=steps[position];kind=event['kind'];name=event.get('name');done=False;result=None
    if step['kind']=='encoder' and kind=='encoder' and event['raw_control']==step['index']:
     travel+=abs(event['value'])
     if travel>=(1 if step['index']==0 else 24):done=True;result=event
    elif step['kind']=='strip' and kind=='strip' and event['value']>100:done=True;result=event
    elif step['kind']=='touch' and kind=='button' and name==step['name'] and event['value']:done=True;result=event
    elif step['kind'] in ('button','pad'):
     if kind=='button' and event['value'] and 'TOUCH' not in name:pending=event
     elif kind=='pad_on' and step['kind']=='pad':pending=event
     elif pending and ((kind=='button' and not event['value'] and pending.get('name')==name) or (kind=='pad_off' and pending.get('name')==name)):
      done=True;result=pending
    if done:
     expected=f'PAD_{step["slot"]+1}' if step['kind']=='pad' else step['name'];skipped=result.get('name')=='MASTER PUSH' and expected!='MASTER PUSH'
     matched=not skipped and (result.get('name')==expected or step['kind'] in ('strip','encoder'))
     record(dict(result=True,stage=position,expected=expected,observed=result,matched=matched,skipped=skipped));position+=1
     if position<len(steps):prompt()
     else:break
  result=dict(completed=position,total=len(steps),cancelled=stopped);record(result);(destination/'status.json').write_text(json.dumps(result));print(json.dumps(result),flush=True)
  for index in (0,1):
   c=Canvas();c.text(25,60,'CHECK COMPLETE' if position==len(steps) else 'CHECK STOPPED',30,True,color=ACCENT);c.text(25,120,f'{position}/{len(steps)} · Return to chat',22);usb.send(display_packet(c.wire(),index))
 finally:
  leds([0]*103);log.close();os.close(fd);usb.close()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('path');p.add_argument('--output',required=True);p.add_argument('--product',type=lambda v:int(v,0),default=0x1600);args=p.parse_args();run(args.path,args.output,args.product)
