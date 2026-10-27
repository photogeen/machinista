import tempfile,unittest
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.mk1_session import Mk1Surface
from app.mk2_surface import Mk2Surface
from app.mk2_display import snapshot,Mk2Renderer

class Mk1SurfaceTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.a=Application(self.temp.name);self.inputs=ControllerInputs(self.a);self.s=Mk1Surface(self.a,self.inputs)
 def test_device_settings_are_independent(self):
  a=self.a;old=dict(a.settings['controllers']['mk2']);micro=a.settings['display_contrast']
  a.page='CONTRAST R';self.s.rotate(4,3)
  self.assertEqual(a.settings['controllers']['mk1']['contrast_right'],32)
  self.assertEqual(a.settings['controllers']['mk2'],old);self.assertEqual(a.settings['display_contrast'],micro)
  self.assertIn(('controller_display_settings','mk1'),a.actions)
  self.assertEqual(snapshot(self.s)['hardware']['contrast_right'],32)
 def test_button_ownership_does_not_release_other_controller(self):
  other=Mk2Surface(self.a,self.inputs)
  other.button('SHIFT',True);self.s.button('SHIFT',True);self.s.button('SHIFT',False)
  self.assertTrue(self.a.shift);other.button('SHIFT',False);self.assertFalse(self.a.shift)
 def test_dedicated_master_controls_and_held_pad_scope(self):
  a=self.a;a.page='PAD';tempo=a.project['tempo'];self.s.rotate(11,1)
  self.assertGreater(a.project['tempo'],tempo)
  self.assertEqual(a.page,'PAD')
  gain=a.project.get('gain',100);self.s.rotate(9,-1);self.assertLess(a.project['gain'],gain)
  self.s.button('CONTROL',True);self.s.button('CONTROL',False)
  self.assertIsNone(self.s.master_mode)
 def test_render_uses_all_dual_screen_layouts(self):
  renderer=Mk2Renderer();self.addCleanup(renderer.close)
  for page in ('PAD','SAMPLER','BROWSE','SAMPLING','SAMPLE EDIT','CHOP','ZONE','STEP','MIXER','SETTINGS','SYSTEM'):
   self.a.page=page
   with self.subTest(page=page):
    left,right=renderer(snapshot(self.s));self.assertEqual(len(left),16384);self.assertEqual(len(right),16384)
 def test_all_engine_screens_keep_encoder_bindings_and_fit_mk1(self):
  from tests.test_fokus_v2 import fixture
  from tools.audit.fokus_fein_cases import cases,apply
  from app.mk1_protocol import pack_frame
  renderer=Mk2Renderer();self.addCleanup(renderer.close);count=0
  for label,page,values in cases():
   with self.subTest(screen=label):
    a=fixture(self.temp.name);a.track()['sampler']={'type':'ADSR','filter':'EQ'}
    surface=Mk1Surface(a,ControllerInputs(a));apply(a,surface,page,values)
    state=snapshot(surface)
    for pixels in renderer(state):
     self.assertFalse(any(pixels[y*256+255] for y in range(64)))
     native=bytearray(v for y in range(64) for v in pixels[y*256:y*256+255])
     self.assertEqual(len(pack_frame(native)),10880)
    count+=1
  self.assertGreater(count,200)
 def test_sensitivity_is_source_local(self):
  a=self.a;a.settings['controllers']['mk1']['pad_sensitivity']=50;a.settings['controllers']['mk2']['pad_sensitivity']=150
  self.assertLess(a.pad_velocity(1000,'mk1'),a.pad_velocity(1000,'mk2'))
 def test_settings_open_back_and_device_local_edit_without_enter(self):
  a=self.a;self.s.button('SHIFT',True);self.s.button('CONTROL',True);self.s.button('CONTROL',False);self.s.button('SHIFT',False)
  self.assertEqual(a.page,'SETTINGS');self.assertEqual(self.s.softkeys()[7],'OPEN')
  self.s.softkey(2) # System
  self.assertEqual(a.settings_folder,'SYSTEM')
  self.s.softkey(7) # Display folder
  self.assertEqual(a.settings_section,'DISPLAY')
  self.s.rotate(1,1);self.s.softkey(7) # Contrast
  self.assertIn(a.page,('CONTRAST','CONTRAST L'))
  old=dict(a.settings['controllers']['mk2']);self.s.rotate(3,1)
  self.assertEqual(a.settings['controllers']['mk2'],old)
  self.s.softkey(0);self.assertEqual(a.page,'SETTINGS')
 def test_confirm_key_has_no_shift_tap_tempo_side_effect(self):
  self.a.page='SETTINGS';self.a.settings_folder='SYSTEM';self.a.menu=0
  self.s.button('SHIFT',True);self.s.softkey(7)
  self.assertEqual(self.a.settings_section,'DISPLAY');self.assertFalse(self.a.taps)
  self.assertTrue(self.a.shift);self.s.button('SHIFT',False)
 def test_mk2_bindings_and_sampling_actions_are_preserved(self):
  a=self.a;a.page='SETTINGS'
  self.assertEqual(Mk2Surface(a,self.inputs).softkeys()[7],'')
  for page in ('SAMPLING','SAMPLE EDIT','CHOP','ZONE','SLICE TARGET','AUTOSAMPLER','PAD CONFIG','PATTERN GRID','MIXER','BROWSE'):
   a.page=page
   self.assertEqual(self.s.softkeys(),Mk2Surface(a,self.inputs).softkeys())
 def test_missing_sample_browse_and_delete_offer_real_selector(self):
  a=self.a;a.page='RELINK BROWSE';a.open_relink_browser()
  self.assertEqual(self.s.fields()[0].label,'SELECT');self.assertEqual(self.s.softkeys()[7],'OPEN')
  a.page='SAMPLE DELETE';a.sample_delete_index=0;a.sample_delete_origin='SAMPLE EDIT'
  self.s.rotate(1,1);self.assertEqual(a.sample_delete_index,1)
  self.s.softkey(7);self.assertEqual(a.page,'CONFIRM')
 def test_plugin_browser_confirmation_and_sidechain_use_softkeys(self):
  a=self.a;a.page='PLUGIN BROWSE';a.plugin_browser_index=0
  self.assertEqual(self.s.softkeys()[7],'LOAD')
  a.plugin_browser_index=-1;self.assertEqual(self.s.softkeys()[7],'REMOVE')
  a.page='PLUGIN';a.track()['plugins']=[{'uri':'urn:test','controls':{}}]
  a.plugin_catalog=[{'uri':'urn:test','sidechain':True}]
  self.s.button('SHIFT',True);self.assertEqual(self.s.softkeys()[7],'SC INPUT')
  self.s.softkey(7);self.assertEqual(a.page,'PLUGIN SC')
  self.s.button('SHIFT',False);self.s.softkey(7);self.assertEqual(a.page,'PLUGIN')
if __name__=='__main__':unittest.main()
