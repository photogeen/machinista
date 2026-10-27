#!/usr/bin/env python3
"""Live controller feedback demo, without audio. Uses the tested C++ decoder."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import time
from mikro_feedback import open_mk1, frame_reports, text, send
from mikro_settings import configure_backlight
from mikro_leds import load_pad_channels, orange_idle_report


def render(fd, label, value, knob):
    pixels = bytearray(8192)
    text(pixels, 4, 3, 'MACHINISTA', 2)
    for x in range(128):
        pixels[17*128+x] = 1
    text(pixels, 4, 24, label.replace('_', ' '), 2 if len(label) < 16 else 1)
    text(pixels, 4, 43, value, 1)
    text(pixels, 4, 55, f'ENCODER {knob}', 1)
    for report in frame_reports(pixels):
        send(fd, report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path')
    parser.add_argument('--seconds', type=int, default=0, help='0 = run until stopped')
    parser.add_argument('--brightness', type=int, default=100)
    args = parser.parse_args()
    if args.seconds < 0 or not 0 <= args.brightness <= 100:
        parser.error('seconds must be nonnegative and brightness must be 0..100')
    root = Path(__file__).resolve().parent.parent
    mapping_path = root/'captures/mikro-mk1-button-map.json'
    button_names = {item['bit']: item['name'] for item in json.loads(mapping_path.read_text())}
    pad_channels = load_pad_channels(root/'captures/mikro-mk1-pad-led-map.json')
    idle_leds = orange_idle_report(pad_channels)
    with (root/'build/surface.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fd = open_mk1(args.path)
        child = None
        stopped = False

        def stop(*_):
            nonlocal stopped
            stopped = True

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        (root/'build/surface.pid').write_text(str(os.getpid())+'\n')
        try:
            configure_backlight(fd, args.brightness)
            send(fd, idle_leds)
            label, value, knob = 'READY', 'CONTROLLER TEST', 0
            render(fd, label, value, knob)
            child = subprocess.Popen([str(root/'build/mikro_monitor'), '--live', args.path, '0'],
                                     stdout=subprocess.PIPE)
            os.set_blocking(child.stdout.fileno(), False)
            buffered = b''
            started = time.monotonic()
            next_frame = 0.0
            dirty = False
            print('Surface ready; no audio', flush=True)
            while not stopped and (args.seconds == 0 or time.monotonic()-started < args.seconds):
                if child.poll() is not None:
                    raise OSError(f'input monitor exited: {child.returncode}')
                if select.select([child.stdout], [], [], 0.02)[0]:
                    chunk = os.read(child.stdout.fileno(), 65536)
                    if not chunk:
                        raise OSError('input monitor disconnected')
                    buffered += chunk
                    while b'\n' in buffered:
                        line, buffered = buffered.split(b'\n', 1)
                        event = json.loads(line)
                        kind = event['kind']
                        if kind == 'button':
                            label = button_names.get(event['raw_control'], 'UNMAPPED')
                            value = 'PRESSED' if event['value'] else 'RELEASED'
                        elif kind == 'encoder':
                            knob += event['value']
                            label, value = 'ENCODER', 'RIGHT' if event['value'] > 0 else 'LEFT'
                        else:
                            label = event['name']
                            value = (f'PRESSURE {event["value"]}' if kind == 'pad_on'
                                     else f'PEAK {event["value"]}')
                        dirty = True
                        print(json.dumps(event | {'name': label}), flush=True)
                if dirty and time.monotonic() >= next_frame:
                    render(fd, label, value, knob)
                    next_frame = time.monotonic()+0.05
                    dirty = False
        finally:
            if child:
                child.terminate()
                try:
                    child.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
            try:
                # Retain low idle illumination on an intentional shutdown.
                send(fd, idle_leds)
                render(fd, 'STOPPED', 'CONTROLLER TEST', 0)
            finally:
                os.close(fd)
                (root/'build/surface.pid').unlink(missing_ok=True)


if __name__ == '__main__':
    main()
