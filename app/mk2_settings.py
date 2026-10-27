"""Descriptor-confirmed MK2 F8/F9 display registers (256x64, 11 bytes).

Brightness byte8 is shared by hardware; contrast byte9 is independent.
Read/modify/write preserves all other fields. Call only in the USB worker.
"""
import fcntl

def read_feature(fd,rid):
    if rid not in (0xf8,0xf9):raise ValueError('invalid MK2 display')
    data=bytearray([rid]+[0]*10)
    count=fcntl.ioctl(fd,(3<<30)|(11<<16)|(ord('H')<<8)|7,data,True)
    if count!=11 or data[:5]!=bytes((rid,0,1,64,0)) or any(x>100 for x in data[8:10]):
        raise ValueError('unexpected MK2 display feature report')
    return data

def write_feature(fd,data):
    if len(data)!=11 or data[0] not in (0xf8,0xf9) or data[1:5]!=bytes((0,1,64,0)) or any(x>100 for x in data[8:10]):
        raise ValueError('invalid MK2 display feature report')
    if fcntl.ioctl(fd,(3<<30)|(11<<16)|(ord('H')<<8)|6,data,True)!=11:raise OSError('short MK2 feature write')

def configure_displays(fd,values):
    before=[read_feature(fd,0xf8),read_feature(fd,0xf9)]
    keys=('brightness','contrast_left','contrast_right')
    desired={key:values.get(key) for key in keys}
    for key,value in desired.items():
        if value is not None and (type(value) is not int or not 0<=value<=100):raise ValueError('invalid MK2 '+key)
    desired={key:desired[key] if desired[key] is not None else before[0 if key!='contrast_right' else 1][8 if key=='brightness' else 9] for key in keys}
    for index,key in enumerate(keys[1:]):
        data=before[index].copy();data[8]=desired['brightness'];data[9]=desired[key]
        if data!=before[index]:write_feature(fd,data)
    after=[read_feature(fd,0xf8),read_feature(fd,0xf9)]
    if any(b[8]!=desired['brightness'] for b in after) or after[0][9]!=desired['contrast_left'] or after[1][9]!=desired['contrast_right']:
        raise OSError('MK2 display settings readback mismatch')
    return desired
