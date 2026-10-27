"""MK3 17cc:1600 HID and RGB565 display framing, independent from audio/MIDI.

Protocol facts checked against device descriptors and the public MK3 hardware
map (autotel/maschine-mk3-linux). Implementation is native to Machinista.
"""
import os,struct,fcntl
from pathlib import Path
WIDTH,HEIGHT=480,272
PAD_SLOTS=(12,13,14,15,8,9,10,11,4,5,6,7,0,1,2,3)
BUTTON_BITS={0:'MASTER PUSH',2:'MASTER UP',3:'MASTER RIGHT',4:'MASTER DOWN',5:'MASTER LEFT',6:'SHIFT',7:'DISPLAY 8',**{8+i:'GROUP '+c for i,c in enumerate('ABCDEFGH')},16:'NOTES',17:'VOLUME',18:'SWING',19:'TEMPO',20:'NOTE REPEAT',21:'LOCK',24:'PAD MODE',25:'KEYBOARD',26:'CHORDS',27:'STEP',28:'FIXED VEL',29:'SCENE',30:'PATTERN',31:'EVENTS',33:'VARIATION',34:'DUPLICATE',35:'SELECT',36:'SOLO',37:'MUTE',38:'PITCH',39:'MOD',40:'PERFORM',41:'RESTART',42:'ERASE',43:'TAP',44:'FOLLOW',45:'PLAY',46:'REC',47:'STOP',48:'MACRO',49:'SETTINGS',50:'PAGE RIGHT',51:'SAMPLING',52:'MIXER',53:'PLUG-IN',56:'CHANNEL',57:'ARRANGER',58:'BROWSE',59:'PAGE LEFT',60:'FILE',61:'AUTO',**{64+i:f'DISPLAY {i+1}' for i in range(7)},71:'MASTER TOUCH',**{72+i:f'KNOB {8-i} TOUCH' for i in range(8)}}
LED_NAMES=('CHANNEL','PLUG-IN','ARRANGER','MIXER','BROWSE','SAMPLING','PAGE LEFT','PAGE RIGHT','FILE','SETTINGS','AUTO','MACRO',*(f'DISPLAY {i}' for i in range(1,9)),'VOLUME','SWING','NOTE REPEAT','TEMPO','LOCK','PITCH','MOD','PERFORM','NOTES',*(f'GROUP {c}' for c in 'ABCDEFGH'),'RESTART','ERASE','TAP','FOLLOW','PLAY','REC','STOP','SHIFT','FIXED VEL','PAD MODE','KEYBOARD','CHORDS','STEP','SCENE','PATTERN','EVENTS','VARIATION','DUPLICATE','SELECT','SOLO','MUTE','MASTER UP','MASTER LEFT','MASTER RIGHT','MASTER DOWN')
COLOUR_SLOTS={5,*range(29,37),41,42,*range(58,62)}

def open_device(path,read_only=False,product=0x1600):
 p=Path(path);identity=(Path('/sys/class/hidraw')/p.name/'device/uevent').read_text()
 if product not in (0x1600,0x1820) or f'HID_ID=0003:000017CC:{product:08X}' not in identity:raise ValueError('Unexpected Maschine controller')
 return os.open(p,(os.O_RDONLY if read_only else os.O_RDWR)|os.O_NONBLOCK|os.O_NOCTTY)

def feature(fd,report,size):
 data=bytearray([report])+bytearray(size)
 n=fcntl.ioctl(fd,(3<<30)|((size+1)<<16)|(ord('H')<<8)|7,data,True)
 if n!=len(data):raise OSError('Short MK3 feature read')
 return data

def configure_displays(fd,values):
 result={}
 for index,report in enumerate((0xf8,0xf9)):
  data=feature(fd,report,10)
  if struct.unpack_from('<HH',data,1)!=(WIDTH,HEIGHT) or data[5]!=16:raise ValueError('Unexpected MK3 display geometry')
  key='contrast_left' if index==0 else 'contrast_right'
  for offset,name in ((8,'brightness'),(9,key)):
   value=values.get(name)
   if value is not None:
    if type(value) is not int or not 0<=value<=100:raise ValueError('Invalid MK3 display setting')
    data[offset]=value
   result[name]=data[offset]
  if fcntl.ioctl(fd,(3<<30)|(11<<16)|(ord('H')<<8)|6,data,True)!=11:raise OSError('MK3 display setting failed')
 return result

def display_packet(pixels,display,x=0,y=0,width=WIDTH,height=HEIGHT,compress=False):
 if display not in (0,1) or width<=0 or height<=0 or x<0 or y<0 or x+width>WIDTH or y+height>HEIGHT or width*height%2 or len(pixels)!=width*height*2:raise ValueError('Invalid MK3 display rectangle')
 stream=None
 if compress:
  from app.mk3_pixels import encode
  stream=encode(pixels)
 if stream is None:stream=struct.pack('>I',width*height//2)+pixels
 return bytes((0x84,0,display,0x60,0,0,0,0))+struct.pack('>HHHH',x,y,width,height)+stream+b'\x03\x00\x00\x00\x40\x00\x00\x00'

def led_reports(values):
 if len(values)!=103 or any(type(v) is not int or not 0<=v<=127 for v in values):raise ValueError('Invalid MK3 LEDs')
 return bytes([0x80]+list(values[:62])),bytes([0x81]+list(values[62:]))

class Decoder:
 def __init__(self):self.buttons=0;self.counters=None;self.strip=0;self.pedal=None;self.active=set();self.contacts=set()
 def decode(self,data):
  if len(data)==42 and data[0]==1:
   current=int.from_bytes(data[1:11],'little');counters=[data[11]&15]+list(struct.unpack_from('<8H',data,12))
   if any(v>999 for v in counters[1:]):return []
   events=[dict(kind='button',name=name,raw_control=bit,value=int(bool(current&(1<<bit)))) for bit,name in BUTTON_BITS.items() if (current^self.buttons)&(1<<bit)];self.buttons=current
   if self.counters is not None:
    for i,(value,old) in enumerate(zip(counters,self.counters)):
     modulus=16 if i==0 else 1000;delta=(value-old+modulus//2)%modulus-modulus//2
     if delta and abs(delta)!=modulus//2:events.append(dict(kind='encoder',raw_control=i,value=delta))
   self.counters=counters
   strip=struct.unpack_from('<H',data,30)[0]
   if strip!=self.strip:events.append(dict(kind='strip',value=min(1024,strip)));self.strip=strip
   pedal=struct.unpack_from('<3H',data,36)
   if self.pedal is not None:
    for i,(v,old) in enumerate(zip(pedal,self.pedal)):
     if abs(v-old)>16:events.append(dict(kind='pedal',raw_control=i,value=v))
   self.pedal=pedal;return events
  if len(data)==64 and data[0]==2:
   events=[]
   for i in range(1,64,3):
    raw,kind_low,value=data[i:i+3]
    if raw==kind_low==value==0 and i>1:break
    if raw>15:continue
    kind=kind_low&0xf0;value=((kind_low&15)<<8)|value;slot=PAD_SLOTS[raw];name=f'PAD_{slot+1}'
    if kind==0x00 and value==0:continue
    if kind==0x00:
     self.contacts.add(slot);events.append(dict(kind='pad_contact',name=name,value=max(1,min(127,round(value*127/2000))),raw_value=value))
    elif kind==0x10:
     if slot in self.active:events.append(dict(kind='pad_off',name=name,value=0))
     self.active.add(slot);events.append(dict(kind='pad_on',name=name,value=max(1,min(127,round(value*127/2000))),raw_value=value))
    elif kind in (0x20,0x30):
     if slot in self.active:self.active.remove(slot);events.append(dict(kind='pad_off',name=name,value=0))
     if slot in self.contacts:self.contacts.remove(slot);events.append(dict(kind='pad_contact_off',name=name,value=0))
    elif kind==0x40 and (slot in self.active or slot in self.contacts):events.append(dict(kind='pad_pressure',name=name,value=min(127,round((value/4095)**.55*127)),raw_value=value))
   return events
  return []
