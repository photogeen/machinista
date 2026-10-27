"""Full-size Maschine MK1 USB wire format (17cc:0808).

Protocol reference: shaduzlabs/cabl, MaschineMK1/GDisplayMaschineMK1,
Copyright (c) 2015 Vincenzo Pacella, MIT. This is not the Mikro HID protocol.
MK1 LCDs have 255 addressable columns, 64 rows, inverted 5-bit pixels,
three pixels per 16-bit word. Keep transport separate from the audio engine.
"""
VID,PID=0x17cc,0x0808
WIDTH,HEIGHT=255,64
BUTTONS=('MUTE','SOLO','SELECT','DUPLICATE','NAVIGATE','PAD MODE','PATTERN','SCENE',
         None,'REC','ERASE','SHIFT','GRID','TRANSPORT RIGHT','TRANSPORT LEFT','RESTART',
         'GROUP E','GROUP F','GROUP G','GROUP H','GROUP D','GROUP C','GROUP B','GROUP A',
         'CONTROL','BROWSE','PAGE LEFT','ALL','AUTO','PAGE RIGHT','SAMPLING','STEP',
         'DISPLAY 8','DISPLAY 7','DISPLAY 6','DISPLAY 5','DISPLAY 4','DISPLAY 3','DISPLAY 2','DISPLAY 1',
         'NOTE REPEAT','PLAY')
LED_NAMES=tuple(f'PAD {p}' for p in (4,3,2,1,8,7,6,5,12,11,10,9,16,15,14,13))+(
    'MUTE','SOLO','SELECT','DUPLICATE','NAVIGATE','PAD MODE','PATTERN','SCENE',
    'SHIFT','ERASE','GRID','TRANSPORT RIGHT','REC','PLAY',None,'TRANSPORT LEFT','RESTART',
    'GROUP H','GROUP G','GROUP D','GROUP C','GROUP F','GROUP E','GROUP B','GROUP A',
    'AUTO','ALL','PAGE RIGHT','PAGE LEFT','SAMPLING','BROWSE','STEP','CONTROL',
    'DISPLAY 8','DISPLAY 7','DISPLAY 6','DISPLAY 5','DISPLAY 4','DISPLAY 3','DISPLAY 2','DISPLAY 1',
    'NOTE REPEAT','BACKLIGHT',None,None,None)
# Raw encoder pair order -> eight screen knobs (0..7), volume/swing/tempo (8..10).
ENCODER_ORDER=(7,3,9,6,2,10,5,1,8,4,0)
PAD_SLOTS=(12,13,14,15,8,9,10,11,4,5,6,7,0,1,2,3)

# Binary LCD frames only need eight possible triples. Avoid per-pixel float
# scaling/generators in the output thread competing for the UI's Python GIL.
_BINARY_PIXELS=bytes([0]+[1]*255)
_BINARY_TRIPLES=tuple(bytes((((0 if code&4 else 31)<<3)|((0 if code&2 else 31)>>2),
                            (((0 if code&2 else 31)&3)<<6)|(0 if code&1 else 31)|32))
                      for code in range(8))

def pack_frame(image):
    if hasattr(image,'size'):
        if image.size!=(WIDTH,HEIGHT):raise ValueError('MK1 frame must be 255x64')
        values=list(image.convert('L').getdata())
    else:
        if len(image)!=WIDTH*HEIGHT:raise ValueError('MK1 frame must be 255x64')
        bits=bytes(image).translate(_BINARY_PIXELS)
        return b''.join(_BINARY_TRIPLES[(bits[i]<<2)|(bits[i+1]<<1)|bits[i+2]] for i in range(0,len(bits),3))
    output=bytearray()
    for y in range(HEIGHT):
        for x in range(0,WIDTH,3):
            a,b,c=(31-round(values[y*WIDTH+x+i]*31/255) for i in range(3))
            output.extend(((a<<3)|(b>>2),((b&3)<<6)|c|0x20))
    return bytes(output)

def frame_packets(display,frame):
    if display not in (0,1) or len(frame)!=10880:raise ValueError('invalid MK1 frame')
    d=display*2
    yield bytes((d,0,3,0x75,0,0x3f))
    yield bytes((d,0,3,0x15,0,0x54))
    yield bytes((d,1,0xf7,0x5c))+frame[:502]
    for offset in range(502,10542,502):yield bytes((d+1,1,0xf6))+frame[offset:offset+502]
    yield bytes((d+1,1,0x52))+frame[10542:]

def init_packets(display):
    if display not in (0,1):raise ValueError('invalid MK1 display')
    commands=((0,1,0x30),(0,4,0xca,4,15,0),(0,2,0xbb,0),(0,1,0xd1),
      (0,1,0x94),(0,3,0x81,0x1e,2),(0,2,0x20,8),(0,2,0x20,11),
      (0,1,0xa7),(0,1,0x31),(0,4,0x32,0,0,5),(0,1,0x34),(0,1,0x30),
      (0,4,0xbc,0,1,2),(0,3,0x75,0,0x3f),(0,3,0x15,0,0x54),
      (0,1,0x5c),(0,1,0x25),(0,1,0xaf),(0,4,0xbc,2,1,1),
      (0,1,0xa7),(0,3,0x81,0x25,2))
    return tuple(bytes((display*2,)+c) for c in commands)

def led_packets(values):
    data=bytearray(62)
    for name,value in values.items():
        if name not in LED_NAMES:raise ValueError('unknown MK1 LED '+str(name))
        if type(value) is not int or not 0<=value<=255:raise ValueError('invalid MK1 brightness')
        data[LED_NAMES.index(name)]=value
    return bytes((12,0))+data[:31],bytes((12,30))+data[31:]

def buttons(report):
    if len(report)<7 or report[0]!=4:raise ValueError('invalid MK1 button report')
    return {name for i,name in enumerate(BUTTONS) if name and report[1+i//8]&(1<<(i%8))}


def pad_samples(report):
    """EP84 has no report-ID prefix: 32 little-endian pressure words.

    Every word carries its own 4-bit pad ID. USB packet boundaries do not
    imply pad zero; preserve both samples and their exact order.
    """
    if len(report)!=64:raise ValueError('invalid MK1 pressure packet')
    return tuple((report[i+1]>>4,report[i]|((report[i+1]&15)<<8)) for i in range(0,64,2))


def is_pad_led(name):
    """PAD MODE is a button, not one of the sixteen pad LEDs."""
    return name in {f'PAD {i}' for i in range(1,17)}
