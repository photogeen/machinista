"""ULTRA GPIO23 speaker toggle. GPIO waits never run on audio/UI threads.

The board has an external pull-up. Request input edges only, active-low, and
identify the header chip by label (Pi5 RP1 need not be gpiochip0).
"""
import logging
import queue
import threading
import time
from pathlib import Path
from app.codec_levels import supported

PIN = 23
DEBOUNCE = .04
HEADER_LABELS = ('pinctrl-bcm2835', 'pinctrl-bcm2711', 'pinctrl-rp1')


class DebouncedPress:
    def __init__(self, pressed, now):
        # A held button at startup is not a new press.
        self.stable = self.candidate = bool(pressed)
        self.changed = now

    def update(self, pressed, now):
        pressed = bool(pressed)
        if pressed != self.candidate:
            self.candidate, self.changed = pressed, now
        if self.candidate != self.stable and now - self.changed >= DEBOUNCE:
            self.stable = self.candidate
            return self.stable
        return False

    def timeout(self, now):
        return max(.001, min(.25, self.changed + DEBOUNCE - now)) if self.candidate != self.stable else .25


def open_button():
    import gpiod
    from gpiod.line import Direction, Edge
    if not hasattr(gpiod, 'request_lines'):
        raise RuntimeError('python3-gpiod 2.x required')
    # Never guess a GPIO controller on another platform or another HAT.
    if not Path('/proc/device-tree/model').read_text().startswith('Raspberry Pi'):
        raise RuntimeError('not a Raspberry Pi')
    seen = set()
    for path in sorted(Path('/dev').glob('gpiochip[0-9]*')):
        real = path.resolve()
        if real in seen:continue
        seen.add(real)
        with gpiod.Chip(str(real)) as chip:
            label = chip.get_info().label
        if label in HEADER_LABELS:
            return gpiod.request_lines(str(real), consumer='machinista-speaker-button',
                                      config={PIN: gpiod.LineSettings(direction=Direction.INPUT,
                                              edge_detection=Edge.BOTH, active_low=True)})
    raise RuntimeError('Pi header GPIO controller not found')


def apply_presses(app, count):
    if count % 2 and supported(app.audio):
        app.set_dac_mute('SPEAKER MUTE')
        app.message = 'SPEAKER MUTED' if app.settings['hat_speaker_mute'] else 'SPEAKER ON'


class HatButton:
    def __init__(self):
        self.enabled = threading.Event()
        self.stop = threading.Event()
        self.presses = queue.SimpleQueue()
        self.error = ''
        self.thread = threading.Thread(target=self._run, name='hat-button', daemon=True)
        self.thread.start()

    def update(self, device):
        if supported(device):self.enabled.set()
        else:self.enabled.clear()

    def poll(self):
        count = 0
        while True:
            try:self.presses.get_nowait();count += 1
            except queue.Empty:return count

    def _listen(self, request):
        from gpiod.line import Value
        state = DebouncedPress(request.get_value(PIN) == Value.ACTIVE, time.monotonic())
        while self.enabled.is_set() and not self.stop.is_set():
            if request.wait_edge_events(state.timeout(time.monotonic())):
                request.read_edge_events()  # Drain edges, then debounce the actual input level.
            if not self.enabled.is_set() or self.stop.is_set():break
            if state.update(request.get_value(PIN) == Value.ACTIVE, time.monotonic()):
                self.presses.put(True)

    def _run(self):
        while not self.stop.is_set():
            if not self.enabled.wait(.25):continue
            try:
                with open_button() as request:
                    self.error = ''
                    self._listen(request)
            except (OSError, ImportError, RuntimeError) as error:
                message = str(error)
                if message != self.error:
                    logging.getLogger(__name__).warning('ULTRA button unavailable: %s', message)
                self.error = message
                self.stop.wait(5)

    def close(self):
        self.stop.set()
        self.thread.join(timeout=.5)
