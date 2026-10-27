"""Mikro MK2 (17cc:1200): 128x64 LCD and 78-byte RGB/mono LED payload.

Addresses checked against the device HID descriptor and OpenAV-Ctlra's
ni_maschine_mikro_mk2 protocol reference. No firmware interface is used.
The logical states remain shared with Mikro MK1; only the wire format differs.
"""
import os
from pathlib import Path

BUTTON_LEDS = dict(zip((
    'F1','F2','F3','MAIN','NAV','NAV LEFT','NAV RIGHT','ENTER',
    'GROUP','BROWSE','SAMPLING','NOTE REPEAT','RESTART','TRANSPORT LEFT',
    'TRANSPORT RIGHT','GRID','PLAY','REC','ERASE','SHIFT','SCENE','PATTERN',
    'PAD MODE','VIEW','DUPLICATE','SELECT','SOLO','MUTE'),
    tuple(range(9))+tuple(range(11,30))))
GROUP_SLOTS=(12,13,14,15,8,9,10,11)
PAD_SLOTS=(12,13,14,15,8,9,10,11,4,5,6,7,0,1,2,3)
PALETTE=((100,25,0),(95,0,0),(95,55,0),(20,90,0),(0,80,45),(0,40,100),(60,0,100),(95,0,50))

def identity(path):
    data=(Path('/sys/class/hidraw')/Path(path).name/'device/uevent').read_text()
    if 'HID_ID=0003:000017CC:00001200' not in data:raise ValueError('not Mikro MK2')

def open_device(path):
    identity(path)
    return os.open(path,os.O_RDWR|os.O_NONBLOCK)

def send(fd,report):
    if not report or len(report)!={0x80:79,0xe0:265}.get(report[0]):raise ValueError('invalid Mikro MK2 output report')
    if os.write(fd,report)!=len(report):raise OSError('short Mikro MK2 write')

def led_report(legacy,channels,buttons,group=0):
    if len(legacy)!=61 or legacy[0]!=0x80:raise ValueError('expected logical Mikro LED report')
    report=bytearray(79);report[0]=0x80
    def level(index):return min(127,legacy[index+1]*4)
    for name,target in BUTTON_LEDS.items():
        source=buttons.get(name)
        if source is not None:report[target+1]=level(source)
    color=PALETTE[group%8]
    intensity=report[9]
    report[9:12]=bytes(round(c*intensity/124) for c in color)
    for raw,slot in enumerate(PAD_SLOTS):
        orange=level(channels[(slot,'orange')]);blue=level(channels[(slot,'blue')]) if (slot,'blue') in channels else 0
        rgb=PALETTE[GROUP_SLOTS.index(slot)] if blue and slot in GROUP_SLOTS else color
        intensity=max(orange,blue)
        report[31+raw*3:34+raw*3]=bytes(round(c*intensity/124) for c in rgb)
    return bytes(report)
