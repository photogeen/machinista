"""Assemble the optional ARM64 Calf effects pack from extracted Debian packages.

No apt install, system library replacement, plug-in execution or network access.
Pass the merged dpkg-deb extraction tree and a native patchelf executable.
The eight upstream DSPs are unchanged; only ELF search paths are made local.
"""
import argparse,hashlib,json,re,shutil,subprocess,zipfile
from pathlib import Path

EFFECTS=('Filter','Equalizer5Band','Compressor','Reverb','VintageDelay','MultiChorus','Saturator','Crusher')
LIBRARIES=('libfluidsynth.so.3','libpipewire-0.3.so.0','libinstpatch-1.0.so.2')

def build(extracted,destination,patchelf,sources):
    extracted=Path(extracted);destination=Path(destination)
    bundle=destination/'calf-effects.lv2'
    if bundle.exists():raise ValueError('Output bundle already exists')
    bundle.mkdir(parents=True);(bundle/'lib').mkdir();(bundle/'licenses').mkdir()
    original=extracted/'usr/lib/lv2/calf.lv2';manifest=['@prefix lv2: <http://lv2plug.in/ns/lv2core#> .','@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .']
    shutil.copyfile(original/'calf.so',bundle/'calf.so')
    for name in EFFECTS:
        data=(original/(name+'.ttl')).read_text()
        # Drop only the plugin-to-GTK-UI reference. DSP ports/ranges stay upstream.
        data=re.sub(r'^\s*uiext:ui <[^>]+> ;\s*$', '',data,flags=re.M)
        (bundle/(name+'.ttl')).write_text(data)
        manifest.append(f'<http://calf.sourceforge.net/plugins/{name}> a lv2:Plugin ; lv2:binary <calf.so> ; rdfs:seeAlso <{name}.ttl> .')
    (bundle/'manifest.ttl').write_text('\n'.join(manifest)+'\n')
    libraries=extracted/'usr/lib/aarch64-linux-gnu'
    for name in LIBRARIES:shutil.copyfile(libraries/name,bundle/'lib'/name)
    binaries=[bundle/'calf.so',*(bundle/'lib'/n for n in LIBRARIES)]
    for path in binaries:
        subprocess.run([str(patchelf),'--set-rpath','$ORIGIN/lib' if path.parent==bundle else '$ORIGIN',str(path)],check=True)
    for package in ('calf-plugins','libfluidsynth3','libpipewire-0.3-0t64','libinstpatch-1.0-2'):
        shutil.copyfile(extracted/'usr/share/doc'/package/'copyright',bundle/'licenses'/(package+'-copyright.txt'))
    # Include exact upstream sources and distribution patches, not just links.
    source_dir=bundle/'source';source_dir.mkdir()
    records=list(Path(sources).glob('*.dsc'))
    if len(records)!=4:raise ValueError('Provide the four matching Debian source packages')
    for p in sorted(Path(sources).iterdir()):
        if p.name.endswith(('.dsc','.tar.gz','.tar.xz','.tar.bz2','.diff.gz')):shutil.copyfile(p,source_dir/p.name)
    shutil.copyfile(__file__,source_dir/'build_calf_effects.py')
    for license in ('GPL-2','LGPL-2','LGPL-2.1'):
        shutil.copyfile(Path('/usr/share/common-licenses')/license,bundle/'licenses'/license)
    (bundle/'README.txt').write_text('Optional Calf effects pack for Machinista / ARM64 Debian Trixie.\nEight original Calf 0.90.3 DSPs, no GUI, instruments or sound content.\nPrivate runtime libraries: FluidSynth, PipeWire and libinstpatch.\nUpload this ZIP in WebUI > LV2. Remove the bundle there when unused.\nController profiles and parameter banks are supplied by Machinista separately.\nSee licenses/ for component notices; preserve them on redistribution.\nSource package records and reproduction instructions accompany this development add-on.\n')
    hashes={str(p.relative_to(bundle)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(bundle.rglob('*')) if p.is_file()}
    (bundle/'files.sha256.json').write_text(json.dumps(hashes,indent=2)+'\n')
    archive=destination/'Machinista-Calf-Effects-0.90.3-arm64.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(bundle.rglob('*')):
            if p.is_file():z.write(p,str(p.relative_to(destination)))
    return archive

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('extracted',type=Path);p.add_argument('destination',type=Path);p.add_argument('--patchelf',type=Path,required=True);p.add_argument('--sources',type=Path,required=True);a=p.parse_args();print(build(a.extracted,a.destination,a.patchelf,a.sources))
