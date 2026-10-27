"""Fokus fein: MK2-only chrome and a fixed, legible eight-encoder footer.

The Mikro and legacy renderers retain their own typography. No image scaling,
font loading or disk work occurs here. All coordinates are native LCD pixels.
"""
from app.fokus import Canvas as BaseCanvas
from app.lcd_text import display_text

FOOTER_TOP=46
LABEL_Y=48
VALUE_Y=54
GRID_TOP=20
BOTTOM=60
CAPTIONS={'PROBABILITY':'PROB.','COUNT BARS':'COUNT-IN','BRIGHTNESS':'BRIGHT.',
          'PAD CURVE':'CURVE','TARGET SLOT':'TARGET','RECORD QUANTIZE':'REC QUANT.',
          'SONG SCROLL':'SCROLL','SONG ZOOM':'ZOOM','MIDI CHANNEL':'MIDI CH.',
          'AUDIO BUFFER':'BUFFER','FIRST SOUND':'FIRST','CHOKE GROUP':'CHOKE',
          'METRO LEVEL':'METRO LVL','RESONANCE':'RESON.','HEADPHONE LEVEL':'HEADPHONES',
          'SPEAKER LEVEL':'SPEAKERS','CHORD MODE':'CHORD','CHORD TYPE':'TYPE'}


class Canvas(BaseCanvas):
    def __init__(self,width=256):
        if width!=256:raise ValueError('MK2 layout requires 256 pixels')
        super().__init__(width);self.last_title=('', '',False)

    def text(self,x,y,value,limit=None,font='regular5',ink=None,center=None):
        # Shared plot/list helpers also use this canvas, so names in chain,
        # route and macro graphics follow the same whole-glyph fitting rule.
        value=display_text(str(value))
        if limit is not None and self.text_width(value,font)>limit:
            while value and self.text_width(value+'...',font)>limit:value=value[:-1]
            value+='...'
        super().text(x,y,value,limit,font,ink,center)

    def fitted(self,x,y,value,limit,font='regular5',ink=None,center=None):
        """Elide whole glyphs, never silently truncate half a number/glyph."""
        super().fitted(x,y,value,limit,font,ink,center)

    def header(self,keys,active=()):
        for i,key in enumerate(keys[:4]):
            if not key or key=='-':continue
            x=2+i*63;chosen=i in active
            if chosen:self.rect(x,1,61,10)
            font=bold_font(self,key,57)
            self.fitted(x+2,3,key,57,font,ink=self.bg if chosen else self.ink,center=x+30)
        self.rect(2,12,252,1)

    def title(self,title,detail='',compact=False):
        self.last_title=(title,str(detail),compact)
        self.rect(2,14,252,9,self.bg)
        font='regular5' if compact else 'regular7';y=14 if compact else 15
        detail=str(detail);space=min(116,self.text_width(detail)+6) if detail else 0
        self.fitted(4,y,title,248-space,font)
        if detail:self.fitted(252-space,14 if compact else 16,detail,space-2)

    def rows(self,rows,y=24,step=7):
        for i,row in enumerate(rows):
            selected=str(row).startswith('>');value=str(row).lstrip('> ');yy=y+i*step
            if selected:self.rect(3,yy-1,250,7)
            self.fitted(5,yy,value,246,ink=self.bg if selected else self.ink)

    def message(self,message):
        # A transient notice may cover body content, never the encoder footer.
        if message:
            self.rect(3,24,250,9)
            self.fitted(5,26,message,246,ink=self.bg)


def bold_font(c,value,width):
    # Values/softkeys keep both weight and seven-row height when space is tight.
    return 'bold7' if c.text_width(value,'bold7')<=width else 'bold7_compact'


def parameters(c,fields,grid=False):
    if not any(fields):return
    c.rect(2,FOOTER_TOP,252,15,c.bg);c.rect(2,FOOTER_TOP,252,1)
    for i,field in enumerate(fields):
        if field is None:continue
        label,value=field;x=3+i*63
        label=str(label).replace('_',' ').upper();label=CAPTIONS.get(label,label)
        c.fitted(x+1,LABEL_Y,label,58,center=x+29)
        value=str(value)
        font=bold_font(c,value,58)
        y=VALUE_Y
        c.fitted(x+1,y,value,58,font,center=x+29)
