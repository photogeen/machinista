"""Rebuildable Browser Sounds for complete parameter-bank instrument patches.

Only the preset worker writes these snapshots. They contain no executable code
or mutable plug-in state, and never replace an existing user Sound.
"""
import copy
import hashlib
import json
import re
import secrets
from pathlib import Path

FORMAT='Machinista-bank-sound'
INSTRUMENTS={'machinista-synth','dexed','obxd','raffosynth'}

def component(value):
    value=re.sub(r'[/\\\x00-\x1f]', ' ', value).strip().strip('.')[:100]
    return value or 'Untitled'

def project(root,data):
    from app.model import new_project,validate_project
    from app.plugin_profiles import profile,validate_bank
    p=profile(data.get('uri'))
    if data.get('format')!=FORMAT or data.get('version')!=1 or not p or p['id'] not in INSTRUMENTS:raise ValueError('Invalid instrument Sound.')
    preset=data['preset'];validate_bank(dict(schema=1,uri=p['uri'],name=data['bank_name'],patches=[preset]),p)
    plugin=dict(uri=p['uri'],name=p['title'],kind='INSTRUMENT',controls=copy.deepcopy(preset['controls']),profile_preset=dict(bank=data['bank'],program=data['program'],name=preset['name']))
    if p['id']=='machinista-synth':
        from app.synth_library import preset_waves
        plugin['synth_waves']=preset_waves(root,preset)
    result=new_project();result['groups'][0]['pads'][0].update(name=preset['name'],plugins=[plugin])
    validate_project(result)
    return result

def sync(root,entries,enabled):
    from app.sound_library import SoundLibrary
    from app.plugin_profiles import profiles
    library=SoundLibrary(root);wanted={}
    for p in profiles():
        if p['id'] not in INSTRUMENTS or p['uri'] not in enabled:continue
        for bank in entries[p['id']][1]:
            # Numeric prefixes preserve the controller bank order, including Init last.
            for index,preset in enumerate(bank['patches']):
                program=preset.get('_program',index)
                identity=hashlib.sha256((p['uri']+'\0'+bank['id']+'\0'+str(program)).encode()).hexdigest()[:32]
                category=component(p['title'])+'/'+component(bank['name'])
                leaf=f'{index+1:03d} {component(preset["name"])}.sound'
                relative=category+'/'+leaf
                wanted[relative]=dict(format=FORMAT,version=1,id=identity,name=preset['name'],uri=p['uri'],bank=bank['id'],bank_name=bank['name'],program=program,preset={k:copy.deepcopy(v) for k,v in preset.items() if k!='_program'})
    with library.writing():
        # An ownership list restricts cleanup to our own unchanged snapshots.
        manifest=library.folder/'.bank-sounds.json'
        if manifest.is_symlink():raise ValueError('Invalid bank Sound catalog.')
        old=json.loads(manifest.read_text()) if manifest.exists() else {}
        published={}
        for relative,data in wanted.items():
            category,leaf=relative.rsplit('/',1);body=json.dumps(data,ensure_ascii=False,sort_keys=True)
            with library.directory(category,True):
                path=library.folder/relative
                if path.is_symlink():continue
                previous=path.read_text() if path.exists() else None
                if previous is not None and hashlib.sha256(previous.encode()).hexdigest()!=old.get(relative):continue
                if previous!=body:
                    temporary=path.parent/('.'+secrets.token_hex(16))
                    with temporary.open('x') as stream:stream.write(body)
                    temporary.replace(path)
                published[relative]=hashlib.sha256(body.encode()).hexdigest()
        for relative,digest in old.items():
            if relative in published:continue
            category,leaf=relative.rsplit('/',1)
            try:
                with library.directory(category):
                    path=library.folder/relative
                    if not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest()==digest:path.unlink()
                # Remove only empty ancestor directories of previously managed files.
                parent=path.parent
                while parent!=library.folder:
                    try:parent.rmdir()
                    except OSError:break
                    parent=parent.parent
            except (OSError,ValueError):pass
        temporary=manifest.parent/('.'+secrets.token_hex(16))
        with temporary.open('x') as stream:stream.write(json.dumps(published,sort_keys=True))
        temporary.replace(manifest)
