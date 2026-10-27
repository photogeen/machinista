#!/usr/bin/env python3
"""MK1 output experiment; uses only descriptor-confirmed output report IDs."""
import argparse
import os
from pathlib import Path

# Original tiny 3x5 diagnostic font; one row-major bit string per character.
GLYPHS = dict(zip('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_ ', [
    '010101111101101','110101110101110','011100100100011','110101101101110',
    '111100110100111','111100110100100','011100101101011','101101111101101',
    '111010010010111','001001001101010','101101110101101','100100100100111',
    '101111111101101','101111111111101','010101101101010','110101110100100',
    '010101101111011','110101110101101','011100010001110','111010010010010',
    '101101101101111','101101101101010','101101111111101','101101010101101',
    '101101010010010','111001010100111','111101101101111','010110010010111',
    '110001010100111','110001010001110','101101111001001','111100110001110',
    '011100110101010','111001010010010','010101010101010','010101011001110',
    '000000111000000','000000000000111','000000000000000']))
GLYPHS['<'] = '001011111011001'
GLYPHS['>'] = '100110111110100'
GLYPHS.update({':': '000010000010000', '/': '001001010100100',
               '.': '000000000000010', '+': '000010111010000',
               '%': '101001010100101', '?': '110001010000010'})


def text(pixels, x, y, value, scale=2):
    for char in value.upper():
        glyph = GLYPHS.get(char, GLYPHS[' '])
        for row in range(5):
            for col in range(3):
                if glyph[row*3+col] != '1':
                    continue
                for dy in range(scale):
                    for dx in range(scale):
                        px, py = x+col*scale+dx, y+row*scale+dy
                        if 0 <= px < 128 and 0 <= py < 64:
                            pixels[py*128+px] = 1
        x += 4*scale


def frame_reports(pixels, layout='pages'):
    """Four independent 32-column strips; Ctlra header, bounded MK1 report size."""
    if len(pixels) != 128*64:
        raise ValueError('expected 128x64 logical pixels')
    reports = []
    for segment in range(4):
        data = bytearray([0xe0, segment*32, 0, 0, 0, 32, 0, 8, 0])
        if layout == 'pages':
            for page in range(8):
                base=page*1024+segment*32
                rows=[pixels[base+bit*128:base+bit*128+32] for bit in range(8)]
                data.extend(bool(a)|(bool(b)<<1)|(bool(c)<<2)|(bool(d)<<3)|
                            (bool(e)<<4)|(bool(f)<<5)|(bool(g)<<6)|(bool(h)<<7)
                            for a,b,c,d,e,f,g,h in zip(*rows))
        else:
            for row in range(64):
                for octet in range(4):
                    data.append(sum((bool(pixels[row*128+segment*32+octet*8+bit]) << (7-bit))
                                    for bit in range(8)))
        assert len(data) == 265
        reports.append(bytes(data))
    return reports


def open_mk1(path):
    device = Path(path)
    identity = (Path('/sys/class/hidraw') / device.name / 'device/uevent').read_text()
    if 'HID_ID=0003:000017CC:00001110' not in identity:
        raise ValueError('not the verified USB Mikro MK1')
    return os.open(device, os.O_RDWR | os.O_NONBLOCK)


def send(fd, report):
    if not ((report[0] == 0x80 and len(report) == 61) or
            (report[0] == 0xe0 and len(report) == 265)):
        raise ValueError('unexpected output report')
    written = os.write(fd, report)
    if written != len(report):
        raise OSError(f'short HID write: {written}/{len(report)}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path')
    parser.add_argument('--level', type=int, default=16)
    parser.add_argument('--led-index', type=int, help='single zero-based LED payload byte')
    parser.add_argument('--layout', choices=['pages', 'rows'], default='pages')
    parser.add_argument('--label', default='DISPLAY TEST')
    parser.add_argument('--no-display', action='store_true')
    args = parser.parse_args()
    if not 0 <= args.level <= 31 or (args.led_index is not None and not 0 <= args.led_index < 60):
        parser.error('level must be 0..31; LED index must be 0..59')
    leds = bytearray(61)
    leds[0] = 0x80
    if args.led_index is None:
        leds[1:] = bytes([args.level])*60
    else:
        leds[args.led_index+1] = args.level
    fd = open_mk1(args.path)
    try:
        send(fd, leds)
        print('LED report accepted: 61 bytes', flush=True)
        if not args.no_display:
            pixels = bytearray(128*64)
            text(pixels, 4, 4, 'MACHINISTA')
            text(pixels, 4, 22, 'MIKRO MK1')
            text(pixels, 4, 42, args.label, 1)
            for x in range(128):
                pixels[63*128+x] = 1
            for report in frame_reports(pixels, args.layout):
                send(fd, report)
            print(f'Display reports accepted: 4 x 265 bytes ({args.layout})', flush=True)
    finally:
        os.close(fd)


if __name__ == '__main__':
    main()
