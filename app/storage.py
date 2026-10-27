"""Atomic, durable JSON storage for settings and musical project state."""
import json
import copy
import threading
import time
import os
from pathlib import Path


_writers = {}


def save_json(path, value):
    writer = _writers.get(Path(path).resolve())
    if writer is not None:
        writer.submit(value)
        return
    _save_json(path, value)


def _save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name+'.tmp')
    with temporary.open('w') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def load_json(path, default):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        return default


class SettingsWriter:
    """One ordered, coalescing writer for a runtime settings path.

    Project saves remain synchronous. All settings callers use the registry, so
    an older background snapshot cannot overwrite a newer synchronous edit.
    """
    def __init__(self, path, quiet=.15, maximum=.75):
        self.path = Path(path).resolve()
        if self.path in _writers:raise RuntimeError('settings writer already active')
        self.quiet, self.maximum = quiet, maximum
        self.condition = threading.Condition()
        self.pending = None
        self.closing = False
        self.error = None
        self.first = self.updated = 0
        _writers[self.path] = self
        self.thread = threading.Thread(target=self.run, name='settings-save', daemon=True)
        self.thread.start()

    def submit(self, value):
        snapshot = copy.deepcopy(value)
        with self.condition:
            if self.error:raise OSError('settings save failed') from self.error
            if self.closing:raise RuntimeError('settings writer closed')
            now = time.monotonic()
            if self.pending is None:self.first = now
            self.updated = now
            self.pending = snapshot
            self.condition.notify()

    def run(self):
        try:
            while True:
                with self.condition:
                    self.condition.wait_for(lambda:self.closing or self.pending is not None)
                    while self.pending is not None and not self.closing:
                        delay = min(self.updated+self.quiet, self.first+self.maximum)-time.monotonic()
                        if delay <= 0:break
                        self.condition.wait(delay)
                    if self.pending is None and self.closing:return
                    value, self.pending = self.pending, None
                _save_json(self.path, value)
        except Exception as error:
            self.error = error

    def close(self):
        with self.condition:
            self.closing = True
            self.condition.notify()
        self.thread.join()  # Flush latest edits on normal stop/restart.
        _writers.pop(self.path, None)
        if self.error:raise OSError('settings save failed') from self.error
