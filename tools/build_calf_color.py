"""Build the three Calf Color LV2 effects from upstream 0.90.3 on Linux ARM64.

Uses extracted development headers and private runtime libraries, never apt install.
The optional package includes original sources, build recipe and license notices.
"""
import argparse,json,re,shutil,subprocess,tarfile,zipfile,hashlib
from pathlib import Path
EFFECTS=('TapeSimulator','BassEnhancer','Vinyl')

def build(source,extracted,runtime,destination,sources):
 source,extracted,runtime,destination,sources=map(Path,(source,extracted,runtime,destination,sources))
 destination.mkdir(parents=True,exist_ok=True);work=destination/'source-build'
 if work.exists():raise ValueError('Build directory already exists')
 shutil.copytree(source,work)
 (work/'config.h').write_text('#define USE_LV2 1\n#define USE_JACK 0\n#define USE_GUI 0\n#define USE_EXEC_GUI 0\n#define PKGLIBDIR "."\n')
 (work/'src/calf/modulelist.h').write_text('#ifdef PER_MODULE_ITEM\nPER_MODULE_ITEM(tapesimulator, false, "tapesimulator")\nPER_MODULE_ITEM(bassenhancer, false, "bassenhancer")\nPER_MODULE_ITEM(vinyl, false, "vinyl")\n#undef PER_MODULE_ITEM\n#endif\n')
 p=work/'src/plugin.cpp';s=p.read_text();s=re.sub(r'^#include <calf/(?!lv2wrap.h|modules_dist.h)[^>]+>\n','',s,flags=re.M);s=s.replace('const LV2_Descriptor *lv2_descriptor(uint32_t index)','__attribute__((visibility("default"))) const LV2_Descriptor *lv2_descriptor(uint32_t index)');p.write_text(s)
 p=work/'src/modules_dist.cpp';s=p.read_text().replace('#include <string>','#include <string>\n#include <dlfcn.h>\n\n// Machinista: locate optional Vinyl assets beside this LV2 binary.\nstatic void calf_color_anchor() {}\nstatic std::string calf_color_asset(const char *name) {\n    Dl_info info{};\n    if (!dladdr(reinterpret_cast<void*>(&calf_color_anchor), &info) || !info.dli_fname)\n        return std::string();\n    std::string path(info.dli_fname);\n    return path.substr(0, path.find_last_of(\'/\') + 1) + "sf2/" + name;\n}\n')
 s=s.replace('PKGLIBDIR "sf2/', '"')
 s=s.replace('fluid_settings_setint(settings, "synth.midi-channels", _synths);','fluid_settings_setint(settings, "synth.midi-channels", 16);')
 s=s.replace('fluid_synth_sfload(synth, paths[i], 0)', 'fluid_synth_sfload(synth, calf_color_asset(paths[i]).c_str(), 0)')
 s=s.replace('fluid_settings_setint(settings, "synth.polyphony", 32);','fluid_settings_setint(settings, "synth.polyphony", 32);\n    fluid_settings_setint(settings, "synth.cpu-cores", 1);\n    fluid_settings_setint(settings, "synth.threadsafe-api", 0);')
 p.write_text(s)
 bundle=destination/'calf-color.lv2';bundle.mkdir();shutil.copytree(runtime/'lib',bundle/'lib');shutil.copytree(runtime/'licenses',bundle/'licenses');shutil.copytree(source/'sf2',bundle/'sf2')
 # The only audio processors instantiated are the three selected modules.
 cpp=['audio_fx','metadata','modmatrix','modules_dist','giface','utils','osctl','preset','lv2wrap','plugin']
 cmd=['g++','-std=gnu++11','-O3','-fPIC','-fvisibility=hidden','-ffunction-sections','-fdata-sections','-Wno-narrowing','-shared','-Wl,--no-undefined','-Wl,--gc-sections','-I'+str(work),'-I'+str(work/'src'),'-I'+str(extracted/'usr/include'),*[str(work/'src'/(n+'.cpp')) for n in cpp],'-L'+str(bundle/'lib'),'-Wl,-rpath,$ORIGIN/lib','-Wl,-rpath-link,'+str(bundle/'lib'),'-l:libfluidsynth.so.3','-l:libexpat.so.1','-ldl','-pthread','-o',str(bundle/'calf-color.so')]
 subprocess.run(cmd,check=True)
 metadata=extracted/'usr/lib/lv2/calf.lv2';manifest=['@prefix lv2: <http://lv2plug.in/ns/lv2core#> .','@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .']
 for name in EFFECTS:
  data=(metadata/(name+'.ttl')).read_text();data=re.sub(r'^\s*uiext:ui <[^>]+> ;\s*$','',data,flags=re.M).replace('<calf.so>','<calf-color.so>')
  (bundle/(name+'.ttl')).write_text(data);manifest.append(f'<http://calf.sourceforge.net/plugins/{name}> a lv2:Plugin ; lv2:binary <calf-color.so> ; rdfs:seeAlso <{name}.ttl> .')
 (bundle/'manifest.ttl').write_text('\n'.join(manifest)+'\n')
 src=bundle/'source';src.mkdir();shutil.copyfile(__file__,src/'build_calf_color.py')
 with tarfile.open(src/'calf-0.90.3-machinista-color-source.tar.gz','w:gz') as t:t.add(work,arcname='calf-0.90.3')
 for p in sources.iterdir():
  if p.name.endswith(('.dsc','.tar.gz','.tar.xz','.tar.bz2','.diff.gz')):shutil.copyfile(p,src/p.name)
 (bundle/'README.txt').write_text('Calf Color / Machinista ARM64: Tape Simulator, Bass Enhancer, Vinyl.\nBuilt from upstream Calf 0.90.3; no GUI or audio driver.\nVinyl uses its included original Calf sf2 noise generators, located relative to this binary.\nOne FluidSynth rendering core; chorus/reverb disabled, no added hardware latency.\nController profiles and optional Calf Color patch banks are supplied separately.\nUpload this ZIP in Machinista WebUI > LV2. Existing Calf Essentials is independent.\nSee licenses/ and source/ for notices, complete corresponding sources and build recipe.\n')
 hashes={str(p.relative_to(bundle)):hashlib.sha256(p.read_bytes()).hexdigest() for p in bundle.rglob('*') if p.is_file()};(bundle/'files.sha256.json').write_text(json.dumps(hashes,indent=2)+'\n')
 archive=destination/'Machinista-Calf-Color-0.90.3-arm64.zip'
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
  for p in bundle.rglob('*'):
   if p.is_file():z.write(p,str(p.relative_to(destination)))
 print(archive)
 return archive
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('extracted');p.add_argument('runtime');p.add_argument('destination');p.add_argument('sources');a=p.parse_args();build(a.source,a.extracted,a.runtime,a.destination,a.sources)
