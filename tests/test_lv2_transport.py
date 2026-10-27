"""Real LV2 fixture validates host time events, simultaneous MIDI and latency."""
import array
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parent.parent

@unittest.skipUnless((ROOT/'build/audio_engine').exists() and Path('/usr/share/alsa/alsa.conf').exists(),'Linux LV2 build required')
class LV2TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name)
        search=cls.root/'lv2';search.mkdir();bundle=search/'time.lv2';bundle.mkdir()
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','lilv-0'],text=True))
        subprocess.run(['c++','-std=c++20','-O2','-shared','-fPIC',str(ROOT/'tests/lv2_time_fixture.cpp'),'-o',str(bundle/'time.so'),*flags],check=True,capture_output=True,text=True)
        (bundle/'manifest.ttl').write_text('@prefix lv2: <http://lv2plug.in/ns/lv2core#> .\n@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n<urn:maschineos:test-time> a lv2:Plugin ; lv2:binary <time.so> ; rdfs:seeAlso <time.ttl> .\n')
        ports=[]
        for index,symbol in enumerate(('left','right','events','tempo','latency','bpm','speed','beat','frame','bar','barbeat','note','valid')):
            direction='InputPort' if index in (2,3) else 'OutputPort'
            kind='AudioPort' if index<2 else 'atom:AtomPort' if index==2 else 'ControlPort'
            kind=kind if ':' in kind else 'lv2:'+kind
            extra='; atom:bufferType atom:Sequence; atom:supports time:Position, midi:MidiEvent' if index==2 else '; lv2:designation time:beatsPerMinute' if index==3 else '; lv2:designation lv2:latency; lv2:portProperty lv2:reportsLatency' if index==4 else ''
            ports.append(f'[ a lv2:{direction}, {kind}; lv2:index {index}; lv2:symbol "{symbol}"; lv2:name "{symbol}" {extra} ]')
        (bundle/'time.ttl').write_text('''@prefix lv2: <http://lv2plug.in/ns/lv2core#> .
@prefix atom: <http://lv2plug.in/ns/ext/atom#> .
@prefix time: <http://lv2plug.in/ns/ext/time#> .
@prefix midi: <http://lv2plug.in/ns/ext/midi#> .
@prefix doap: <http://usefulinc.com/ns/doap#> .
<urn:maschineos:test-time> a lv2:Plugin; doap:name "Time fixture";
lv2:requiredFeature <http://lv2plug.in/ns/ext/urid#map>; lv2:port '''+',\n'.join(ports)+'.\n')
        cls.env=dict(os.environ,LV2_PATH=str(search))
        cls.harness=cls.root/'host-test'
        subprocess.run(['c++','-std=c++20','-O2','-pthread','-I'+str(ROOT/'src'),str(ROOT/'tests/lv2_time_host_test.cpp'),'-o',str(cls.harness),*flags],check=True,capture_output=True,text=True)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def test_time_atoms_control_designations_midi_latency_and_lockfree_clock(self):
        result=subprocess.run([str(self.harness)],env=self.env,capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        catalog=json.loads(subprocess.check_output([str(ROOT/'build/audio_engine'),'--plugins'],env=self.env,text=True))
        self.assertEqual(catalog[0]['ports'],[]) # host owns the designated BPM input
    def test_engine_real_bus_peaks_master_clipping_and_latency_report(self):
        output=self.root/'render.raw';config=self.root/'alsa.conf'
        config.write_text('</usr/share/alsa/alsa.conf>\n'+f'pcm.fixture {{ type file slave.pcm "null" file "{output}" format "raw" }}\n')
        p=subprocess.Popen([str(ROOT/'build/audio_engine')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=dict(self.env,ALSA_CONFIG_PATH=str(config)))
        def send(text):p.stdin.write(text+'\n');p.stdin.flush()
        try:
            send('plugins 0 "urn:maschineos:test-time"');self.assertEqual(json.loads(p.stdout.readline())['status'],'ready')
            send('transport 90 1 9.25 0');send('mixer_watch 0 8');send('device "fixture" 48000');self.assertEqual(json.loads(p.stdout.readline())['status'],'ready')
            send('plugin_note 0 60 100');time.sleep(.04)
            send('mixer_status 0 8');event=json.loads(p.stdout.readline())
            self.assertAlmostEqual(event['levels'][0][0],.09,places=5);self.assertAlmostEqual(event['levels'][0][1],.06,places=5)
            self.assertAlmostEqual(event['master'][0],.09,places=5);self.assertEqual(event['levels'][1],[0,0])
            send('plugin_latency 0');event=json.loads(p.stdout.readline());self.assertEqual(event['frames'],123);self.assertEqual(event['rate'],48000)
            send('plugin_bypass 0 0 1');time.sleep(.02);send('plugin_latency 0');self.assertEqual(json.loads(p.stdout.readline())['frames'],0)
            sample=self.root/'clip.f32';sample.write_bytes(array.array('f',[.75,.5]*256).tobytes())
            send('mixer_status 0 8');p.stdout.readline() # clear the earlier fixture peaks
            send('load 1 48000 '+json.dumps(str(sample)));send('hit 1 2 1');time.sleep(.02)
            send('mixer_status 0 8');event=json.loads(p.stdout.readline())
            self.assertEqual(event['levels'][1],[1.5,1]);self.assertEqual(event['master'],[1.5,1])
            # Muted routing must measure silence, not the configured fader value.
            from app.model import Application
            from app.audio import AudioBackend
            a=Application(self.root/'project');a.project['groups'][0]['pads'][1]['audio_mute']=True
            commands=[];backend=AudioBackend.__new__(AudioBackend);backend.command=commands.append
            backend.desired=backend.recorder=backend.capture_pending=backend.native_capture=None;backend.input_device='-';backend.routing_signature=None
            backend.routing(a.project)
            send(commands[-1]);self.assertEqual(json.loads(p.stdout.readline())['kind'],'routing')
            send('hit 1 2 1');time.sleep(.02);send('mixer_status 0 8');event=json.loads(p.stdout.readline())
            self.assertEqual(event['levels'][1],[0,0]);self.assertEqual(event['master'],[0,0])
            send('quit');_,error=p.communicate(timeout=5);self.assertEqual(p.returncode,0,error)
        finally:
            if p.poll() is None:p.kill();p.communicate()
