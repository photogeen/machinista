"""Maschine MK2 HID protocol (17cc:1140), independent of the Mikro driver.

Protocol reference: shaduzlabs/cabl, MaschineMK2 (MIT, Vincenzo Pacella).
Sizes validated against the attached MK2 HID report descriptor, 2026-10-10.
"""
import os
from pathlib import Path

BUTTONS = tuple([f'DISPLAY {n}' for n in range(1,9)] + [
    'CONTROL','STEP','BROWSE','SAMPLING','PAGE LEFT','PAGE RIGHT','ALL','AUTO',
    'VOLUME','SWING','TEMPO','MASTER LEFT','MASTER RIGHT','ENTER','NOTE REPEAT','MASTER PUSH',
] + [f'GROUP {c}' for c in 'ABCDEFGH'] + [
    'RESTART','TRANSPORT LEFT','TRANSPORT RIGHT','GRID','PLAY','REC','ERASE','SHIFT',
    'SCENE','PATTERN','PAD MODE','NAVIGATE','DUPLICATE','SELECT','SOLO','MUTE'])
LED_BUTTONS = ('CONTROL','STEP','BROWSE','SAMPLING','PAGE LEFT','PAGE RIGHT','ALL','AUTO') + tuple(f'DISPLAY {n}' for n in range(1,9)) + ('SCENE','PATTERN','PAD MODE','NAVIGATE','DUPLICATE','SELECT','SOLO','MUTE','VOLUME','SWING','TEMPO','MASTER LEFT','MASTER RIGHT','ENTER','NOTE REPEAT')
TRANSPORT = ('RESTART','TRANSPORT LEFT','TRANSPORT RIGHT','GRID','PLAY','REC','ERASE','SHIFT')
PAD_SLOTS = (12,13,14,15,8,9,10,11,4,5,6,7,0,1,2,3)


def open_device(path):
    device=Path(path)
    identity=(Path('/sys/class/hidraw')/device.name/'device/uevent').read_text()
    if 'HID_ID=0003:000017CC:00001140' not in identity:raise ValueError('not Maschine MK2')
    return os.open(device,os.O_RDWR|os.O_NONBLOCK)


def send(fd,report):
    sizes={0x80:49,0x81:57,0x82:32,0xe0:265,0xe1:265}
    if not report or len(report)!=sizes.get(report[0]):raise ValueError('invalid MK2 output report')
    if os.write(fd,report)!=len(report):raise OSError('short MK2 HID write')


_BINARY_ASCII=bytes([48]+[49]*255)

def display_reports(pixels,display):
    if len(pixels)!=256*64 or display not in (0,1):raise ValueError('expected MK2 display 256x64')
    packed=int(bytes(pixels).translate(_BINARY_ASCII),2).to_bytes(2048,'big')
    return [bytes((0xe0|display,0,0,chunk*8,0,32,0,8,0))+packed[chunk*256:(chunk+1)*256] for chunk in range(8)]


def led_reports(buttons=None,pads=None,groups=None):
    buttons=buttons or {};pads=pads or {};groups=groups or {}
    mono=bytearray(32);mono[0]=0x82
    group=bytearray(57);group[0]=0x81
    pad=bytearray(49);pad[0]=0x80
    for i,name in enumerate(LED_BUTTONS):mono[1+i]=max(0,min(127,int(buttons.get(name,0))))
    for i,name in enumerate(TRANSPORT):group[49+i]=max(0,min(127,int(buttons.get(name,0))))
    for i,c in enumerate('ABCDEFGH'):
        rgb=bytes(max(0,min(127,int(v))) for v in groups.get(c,(0,0,0)))
        if len(rgb)!=3:raise ValueError('invalid group RGB')
        group[1+i*6:7+i*6]=rgb*2
    for raw,slot in enumerate(PAD_SLOTS):
        rgb=bytes(max(0,min(127,int(v))) for v in pads.get(slot,(0,0,0)))
        if len(rgb)!=3:raise ValueError('invalid pad RGB')
        pad[1+raw*3:4+raw*3]=rgb
    return bytes(mono),bytes(group),bytes(pad)


class ButtonsDecoder:
    """Lossless button edges and wrapped counters; first frame is a baseline."""
    def __init__(self):self.buttons=0;self.encoders=None
    def decode(self,data):
        if len(data)!=25 or data[0]!=1:return []
        counters=[data[8]&15]+[int.from_bytes(data[i:i+2],'little') for i in range(9,25,2)]
        if data[8]>15 or any(v>999 for v in counters[1:]):return []
        buttons=int.from_bytes(data[1:8],'little');events=[]
        for bit,name in enumerate(BUTTONS):
            if (buttons^self.buttons)&(1<<bit):events.append(('button',name,bool(buttons&(1<<bit))))
        self.buttons=buttons
        if self.encoders is not None:
            for i,(value,old) in enumerate(zip(counters,self.encoders)):
                modulus=16 if i==0 else 1000
                delta=(value-old+modulus//2)%modulus-modulus//2
                if delta and abs(delta)!=modulus//2:events.append(('encoder',i,delta))
        self.encoders=counters
        return events
