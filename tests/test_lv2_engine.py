"""Render installed LV2 plugins into an ALSA file sink on Linux."""
import array
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
ENGINE=Path(__file__).resolve().parent.parent/'build/audio_engine'
@unittest.skipUnless(ENGINE.exists() and Path('/usr/share/alsa/alsa.conf').exists(),'Linux LV2/ALSA build required')
class LV2RenderTests(unittest.TestCase):
    def setup_engine(self,root):
        output=root/'audio.raw';config=root/'alsa.conf';config.write_text('</usr/share/alsa/alsa.conf>\n'+f'pcm.fixture {{ type file slave.pcm "null" file "{output}" format "raw" }}\n')
        process=subprocess.Popen([str(ENGINE)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=dict(os.environ,ALSA_CONFIG_PATH=str(config)))
        self.addCleanup(lambda:process.poll() is None and process.kill())
        return process,output
    def send(self,p,text):p.stdin.write(text+'\n');p.stdin.flush()
    def test_effect_gain_and_state_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);p,output=self.setup_engine(root);sample=root/'sample.f32';sample.write_bytes(array.array('f',[.125]*96).tobytes())
            self.send(p,'plugins 0 "http://plugin.org.uk/swh-plugins/amp"');self.assertEqual(json.loads(p.stdout.readline())['status'],'ready')
            self.send(p,'plugin_param 0 0 0 6.0205999');self.send(p,f'load 0 48000 {json.dumps(str(sample))}');self.send(p,'device "fixture"');self.assertEqual(json.loads(p.stdout.readline())['status'],'ready')
            self.send(p,'hit 0 1 1');time.sleep(.04)
            self.send(p,'plugin_save 0 0 '+json.dumps(str(root/'state')));self.assertEqual(json.loads(p.stdout.readline())['status'],'saved');self.assertTrue((root/'state/state.ttl').is_file())
            self.send(p,'quit');_,error=p.communicate(timeout=5);self.assertEqual(p.returncode,0,error)
            values=array.array('h');values.frombytes(output.read_bytes());sounding=[v for v in values if v];self.assertEqual(len(sounding),96);self.assertLessEqual(max(abs(v-8191) for v in sounding),1)
    def test_instrument_responds_to_midi_and_panic(self):
        catalog=json.loads(subprocess.check_output([str(ENGINE),'--plugins'],text=True));uri='http://drobilla.net/plugins/mda/EPiano'
        if not any(p['uri']==uri for p in catalog):self.skipTest('MDA test instrument absent')
        with tempfile.TemporaryDirectory() as directory:
            p,output=self.setup_engine(Path(directory));self.send(p,'plugins 0 '+json.dumps(uri));self.assertEqual(json.loads(p.stdout.readline())['status'],'ready')
            self.send(p,'device "fixture"');self.assertEqual(json.loads(p.stdout.readline())['status'],'ready');self.send(p,'plugin_note 0 60 100');time.sleep(.04);self.send(p,'plugin_note 0 60 0');self.send(p,'panic');time.sleep(.02);self.send(p,'quit')
            _,error=p.communicate(timeout=5);self.assertEqual(p.returncode,0,error);values=array.array('h');values.frombytes(output.read_bytes());self.assertGreater(max(abs(v) for v in values),100)
    def test_plugin_state_survives_group_bus_compaction(self):
        from app.model import Application
        from app.group_delete import compact_group
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);a=Application(root);p,output=self.setup_engine(root)
            uri='http://plugin.org.uk/swh-plugins/amp';state=root/'saved'
            a.project['groups'][2]['pads'][3]['plugins']=[{'uri':uri,'kind':'EFFECT','controls':{'gain':6.0205999},'state':str(state/'state.ttl')}]
            self.send(p,'plugins 35 '+json.dumps(uri));self.assertEqual(json.loads(p.stdout.readline())['status'],'ready')
            self.send(p,'plugin_param 35 0 0 6.0205999');self.send(p,'plugin_save 35 0 '+json.dumps(str(state)))
            self.assertEqual(json.loads(p.stdout.readline())['status'],'saved')
            self.send(p,'state_barrier');self.assertEqual(json.loads(p.stdout.readline())['kind'],'state_barrier')
            project,_=compact_group(a.project,1);plugin=project['groups'][1]['pads'][3]['plugins'][0]
            self.send(p,'plugins 35');self.assertEqual(json.loads(p.stdout.readline())['status'],'ready')
            self.send(p,'plugins 19 '+json.dumps(plugin['uri']));self.assertEqual(json.loads(p.stdout.readline())['status'],'ready')
            self.send(p,'plugin_restore 19 0 '+json.dumps(plugin['state']));self.assertEqual(json.loads(p.stdout.readline())['status'],'saved')
            # Control ports live in the project, separately from opaque LV2 state.
            self.send(p,'plugin_param 19 0 0 '+str(plugin['controls']['gain']))
            sample=root/'sample.f32';sample.write_bytes(array.array('f',[.125]*96).tobytes())
            self.send(p,'load 19 48000 '+json.dumps(str(sample)));self.send(p,'device "fixture"')
            event=json.loads(p.stdout.readline())
            if event['status']=='idle':event=json.loads(p.stdout.readline())
            self.assertEqual(event['status'],'ready')
            self.send(p,'hit 19 1 1');time.sleep(.04);self.send(p,'quit');_,error=p.communicate(timeout=5)
            self.assertEqual(p.returncode,0,error);values=array.array('h');values.frombytes(output.read_bytes());sounding=[v for v in values if v]
            self.assertEqual(len(sounding),96);self.assertLessEqual(max(abs(v-8191) for v in sounding),1)
    def test_added_group_routes_audio_and_internal_recording(self):
        from app.model import Application
        from app.audio import AudioBackend
        from app.layout import MASTER
        import wave
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);a=Application(root);a.ensure_group_bank(1)
            a.project['groups'][8]['pads'][0]['gain']=100
            commands=[];b=AudioBackend.__new__(AudioBackend);b.command=commands.append;b.desired=b.recorder=b.capture_pending=b.native_capture=None;b.input_device='-';b.routing_signature=None;b.routing(a.project)
            p,output=self.setup_engine(root);self.send(p,commands[-1]);self.assertEqual(json.loads(p.stdout.readline()),{'kind':'routing','status':'ready'})
            sample=root/'sample.f32';sample.write_bytes(array.array('f',[.25]*96).tobytes());self.send(p,f'load 128 48000 {json.dumps(str(sample))}')
            self.send(p,'device "fixture"');self.assertEqual(json.loads(p.stdout.readline())['status'],'ready')
            self.send(p,'record_start '+json.dumps(str(root/'record.wav'))+f' {MASTER} 1 0 -20 48 0')
            self.send(p,'hit 128 1 1');time.sleep(.05);self.send(p,'record_stop');self.assertEqual(json.loads(p.stdout.readline())['frames'],48)
            self.send(p,'quit');_,error=p.communicate(timeout=5);self.assertEqual(p.returncode,0,error)
            with wave.open(str(root/'record.wav')) as wav:
                self.assertEqual((wav.getframerate(),wav.getnframes()),(48000,48));values=array.array('h');values.frombytes(wav.readframes(48));self.assertTrue(all(abs(v-8191)<=1 for v in values))

    def test_internal_meter_reports_actual_audio_without_recording(self):
        from app.layout import MASTER
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);p,output=self.setup_engine(root)
            sample=root/'meter.f32';sample.write_bytes(array.array('f',[.25,.125]*256).tobytes())
            self.send(p,'meter_source '+str(MASTER));self.send(p,'load 0 48000 '+json.dumps(str(sample)))
            self.send(p,'device "fixture"');self.assertEqual(json.loads(p.stdout.readline())['status'],'ready')
            self.send(p,'hit 0 1 1');time.sleep(.03);self.send(p,'meter_status')
            report=json.loads(p.stdout.readline());self.assertEqual(report['kind'],'input_meter');self.assertAlmostEqual(report['peak'],.25,places=4);self.assertAlmostEqual(report['left'],.25,places=4);self.assertAlmostEqual(report['right'],.125,places=4)
            self.send(p,'quit');_,error=p.communicate(timeout=5);self.assertEqual(p.returncode,0,error)

    def test_live_preview_reports_end_and_restarts_from_existing_marker(self):
        from app.layout import PREVIEW
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);p,output=self.setup_engine(root)
            sample=root/'preview.f32';sample.write_bytes(array.array('f',[.25]*96).tobytes())
            self.send(p,f'load {PREVIEW} 48000 '+json.dumps(str(sample)))
            self.send(p,'device "fixture"');self.assertEqual(json.loads(p.stdout.readline())['status'],'ready')
            self.send(p,'preview 101 1');time.sleep(.02);self.send(p,'preview_status')
            self.assertEqual(json.loads(p.stdout.readline()),{'kind':'preview','status':'finished','token':101,'frame':48})
            self.send(p,f'range {PREVIEW} 16 48');self.send(p,'preview 102 1');time.sleep(.02);self.send(p,'preview_status')
            self.assertEqual(json.loads(p.stdout.readline()),{'kind':'preview','status':'finished','token':102,'frame':48})
            self.send(p,'quit');_,error=p.communicate(timeout=5);self.assertEqual(p.returncode,0,error)
            values=array.array('h');values.frombytes(output.read_bytes());self.assertEqual(len([v for v in values if v]),160)

    def test_reset_bus_stops_only_its_sampler_voices(self):
        from app.layout import ZONE_BASE
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);p,output=self.setup_engine(root)
            first=root/'first.f32';second=root/'second.f32'
            first.write_bytes(array.array('f',[.125]*96000).tobytes());second.write_bytes(array.array('f',[.25]*96000).tobytes())
            self.send(p,f'load {ZONE_BASE} 48000 '+json.dumps(str(first)))
            self.send(p,f'load {ZONE_BASE+128} 48000 '+json.dumps(str(second)))
            # Loop the short constant sources: the null PCM is unpaced and a
            # fast VM can exhaust one-shot files before kill_bus is dispatched.
            from app.audio import AudioBackend
            backend=AudioBackend.__new__(AudioBackend);backend.command=lambda command:self.send(p,command)
            for slot in (ZONE_BASE,ZONE_BASE+128):backend._params(slot,{},dict(loop=True,loop_start=0,loop_end=32))
            self.send(p,'device "fixture"');self.assertEqual(json.loads(p.stdout.readline())['status'],'ready')
            self.send(p,f'hit {ZONE_BASE} 1 1');self.send(p,f'hit {ZONE_BASE+128} 1 1');time.sleep(.03)
            self.send(p,'kill_bus 0');time.sleep(.03);self.send(p,'quit');_,error=p.communicate(timeout=5)
            self.assertEqual(p.returncode,0,error);values=array.array('h');values.frombytes(output.read_bytes())
            self.assertTrue(any(abs(v-12287)<=1 for v in values));self.assertTrue(any(abs(v-8191)<=1 for v in values))
            self.assertTrue(all(abs(v-8191)<=1 for v in values[-512:]))
