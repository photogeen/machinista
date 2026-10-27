#!/usr/bin/env python3
"""Isolated MK2 verification: never sends commands to the audio engine."""
import argparse,json,os,select,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from app.mk2_protocol import BUTTONS,LED_BUTTONS,PAD_SLOTS,ButtonsDecoder,display_reports,led_reports,open_device,send
from app.lcd_font import FONTS

def display(fd,left,right):
 for index,lines in enumerate((left,right)):
  pixels=bytearray(256*64)
  for row,value in enumerate(lines):
   x=5;y=5+row*13
   for char in value.upper():
    glyph=FONTS['regular7'].get(char,FONTS['regular7']['?'])
    for dy,bits in enumerate(glyph):
     for dx,bit in enumerate(bits):
      if bit=='1' and x+dx<251 and y+dy<63:pixels[(y+dy)*256+x+dx]=1
    x+=len(glyph[0])+1
  for report in display_reports(pixels,index):send(fd,report)

def expected_pressure(kind):return kind.startswith('pad')

def main():
 p=argparse.ArgumentParser();p.add_argument('path');p.add_argument('--record',action='store_true');p.add_argument('--leds',action='store_true');p.add_argument('--output',default=str(ROOT/'captures/mk2-calibration.jsonl'));p.add_argument('--seconds',type=int,default=600);a=p.parse_args()
 fd=open_device(a.path);decoder=ButtonsDecoder();start=time.monotonic();position=0
 stages=[('button',name) for name in BUTTONS]+[('encoder',i) for i in range(9)]+[('pad',slot) for slot in range(16)]
 if a.leds:stages=[('button',name) for name in LED_BUTTONS]+[('button',name) for name in ('RESTART','TRANSPORT LEFT','TRANSPORT RIGHT','GRID','PLAY','REC','ERASE','SHIFT')]+[('button',f'GROUP {c}') for c in 'ABCDEFGH']+[(f'pad {color}',slot) for color in ('RED','GREEN','BLUE') for slot in range(16)]
 def prompt():
  kind,control=stages[position]
  if a.leds:
   buttons={};pads={};groups={}
   if kind=='button':
    if str(control).startswith('GROUP '):groups[str(control)[-1]]=(0,0,40)
    else:buttons[control]=35
   else:pads[control]={'pad RED':(45,0,0),'pad GREEN':(0,45,0),'pad BLUE':(0,0,45)}[kind]
   for report in led_reports(buttons,pads,groups):send(fd,report)
  title=f'{kind}: {control+1 if kind.startswith("pad") else control}'
  if control=='MASTER PUSH':title='PRESS MASTER KNOB'
  if kind=='encoder':title='MASTER ENCODER' if control==0 else f'KNOB {control}'
  display(fd,['MASCHINE MK2',f'CHECK {position+1}/{len(stages)}',title],['Machinista','PRESS / TURN ONCE','THEN RELEASE'])
  print(json.dumps({'prompt':[kind,control],'position':position}),flush=True)
 for report in led_reports(dict.fromkeys(LED_BUTTONS,24),dict.fromkeys(range(16),(40,12,0)),dict.fromkeys('ABCDEFGH',(0,12,35))):send(fd,report)
 if not a.record:
  display(fd,['Machinista','MASCHINE MK2','LEFT DISPLAY'],['DUAL DISPLAY TEST','RIGHT DISPLAY','256 X 64'])
  os.close(fd);return
 Path(a.output).parent.mkdir(parents=True,exist_ok=True)
 with open(a.output,'w') as out:
  prompt();last_pad=None
  while position<len(stages) and time.monotonic()-start<a.seconds:
   if not select.select([fd],[],[],.1)[0]:continue
   data=os.read(fd,4096);events=decoder.decode(data)
   if data and data[0]==0x20 and not expected_pressure(stages[position][0]):continue
   out.write(json.dumps({'elapsed_ns':int((time.monotonic()-start)*1e9),'hex':data.hex(),'events':events})+'\n');out.flush()
   expected_kind,expected=stages[position]
   matched=False
   if expected_kind=='button':
    # Advance on release; held SHIFT cannot contaminate the next prompt.
    matched=any(kind=='button' and name==expected and value is False for kind,name,value in events)
   elif expected_kind=='encoder':matched=any(kind=='encoder' and name==expected for kind,name,value in events)
   elif data and data[0]==0x20 and len(data)==65:
    for i in range(1,65,2):
     raw=data[i+1]>>4;pressure=data[i]|((data[i+1]&15)<<8)
     if PAD_SLOTS[raw]==expected:
      if pressure>200:last_pad=expected
      elif pressure<60 and last_pad==expected:matched=True;last_pad=None
   if matched:
    position+=1
    if position<len(stages):prompt()
  display(fd,['CHECK COMPLETE' if position==len(stages) else 'CHECK TIMEOUT',f'{position}/{len(stages)}'],['Machinista','LOG SAVED','THANK YOU'])
  print(json.dumps({'completed':position,'total':len(stages)}),flush=True)
 os.close(fd)
if __name__=='__main__':main()
