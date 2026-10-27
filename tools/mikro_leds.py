"""Build MK1 LED reports using the observed pad/color channel mapping."""
import json
from pathlib import Path


def load_pad_channels(path):
    channels = {}
    indices = set()
    for row in json.loads(Path(path).read_text()):
        index, slot, color = row['payload_index'], row['pad_slot'], row['color']
        if type(index) is not int or not 0 <= index < 60 or index in indices:
            raise ValueError('invalid or duplicate LED payload index')
        indices.add(index)
        if slot is None and color is None:
            continue
        if type(slot) is not int or not 0 <= slot < 16 or color not in ('orange', 'blue'):
            raise ValueError('invalid pad/color mapping')
        key = (slot, color)
        if key in channels:
            raise ValueError('duplicate pad/color channel')
        channels[key] = index
    if any((slot, 'orange') not in channels for slot in range(16)):
        raise ValueError('orange channels for all 16 pads must be calibrated')
    if any((slot, 'blue') not in channels for slot in range(8, 16)):
        raise ValueError('blue channels for pads 9..16 must be calibrated')
    return channels


def orange_idle_report(channels, level=16):
    if type(level) is not int or not 0 <= level <= 31:
        raise ValueError('LED level must be 0..31')
    # Retain the previously tested button illumination, but disable blue pads.
    report = bytearray([0x80]+[level]*60)
    for (slot, color), index in channels.items():
        report[index+1] = level if color == 'orange' else 0
    return bytes(report)
