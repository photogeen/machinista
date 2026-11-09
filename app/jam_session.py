"""Maschine JAM companion surface. USB layout verified against Controller Lab."""
import math
import os
from pathlib import Path
import threading
import time

from app.controller_output import ControllerOutput

HID_ID = 'HID_ID=0003:000017CC:00001500'
# Byte indices include the report ID. Bit 3 of byte 16 is encoder touch.
BUTTONS = {
    2: ('SONG', *(f'SCENE {i}' for i in range(1, 8))),
    3: ('SCENE 8', 'STEP', 'PAD MODE', 'CLEAR', 'DUPLICATE', 'UP', 'LEFT', 'RIGHT'),
    4: ('DOWN', 'NOTE REPEAT'),
    12: (None, None, *(f'GROUP {i}' for i in range(6))),
    13: ('GROUP 6', 'GROUP 7', 'MST', 'GRP', 'IN1', 'CUE', 'BROWSE', 'MACRO'),
    14: ('LEVEL', 'AUX', 'CONTROL', 'AUTO', 'PERFORM', 'NOTES', 'LOCK', 'TUNE'),
    15: ('SWING', 'SHIFT', 'PLAY', 'REC', 'PAGE LEFT', 'PAGE RIGHT', 'TEMPO', 'GRID'),
    16: ('SOLO', 'MUTE', 'SELECT', None, 'ENCODER PUSH'),
}
BUTTON_BITS = tuple((name, byte, 1 << bit) for byte, names in BUTTONS.items()
                    for bit, name in enumerate(names) if name)
MATRIX_BITS = tuple((4 + row + (col >= 6), 1 << ((col + 2) % 8))
                    for row in range(8) for col in range(8))
LED_LENGTHS = (66, 81, 90)
# NI palette indices, from orange through magenta.
GROUP_COLORS = (2, 1, 5, 8, 10, 13, 15, 17)
SHARED_BUTTONS = {'SHIFT': 'SHIFT', 'PLAY': 'PLAY', 'REC': 'REC'}


def decode_buttons(report):
    if len(report) < 17 or report[0] != 1:
        return None
    buttons = {name for name, byte, mask in BUTTON_BITS if report[byte] & mask}
    cells = {i for i, (byte, mask) in enumerate(MATRIX_BITS) if report[byte] & mask}
    return buttons, cells, report[1] & 15


def decode_strips(report):
    if len(report) < 49 or report[0] != 2:
        return None
    return tuple(int.from_bytes(report[i:i+2], 'little') for i in range(3, 46, 6))


def send_leds(fd, frame):
    offset = 0
    for length in LED_LENGTHS:
        report = frame[offset:offset+length]
        if os.write(fd, report) != length:
            raise OSError('short JAM HID write')
        offset += length


class JamSurface:
    def __init__(self, app, inputs):
        self.app, self.inputs = app, inputs
        self.mode = 'SONG'
        self.level = False
        self.level_scope = 'GRP'
        self.page = 0
        self.buttons = set()
        self.cells = set()
        self.encoder = None
        self.strip_edits = [None] * 8

    def disconnect(self):
        self.inputs.disconnect('jam')
        self.buttons.clear()
        self.cells.clear()
        self.encoder = None
        self.strip_edits = [None] * 8

    def feed(self, report):
        state = decode_buttons(report)
        if state is None:
            positions = decode_strips(report)
            if positions is not None and self.level:
                self.move_strips(positions)
            return
        buttons, cells, encoder = state
        changed = self.buttons ^ buttons
        self.buttons = buttons
        for name in SHARED_BUTTONS:
            if name in changed:
                self.inputs.button('jam', SHARED_BUTTONS[name], name in buttons)
        for name, _, _ in BUTTON_BITS:
            if name in changed and name in buttons and name not in SHARED_BUTTONS:
                self.press(name)
        if self.encoder is not None and encoder != self.encoder:
            self.turn((encoder - self.encoder + 8) % 16 - 8)
        self.encoder = encoder
        for cell in sorted(cells - self.cells):
            self.press_cell(cell)
        self.cells = cells

    def press(self, name):
        app = self.app
        if name in ('SONG', 'STEP', 'PAD MODE'):
            self.mode, self.page = name, 0
        elif name.startswith('SCENE '):
            scene = app.scene//8*8 + int(name.split()[-1])-1
            if scene < len(app.project['scenes']):
                app.select_scene(scene)
        elif name.startswith('GROUP '):
            group = app.group//8*8 + int(name.split()[-1])
            if group >= len(app.project['groups']):
                return
            modifier = next((key.lower() for key in ('MUTE', 'SOLO') if key in self.buttons), None)
            if modifier:
                app.remember()
                target = app.project['groups'][group]
                target[modifier] = not target.get(modifier, False)
            else:
                app.select_group(group)
                self.page = 0
        elif name in ('PAGE LEFT', 'PAGE RIGHT', 'LEFT', 'RIGHT'):
            self.turn(-1 if name in ('PAGE LEFT', 'LEFT') else 1)
        elif name in ('UP', 'DOWN'):
            app.select_sound(max(0, min(15, app.pad + (-1 if name == 'UP' else 1))))
        elif name == 'LEVEL':
            self.level = not self.level
            self.strip_edits = [None] * 8
        elif name in ('MST', 'GRP'):
            self.level_scope = name
            self.level = True
            self.strip_edits = [None] * 8

    def turn(self, delta):
        app = self.app
        if 'TEMPO' in self.buttons:
            app.adjust_tempo(delta)
        elif self.mode != 'PAD MODE':
            if self.mode == 'STEP':
                last = (app.step_cell_count()-1)//64
            else:
                last = (len(app.project['groups'][app.group]['patterns'])-1)//8
            self.page = max(0, min(last, self.page+delta))

    def press_cell(self, index):
        app = self.app
        if self.mode == 'STEP':
            app.toggle_step_cell(self.page*64 + index,100)
        elif self.mode == 'PAD MODE':
            if index < 16:
                app.select_sound(index)
        else:
            row, col = divmod(index, 8)
            group = app.group//8*8 + col
            if group < len(app.project['groups']):
                app.select_group(group)
                pattern = self.page*8 + row
                if pattern < len(app.project['groups'][group]['patterns']) and 'SELECT' not in self.buttons:
                    app.select_scene_pattern(pattern)
                    app.pattern_bank = pattern//16

    def strip_targets(self):
        app = self.app
        if self.level_scope == 'MST':
            return [app.project] + [None]*7
        start = app.group//8*8
        groups = app.project['groups'][start:start+8]
        return groups + [None]*(8-len(groups))

    def move_strips(self, positions):
        for i, (position, target) in enumerate(zip(positions, self.strip_targets())):
            if not 1 <= position <= 1023 or target is None:
                self.strip_edits[i] = None
                continue
            gain = round((position-1)*100/1022)
            if gain == target.get('gain', 100):
                continue
            if self.strip_edits[i] is not target:
                self.app.remember()
                self.strip_edits[i] = target
            else:
                self.app.revision += 1
                self.app.dirty = True
            target['gain'] = gain

    def led_frame(self):
        app = self.app
        control, matrix, strips = (bytearray(n) for n in LED_LENGTHS)
        control[0], matrix[0], strips[0] = 0x80, 0x81, 0x82
        for offset, active in (
            (1,self.mode=='SONG'), (2,self.mode=='STEP'), (3,self.mode=='PAD MODE'),
            (11,self.level and self.level_scope=='MST'), (12,self.level and self.level_scope=='GRP'),
            (19,self.level), (28,app.shift), (29,app.playing),
            (30,app.recording or bool(app.count_remaining)),
            (35,'SOLO' in self.buttons), (36,'MUTE' in self.buttons), (37,'SELECT' in self.buttons),
        ):
            control[offset] = 60 if active else 8
        for offset, level in zip((38, 46), app.mixer_master):
            for i in range(max(0,min(8,round((60+20*math.log10(max(level,1e-9)))*8/60)))):
                control[offset+i] = 60
        for i in range(8):
            scene = app.scene//8*8+i
            if scene==app.scene or scene in app.project['scene_created']:
                matrix[1+i] = (GROUP_COLORS[i]<<2) | (3 if scene==app.scene else 2 if scene==app.pending_scene else 1)
            group = app.group//8*8+i
            if group < len(app.project['groups']):
                target = app.project['groups'][group]
                bright = 0 if target.get('mute') else 3 if group==app.group else 1
                matrix[73+i] = (GROUP_COLORS[i]<<2) | bright
        if self.mode == 'STEP':
            start = self.page*64
            grid = app.grid_ticks()
            length = app.pattern_ticks()
            play = (app.clock_phase % length)//grid if app.playing and app.clock_phase>=0 else -1
            filled = {tick//grid for pad,tick in app.notes() if pad==app.pad}
            for i in range(min(64,app.step_cell_count()-start)):
                brightness = 3 if start+i==play else 2 if start+i in filled else 0
                if brightness:
                    matrix[9+i] = (GROUP_COLORS[app.group%8]<<2) | brightness
        elif self.mode == 'PAD MODE':
            for i, track in enumerate(app.project['groups'][app.group]['pads']):
                if i==app.pad or track.get('sample') or track.get('plugins') or track.get('zones'):
                    matrix[9+i] = (GROUP_COLORS[app.group%8]<<2) | (3 if i==app.pad else 1)
        else:
            start = app.group//8*8
            for col, group in enumerate(app.project['groups'][start:start+8]):
                index = start+col
                for pattern in group['pattern_created']:
                    row = pattern-self.page*8
                    if 0<=row<8:
                        active = app.active_clips[index] and app.active_patterns[index]==pattern
                        matrix[9+row*8+col] = (GROUP_COLORS[col]<<2) | (3 if active else 1)
        if self.level:
            for i, target in enumerate(self.strip_targets()):
                if target is not None:
                    count = round(target.get('gain',100)*11/100)
                    strips[1+i*11:1+i*11+count] = bytes([60])*count
        return bytes(control+matrix+strips)


class JamSession:
    def __init__(self, app, inputs):
        self.surface = JamSurface(app, inputs)
        self.fd = self.output = None
        self.cleanup = None
        self.next_scan = self.next_led = 0

    def poll(self, now):
        if self.fd is None:
            if now < self.next_scan or self.cleanup and self.cleanup.is_alive():
                return
            self.next_scan = now + 2
            for hid in Path('/sys/class/hidraw').glob('hidraw*'):
                try:
                    if HID_ID not in (hid/'device/uevent').read_text().splitlines():
                        continue
                    self.fd = os.open('/dev/'+hid.name, os.O_RDWR | os.O_NONBLOCK)
                except OSError as error:
                    if not isinstance(error, FileNotFoundError):
                        print(f'JAM USB: {error}',flush=True)
                    continue
                self.output = ControllerOutput(self.fd,None,send_leds,None)
                self.next_led = 0
                print(f'Maschine JAM connected: {hid.name}',flush=True)
                break
            return
        try:
            self.output.check()
            deadline = time.monotonic()+.001
            for _ in range(32):
                if time.monotonic() >= deadline:
                    break
                try:
                    report = os.read(self.fd,128)
                except BlockingIOError:
                    break
                if not report:
                    raise OSError('JAM disconnected')
                app = self.surface.app
                previous = app.input_timestamp
                app.input_timestamp = time.monotonic()
                try:
                    self.surface.feed(report)
                finally:
                    app.input_timestamp = previous
        except OSError as error:
            print(f'JAM USB: {error}',flush=True)
            self.close()
            self.next_scan = now+2

    def update(self, now):
        if self.output is not None and self.output.error is None and now >= self.next_led:
            self.next_led = now+.05
            try:
                self.output.submit_leds(self.surface.led_frame())
            except OSError:
                pass  # poll handles a detached or failed output worker

    def close(self):
        self.surface.disconnect()
        fd, output = self.fd, self.output
        self.fd = self.output = None
        if output is not None:
            def cleanup():
                try:
                    output.close()
                finally:
                    os.close(fd)
            self.cleanup = threading.Thread(target=cleanup, name='jam-cleanup', daemon=True)
            self.cleanup.start()
