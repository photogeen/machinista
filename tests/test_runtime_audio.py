from pathlib import Path
import tempfile
import unittest
from app.model import Application
from app.ni_display import frame
from app.runtime_audio import RuntimeAudio, meter_height


class RuntimeAudioTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.a=Application(self.temp.name)
        self.runtime=RuntimeAudio();self.commands=[]
        self.audio=type('Audio',(),{'command':self.commands.append})()
    def tearDown(self):self.temp.cleanup()
    def test_transport_start_stop_tempo_seek_and_bounded_update_rate(self):
        a=self.a;r=self.runtime
        r.update(a,self.audio,10,10);self.assertIn('transport 120 0 0.000000000 10.000000000',self.commands)
        self.commands.clear();r.update(a,self.audio,10.01,10.01);self.assertEqual(self.commands,[])
        a.playing=True;a.clock_phase=96;r.update(a,self.audio,11,11+a.clock_interval())
        self.assertTrue(self.commands[-1].startswith('transport 120 1 1.000000000'))
        self.commands.clear();a.clock_phase=97;r.update(a,self.audio,11.002,11.002+a.clock_interval());self.assertEqual(self.commands,[])
        a.clock_phase=0;r.update(a,self.audio,11.003,11.003+a.clock_interval());self.assertTrue(self.commands[-1].startswith('transport 120 1 0.'))
        a.project['tempo']=78.25;r.update(a,self.audio,11.004,11.004+a.clock_interval());self.assertTrue(self.commands[-1].startswith('transport 78.25 1'))
        a.playing=False;r.update(a,self.audio,11.005,11.005);self.assertTrue(self.commands[-1].startswith('transport 78.25 0'))
    def test_meter_bank_stale_response_and_exit(self):
        a=self.a;r=self.runtime;a.page='MIXER';a.group=1;a.pad=10
        r.update(a,self.audio,10,10)
        self.assertIn('mixer_watch 24 8',self.commands);self.assertIn('mixer_status 24 8',self.commands)
        event=dict(kind='mixer_meter',first=24,levels=[[.5,.25]]*8,master=[.75,.6])
        r.receive(a,event);self.assertEqual(a.mixer_levels[26],(.5,.25))
        sounding=frame(a);a.mixer_levels={};self.assertNotEqual(sounding,frame(a))
        a.pad=0;r.update(a,self.audio,11,11);r.receive(a,event);self.assertEqual(a.mixer_levels,{})
        a.page='PAD';r.update(a,self.audio,12,12);self.assertIn('mixer_watch -1 0',self.commands)
    def test_latency_bus_and_meter_scale(self):
        a=self.a;a.page='PLUGIN';r=self.runtime;r.update(a,self.audio,10,10)
        r.receive(a,dict(kind='plugin_latency',bus=0,frames=480,rate=48000));self.assertEqual(a.plugin_latency_ms,10)
        r.receive(a,dict(kind='plugin_latency',bus=1,frames=48000,rate=48000));self.assertEqual(a.plugin_latency_ms,10)
        self.assertEqual([meter_height(x) for x in (0,float('nan'),.001,1,2)],[0,0,0,20,20])
        self.assertLess(meter_height(.1),meter_height(.5))
