"""Bounded, asynchronous PCM waveform envelopes for the controller display."""
import array
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
import sys
import wave


@dataclass(frozen=True)
class Envelope:
    frames: int
    peaks: tuple
    start: int = 0
    end: int | None = None


def read_envelope(path, columns=120, start=0, end=None):
    with wave.open(str(path), 'rb') as wav:
        width, channels, frames = wav.getsampwidth(), wav.getnchannels(), wav.getnframes()
        if width not in (1, 2, 3, 4) or channels not in (1, 2) or frames > 8*1024*1024:
            raise ValueError('unsupported or oversized display sample')
        start=max(0,min(frames,start));end=frames if end is None else max(start,min(frames,end))
        peaks = []
        for column in range(columns):
            first, last = start+(end-start)*column//columns, start+(end-start)*(column+1)//columns
            if first == last:
                peaks.append((0.0, 0.0))
                continue
            wav.setpos(first)
            data = wav.readframes(last-first)
            if width == 3:
                values = [int.from_bytes(data[i:i+3], 'little', signed=True) for i in range(0, len(data), 3)]
            else:
                values = array.array({1: 'B', 2: 'h', 4: 'i'}[width])
                values.frombytes(data)
                if width > 1 and sys.byteorder != 'little':
                    values.byteswap()
            if not values:
                peaks.append((0.0, 0.0))
                continue
            minimum, maximum = min(values), max(values)
            if width == 1:
                minimum -= 128
                maximum -= 128
            divisor = 1 << (width*8-1)
            peaks.append((minimum/divisor, maximum/divisor))
        return Envelope(frames, tuple(peaks),start,end)


class Waveforms:
    def __init__(self):
        self.worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix='waveform')
        self.cache = OrderedDict()
        self.future = None
        self.loading_key = None

    def envelope(self, path, start=0, end=None):
        if self.future and self.future.done():
            try:
                self.cache[self.loading_key] = self.future.result()
            except (OSError, ValueError, wave.Error, EOFError):
                self.cache[self.loading_key] = Envelope(0, ())
            while len(self.cache) > 8:
                self.cache.popitem(last=False)
            self.future = None
        if not path:
            return None
        try:
            metadata = Path(path).stat()
        except OSError:
            return Envelope(0, ())
        key = (str(path), metadata.st_mtime_ns, metadata.st_size,start,end)
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        if self.future is None:
            self.loading_key = key
            self.future = self.worker.submit(read_envelope, path,120,start,end)
        return None

    def close(self):
        self.worker.shutdown(wait=True, cancel_futures=True)
