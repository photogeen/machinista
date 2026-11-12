"""Renderer-local color roles. Never mutate shared palettes or hardware LEDs."""
from contextvars import ContextVar
from functools import wraps

DEFAULT_SCHEME='original'
# Stored identifiers stay compatible with existing controller preferences.
SCHEMES=('original','current','furnace','polar','voltage','amber','daylight')
LABELS=dict(zip(SCHEMES,('Plus','Classic','Furnace','Polar','Voltage','Amber','Daylight')))
# bg, panel, line, text, muted, accent, position, envelope, filter, level, error
BASE=('#11161e','#202b3a','#344151','#f1f4f7','#a7b2c0','#ff8000','#00dcff','#bc63ff','#ffda00','#25ee77','#ff304f')
PALETTES={
 'current':BASE,
 'furnace':('#101316','#22292f','#39434c','#faf5eb','#aab8c2','#ff891f','#49dfff','#c492ff','#fff076','#4aefa0','#ff5267'),
 'polar':('#071722','#122f40','#285269','#f2fcff','#9bbdce','#12e1f1','#ff765e','#c4a0ff','#ffe467','#46e6ab','#ff5267'),
 'voltage':('#100e19','#282039','#4a3c62','#f9f4ff','#b7a9ce','#b17aff','#c7ff45','#ed9dff','#ffcf40','#50edac','#ff5267'),
 'amber':('#17130d','#30281b','#50432e','#fff2d4','#c1b08f','#ffbe3b','#f3e2b5','#e7b66d','#ffffff','#e5d59b','#ff6970'),
 # Sampled from the Maschine+ Sampling and Settings manual screenshots.
 'original':('#101010','#1a1a1a','#474747','#ffffff','#b2b2b2','#ff3c14','#b2b2b2','#dedede','#fff000','#ff3c14','#ff304f'),
 'daylight':('#eeeae2','#ffffff','#c5c1b8','#242628','#61676b','#cb4b00','#006c8a','#8546ac','#806000','#007a45','#ba253d'),
}
_active=ContextVar('mk3_color_scheme',default='current')
class GroupColor(str):
    """Group A and the current accent share RGB, but have different roles."""

def resolve(color,scheme=None):
    if color is None or isinstance(color,GroupColor) or not isinstance(color,str):return color
    scheme=scheme or _active.get()
    values=PALETTES.get(scheme,BASE)
    try:return values[BASE.index(color.lower())]
    except ValueError:return color

def themed(function):
    @wraps(function)
    def wrapped(self,*args,**kwargs):
        state=kwargs.get('state',args[-1] if args else {})
        scheme=state.get('color_scheme',DEFAULT_SCHEME)
        token=_active.set(scheme if scheme in SCHEMES else DEFAULT_SCHEME)
        try:return function(self,*args,**kwargs)
        finally:_active.reset(token)
    return wrapped

def active():return _active.get()

def rotate(app,delta):
    if app.controller_source not in ('mk3','plus'):return
    from app.controller_settings import save_display
    values=app.settings['controllers'][app.controller_source]
    current=values.get('color_scheme',DEFAULT_SCHEME)
    index=SCHEMES.index(current) if current in SCHEMES else 0
    save_display(app,'color_scheme',SCHEMES[max(0,min(len(SCHEMES)-1,index+delta))])


def foreground(color):
    """Readable text on literal group colors, also in the light palette."""
    from PIL import ImageColor
    resolved=resolve(color)
    r,g,b=ImageColor.getrgb(resolved) if isinstance(resolved,str) else resolved[:3]
    return GroupColor('#101316' if .2126*r+.7152*g+.0722*b>145 else '#faf5eb')
