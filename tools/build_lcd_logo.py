"""Build approved logo 6: Helvetica Neue Bold, with the unchanged device icon.

Native monochrome glyph rasterization with one visible baseline per logo.
Font/Pillow are build-time only; the Pi uses the checked-in cached masks.
Use --font to provide Helvetica Neue on a different build host.
"""
import argparse
import base64
from pathlib import Path
import zlib
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
FONT='/System/Library/Fonts/HelveticaNeue.ttc'
LAYOUTS={
    120:dict(height=17,icon=18,gap=3,pads=(6,5,2,2,3,3)),
    236:dict(height=33,icon=36,gap=6,pads=(12,12,4,4,5,5)),
}


def word_glyphs(available,height,font_path=FONT):
    for size in range(48,5,-1):
        font=ImageFont.truetype(font_path,size,index=1)
        glyphs=[]
        for character in 'Machinista':
            bounds=font.getbbox(character)
            im=Image.new('1',(max(1,bounds[2]-bounds[0]),max(1,bounds[3]-bounds[1])))
            draw=ImageDraw.Draw(im);draw.fontmode='1'
            draw.text((-bounds[0],-bounds[1]),character,font=font,fill=1)
            glyphs.append(im.crop(im.getbbox()))
        if sum(g.width for g in glyphs)+len(glyphs)-1<=available and max(g.height for g in glyphs)<=height:
            return glyphs
    raise ValueError('Selected font does not fit native logo size')


def icon_mask(layout):
    width,height=layout['icon'],layout['height'];im=Image.new('1',(width,height));d=ImageDraw.Draw(im)
    large=width>20
    d.rounded_rectangle((0,0,width-1,height-1),radius=2 if large else 1,fill=1)
    if large:
        bars=((3,3,16,5),(19,3,32,5));dots=(14,19,24,29);dot_y=8
        # Circular knob: black ring, bright annular cutout and black centre.
        d.ellipse((2,12,9,19),fill=0);d.ellipse((3,13,8,18),fill=1);d.ellipse((4,14,7,17),fill=0)
        buttons=((3,y,7,y+1) for y in (22,26,29))
    else:
        bars=((2,1,8,1),(10,1,15,1));dots=(7,10,13,16);dot_y=3
        d.rectangle((1,6,4,9),fill=0);d.rectangle((2,7,3,8),fill=1)
        buttons=((2,y,3,y) for y in (11,13,15))
    for box in bars:d.rectangle(box,fill=0)
    for x in dots:
        d.rectangle((x,dot_y,x+(1 if large else 0),dot_y+(1 if large else 0)),fill=0)
    for box in buttons:d.rectangle(box,fill=0)
    x,y,w,h,dx,dy=layout['pads']
    for row in range(4):
        for col in range(4):d.rectangle((x+col*dx,y+row*dy,x+col*dx+w-1,y+row*dy+h-1),fill=0)
    return im



def lcd_logo(width,font_path=FONT):
    layout=LAYOUTS[width];height=layout['height']
    glyphs=word_glyphs(width-layout['icon']-layout['gap']-2,height-3,font_path)
    used=layout['icon']+layout['gap']+sum(g.width for g in glyphs)+len(glyphs)-1
    x=(width-used)//2;im=Image.new('1',(width,height))
    im.paste(icon_mask(layout),(x,0));x+=layout['icon']+layout['gap']
    tallest=max(g.height for g in glyphs)
    baseline=(height-tallest)//2+tallest-1
    for glyph in glyphs:
        im.paste(glyph,(x,baseline-glyph.height+1));x+=glyph.width+1
    return height,bytes(bool(v) for v in im.convert('L').tobytes())


def build(font_path=FONT):
    masks={}
    for width in LAYOUTS:
        height,data=lcd_logo(width,font_path)
        masks[width]=(height,base64.b85encode(zlib.compress(data,9)).decode())
    (ROOT/'app/branding_bitmaps.py').write_text(
        '\"\"\"Approved Helvetica Neue Bold LCD logo masks; rebuild with tools/build_lcd_logo.py.\"\"\"\nBITMAPS = '+repr(masks)+'\n')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--font',default=FONT,help='Helvetica Neue TTC; bold face index 1')
    build(parser.parse_args().font)
