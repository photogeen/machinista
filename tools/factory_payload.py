"""Required original synth assets for a clean distributable image payload."""
import json,struct
from pathlib import Path

def factory_files(root):
    from app.plugin_profiles import profile,validate_bank
    from app.synth_library import preset_waves
    root=Path(root);declaration=root/'assets/synth-factory.json'
    declared=json.loads(declaration.read_text());folder=root/'presets/plugin-banks/machinista-synth'
    factory=root/'presets/plugin-banks/machinista-synth/factory.json'
    if declared['bank']!=str(factory.relative_to(root)):raise ValueError('Unexpected Factory bank path')
    banks=[factory]
    for row in declared.get('category_banks',[]):
        path=root/row['file']
        if path.parent!=folder or not path.name.startswith('category-'):raise ValueError('Invalid Factory category path')
        banks.append(path)
    allowed={row['id']:row for row in declared['waves']};identities=set()
    for path in banks:
        if path.is_symlink():raise ValueError('Factory banks must be regular files')
        bank=validate_bank(json.loads(path.read_text()),profile('urn:machinista:instrument:synth'))
        if path==factory and not bank['patches']:raise ValueError('Factory patches missing')
        for patch in bank['patches']:
            for row in patch.get('synth_waves',{}).values():
                if row['id'] not in allowed:raise ValueError('Factory references undeclared/user waveforms')
                identities.add(row['id'])
            preset_waves(root,patch)  # Verify referenced assets before packaging.
    result=[declaration,*banks,root/'assets/synth-waves.json',root/'docs/synth/FACTORY_BANK.md']
    for identity in sorted(identities):
        metadata=root/'presets/Oscillators'/(identity+'.json');asset=root/'presets/Oscillators/.assets'/(identity+'.mwave')
        if json.loads(metadata.read_text())!=allowed[identity]:raise ValueError('Factory wave metadata differs from declaration')
        data=asset.read_bytes();row=allowed[identity]
        if data[:8] not in (b'MWAVE001',b'MWAVET02') or struct.unpack_from('<II',data,8)!=(row['frames'],row['cycle']) or len(data)!=16+4*row['frames']*row['cycle']*(10 if data[:8]==b'MWAVET02' else 1):raise ValueError('Invalid Factory wave data')
        result.extend((metadata,asset))
    for path in result:
        if not path.is_file() or path.is_symlink():raise ValueError('Missing or unsafe Factory asset: '+str(path))
    return tuple(result)
