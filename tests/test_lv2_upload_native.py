"""Linux integration: real ARM/x86 host metadata, dependencies and lazy discovery."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
import zipfile
from app.lv2_manager import Manager,elf,needed_libraries,check_dependencies
ROOT=Path(__file__).resolve().parents[1]

@unittest.skipUnless(sys.platform=='linux' and (ROOT/'build/audio_engine').exists(),'Native Linux LV2 build required')
class NativeUploadTests(unittest.TestCase):
    def test_real_bundle_validates_without_loading_and_later_loads_in_existing_world(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source';bundle=source/'UploadTest.lv2';bundle.mkdir(parents=True)
            marker=root/'loaded'
            code=root/'fixture.cpp';code.write_text('''#include <lv2/core/lv2.h>
#include <cstdio>
#include <cstdlib>
struct P{float* in=nullptr;float* out=nullptr;};
__attribute__((constructor)) static void loaded(){auto f=std::fopen("'''+str(marker)+'''","w");if(f){std::fputs("loaded",f);std::fclose(f);}}
static LV2_Handle create(const LV2_Descriptor*,double,const char*,const LV2_Feature*const*){return new P;}
static void connect(LV2_Handle h,uint32_t i,void* p){if(i==0)static_cast<P*>(h)->in=(float*)p;else static_cast<P*>(h)->out=(float*)p;}
static void run(LV2_Handle h,uint32_t n){auto p=static_cast<P*>(h);for(uint32_t i=0;i<n;++i)p->out[i]=p->in[i]*.5f;}
static void clean(LV2_Handle h){delete static_cast<P*>(h);}
static const LV2_Descriptor d={"urn:machinista:upload-test",create,connect,nullptr,run,nullptr,clean,nullptr};
extern "C" const LV2_Descriptor* lv2_descriptor(uint32_t i){return i?nullptr:&d;}
''')
            subprocess.run(['c++','-shared','-fPIC',str(code),'-o',str(bundle/'plugin.so')],check=True,capture_output=True)
            (bundle/'manifest.ttl').write_text('''@prefix lv2: <http://lv2plug.in/ns/lv2core#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
<urn:machinista:upload-test> a lv2:Plugin; lv2:binary <plugin.so>;rdfs:seeAlso <plugin.ttl> .''')
            (bundle/'plugin.ttl').write_text('''@prefix lv2: <http://lv2plug.in/ns/lv2core#> .
@prefix doap: <http://usefulinc.com/ns/doap#> .
<urn:machinista:upload-test> a lv2:Plugin;doap:name "Machinista Upload Test";lv2:port
[a lv2:InputPort,lv2:AudioPort;lv2:index 0;lv2:symbol "in";lv2:name "Input"],
[a lv2:OutputPort,lv2:AudioPort;lv2:index 1;lv2:symbol "out";lv2:name "Output"] .''')
            archive=root/'plugin.zip'
            with zipfile.ZipFile(archive,'w') as z:
                for p in bundle.iterdir():z.write(p,p.relative_to(source))
            manager=Manager(ROOT,root/'state',root/'run',roots=[])
            extracted=root/'extract';extracted.mkdir()
            bundles,rows=manager.check(archive,extracted)
            self.assertEqual(rows[0]['uri'],'urn:machinista:upload-test');self.assertTrue(rows[0]['supported'])
            self.assertFalse(marker.exists(),'Checking metadata must never dlopen the uploaded binary')
            needed,_=needed_libraries(bundles[0]/'plugin.so');self.assertTrue(needed)
            with self.assertRaisesRegex(ValueError,'required library'):check_dependencies(bundles[0]/'plugin.so',bundles[0],set())
            # Keep a world alive before the bundle exists, then load/process it.
            active=root/'late';active.mkdir();harness=root/'host.cpp'
            harness.write_text('''#include "audio/lv2_host.hpp"
#include <filesystem>
int main(int argc,char** argv){maschine::LV2World world;std::filesystem::copy(argv[1],std::filesystem::path(argv[2])/"UploadTest.lv2",std::filesystem::copy_options::recursive);maschine::LV2Plugin p(world,"urn:machinista:upload-test",44100);return p.instance?0:1;}''')
            flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','lilv-0'],text=True))
            subprocess.run(['c++','-std=c++20','-O2','-pthread','-I'+str(ROOT/'src'),str(harness),'-o',str(root/'host'),*flags],check=True,capture_output=True)
            subprocess.run([str(root/'host'),str(bundles[0]),str(active)],env=dict(os.environ,LV2_PATH=str(active)),check=True,capture_output=True)
            self.assertTrue(marker.exists(),'Plugin is loaded only when explicitly instantiated')

if __name__=='__main__':unittest.main()
