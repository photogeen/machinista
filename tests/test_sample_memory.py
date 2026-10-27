"""Explicit idle reclamation preserves assigned assets and immutable plans."""
import array
import copy
import json
import os
from pathlib import Path
import time
import subprocess
import tempfile
import unittest
from app.model import Application
from app.ni_display import frame
ROOT=Path(__file__).resolve().parent.parent

class SampleMemoryUiTests(unittest.TestCase):
    def test_menu_stats_confirmation_and_transport_recording_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=Application(tmp);before=copy.deepcopy(a.project)
            from app.project_manager import MANAGE
            a.page='PROJECT MANAGE';a.manage_index=MANAGE.index('SAMPLE RAM');a.button('ENTER',True)
            self.assertEqual(a.page,'SAMPLE RAM');self.assertEqual(a.actions[-1],('sample_memory',None));self.assertEqual(a.softkeys(),('BACK','REFRESH','PURGE'))
            a.sample_memory=dict(bytes=10485760,reclaimable_bytes=2097152,limit=536870912)
            self.assertIn('USED 10.0 MB',a.display()[1]);self.assertEqual(len(frame(a)),8192)
            for key in ('playing','recording','capture_armed','export_busy'):
                setattr(a,key,True);a.button('F3',True);self.assertEqual(a.page,'SAMPLE RAM');setattr(a,key,False)
            a.button('F3',True);self.assertEqual(a.page,'CONFIRM');a.playing=True;a.button('F2',True)
            self.assertFalse(any(op=='sample_purge' for op,_ in a.actions));a.playing=False
            a.button('F3',True);a.button('F2',True);self.assertEqual(a.actions[-1],('sample_purge',None));self.assertEqual(a.project,before)

@unittest.skipUnless((ROOT/'build/audio_engine').exists() and Path('/usr/share/alsa/alsa.conf').exists(),'Linux native build required')
class NativeSampleMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.sample=self.root/'tone.f32';self.sample.write_bytes(array.array('f',[.25,.125]*256).tobytes())
        self.output=self.root/'render.raw';config=self.root/'alsa.conf'
        config.write_text('</usr/share/alsa/alsa.conf>\npcm.fixture { type file slave.pcm \"null\" file \"'+str(self.output)+'\" format \"raw\" }\n')
        self.p=subprocess.Popen([str(ROOT/'build/audio_engine')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=dict(os.environ,ALSA_CONFIG_PATH=str(config)))
        self.addCleanup(self.close)
    def close(self):
        if self.p.poll() is None:
            self.p.stdin.write('quit\n');self.p.stdin.flush()
        self.p.communicate(timeout=5)
    def send(self,text):self.p.stdin.write(text+'\n');self.p.stdin.flush()
    def memory(self,purge=False):
        self.send('sample_purge' if purge else 'sample_memory')
        # TextIO can prefetch multiple lines; engine always emits this response last.
        while True:
            event=json.loads(self.p.stdout.readline())
            if event['kind']=='sample_memory':return event
    def load(self,slot):self.send(f'load {slot} 48000 '+json.dumps(str(self.sample)))
    def test_replaced_samples_are_reclaimed_and_shared_assignments_count_once(self):
        self.load(0);self.send('assign 1 0');first=self.memory();self.assertEqual(first['assets'],3);self.assertEqual(first['slots'],4)
        self.load(0);self.send('clear 1');second=self.memory();self.assertEqual(second['reclaimable_bytes'],2048)
        freed=self.memory(True);self.assertEqual(freed['freed_bytes'],2048);self.assertEqual(freed['bytes'],first['bytes']);self.assertEqual(freed['assets'],3)
        self.send('clear 0');freed=self.memory(True);self.assertEqual(freed['assets'],2);self.assertEqual(freed['freed_bytes'],2048)
        self.assertEqual(self.sample.read_bytes(),array.array('f',[.25,.125]*256).tobytes())
    def test_pending_native_plan_and_build_references_survive_purge(self):
        self.load(0);self.send('sequence_begin\nsequence_lane 384\nsequence_event 0 24 100 0\nhit 0 1 1\nsequence_commit\nclear 0')
        status=self.memory(True);self.assertEqual(status['assets'],3);self.assertEqual(status['freed_bytes'],0)
        self.send('sequence_begin\nsequence_lane 384\nsequence_commit');status=self.memory(True);self.assertEqual(status['assets'],2)
        self.load(0);self.send('sequence_begin\nsequence_lane 384\nsequence_event 0 24 100 0\nhit 0 1 1\nclear 0');status=self.memory(True);self.assertEqual(status['assets'],3)
        self.send('sequence_begin');status=self.memory(True);self.assertEqual(status['assets'],2)
    def test_native_guards_recording_and_playback_without_reclaiming(self):
        self.load(0);self.load(0);before=self.memory();self.send('sequence_transport 120 1 0 0');status=self.memory(True)
        self.assertEqual(status['status'],'busy');self.assertEqual(status['bytes'],before['bytes'])
        self.send('sequence_transport 120 0 0 0\ndevice \"-\" 48000');self.assertEqual(json.loads(self.p.stdout.readline())['status'],'idle');record=self.root/'rec.wav'
        self.send('record_start '+json.dumps(str(record))+' 1088 0 0 -20 100000 0')
        status=self.memory(True);self.assertEqual(status['status'],'busy');self.send('record_stop');self.assertEqual(self.memory(True)['status'],'purged')
    def test_live_input_routing_blocks_purge(self):
        self.load(0);self.load(0);before=self.memory()
        self.send('routing 1 0 0 1 0 -1 -1 0 0 -1 0 0 1 1')
        status=self.memory(True);self.assertEqual(status['status'],'live_input');self.assertEqual(status['bytes'],before['bytes'])

    def test_idle_worker_restart_keeps_assigned_audio_playable_and_lv2_chain(self):
        # Equal stereo inputs test restored chain gain with mono or stereo amp
        # plugins, without imposing a channel-folding policy on the fixture.
        self.sample.write_bytes(array.array('f',[.25,.25]*256).tobytes())
        self.load(0);self.load(0);self.send('device "fixture" 48000');self.assertEqual(json.loads(self.p.stdout.readline())['status'],'ready')
        uri='http://plugin.org.uk/swh-plugins/amp';self.send('plugins 0 '+json.dumps(uri))
        self.assertEqual(json.loads(self.p.stdout.readline())['status'],'ready')
        # A non-neutral gain proves the restored chain still processes audio.
        self.send('plugin_param 0 0 0 6.0205999')
        status=self.memory(True);self.assertEqual(status['freed_bytes'],2048)
        state=self.root/'state';self.send('plugin_save 0 0 '+json.dumps(str(state)));self.send('sample_memory')
        while True:
            event=json.loads(self.p.stdout.readline())
            if event['kind']=='sample_memory':break
        self.assertTrue((state/'state.ttl').exists())
        self.send('hit 0 1 1');self.assertEqual(self.memory()['assets'],3)
        deadline=time.monotonic()+2;values=array.array('h')
        while time.monotonic()<deadline:
            values=array.array('h');values.frombytes(self.output.read_bytes() if self.output.exists() else b'')
            if sum(v!=0 for v in values)>=512:break
            time.sleep(.005)
        sounding=[v for v in values if v];self.assertEqual(set(sounding),{16383});self.assertEqual(len(sounding),512)
