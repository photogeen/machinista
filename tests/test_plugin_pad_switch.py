"""Pad changes refresh the source engine rather than keeping sampler voices."""
import tempfile,unittest
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.mk2_surface import Mk2Surface
from app.mk3_surface import Mk3Surface
from app.plus_session import PlusSurface
from app.mk1_session import Mk1Surface
from app.mk2_display import snapshot
from app.mk3_state import snapshot as color_snapshot
from app.plugin_profiles import profile
URI='urn:machinista:instrument:synth'

class PluginPadSwitchTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  a=self.a=Application(self.tmp.name);a.control_level=2
  meta=profile(URI);a.plugin_catalog=[dict(uri=URI,name=meta['title'],kind='INSTRUMENT',supported=True,builtin=True,ports=meta['parameters'])]
  a.project['groups'][0]['pads'][0]['sample']='drum.wav'
  a.project['groups'][0]['pads'][1]['plugins']=[dict(uri=URI,kind='INSTRUMENT',controls={})]
 def test_sampler_to_instrument_shows_patch_names_on_all_full_size_surfaces(self):
  a=self.a
  for surface in (Mk1Surface,Mk2Surface,Mk3Surface,PlusSurface):
   with self.subTest(surface=surface):
    a.pad=0;a.page='SAMPLER';a.sampler_page=0;a.plugin_param=40
    inputs=ControllerInputs(a);s=surface(a,inputs);inputs.pad_on(s.source,1,100);inputs.pad_off(s.source,1)
    self.assertEqual(a.page,'PLUGIN');self.assertEqual(a.plugin_slot,0);self.assertEqual(a.plugin_param,0)
    state=color_snapshot(s) if surface in (Mk3Surface,PlusSurface) else snapshot(s)
    self.assertNotIn('sampler_values',state);self.assertIn('plugin_names',state)
 def test_instrument_to_sample_returns_to_sampler(self):
  a=self.a;a.pad=1;a.page='PLUGIN';a.plugin_param=24;a.select_sound(0)
  self.assertEqual(a.page,'SAMPLER');self.assertTrue(a.sampler_slot_present())
 def test_effect_only_and_empty_slots_do_not_inherit_sampler_engine(self):
  for effects in ([dict(uri='urn:effect',kind='EFFECT',controls={})],[]):
   a=self.a;a.pad=0;a.page='SAMPLER';a.project['groups'][0]['pads'][2]['plugins']=effects;a.select_sound(2)
   self.assertEqual(a.page,'PLUGIN');self.assertFalse(a.sampler_slot_present())
 def test_keyboard_performance_keeps_current_instrument_and_parameter_page(self):
  a=self.a;a.pad=1;a.page='PLUGIN';a.plugin_param=24;a.keyboard_enabled=True
  a.pad_on(4,100);a.release_pad(4)
  self.assertEqual(a.pad,1);self.assertEqual(a.plugin_param,24)
 def test_browse_sampling_editor_and_group_plugin_context_stay_open(self):
  a=self.a
  for page,scope in (('BROWSE',2),('SAMPLING',2),('SAMPLE EDIT',2),('PATTERN GRID',2),('PLUGIN',1)):
   a.pad=0;a.page=page;a.control_level=scope;a.select_sound(1)
   self.assertEqual(a.page,page)
 def test_same_pad_keeps_current_plugin_page(self):
  a=self.a;a.pad=1;a.page='PLUGIN';a.plugin_param=24;a.select_sound(1)
  self.assertEqual(a.plugin_param,24)
