#!/usr/bin/env python3
"""Rename legacy recordings and update saved project references with audio preserved.

Run only while Machinista is stopped. Make a backup first. Old audio remains
until all project files have been updated; a failed run can safely be retried.
"""
import json
import os
from pathlib import Path
import re
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.audio import reserve_recording_path
from app.storage import save_json


def migrate(root):
    root = Path(root).resolve()
    folder = root/'samples/recordings'
    projects = [(path, json.loads(path.read_text())) for path in (root/'projects').glob('*.json')]
    for old in sorted(folder.glob('REC-*.wav')):
        if not re.fullmatch(r'REC-[0-9]+\.wav', old.name):
            continue
        destination = reserve_recording_path(folder)
        destination.unlink()
        os.link(old, destination)  # Retain original audio until every reference is saved.
        def update(value):
            if isinstance(value, dict):
                return {key: update(item) for key, item in value.items()}
            if isinstance(value, list):
                return [update(item) for item in value]
            return str(destination) if value == str(old) else value
        for index, (path, project) in enumerate(projects):
            changed = update(project)
            if changed != project:
                save_json(path, changed)
                projects[index] = path, changed
        old.unlink()
        print(f'{old.name} -> {destination.name}')


if __name__ == '__main__':
    migrate(Path(__file__).resolve().parents[1])
