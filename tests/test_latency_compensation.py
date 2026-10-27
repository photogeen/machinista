"""Known LV2 delays exercise real routing and offline preroll, not UI estimates."""
import array
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
import wave
from app.model import Application

ROOT=Path(__file__).resolve().parents[1]

class DelaySettingsTests(unittest.TestCase):
    def test_setting_persists_and_refuses_running_transport(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=Application(tmp);a.page='PLUGIN DELAY'
            self.assertFalse(a.settings['plugin_delay']);a.rotate(1)
            self.assertTrue(a.settings['plugin_delay']);self.assertIn(('plugin_delay',True),a.actions)
            a.playing=True;a.rotate(-1);self.assertTrue(a.settings['plugin_delay'])
            a.playing=False;a.rotate(-1);self.assertFalse(a.settings['plugin_delay'])
            a.page='PLUGIN DELAY';a.pdc_status={'frames':600,'rate':48000,'status':0}
            self.assertIn('600 FR 12.5 MS',a.display()[1])
            self.assertFalse(Application(tmp).settings['plugin_delay'])

@unittest.skipUnless((ROOT/'build/audio_engine').exists() and Path('/usr/share/alsa/alsa.conf').exists() and shutil.which('cc'),'Linux native LV2 host required')
class NativeDelayTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        bundle=self.root/'lv2'/'delay.lv2';bundle.mkdir(parents=True)
        uris=['urn:test:latency','urn:test:musical']
        prefix='@prefix lv2: <http://lv2plug.in/ns/lv2core#> . @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> . @prefix doap: <http://usefulinc.com/ns/doap#> . '
        (bundle/'manifest.ttl').write_text(prefix+'\n'.join(f'<{u}> a lv2:Plugin; lv2:binary <delay.so>; rdfs:seeAlso <delay.ttl> .' for u in uris))
        parts=[]
        for uri in uris:
            ports=[]
            for i in range(7):
                direction='InputPort' if i in (0,1,4,6) else 'OutputPort'
                kind='AudioPort' if i<5 else 'ControlPort'
                extra='; lv2:portProperty lv2:isSideChain' if i==4 else '; lv2:designation lv2:latency' if i==5 and uri==uris[0] else '; lv2:default 600; lv2:minimum 0; lv2:maximum 20000; lv2:portProperty lv2:integer' if i==6 else ''
                ports.append(f'[a lv2:{direction},lv2:{kind}; lv2:index {i}; lv2:symbol "p{i}"; lv2:name "p{i}" {extra}]')
            parts.append(f'<{uri}> a lv2:Plugin; doap:name "Known delay"; lv2:port '+','.join(ports)+'.')
        (bundle/'delay.ttl').write_text(prefix+'\n'.join(parts))
        source=self.root/'delay.c';source.write_text('''#include <lv2/core/lv2.h>
#include <stdlib.h>
#include <string.h>
typedef struct {float* p[7];float l[20001],r[20001];unsigned pos;} S;
static LV2_Handle init(const LV2_Descriptor*d,double r,const char*p,const LV2_Feature*const*f){return calloc(1,sizeof(S));}
static void connect(LV2_Handle h,uint32_t p,void*v){((S*)h)->p[p]=v;}
static void activate(LV2_Handle h){S*s=h;s->pos=0;memset(s->l,0,sizeof(s->l));memset(s->r,0,sizeof(s->r));}
static void run(LV2_Handle h,uint32_t n){S*s=h;unsigned delay=(unsigned)*s->p[6];if(delay>20000)delay=20000;*s->p[5]=delay;
 for(unsigned i=0;i<n;++i){s->l[s->pos]=s->p[0][i]+s->p[4][i];s->r[s->pos]=s->p[1][i]+s->p[4][i];unsigned at=(s->pos+20001-delay)%20001;s->p[2][i]=s->l[at];s->p[3][i]=s->r[at];s->pos=(s->pos+1)%20001;}}
static void clean(LV2_Handle h){free(h);}
static const LV2_Descriptor d[]={ {"urn:test:latency",init,connect,activate,run,0,clean,0},{"urn:test:musical",init,connect,activate,run,0,clean,0} };
const LV2_Descriptor* lv2_descriptor(uint32_t i){return i<2?d+i:0;}
''')
        flags=subprocess.check_output(['pkg-config','--cflags','lv2'],text=True).split()
        subprocess.run(['cc','-shared','-fPIC',str(source),'-o',str(bundle/'delay.so'),*flags],check=True,capture_output=True)
        self.env=dict(os.environ,LV2_PATH=str(self.root/'lv2'))
        self.left=self.root/'left.f32';self.right=self.root/'right.f32'
        self.left.write_bytes(array.array('f',[.2,0]+[0,0]*1023).tobytes())
        self.right.write_bytes(array.array('f',[0,.3]+[0,0]*1023).tobytes())

    def graph(self,rows):
        # bus,dest,auxdest,auxgain,auxpre
        order=[r[0] for r in rows]
        return 'routing '+str(len(rows))+' '+' '.join(map(str,order))+' '+' '.join(f'{b} 1 0 {d} {a} {gain} {int(pre)} -1 0 0 0 1' for b,d,a,gain,pre in rows)

    def render(self,rows,plugins,enabled=True,bus=1088,extra=''):
        output=self.root/'render.wav'
        script=self.graph(rows)+'\n'+plugins+f'\npdc {int(enabled)}\nload 0 48000 {json.dumps(str(self.left))}\nload 1 48000 {json.dumps(str(self.right))}\n'
        script+='sequence_begin\nsequence_lane 10000\nsequence_event 0 1 100 0\nhit 0 1 1\nhit 1 1 1\nsequence_commit\nsequence_seek 0 1\nsequence_transport 120 1\n'
        script+=extra+f'\nrender_start {json.dumps(str(output))} 4096 {bus}\npdc\nquit\n'
        result=subprocess.run([str(ROOT/'build/audio_engine'),'--offline-render'],input=script,text=True,capture_output=True,env=self.env,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        events=[json.loads(line) for line in result.stdout.splitlines()]
        self.assertFalse(any(e.get('status')=='error' for e in events),events)
        with wave.open(str(output)) as wav:
            self.assertEqual(wav.getnframes(),4096);data=array.array('h');data.frombytes(wav.readframes(4096))
        return data,events[-1]

    def indices(self,data,ch):return [i for i,v in enumerate(data[ch::2]) if abs(v)>10]
    def test_sound_group_master_paths_align_and_export_preroll_is_removed(self):
        rows=[(0,1024,-1,0,False),(1,1025,-1,0,False),(1024,1088,-1,0,False),(1025,1088,-1,0,False),(1088,-1,-1,0,False)]
        plugins='plugins 0 "urn:test:latency"\nplugins 1024 "urn:test:latency"\nplugin_param 1024 0 6 17\nplugins 1088 "urn:test:latency"\nplugin_param 1088 0 6 13'
        data,status=self.render(rows,plugins);self.assertEqual(status['frames'],630);self.assertEqual(status['status'],0)
        self.assertEqual(self.indices(data,0),[0]);self.assertEqual(self.indices(data,1),[0])
        self.assertAlmostEqual(data[0],6553,delta=1);self.assertAlmostEqual(data[1],9830,delta=1)
        data,_=self.render(rows,plugins,False);self.assertEqual(self.indices(data,0),[630]);self.assertEqual(self.indices(data,1),[13])

    def test_aux_prefader_and_internal_sidechain_align(self):
        rows=[(0,-1,1024,1,True),(1,1024,-1,0,False),(1024,1088,-1,0,False),(1088,-1,-1,0,False)]
        data,_=self.render(rows,'plugins 0 "urn:test:latency"');self.assertEqual(self.indices(data,0),[0]);self.assertEqual(self.indices(data,1),[0])
        rows=[(0,-1,-1,0,False),(1,1088,-1,0,False),(1088,-1,-1,0,False)]
        data,status=self.render(rows,'plugins 0 "urn:test:latency"\nplugins 1 "urn:test:latency"\nplugin_param 1 0 6 17\nplugin_sidechain 1 0 0')
        self.assertEqual(status['frames'],617);self.assertEqual(self.indices(data,0),[0]);self.assertEqual(self.indices(data,1),[0])
        self.assertAlmostEqual(data[0],6553,delta=1);self.assertAlmostEqual(data[1],16383,delta=1)

    def test_bypass_musical_delay_and_limit_are_explicit(self):
        rows=[(0,1088,-1,0,False),(1,1088,-1,0,False),(1088,-1,-1,0,False)]
        data,status=self.render(rows,'plugins 0 "urn:test:latency"\nplugin_bypass 0 0 1');self.assertEqual(status['frames'],0);self.assertEqual(self.indices(data,0),[0])
        data,status=self.render(rows,'plugins 0 "urn:test:musical"');self.assertEqual(status['frames'],0);self.assertEqual(self.indices(data,0),[600]);self.assertEqual(self.indices(data,1),[0])
        data,status=self.render(rows,'plugins 0 "urn:test:latency"\nplugin_param 0 0 6 20000');self.assertEqual(status['status'],1);self.assertEqual(status['frames'],0);self.assertEqual(self.indices(data,1),[0])

    def test_live_separate_hardware_outputs_are_aligned(self):
        for enabled in (False,True):
            self.check_live_outputs(enabled)

    def check_live_outputs(self,enabled):
        out=self.root/'physical.raw';conf=self.root/'alsa.conf'
        conf.write_text('</usr/share/alsa/alsa.conf>\n'+f'pcm.fixture {{ type file slave.pcm "null" file "{out}" format "raw" }}\n')
        env=dict(self.env,ALSA_CONFIG_PATH=str(conf))
        rows=[(0,-3,-1,0,False),(1,-2,-1,0,False),(1088,-99,-1,0,False)]
        commands=('pdc 1\n' if enabled else '')+self.graph(rows)+'\nplugins 0 "urn:test:latency"\n'
        commands+=f'load 0 48000 {json.dumps(str(self.left))}\nload 1 48000 {json.dumps(str(self.right))}\n'
        commands+='sequence_begin\nsequence_lane 10000\nsequence_event 0 1 100 0\nhit 0 1 1\nhit 1 1 1\nsequence_commit\nsequence_seek 0 1\nsequence_transport 120 1\ndevice "fixture" 48000 512 4 2\n'
        proc=subprocess.Popen([str(ROOT/'build/audio_engine')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
        try:
            proc.stdin.write(commands);proc.stdin.flush()
            while True:
                event=json.loads(proc.stdout.readline())
                if event['kind']=='pdc':self.assertTrue(event['enabled']);continue
                self.assertEqual(event['status'],'ready')
                if event['kind']=='audio':break
            deadline=time.monotonic()+3
            while time.monotonic()<deadline and (not out.exists() or out.stat().st_size<8192):time.sleep(.005)
            proc.stdin.write('pdc\nquit\n');proc.stdin.flush();stdout,err=proc.communicate(timeout=5)
            self.assertEqual(proc.returncode,0,err);self.assertEqual(json.loads(stdout.splitlines()[-1])['frames'],600 if enabled else 0)
            data=array.array('h');data.frombytes(out.read_bytes())
            self.assertEqual([i for i,v in enumerate(data[1::4]) if abs(v)>10],[600 if enabled else 0])
            self.assertEqual([i for i,v in enumerate(data[2::4]) if abs(v)>10],[600])
            self.assertTrue(all(v==0 for v in data[::4]));self.assertTrue(all(v==0 for v in data[3::4]))
        finally:
            if proc.poll() is None:proc.kill();proc.communicate()

    def test_preroll_uses_render_timeline_for_automation(self):
        rows=[(0,1088,-1,0,False),(1,1088,-1,0,False),(1088,-1,-1,0,False)]
        # Mute dry input after frame256. Its already delayed frame0 impulse must
        # survive; commands must not be repeatedly applied at writer frame0.
        muted=self.graph([(0,1088,-1,0,False),(1,1088,-1,0,False),(1088,-1,-1,0,False)]).replace('1 1 0 1088','1 0 0 1088')
        data,_=self.render(rows,'plugins 0 "urn:test:latency"',extra='offline_control 256 '+json.dumps(muted))
        self.assertEqual(self.indices(data,1),[0])
