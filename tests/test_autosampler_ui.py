"""The two controller surfaces operate the same autosampler runtime as the web."""
import copy
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.mk2_surface import Mk2Surface
from app.mk2_display import snapshot,Mk2Renderer
from app.ni_display import frame
from app.sound_runtime import SoundRuntime
from app.devices import AudioDevice

class AutosamplerUITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=Application(self.tmp.name);self.s=Mk2Surface(self.a,ControllerInputs(self.a))
    def test_mikro_nav_selection_name_and_return(self):
        a=self.a;a.page='SAMPLING';a.button('NAV',True);a.rotate(4)
        self.assertEqual(a.sampling_nav,4);self.assertEqual(len(frame(a)),8192)
        a.button('NAV',False);self.assertEqual(a.page,'AUTOSAMPLER')
        self.assertEqual(len(frame(a)),8192)
        a.auto_field=8;a.button('ENTER',True);a.button('ENTER',False)
        self.assertEqual(a.page,'PROJECT NAME');a.name_value='Studio Keys';a.finish_project_name()
        self.assertEqual(a.page,'AUTOSAMPLER');self.assertEqual(a.auto_config['name'],'Studio Keys')
        a.button('F1',True);a.button('F1',False);self.assertEqual(a.page,'SAMPLING')
    def test_mk2_encoder_pages_bindings_and_render(self):
        a=self.a;a.page='SAMPLING'
        self.s.change_page(1);self.s.change_page(1)
        self.assertEqual(a.page,'AUTOSAMPLER');self.assertEqual(self.s.fields()[0].value,'LV2')
        self.s.rotate(1,1);self.assertEqual(a.auto_config['source'],'EXTERNAL')
        self.s.rotate(2,1);self.assertEqual(a.auto_config['low'],49)
        self.s.rotate(5,2);self.assertEqual(len(a.auto_config['velocities']),3)
        self.s.softkey(3);self.s.rotate(2,-1);self.assertEqual(a.auto_config['velocities'][1],63)
        state=snapshot(self.s);self.assertIn('autosampler',state)
        renderer=Mk2Renderer();self.addCleanup(renderer.close);renderer(state)
        self.s.softkey(2);self.assertEqual(a.auto_field,8)
        self.s.softkey(4);self.assertEqual(a.page,'PROJECT NAME')
        a.name_value='Keys';a.finish_project_name();self.s.softkey(0)
        self.assertEqual(a.page,'SAMPLING')
    def test_internal_source_can_reach_auto_and_return(self):
        a=self.a;a.page='SAMPLING';a.capture_options()['source']='INTERNAL'
        self.s.change_page(1);self.assertEqual(a.page,'AUTOSAMPLER')
        self.s.change_page(-1);self.assertEqual(a.page,'SAMPLING')
        self.assertEqual(a.capture_section,0)
    def test_boundaries_and_status_lock(self):
        a=self.a;a.open_sampling_page('AUTOSAMPLER')
        a.auto_adjust(1,200);self.assertEqual(a.auto_config['low'],84)
        a.auto_adjust(2,-200);self.assertEqual(a.auto_config['high'],84)
        a.auto_adjust(4,7);self.assertEqual(len(a.auto_config['velocities']),8)
        a.auto_adjust(16,200);self.assertLess(a.auto_config['velocities'][0],a.auto_config['velocities'][1])
        before=copy.deepcopy(a.auto_config);a.auto_status={'state':'RECORDING'}
        a.auto_adjust(3,3);self.assertEqual(before,a.auto_config)
    def test_shared_runtime_start_busy_rejection_and_cancel(self):
        a=self.a;a.open_sampling_page('AUTOSAMPLER');a.auto_config['name']='Test Sound'
        audio=Mock();audio.native_capture=None;audio.recorder=None;audio.capture_pending=None
        rt=SoundRuntime(a.root,a,audio,Mock());self.addCleanup(rt.close)
        # Missing interface produces the same backend validation message.
        a.auto_start();rt.poll(time.monotonic());self.assertEqual(a.auto_status['state'],'ERROR')
        a.audio=AudioDevice('test','Test','play','capture',2,2)
        a.track()['plugins']=[dict(uri='urn:test',kind='INSTRUMENT',controls={},bypass=False)]
        audio.sample_rate=44100
        a.auto_start();rt.poll(time.monotonic(),other_busy=True);self.assertFalse(rt.auto.active)
        a.auto_start();rt.poll(time.monotonic());self.assertTrue(rt.auto.active)
        self.assertEqual(a.auto_status['state'],'RECORDING')
        a.auto_ui_button('F3',True);rt.poll(time.monotonic());self.assertTrue(rt.auto.cancelled)
