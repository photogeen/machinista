import tempfile,unittest
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.mk3_surface import Mk3Surface
from app.mk3_session import Mk3Session
from app.mk3_protocol import LED_NAMES

class Mk3TapTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.a=Application(self.tmp.name);self.inputs=ControllerInputs(self.a);self.s=Mk3Surface(self.a,self.inputs)
 def press(self,name):self.s.button(name,True);self.s.button(name,False)
 def test_shift_tap_toggles_globally_without_touching_tempo_taps_or_transport(self):
  for page in ('PAD','PLUGIN','SAMPLING','BROWSE','SETTINGS','PATTERN GRID'):
   self.a.page=page;self.a.timing()['metro']=False;self.a.playing=True;self.a.recording=True
   self.s.button('SHIFT',True);self.press('TAP')
   self.assertTrue(self.a.timing()['metro']);self.assertEqual(self.a.project['tempo'],120)
   self.assertEqual(self.a.taps,[]);self.assertTrue(self.a.playing);self.assertTrue(self.a.recording);self.assertEqual(self.a.page,page)
   self.press('TAP');self.assertFalse(self.a.timing()['metro']);self.s.button('SHIFT',False)
 def test_unshifted_tap_still_sets_tempo(self):
  self.a.input_timestamp=10;self.press('TAP');self.a.input_timestamp=10.5;self.press('TAP')
  self.assertEqual(self.a.project['tempo'],120);self.assertEqual(self.a.taps,[10,10.5]);self.assertFalse(self.a.timing()['metro'])
 def test_repeated_press_and_release_order_do_not_toggle_twice_or_leave_owners(self):
  self.s.button('SHIFT',True);self.s.button('TAP',True);self.s.button('TAP',True)
  self.assertTrue(self.a.timing()['metro'])
  self.s.button('SHIFT',False);self.s.button('TAP',False)
  self.assertEqual(self.a.taps,[]);self.assertFalse(self.s.held);self.assertFalse(self.inputs.buttons.get('TAP'))
  self.a.input_timestamp=20;self.s.button('TAP',True);self.s.button('SHIFT',True);self.s.button('TAP',False);self.s.button('SHIFT',False)
  self.assertTrue(self.a.timing()['metro']);self.assertEqual(self.a.taps,[20]);self.assertFalse(self.inputs.buttons.get('TAP'))
 def test_shift_led_and_mk3_manual_wording(self):
  session=Mk3Session(self.tmp.name,self.a,self.inputs,{});self.addCleanup(session.close)
  session.surface=self.s;session.palette=[(0,0,0),(127,64,0),(0,127,0),(127,0,0)];self.s.button('SHIFT',True)
  def tap_led():return session.reports(1)[0][1+LED_NAMES.index('TAP')]
  self.a.timing()['metro']=False;off=tap_led();self.a.timing()['metro']=True;self.assertGreater(tap_led(),off)
  self.s.button('SHIFT',False)
  from tools.manual_current import mk3_text
  self.assertEqual(mk3_text('SHIFT + PLAY: Metronom umschalten.'),'SHIFT + TAP: Metronom umschalten.')

 def test_shift_follow_opens_grid_and_keeps_follow_state(self):
  for page in ('PAD','PATTERN GRID','SAMPLING'):
   self.a.page=page;self.a.follow=True;self.a.grid_follow=False
   self.s.button('SHIFT',True);self.s.button('FOLLOW',True)
   self.assertEqual(self.a.page,'OPTIONS');self.assertTrue(self.a.shift)
   self.assertIn('GRID',self.inputs.buttons);self.assertTrue(self.a.follow);self.assertFalse(self.a.grid_follow)
   self.s.button('SHIFT',False);self.s.button('FOLLOW',False)
   self.assertNotIn('GRID',self.a.held_buttons);self.assertFalse(self.inputs.buttons.get('GRID'));self.assertFalse(self.s.follow_grid)
 def test_plain_follow_stays_follow_even_if_shift_changes_while_held(self):
  self.a.page='PATTERN GRID';self.a.grid_follow=True
  self.s.button('FOLLOW',True);self.assertFalse(self.a.grid_follow)
  self.s.button('SHIFT',True);self.s.button('FOLLOW',True);self.assertEqual(self.a.page,'PATTERN GRID')
  self.s.button('FOLLOW',False);self.s.button('SHIFT',False)
  self.assertFalse(self.s.held);self.assertFalse(self.inputs.buttons.get('GRID'))
 def test_mk3_grid_manual_shortcut(self):
  from tools.manual_current import mk3_text
  self.assertEqual(mk3_text('Press GRID / SHIFT + GRID'),'Press SHIFT + FOLLOW / SHIFT + FOLLOW')

 def test_grid_opens_resolution_and_record_quantize_on_encoder_five(self):
  self.a.grid_tab=0;self.a.timing()['grid_on']=True;self.a.timing()['record_quantize']=True
  self.s.button('SHIFT',True);self.s.button('FOLLOW',True)
  self.assertEqual(self.a.grid_tab,2);self.assertEqual(self.s.softkeys()[2],'GRID')
  self.assertEqual(self.s.fields()[4].label,'REC QUANT');self.assertEqual(self.s.fields()[4].value,'ON')
  original=self.a.timing()['grid']
  self.s.rotate(5,-1);self.assertFalse(self.a.timing()['record_quantize']);self.assertTrue(self.a.timing()['grid_on']);self.assertEqual(self.a.timing()['grid'],original)
  self.s.rotate(5,1);self.assertTrue(self.a.timing()['record_quantize'])
  self.s.button('FOLLOW',False);self.s.button('SHIFT',False)
 def test_record_quantize_control_is_shared_and_step_button_keeps_sequencer(self):
  from app.mk2_surface import Mk2Surface
  self.a.page='OPTIONS';self.a.grid_tab=2
  other=Mk2Surface(self.a,self.inputs)
  self.assertEqual(other.softkeys()[2],'GRID');self.assertIsNotNone(other.fields()[4])
  self.assertEqual(self.s.softkeys()[2],'GRID');self.assertIsNotNone(self.s.fields()[4])
  self.a.page='PAD';self.press('STEP');self.assertEqual(self.a.page,'STEP')
