#!/usr/bin/env python3
"""Repair interrupted arecord headers and clamp saved ranges to actual frames.
Run with Machinista stopped and a backup of samples/projects.
"""
import json
from pathlib import Path
import sys
import wave
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.audio import repair_recording_header
from app.storage import save_json


def repair(root):
    root=Path(root).resolve();lengths={}
    for path in (root/'samples/recordings').glob('*.wav'):
        if repair_recording_header(path):print('Repaired header:',path.name)
        with wave.open(str(path),'rb') as wav:lengths[str(path)]=wav.getnframes()
    for file in (root/'projects').glob('*.json'):
        project=json.loads(file.read_text());changed=False
        for group in project['groups']:
            for track in group['pads']:
                frames=lengths.get(track.get('sample'))
                if frames is None:continue
                for start,end in (('start','end'),('selection_start','selection_end')):
                    if start not in track:continue
                    last=max(0,min(frames,track.get(end,frames)))
                    first=max(0,min(last,track[start]))
                    if (first,last)!=(track[start],track.get(end)):
                        track[start],track[end]=first,last;changed=True
        if changed:save_json(file,project);print('Repaired ranges:',file.name)


if __name__=='__main__':repair(Path(__file__).resolve().parents[1])
