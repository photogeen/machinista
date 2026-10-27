#!/usr/bin/env python3
"""Label button presses one at a time using prompts on the controller LCD."""
import argparse
import json
import os
from pathlib import Path
import select
import time
from mikro_feedback import open_mk1, frame_reports, text, send

BUTTONS = ['RESTART', 'TRANSPORT LEFT', 'TRANSPORT RIGHT', 'GRID', 'PLAY', 'REC',
           'ERASE', 'SHIFT', 'GROUP', 'BROWSE', 'SAMPLING', 'NOTE REPEAT',
           'ENCODER PUSH', 'F1', 'F2', 'F3', 'NAV', 'NAV LEFT',
           'NAV RIGHT', 'ENTER', 'MAIN', 'SCENE', 'PATTERN', 'PAD MODE', 'VIEW',
           'DUPLICATE', 'SELECT', 'SOLO', 'MUTE']


def show(fd, label, progress):
    pixels = bytearray(8192)
    text(pixels, 4, 4, 'PRESS', 2)
    text(pixels, 4, 24, label, 2 if len(label) <= 15 else 1)
    text(pixels, 4, 48, progress, 1)
    for report in frame_reports(pixels):
        send(fd, report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path')
    parser.add_argument('output', type=Path)
    parser.add_argument('--buttons', nargs='+', default=BUTTONS,
                        help='quoted target labels, e.g. GROUP BROWSE SAMPLING')
    args = parser.parse_args()
    fd = open_mk1(args.path)
    results = []
    previous = 0
    try:
        for index, name in enumerate(args.buttons):
            show(fd, name, f'{index+1} OF {len(args.buttons)}')
            print(f'PRESS {name}', flush=True)
            pending = None
            deadline = time.monotonic()+120
            while time.monotonic() < deadline:
                if not select.select([fd], [], [], 0.2)[0]:
                    continue
                report = os.read(fd, 4096)
                if not report:
                    raise OSError('controller disconnected')
                if len(report) != 6 or report[0] != 1:
                    continue
                state = int.from_bytes(report[1:5], 'little')
                rising = state & ~previous
                previous = state
                if pending is None and rising:
                    if state.bit_count() != 1:
                        print('One button at a time; release and retry', flush=True)
                        continue
                    pending = state.bit_length()-1
                if pending is not None and state == 0:
                    record = {'name': name, 'bit': pending,
                              'byte': 1+pending//8, 'mask': f'0x{1 << (pending%8):02x}'}
                    results.append(record)
                    args.output.write_text(json.dumps(results, indent=2)+'\n')
                    print(json.dumps(record), flush=True)
                    break
            else:
                raise TimeoutError(f'no completed press for {name}; partial results saved')
        show(fd, 'DONE', 'BUTTONS RECORDED')
        print('DONE', flush=True)
    finally:
        os.close(fd)


if __name__ == '__main__':
    main()
