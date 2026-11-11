"""480x272 color drawing primitives; native Pillow operations, RGB565 wire bytes."""
import math
from pathlib import Path
from functools import lru_cache
from app.mk3_theme import GroupColor,resolve,active
from PIL import Image,ImageDraw,ImageFont,ImageChops
WIDTH,HEIGHT=480,272
BG='#11161e';PANEL='#202b3a';LINE='#344151';INK='#f1f4f7';MUTED='#a7b2c0';ACCENT='#ff8000'
# LCD colors in A–H order. Give red and violet distinct RGB565 channel
# balances from orange and pink, even on bright LCD panels.
GROUPS=tuple(GroupColor(v) for v in (
 '#ff3c14','#ff0000','#f6c400','#70d522','#00c7a2','#0088ff','#862cff','#f028ba',
))
@lru_cache(maxsize=48)
def font(size=16,bold=False):
 name='DejaVuSans'+('-Bold' if bold else '')+'.ttf'
 for folder in (Path(__file__).resolve().parents[1]/'assets/fonts',Path('/usr/share/fonts/truetype/dejavu')):
  if (folder/name).is_file():return ImageFont.truetype(str(folder/name),size,layout_engine=ImageFont.Layout.BASIC)
 return ImageFont.load_default(size=size)
@lru_cache(maxsize=1024)
def text_stamp(value,size,bold,color,width):
 f=font(size,bold)
 if width is not None:
  while value and f.getlength(value)>width:value=value[:-1]
 length=f.getlength(value);bounds=f.getbbox(value)
 tile=Image.new('RGBA',(max(1,math.ceil(max(length,bounds[2]))+1),max(1,bounds[3]+1)))
 ImageDraw.Draw(tile).text((0,0),value,font=f,fill=color)
 return tile,length

def content_y(y,compact_header=False):
 # Right display omits the shared group/transport row. Header keys and the
 # encoder footer keep their physical alignment; body artwork remains native.
 return y-26 if compact_header and 59<=y<216 else y

class Canvas:
 def __init__(self,compact_header=False):
  self.compact_header=compact_header;self.scheme=active()
  self.image=Image.new('RGB',(WIDTH,HEIGHT),resolve(BG,self.scheme));self.draw=ImageDraw.Draw(self.image)
 def rect(self,x,y,w,h,fill=PANEL,outline=None,radius=0):
  if w<=0 or h<=0:return
  y=content_y(y,self.compact_header)
  self.draw.rounded_rectangle((x,y,x+w-1,y+h-1),radius=radius,fill=resolve(fill,self.scheme),outline=resolve(outline,self.scheme))
 def text(self,x,y,value,size=16,bold=False,color=INK,width=None,center=False):
  stamp,length=text_stamp(str(value).replace('\n',' '),size,bold,resolve(color,self.scheme),width)
  if center:x-=length/2
  self.image.paste(stamp,(round(x),round(content_y(y,self.compact_header))),stamp)
 def line(self,points,color=INK,width=1):
  if points and isinstance(points[0],(tuple,list)):
   points=tuple((x,content_y(y,self.compact_header)) for x,y in points)
  else:points=tuple(content_y(v,self.compact_header) if i%2 else v for i,v in enumerate(points))
  self.draw.line(points,fill=resolve(color,self.scheme),width=width)
 def polygon(self,points,color=INK):
  self.draw.polygon(tuple((x,content_y(y,self.compact_header)) for x,y in points),fill=resolve(color,self.scheme))
 def wire(self,invert=False):return rgb565(self.image,invert)

def rgb565(image,invert=False):
 if image.size!=(WIDTH,HEIGHT):raise ValueError('Expected MK3 color display')
 from app.mk3_pixels import pack
 accelerated=pack(image.convert('RGB').tobytes(),invert)
 if accelerated is not None:return accelerated
 r,g,b=image.convert('RGB').split()
 hi=ImageChops.add(r.point([v&248 for v in range(256)]),g.point([v>>5 for v in range(256)]))
 lo=ImageChops.add(g.point([(v&28)<<3 for v in range(256)]),b.point([v>>3 for v in range(256)]))
 if invert:hi=hi.point([255-v for v in range(256)]);lo=lo.point([255-v for v in range(256)])
 return Image.merge('LA',(hi,lo)).tobytes()
