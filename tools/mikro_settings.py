#!/usr/bin/env python3
"""Read F8, or experimentally adjust one descriptor-confirmed percentage field."""
import argparse
import fcntl
import os
import json
from pathlib import Path
from mikro_feedback import open_mk1


def read_feature(fd):
    data = bytearray([0xf8]+[0]*10)
    request = (3 << 30) | (len(data) << 16) | (ord('H') << 8) | 7
    length = fcntl.ioctl(fd, request, data, True)
    if length != 11 or data[:5] != bytes.fromhex('f880004000'):
        raise ValueError('unexpected MK1 F8 report or display dimensions')
    return data


def write_feature(fd, data):
    if len(data) != 11 or data[:5] != bytes.fromhex('f880004000') or data[8] > 100 or data[9] > 100:
        raise ValueError('invalid MK1 feature report')
    request = (3 << 30) | (len(data) << 16) | (ord('H') << 8) | 6
    written = fcntl.ioctl(fd, request, data, True)
    if written != 11:
        raise OSError(f'short feature write: {written}/11')
    return written


def configure_backlight(fd, level=100):
    if not 0 <= level <= 100:
        raise ValueError('brightness must be 0..100')
    data = read_feature(fd)
    data[8] = level
    write_feature(fd, data)
    if read_feature(fd)[8] != level:
        raise OSError('brightness readback mismatch')



def configure_display(fd, brightness, contrast):
    if any(type(value) is not int or not 0 <= value <= 100 for value in (brightness, contrast)):
        raise ValueError('display settings must be integers 0..100')
    data = read_feature(fd)
    data[8], data[9] = brightness, contrast
    write_feature(fd, data)
    if read_feature(fd)[8:10] != bytes((brightness, contrast)):
        raise OSError('display settings readback mismatch')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path')
    parser.add_argument('--field', type=int, choices=[8, 9])
    parser.add_argument('--value', type=int)
    parser.add_argument('--backup', type=Path)
    parser.add_argument('--restore', type=Path)
    args = parser.parse_args()
    if args.field is not None and (args.value is None or not 0 <= args.value <= 100 or not args.backup):
        parser.error('field changes require --value 0..100 and --backup')
    if args.field is not None and args.restore:
        parser.error('choose a field change or restore, not both')
    fd = open_mk1(args.path)
    try:
        data = read_feature(fd)
        print(f'GET F8 returned 11 bytes: {data.hex()}')
        for index, value in enumerate(data):
            print(f'byte {index}: {value} (0x{value:02x})')
        if args.field is not None or args.restore:
            if args.field is not None:
                if not args.backup.exists():
                    args.backup.write_text(json.dumps({'hex': data.hex()}, indent=2)+'\n')
                data[args.field] = args.value
            else:
                saved = bytearray.fromhex(json.loads(args.restore.read_text())['hex'])
                if len(saved) != 11 or saved[:8] != data[:8] or saved[10] != data[10]:
                    raise ValueError('backup must match this device and untouched fields')
                if saved[8] > 100 or saved[9] > 100:
                    raise ValueError('invalid percentage fields')
                data = saved
            written = write_feature(fd, data)
            print(f'SET F8 returned {written} bytes: {data.hex()}')
    finally:
        os.close(fd)


if __name__ == '__main__':
    main()
