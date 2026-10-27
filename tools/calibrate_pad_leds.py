#!/usr/bin/env python3
"""Associate LED output bytes with physical pads and observed colors."""
import argparse
import json
import os
from pathlib import Path
import select
import time
from mikro_feedback import open_mk1, send, frame_reports, text


def show(fd, title, lines):
    pixels = bytearray(8192)
    text(pixels, 4, 3, title, 2)
    for index, line in enumerate(lines):
        text(pixels, 4, 23+index*11, line, 1)
    for report in frame_reports(pixels):
        send(fd, report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path')
    parser.add_argument('output', type=Path)
    parser.add_argument('--start', type=int, default=20)
    parser.add_argument('--end', type=int, default=60, help='exclusive end')
    parser.add_argument('--resume', action='store_true', help='retain already recorded indices')
    args = parser.parse_args()
    if not 0 <= args.start < args.end <= 60:
        parser.error('expected 0 <= start < end <= 60')
    fd = open_mk1(args.path)
    records = json.loads(args.output.read_text()) if args.resume else []
    buttons = 0
    try:
        for led_index in range(args.start, args.end):
            if any(row['payload_index'] == led_index for row in records):
                continue
            report = bytearray(61)
            report[0] = 0x80
            report[led_index+1] = 16
            send(fd, report)
            show(fd, f'LED {led_index}', ['PRESS LIT PAD', 'ENTER IF NO PAD'])
            print(f'LED {led_index}: press illuminated pad; ENTER skips non-pad channels', flush=True)
            selected = None
            stage = 'identify'
            color = None
            skipped = False
            deadline = time.monotonic()+120
            while time.monotonic() < deadline:
                if not select.select([fd], [], [], 0.2)[0]:
                    continue
                data = os.read(fd, 4096)
                if not data:
                    raise OSError('controller disconnected')
                if data[0] == 0x20 and len(data) == 65:
                    pressures = [0]*16
                    for offset in range(1, 65, 2):
                        word = int.from_bytes(data[offset:offset+2], 'little')
                        channel, pressure = word >> 12, word & 4095
                        pressures[channel] = max(pressures[channel], pressure)
                    if stage == 'identify':
                        active = [index for index, pressure in enumerate(pressures) if pressure >= 100]
                        if len(active) == 1:
                            channel = active[0]
                            selected = (3-channel//4)*4+channel%4
                            stage = 'release'
                    elif stage == 'release' and max(pressures) <= 60:
                        stage = 'color'
                        show(fd, f'PAD {selected+1}', ['F1 ORANGE', 'F2 BLUE', 'ENTER SKIP'])
                        print(f'Pad {selected+1}: F1 orange, F2 blue, ENTER skip', flush=True)
                elif data[0] == 1 and len(data) == 6:
                    current = int.from_bytes(data[1:5], 'little')
                    rising = current & ~buttons
                    buttons = current
                    if rising == (1 << 16):
                        skipped = True
                        stage = 'finish'
                    elif stage == 'color' and rising in (1 << 23, 1 << 22):
                        color = 'orange' if rising == (1 << 23) else 'blue'
                        stage = 'finish'
                    elif stage == 'finish' and current == 0:
                        row = {'payload_index': led_index, 'pad_slot': None if skipped else selected,
                               'color': None if skipped else color}
                        records.append(row)
                        args.output.write_text(json.dumps(records, indent=2)+'\n')
                        print(json.dumps(row), flush=True)
                        break
            else:
                raise TimeoutError(f'LED {led_index}: no completed identification; partial results saved')
        show(fd, 'DONE', ['LED MAP SAVED'])
    finally:
        send(fd, bytes([0x80]+[0]*60))
        os.close(fd)


if __name__ == '__main__':
    main()
