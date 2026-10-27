import struct,tempfile,unittest
from pathlib import Path
from app.mk3_protocol import Decoder,display_packet,led_reports,PAD_SLOTS
from app.mk3_graphics import Canvas,rgb565
from app.mk3_surface import Mk3Surface
from app.mk3_display import Mk3Renderer
from app.mk2_display import snapshot
from app.model import Application
from app.controller_inputs import ControllerInputs

class ProtocolTests(unittest.TestCase):
 def test_rgb_and_frames(self):
  c=Canvas();c.image.paste((255,0,0),(0,0,480,272));self.assertEqual(c.wire()[:2],b'\xf8\x00')
  c.image.paste((0,255,0),(0,0,480,272));self.assertEqual(c.wire()[:2],b'\x07\xe0')
  c.image.paste((0,0,255),(0,0,480,272));self.assertEqual(c.wire()[:2],b'\x00\x1f')
  self.assertEqual(c.wire(True)[:2],b'\xff\xe0')
  packet=display_packet(c.wire(),1);self.assertEqual(len(packet),261148);self.assertEqual(packet[2],1)
  with self.assertRaises(ValueError):display_packet(b'',0)
  self.assertEqual(tuple(map(len,led_reports([0]*103))),(63,42))
 def test_free_running_counter_does_not_make_events_and_wraps(self):
  d=Decoder();data=bytearray(42);data[0]=1;struct.pack_into('<8H',data,12,*([999]*8));d.decode(data)
  struct.pack_into('<8H',data,12,*([0]*8));struct.pack_into('<H',data,28,100)
  events=d.decode(data);self.assertEqual([e['value'] for e in events],[1]*8)
  struct.pack_into('<H',data,28,200);self.assertEqual(d.decode(data),[])
 def test_pad_order_retrigger_and_release(self):
  d=Decoder()
  def report(raw,kind,value):return bytes((2,raw,kind|(value>>8),value&255))+bytes(60)
  for raw,slot in enumerate(PAD_SLOTS):
   self.assertEqual(d.decode(report(raw,0x40,2000)),[])
   on=d.decode(report(raw,0x10,1000));self.assertEqual(on[0]['name'],f'PAD_{slot+1}')
   self.assertEqual([e['kind'] for e in d.decode(report(raw,0x10,2000))],['pad_off','pad_on'])
   self.assertEqual(d.decode(report(raw,0x30,0))[0]['kind'],'pad_off')
   self.assertEqual(d.decode(report(raw,0x20,0)),[])

class SurfaceTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.a=Application(self.tmp.name);self.inputs=ControllerInputs(self.a);self.s=Mk3Surface(self.a,self.inputs)
 def press(self,name):self.s.button(name,True);self.s.button(name,False)
 def test_dedicated_modes_and_settings_are_per_device(self):
  self.press('KEYBOARD');self.assertTrue(self.a.keyboard_enabled)
  self.press('KEYBOARD');self.assertFalse(self.a.keyboard_enabled)
  self.press('EVENTS');self.assertEqual(self.a.page,'PATTERN GRID')
  self.press('FOLLOW');self.assertFalse(self.a.grid_follow)
  self.press('SETTINGS');self.assertEqual(self.a.page,'SETTINGS')
  self.press('SETTINGS');self.assertNotEqual(self.a.page,'SETTINGS')
  self.assertIn('mk3',self.a.settings['controllers'])
 def test_strip_release_centres_pitch_and_releases_note(self):
  self.s.strip_mode='PITCH';self.s.strip(1024);self.s.strip(0)
  self.assertEqual(self.a.actions[-1],('controller_midi',(0xe0,(0,64))))
  self.s.strip_mode='NOTES';self.s.strip(1);self.assertTrue(self.inputs.pads)
  self.s.strip(0);self.assertFalse(self.inputs.pads)
 def test_native_views_and_eight_bindings(self):
  renderer=Mk3Renderer();self.addCleanup(renderer.close)
  for page in ('CHANNEL','INPUT','SAMPLER','PLUGIN','PLUGIN BROWSE','SAMPLING','SAMPLE EDIT','CHOP','ZONE','STRETCH','MIXER','STEP','PATTERN','SCENE','PAD CONFIG','PATTERN GRID','SETTINGS','SYSTEM','PROJECT','LIVE FX'):
   with self.subTest(page=page):
    self.a.page=page;state=snapshot(self.s);self.assertEqual(len(state['fields']),8)
    self.assertEqual(tuple(map(len,renderer(state))),(261120,261120))
 def test_lock_restores_parameters_without_overwriting_notes_or_slots(self):
  a=self.a;a.track()['gain']=75
  self.press('LOCK');a.track()['gain']=30;a.put_note(0,24,dict(velocity=100,note=36))
  self.press('LOCK');self.assertEqual(a.track()['gain'],75);self.assertIn((0,24),a.notes())
 def test_variation_navigate_release_and_view_binding(self):
  self.press('CHANNEL');self.s.button('VARIATION',True)
  self.assertEqual(self.a.page,'VIEW NAV')
  self.s.button('VARIATION',False)
  self.assertNotIn('VIEW',self.inputs.buttons)
 def test_shared_session_optional_event_hook_preserves_keyboard_binding(self):
  from app.mk3_session import Mk3Session
  s=Mk3Session(self.tmp.name,self.a,self.inputs,{});self.addCleanup(s.close)
  self.assertTrue(s.handle_event(dict(kind='strip',value=0)))
  self.assertFalse(s.handle_event(dict(kind='button',name='PLAY',value=1)))

class VariationBindingsTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.a=Application(self.tmp.name);self.inputs=ControllerInputs(self.a);self.s=Mk3Surface(self.a,self.inputs)
 def test_shift_variation_opens_grid_and_release_keeps_owned_binding(self):
  self.s.button('SHIFT',True);self.s.button('VARIATION',True)
  self.assertEqual(self.a.page,'OPTIONS');self.assertTrue(self.a.shift)
  self.assertIn('GRID',self.inputs.buttons);self.assertNotIn('VIEW',self.inputs.buttons)
  self.s.button('SHIFT',False);self.s.button('VARIATION',False)
  self.assertNotIn('GRID',self.inputs.buttons);self.assertNotIn('GRID',self.a.held_buttons)
 def test_plain_navigation_stays_navigation_if_shift_pressed_afterwards(self):
  self.s.button('VARIATION',True);self.assertEqual(self.a.page,'VIEW NAV')
  self.s.softkey(3);self.s.button('SHIFT',True);self.s.button('VARIATION',False)
  self.assertEqual(self.a.page,'MIXER');self.assertTrue(self.a.shift)
  self.assertNotIn('VIEW',self.inputs.buttons);self.s.button('SHIFT',False)
