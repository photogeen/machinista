#!/usr/bin/env python3
"""Create a fresh, audited source export. No Git/network/deployment operations."""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.check_public_source import audit
from tools.factory_payload import factory_files

DOCS=('BUILD','INSTALL','ARCHITECTURE','GITHUB_PUBLISH','LICENSING_PLAN','WEB_UI',
      'USER_MANUALS','SOUNDS_AND_AUTOSAMPLER','SOUNDFONT_IMPORT','PLUGIN_PROFILES',
      'MK1_MIDI','MK3_SUPPORT','MASCHINE_PLUS_SUPPORT','INIT_BANK_ORDER','UPDATER_PLAN')
MAPS=('mikro-mk1-pad-led-map.json','mikro-mk1-button-map.json',
      'mikro-mk1-button-led-map.json','maschine-mk2-hardware-map.json')
EXCLUDED_TOOLS={'install_machinista_branding.py','install_lv2_web.py'}

def prepare(source,destination):
    source=Path(source).resolve();destination=Path(destination).resolve()
    if destination==source or source.is_relative_to(destination):raise ValueError('Export must not contain the source workspace.')
    if destination.exists():raise FileExistsError('Destination already exists; choose a fresh path.')
    destination.mkdir(parents=True);selected={}
    def add(path):
        relative=path.relative_to(source)
        if path.is_symlink():raise ValueError('Source symlink: '+str(relative))
        selected[str(relative)]=path
    for folder in ('app','src','web','tests','deploy','.github'):
        for path in (source/folder).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc':add(path)
    for path in (source/'tools').rglob('*'):
        if path.is_file() and path.suffix in ('.py','.cpp','.cjs') and '__pycache__' not in path.parts and path.name not in EXCLUDED_TOOLS:add(path)
    for folder in ('branding','fonts','instrument-art','manual-web'):
        for path in (source/'assets'/folder).rglob('*'):
            if path.is_file():add(path)
    for path in factory_files(source):add(path)
    for name in DOCS:add(source/'docs'/(name+'.md'))
    for name in ('README.md','CMakeLists.txt','THIRD_PARTY_NOTICES.md','CONTRIBUTING.md','SECURITY.md','LICENSING.md','LICENSE.md','.gitignore','.gitattributes','.python-version','requirements-dev.txt'):add(source/name)
    for name,path in sorted(selected.items()):
        target=destination/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
    for name in MAPS:
        data=json.loads((source/'captures'/name).read_text())
        if isinstance(data,dict):
            data.pop('evidence',None)
            if isinstance(data.get('device'),dict):data['device'].pop('serial',None)
        target=destination/'captures'/name;target.parent.mkdir(exist_ok=True);target.write_text(json.dumps(data,indent=2)+'\n')
    # Only declared original tables/banks and sanitized maps may be staged in Git.
    permitted=[str(p.relative_to(source)) for p in factory_files(source) if str(p.relative_to(source)).startswith('presets/')]
    ignore=destination/'.gitignore'
    with ignore.open('a') as stream:
        stream.write('\n# Explicit original Factory assets and sanitized generic maps.\n')
        stream.write('!/presets/Oscillators/\n/presets/Oscillators/*\n!/presets/Oscillators/.assets/\n/presets/Oscillators/.assets/*\n!/presets/plugin-banks/\n/presets/plugin-banks/*\n!/presets/plugin-banks/machinista-synth/\n/presets/plugin-banks/machinista-synth/*\n')
        for name in permitted:stream.write('!/'+name+'\n')
        for name in MAPS:stream.write('!/captures/'+name+'\n')
    report=audit(destination)
    reportfile=destination.parent/(destination.name+'-audit.json');reportfile.write_text(json.dumps(report,indent=2)+'\n')
    if not report['ok']:raise ValueError('Export audit failed: '+json.dumps(report['errors']))
    return dict(destination=str(destination),audit=str(reportfile),files=report['files'],bytes=report['bytes'],published=False,license_status='custom-source-available; legal review recommended')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--destination',type=Path,default=ROOT/'output/github/machinista')
    args=parser.parse_args();print(json.dumps(prepare(ROOT,args.destination),indent=2))

if __name__=='__main__':main()
