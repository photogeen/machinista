"""Color Layers roles; group identity is independent from selection/status."""
from PIL import ImageColor
from app.mk3_graphics import BG,ACCENT,GROUPS
CYAN='#00dcff';PURPLE='#bc63ff';YELLOW='#ffda00';GREEN='#25ee77';RED='#ff304f'

def tint(color,amount=.14,background='#000000'):
    a=ImageColor.getrgb(color);b=ImageColor.getrgb(background)
    return tuple(round(x*amount+y*(1-amount)) for x,y in zip(a,b))

def parameter_color(label,group=0):
    name=label.upper()
    if name=='END' or name.endswith(' END'):return PURPLE
    if name=='VELOCITY':return ACCENT
    if any(v in name for v in ('CUTOFF','RESONANCE','FILTER','KEYTRACK')):return YELLOW
    if any(v in name for v in ('ATTACK','DECAY','SUSTAIN','RELEASE','ENV','PITCH','PROB')):return PURPLE
    if any(v in name for v in ('START','POSITION','LENGTH','RATE','LFO','MOD','SCROLL','END')):return CYAN
    if any(v in name for v in ('GAIN','LEVEL','VOLUME','PAN','VELOCITY','PEAK','CPU','RAM')):return GREEN
    if any(v in name for v in ('SOUND','GROUP','BANK','PATCH','EVENT','SLICE')):return GROUPS[group%8]
    return ACCENT
