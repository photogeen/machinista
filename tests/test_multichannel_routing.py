"""Physical channel mapping, Cue isolation and acyclic LV2 sidechain routing."""
import array
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from app.model import Application
from app.devices import AudioDevice,usb_channels
from app.audio import AudioBackend
from app.audio_ports import ports,port,cue_sound
from app.routing import build_graph,route_defaults,destination
from app.native_sequence import sequence_commands
ROOT=Path(__file__).resolve().parent.parent

class RoutingPortsTests(unittest.TestCase):
    def test_usb_descriptor_counts_mono_pairs_and_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'stream0').write_text('Playback:\n  Channels: 8\nCapture:\n  Channels: 6\n')
            self.assertEqual(usb_channels(p),(8,6))
        self.assertEqual(ports(3,'OUT'),('OUT 1','OUT 2','OUT 3','OUT 1/2'))
        self.assertEqual(destination('OUT 3',0),-102);self.assertEqual(destination('OUT 3/4',0),-3)
        for invalid in ('OUT 0','OUT 2/3','OUT 66','OUT 1/3'):
            with self.assertRaises(ValueError):port(invalid,'OUT')
        self.assertEqual(AudioBackend.capture_source(dict(source='EXT STEREO',input='IN 5/6')),-1004)
        self.assertEqual(AudioBackend.capture_source(dict(source='EXT MONO',input='IN 5')),-2004)
        self.assertEqual(AudioBackend.input_code('IN 5'),14);self.assertEqual(AudioBackend.input_code('IN 5/6'),102)

    def test_mixer_assignment_settings_persistence_and_missing_device(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=Application(tmp);a.audio=AudioDevice('x','USB','null','null',8,6)
            a.page='MIXER';a.button('SHIFT',True);a.button('F2',True);a.button('SHIFT',False)
            self.assertEqual(a.mixer_field,2);a.rotate(5)
            self.assertEqual(a.track()['routing']['dest'],'OUT 3')
            a.button('F2',True);a.rotate(3);self.assertEqual(a.project['groups'][0]['routing']['dest'],'OUT 1')
            a.page='CUE OUTPUT';a.rotate(10);self.assertEqual(a.settings['cue_output'],'OUT 3/4')
            a.page='MAIN OUTPUT';a.rotate(1);self.assertEqual(a.settings['main_output'],'OUT 1/2')
            self.assertEqual(a.message,'MAIN / CUE MUST DIFFER')
            a.page='INPUT';a.input_field=0;a.rotate(8);self.assertEqual(a.plugin_target()['routing']['input'],'IN 5')
            a.save();b=Application(tmp)
            self.assertEqual(b.settings['cue_output'],'OUT 3/4');self.assertEqual(b.track()['routing']['dest'],'OUT 3')
            b.page='CUE OUTPUT';self.assertIn('UNAVAILABLE',b.display()[1]);self.assertEqual(b.settings['cue_output'],'OUT 3/4')

    def test_sidechain_precedes_receiver_and_rejects_feedback(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=Application(tmp);target=a.track();target['plugins']=[dict(uri='urn:sc',kind='EFFECT',controls={},sidechain='SOUND 1')]
            _,order=build_graph(a.project);self.assertLess(order.index(1),order.index(0))
            a.project['groups'][0]['pads'][1]['routing']={'dest':'SOUND 0'}
            build_graph(a.project)
            a.project['groups'][0]['pads'][1]['plugins']=[dict(uri='urn:sc',kind='EFFECT',controls={},sidechain='SOUND 0')]
            with self.assertRaises(ValueError):build_graph(a.project)
            target['plugins'][0]['sidechain']='GROUP 0'
            with self.assertRaises(ValueError):build_graph(a.project)

    def test_cue_pattern_ignores_mute_solo_but_does_not_send_external_midi(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=Application(tmp);track=a.track();track['routing']={'dest':'CUE','midi_send':True};track['mute']=True
            a.project['groups'][0]['mute']=True;a.put_note(0,0,dict(velocity=100,length=24,probability=100))
            self.assertTrue(cue_sound(a.project,0,0))
            commands=sequence_commands(a);self.assertTrue(any(c.startswith('hit ') for c in commands))
            self.assertFalse(any(c.startswith('external_note ') for c in commands))
            backend=AudioBackend.__new__(AudioBackend);backend.command=lambda x:None
            backend.desired=backend.native_capture=backend.recorder=backend.capture_pending=None;backend.input_device='-';backend.routing_signature=None
            backend.routing(a.project)
            a.project['groups'][0]['routing']={'dest':'CUE'};track['routing']['dest']='PARENT'
            self.assertTrue(cue_sound(a.project,0,0))

@unittest.skipUnless((ROOT/'build/audio_engine').exists() and Path('/usr/share/alsa/alsa.conf').exists(),'Linux native audio required')
class NativePortsTests(unittest.TestCase):
    def render(self,dest,main=0,cue=-1,preview=False,channels=4):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);output=root/'out.raw';config=root/'alsa.conf';sample=root/'sample.f32'
            sample.write_bytes(array.array('f',[.5,.25]*4096).tobytes())
            config.write_text('</usr/share/alsa/alsa.conf>\n'+f'pcm.fixture {{ type file slave.pcm "null" file "{output}" format "raw" }}\n')
            p=subprocess.Popen([str(ROOT/'build/audio_engine')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=dict(os.environ,ALSA_CONFIG_PATH=str(config)))
            try:
                a=Application(root/'project');a.track()['gain']=100;a.track()['routing']={'dest':dest};a.project['gain']=0 if dest=='CUE' else 100
                backend=AudioBackend.__new__(AudioBackend);commands=[];backend.command=commands.append
                backend.desired=backend.native_capture=backend.recorder=backend.capture_pending=None;backend.input_device='-';backend.routing_signature=None;backend.routing(a.project)
                text=f'output_map {main} {cue} 1\n'+commands[-1]+f'\ndevice "fixture" 48000 512 {channels} 2\n'
                p.stdin.write(text);p.stdin.flush()
                self.assertEqual(json.loads(p.stdout.readline())['status'],'ready') # routing
                ready=json.loads(p.stdout.readline());self.assertEqual(ready['channels'],channels)
                from app.layout import PREVIEW
                slot=PREVIEW if preview else 0
                p.stdin.write(f'load {slot} 48000 {json.dumps(str(sample))}\nhit {slot} 1 1\n');p.stdin.flush();time.sleep(.15)
                p.stdin.write('quit\n');p.stdin.flush();_,err=p.communicate(timeout=5);self.assertEqual(p.returncode,0,err)
                data=array.array('h');data.frombytes(output.read_bytes())
                return [max((abs(v) for v in data[ch::channels]),default=0) for ch in range(channels)]
            finally:
                if p.poll() is None:p.kill();p.communicate()

    def test_mono_and_pair_outputs_do_not_leak_to_master(self):
        self.assertEqual(self.render('OUT 3'),[0,0,12287,0])
        self.assertEqual(self.render('OUT 3/4'),[0,0,16383,8191])
        self.assertEqual(self.render('PARENT',main=2),[0,0,16383,8191])

    def test_cue_bypasses_master_and_preview_never_falls_back_on_missing_cue(self):
        self.assertEqual(self.render('CUE',cue=2),[0,0,16383,8191])
        self.assertEqual(self.render('PARENT',cue=2,preview=True),[0,0,16383,8191])
        self.assertEqual(self.render('PARENT',cue=2,preview=True,channels=2),[0,0])

    def test_input_channels_beyond_first_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);out=root/'out.raw';incoming=root/'in.raw';conf=root/'alsa.conf'
            incoming.write_bytes(array.array('h',[1000,2000,3000,4000,5000,6000]*48000).tobytes())
            conf.write_text('</usr/share/alsa/alsa.conf>\n'+f'pcm.fixture {{ type file slave.pcm "null" file "{out}" format "raw" }}\npcm.incoming {{ type file slave.pcm "null" infile "{incoming}" file "/dev/null" format "raw" }}\n')
            a=Application(root/'project');a.track()['gain']=100;a.track()['routing']={'input':'IN 5/6'}
            backend=AudioBackend.__new__(AudioBackend);commands=[];backend.command=commands.append
            backend.desired=backend.native_capture=backend.recorder=backend.capture_pending=None;backend.input_device='-';backend.routing_signature=None;backend.routing(a.project)
            recorded=root/'recorded.wav'
            p=subprocess.Popen([str(ROOT/'build/audio_engine')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=dict(os.environ,ALSA_CONFIG_PATH=str(conf)))
            try:
                p.stdin.write(commands[-1]+f'\ndevice "fixture" 48000 512 2 6\ninput_device "incoming"\nrecord_start {json.dumps(str(recorded))} -1004 0 0 -24 1024 0\nmeter_source -1004\n');p.stdin.flush()
                for _ in range(4):self.assertEqual(json.loads(p.stdout.readline())['status'],'ready')
                time.sleep(.15)
                p.stdin.write('quit\n');p.stdin.flush();stdout,err=p.communicate(timeout=5);self.assertEqual(p.returncode,0,err)
                self.assertTrue(recorded.is_file())
                data=array.array('h');data.frombytes(out.read_bytes())
                self.assertAlmostEqual(max(data[::2]),5000,delta=2);self.assertAlmostEqual(max(data[1::2]),6000,delta=2)
                import wave
                with wave.open(str(recorded),'rb') as wav:
                    self.assertEqual(wav.getnframes(),1024);take=array.array('h');take.frombytes(wav.readframes(1024))
                self.assertAlmostEqual(max(take[::2]),5000,delta=2);self.assertAlmostEqual(max(take[1::2]),6000,delta=2)
            finally:
                if p.poll() is None:p.kill();p.communicate()

    def test_real_lv2_sidechain_uses_dependency_without_main_output_leak(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);bundle=root/'lv2'/'sidechain.lv2';bundle.mkdir(parents=True)
            (bundle/'manifest.ttl').write_text('@prefix lv2: <http://lv2plug.in/ns/lv2core#> . @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> . <urn:test:sidechain> a lv2:Plugin; lv2:binary <sc.so>; rdfs:seeAlso <sc.ttl> .')
            declarations=[]
            for i in range(5):
                direction='InputPort' if i in (0,1,4) else 'OutputPort';extra='; lv2:portProperty lv2:isSideChain' if i==4 else ''
                declarations.append(f'[ a lv2:{direction},lv2:AudioPort; lv2:index {i}; lv2:symbol "p{i}"; lv2:name "p{i}" {extra} ]')
            (bundle/'sc.ttl').write_text('@prefix lv2: <http://lv2plug.in/ns/lv2core#> . @prefix doap: <http://usefulinc.com/ns/doap#> . <urn:test:sidechain> a lv2:Plugin; doap:name "Sidechain fixture"; lv2:port '+','.join(declarations)+'.')
            source=root/'sc.c';source.write_text('''#include <lv2/core/lv2.h>
#include <stdlib.h>
typedef struct {float* p[5];} S;
static LV2_Handle init(const LV2_Descriptor*d,double r,const char*p,const LV2_Feature*const*f){return calloc(1,sizeof(S));}
static void connect(LV2_Handle h,uint32_t p,void*v){((S*)h)->p[p]=v;}
static void run(LV2_Handle h,uint32_t n){S*s=h;for(unsigned i=0;i<n;++i){s->p[2][i]=s->p[0][i]+s->p[4][i];s->p[3][i]=s->p[1][i]+s->p[4][i];}}
static void clean(LV2_Handle h){free(h);}
static const LV2_Descriptor d={"urn:test:sidechain",init,connect,0,run,0,clean,0};
const LV2_Descriptor* lv2_descriptor(uint32_t i){return i?0:&d;}
''')
            flags=subprocess.check_output(['pkg-config','--cflags','lv2'],text=True).split()
            subprocess.run(['cc','-shared','-fPIC',str(source),'-o',str(bundle/'sc.so'),*flags],check=True,capture_output=True)
            env=dict(os.environ,LV2_PATH=str(root/'lv2'))
            catalog=json.loads(subprocess.check_output([str(ROOT/'build/audio_engine'),'--plugins'],env=env,text=True))
            self.assertTrue(catalog[0]['sidechain'])
            out=root/'out.raw';conf=root/'alsa.conf';conf.write_text('</usr/share/alsa/alsa.conf>\n'+f'pcm.fixture {{ type file slave.pcm "null" file "{out}" format "raw" }}\n');env['ALSA_CONFIG_PATH']=str(conf)
            a=Application(root/'project');target=a.project['groups'][0]['pads'][1]
            a.track()['gain']=target['gain']=100;a.track()['routing']={'dest':'NONE'};target['routing']={'dest':'OUT 3/4'}
            target['plugins']=[dict(uri='urn:test:sidechain',kind='EFFECT',controls={},sidechain='SOUND 0')]
            commands=[];backend=AudioBackend.__new__(AudioBackend);backend.command=commands.append
            backend.desired=backend.native_capture=backend.recorder=backend.capture_pending=None;backend.input_device='-';backend.routing_signature=None;backend.routing(a.project)
            sc=root/'sc.f32';sc.write_bytes(array.array('f',[.5,.5]*4096).tobytes());main=root/'main.f32';main.write_bytes(array.array('f',[.25,.25]*4096).tobytes())
            p=subprocess.Popen([str(ROOT/'build/audio_engine')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
            try:
                p.stdin.write(commands[-1]+'\nplugins 1 "urn:test:sidechain"\nplugin_sidechain 1 0 0\ndevice "fixture" 48000 512 4 2\n');p.stdin.flush()
                for _ in range(3):self.assertEqual(json.loads(p.stdout.readline())['status'],'ready')
                p.stdin.write(f'load 0 48000 {json.dumps(str(sc))}\nload 1 48000 {json.dumps(str(main))}\nhit 0 1 1\nhit 1 1 1\n');p.stdin.flush();time.sleep(.15)
                p.stdin.write('quit\n');p.stdin.flush();_,err=p.communicate(timeout=5);self.assertEqual(p.returncode,0,err)
                data=array.array('h');data.frombytes(out.read_bytes())
                self.assertEqual(max(data[::4]),0);self.assertEqual(max(data[1::4]),0)
                self.assertEqual(max(data[2::4]),24575);self.assertEqual(max(data[3::4]),24575)
            finally:
                if p.poll() is None:p.kill();p.communicate()
