"""One display name for a Sound, derived from its current instrument.

Do not rename project/sample assets from a renderer. Resolve old projects on read,
so replacing/removing instruments never leaves a stored automatic plugin label.
"""
import re
from pathlib import Path
from urllib.parse import unquote

FALLBACK_NAMES = {
    'urn:machinista:instrument:synth': 'Machinista Synth',
    'urn:machinista:ports:virtualjv': 'VirtualJV',
    'urn:machinista:ports:virtualjv-multi': 'VirtualJV Multitimbral',
    'urn:machinista:ports:obxd-2dat': 'OB-Xd',
    'https://github.com/dcoredump/dexed.lv2': 'Dexed',
    'urn:machinista:ports:raffosynth': 'RaffoSynth',
}
LEGACY_JV = re.compile(r'JV (?:Part [1-8]|Rhythm)\Z',re.IGNORECASE)


def instrument_name(app, target):
    for plugin in target.get('plugins',[]):
        uri=plugin.get('uri','');lookup=getattr(app,'plugin_metadata',None)
        metadata=(lookup(uri) or {}) if lookup else {}
        if plugin.get('kind',metadata.get('kind'))!='INSTRUMENT':continue
        for value in (metadata.get('name'),plugin.get('name'),FALLBACK_NAMES.get(uri)):
            if isinstance(value,str) and value.strip():return value.strip()
        # Missing plugins can still identify themselves, rather than showing EMPTY.
        return unquote(re.split(r'[/#:]',uri.rstrip('/#'))[-1]) or 'INSTRUMENT'
    return None


def sound_name(app, track=None, empty='EMPTY'):
    track=app.track() if track is None else track
    target=track;seen=set();groups=getattr(app,'project',{}).get('groups',[])
    for _ in range(4):
        if id(target) in seen:break
        seen.add(id(target));name=instrument_name(app,target)
        if name:return name
        destination=target.get('routing',{}).get('midi_target','NONE')
        match=re.fullmatch(r'(GROUP|SOUND) (\d+)',destination) if isinstance(destination,str) else None
        if not match:break
        number=int(match[2])
        if match[1]=='GROUP':
            if number>=len(groups):break
            target=groups[number]
        else:
            group,pad=divmod(number,16)
            if group>=len(groups) or pad>=len(groups[group]['pads']):break
            target=groups[group]['pads'][pad]
    stored=track.get('name') or ''
    if stored and not LEGACY_JV.fullmatch(stored):return stored
    if track.get('sample'):return Path(track['sample']).stem
    return empty
