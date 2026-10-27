"""Renderer-owned, clipped name scrolling. No engine timers or model mutations."""
import math
import time

class Marquee:
    def __init__(self):self.context=None;self.entries={};self.seen=set();self.active=False
    def begin(self,context):
        if context!=self.context:self.entries.clear();self.context=context
        self.seen=set();self.active=False
    def offset(self,key,value,width,extent,speed=18,now=None):
        if extent<=width:return None
        now=time.monotonic() if now is None else now
        self.active=True;self.seen.add(key);identity=(value,width,extent)
        old=self.entries.get(key)
        if old is None or old[0]!=identity:self.entries[key]=(identity,now)
        age=max(0,now-self.entries[key][1]);distance=extent-width
        phase=age%(4+distance/speed)
        return min(distance,max(0,int((phase-2)*speed)))
    def end(self):
        self.entries={k:v for k,v in self.entries.items() if k in self.seen}

def context(state):
    return tuple(state.get(k) for k in ('page','page_index','group','pad'))

def mikro_names(marquee,state,pixels):
    """Scroll only the first-page overview name, inside its existing 96x5 cell."""
    from app.fokus import enabled,Canvas
    from app.lcd_text import display_text
    overview=state.get('micro_overview') if enabled() and state.get('kind')=='CONTROL' and state.get('page')=='PLUGIN' else None
    marquee.begin((state.get('page'),state.get('title')))
    if overview:
        value=display_text(str(overview['name'])).upper();c=Canvas()
        offset=marquee.offset('overview',value,96,c.text_width(value),speed=12)
        if offset:
            from app.lcd_font import FONTS
            glyphs=FONTS['regular5'];digit=max(len(glyphs[v][0]) for v in '0123456789')
            result=bytearray(pixels);x=27-offset
            for y in range(37,42):result[y*128+27:y*128+123]=bytes([1])*96
            for char in value:
                glyph=glyphs.get(char,glyphs[' '])
                for dy,row in enumerate(glyph):
                    for dx,bit in enumerate(row):
                        if bit=='1' and 27<=x+dx<123:result[(37+dy)*128+x+dx]=0
                x+=(digit if char.isdigit() else len(glyph[0]))+1
            pixels=bytes(result)
    marquee.end()
    return pixels

def bitmap_names(marquee,state,frames):
    from app.mk2_font import FONTS
    from app.lcd_text import display_text
    from app.fokus import enabled
    marquee.begin(context(state));result=list(frames)
    if state['page']=='PAD CONFIG':
        targets=[]
        for i,f in enumerate(state.get('fields',())):
            if f and f[0].upper() in ('SCALE','PRESET'):
                targets.append((i//4,4+(i%4)*63,54,58,f[1],('field',i)))
        if enabled() and state.get('keyboard_custom'):
            targets.append((0,4,26,246,state.get('chord_name',''),'chord'))
        for side,x,y,width,value,key in targets:
            value=display_text(str(value)).upper();glyphs=FONTS['bold7']
            digit=max(len(glyphs[c][0]) for c in '0123456789')
            def advance(c):return (digit if c.isdigit() else len(glyphs.get(c,glyphs[' '])[0]))+1
            extent=max(0,sum(advance(c) for c in value)-1)
            offset=marquee.offset(key,value,width,extent)
            if offset is None:continue
            if not isinstance(result[side],bytearray):result[side]=bytearray(result[side])
            pixels=result[side]
            for yy in range(y,y+7):pixels[yy*256+x:yy*256+x+width]=bytes(width)
            position=x-offset
            for c in value:
                for dy,row in enumerate(glyphs.get(c,glyphs[' '])):
                    for dx,bit in enumerate(row):
                        if bit=='1' and x<=position+dx<x+width:pixels[(y+dy)*256+position+dx]=1
                position+=advance(c)
    marquee.end()
    return tuple(bytes(p) for p in result)

def color_names(marquee,state,images):
    from PIL import Image,ImageDraw
    from app.mk3_graphics import font,BG,INK,content_y
    from app.mk3_style import parameter_color
    marquee.begin(context(state));result=list(images)
    if state['page']=='PAD CONFIG' and state.get('keyboard_custom'):
        targets=[(0,20,105,440,30,state.get('chord_name',''),22,INK,BG,'chord'),
                 (1,15,194,450,20,state.get('chord_name',''),12,'#a7b2c0',BG,'caption')]
        for i,f in enumerate(state.get('fields',())):
            if f and f[0].upper()=='PRESET':
                targets.append((i//4,(i%4)*120+10,242,104,22,f[1],17,BG,parameter_color(f[0],state.get('group',0)),('field',i)))
        for side,x,y,width,height,value,size,ink,bg,key in targets:
            value=str(value);face=font(size,True);extent=math.ceil(face.getlength(value))
            offset=marquee.offset(key,value,width,extent,speed=42)
            if offset is None:continue
            tile=Image.new('RGB',(width,height),bg)
            ImageDraw.Draw(tile).text((-offset,0),value,font=face,fill=ink)
            result[side].paste(tile,(x,content_y(y,side==1)))
    marquee.end()
    return tuple(result)
