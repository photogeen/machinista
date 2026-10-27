"""Graphic workspaces sized for the verified 128x64 monochrome display."""
from pathlib import Path


def rectangle(pixels, x, y, width, height, fill=False):
    for yy in range(y, y+height):
        for xx in range(x, x+width):
            if 0 <= xx < 128 and 0 <= yy < 64 and (fill or yy in (y, y+height-1) or xx in (x, x+width-1)):
                pixels[yy*128+xx] = 1


def graphics(pixels, app, draw_text):
    if app.page in ('PATTERN', 'SCENE', 'GROUP', 'MUTE', 'SOLO'):
        pixels[24*128:57*128] = bytes(33*128)
        count = 8 if app.page == 'GROUP' else 16
        selected = app.group if app.page == 'GROUP' else app.pattern if app.page == 'PATTERN' else app.scene
        for index in range(count):
            x, y = 2+(index%8)*16, 25+(index//8)*16
            rectangle(pixels, x, y, 14, 13)
            label = chr(65+index) if app.page == 'GROUP' else str(index+1)
            draw_text(pixels, x+2, y+4, label, 1)
            active = index == selected
            if app.page in ('MUTE', 'SOLO'):
                active = app.project['groups'][app.group]['pads'][index][app.page.lower()]
            if active:
                for yy in range(y+1, y+12):
                    for xx in range(x+1, x+13):
                        pixels[yy*128+xx] ^= 1
        if app.page == 'GROUP':
            draw_text(pixels, 2, 44, 'A-D PADS13-16 E-H PADS9-12', 1)
        elif app.page == 'SCENE' and app.pending_scene is not None:
            draw_text(pixels, 2, 58, f'NEXT {app.pending_scene+1}', 1)
    elif app.page == 'STEP':
        pixels[24*128:57*128] = bytes(33*128)
        lane = app.lane()
        for index in range(16):
            x, y = 3+(index%8)*16, 25+(index//8)*13
            step = app.bank*16+index
            active = step < len(lane) and lane[step]
            rectangle(pixels, x, y, 12, 10, active)
            if app.playing and step == app.step % len(lane):
                rectangle(pixels, x-1, y-1, 14, 12)
        draw_text(pixels, 2, 52, f'{app.bank*16+1}-{min((app.bank+1)*16,len(lane))} {len(lane)//16} BAR', 1)
    elif app.page == 'MIXER':
        pixels[24*128:57*128] = bytes(33*128)
        bank = app.pad//8
        for index in range(8):
            slot = bank*8+index
            track = app.project['groups'][app.group]['pads'][slot]
            x = 3+index*16
            rectangle(pixels, x, 26, 8, 23)
            height = round(track['gain']/100*21)
            rectangle(pixels, x+1, 48-height, 6, height, True)
            draw_text(pixels, x, 52, str(slot+1), 1)
            if slot == app.pad:
                rectangle(pixels, x-1, 24, 10, 27)
    elif app.page in ('KEYBOARD', 'CHORD'):
        pixels[34*128:57*128] = bytes(23*128)
        for index in range(16):
            rectangle(pixels, index*8, 35, 8, 21)
            if (app.keyboard_root+index)%12 in (1, 3, 6, 8, 10):
                rectangle(pixels, index*8+2, 35, 4, 12, True)
        draw_text(pixels, 2, 58, 'MIDI OUT / PADS CHROMATIC', 1)
    elif app.page == 'SONG':
        pixels[24*128:57*128] = bytes(33*128)
        song = app.project['song']
        if not song:
            draw_text(pixels, 2, 30, 'EMPTY SONG', 1)
            draw_text(pixels, 2, 43, 'F1 INSERT CURRENT SCENE', 1)
        else:
            first = max(0, app.song_index-3)
            for column, index in enumerate(range(first, min(first+8, len(song)))):
                x = column*16+1
                rectangle(pixels, x, 29, 14, 15)
                draw_text(pixels, x+2, 34, str(song[index]+1), 1)
                if index == app.song_index:
                    rectangle(pixels, x, 46, 14, 2, True)
            draw_text(pixels, 2, 52, f'POS {app.song_index+1}/{len(song)}', 1)
