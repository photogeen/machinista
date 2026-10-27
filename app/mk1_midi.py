"""Discover the live MK1 DIN bridge; no fixed ALSA card or pseudo-terminal ID."""
from pathlib import Path
import json
import os
import re
import stat

MANIFEST=Path(__file__).resolve().parents[1]/'samples/.mk1-midi.json'

def discover_mk1(manifest=None,proc=Path('/proc')):
    from app.devices import MidiDevice
    manifest=Path(manifest) if manifest is not None else MANIFEST
    try:
        info=manifest.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_size>1024:return []
        value=json.loads(manifest.read_text());pid=value['pid'];path=value['path']
        if type(pid) is not int or pid<=0 or not isinstance(path,str) or not re.fullmatch(r'/dev/pts/[0-9]+',path):return []
        process=proc/str(pid)
        if (process/'exe').resolve(strict=True).name!='mk1_monitor':return []
        if process.stat().st_uid!=os.getuid():return []
        device=Path(path).lstat()
        if not stat.S_ISCHR(device.st_mode) or device.st_uid!=os.getuid():return []
        return [MidiDevice('mk1:din','Maschine MK1 MIDI DIN',path)]
    except (OSError,ValueError,KeyError,TypeError):return []
