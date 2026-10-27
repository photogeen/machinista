"""Maschine+ ownership, sensitivity, display and USB interface isolation."""
import tempfile,unittest
from unittest.mock import patch
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.controller_settings import controller_context
from app.plus_session import PlusSurface,PlusSession
from app.mk3_surface import Mk3Surface
from app.mk3_session import Mk3Session
from app.mk3_state import snapshot
from app.mk3_display import Mk3Renderer
from app.mk3_protocol import open_device
from app.mk3_usb import DisplayUSB

class PlusControllerTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.a=Application(self.tmp.name);self.inputs=ControllerInputs(self.a)
  self.plus=PlusSurface(self.a,self.inputs);self.mk3=Mk3Surface(self.a,self.inputs)
 def test_settings_and_normalized_velocity_are_independent(self):
  a=self.a;a.page='PAD SENS';self.plus.rotate(2,30)
  self.assertEqual(a.settings['controllers']['plus']['pad_sensitivity'],130)
  self.assertEqual(a.settings['controllers']['mk3']['pad_sensitivity'],100)
  self.assertEqual([a.pad_velocity(v,'plus') for v in range(1,128)],list(range(1,128)))
  a.page='BRIGHTNESS';self.plus.rotate(1,-15)
  self.assertEqual(a.settings['controllers']['plus']['brightness'],85)
  self.assertIsNone(a.settings['controllers']['mk3']['brightness'])
  self.assertIn(('controller_display_settings','plus'),a.actions)
 def test_buttons_and_pad_release_belong_to_their_device(self):
  self.inputs.pad_on('plus',0,90);self.inputs.pad_on('mk3',0,90)
  self.plus.disconnect();self.assertNotIn(('plus',0),self.inputs.pads)
  self.assertIn(('mk3',0),self.inputs.pads)
  self.plus.button('KEYBOARD',True);self.plus.button('KEYBOARD',False)
  self.assertTrue(self.a.keyboard_enabled)
 def test_color_renderer_supports_plus_and_keeps_eight_encoders(self):
  r=Mk3Renderer();self.addCleanup(r.close)
  for page in ('CHANNEL','PLUGIN','SAMPLING','CHOP','MIXER','PAD CONFIG','PATTERN GRID','LIVE FX'):
   self.a.page=page;state=snapshot(self.plus)
   self.assertEqual(state['controller'],'plus');self.assertEqual(len(state['fields']),8)
   self.assertEqual([im.size for im in r.images(state)],[(480,272)]*2)
 def test_usb_ids_and_interfaces_do_not_overlap(self):
  self.assertEqual((PlusSession.product,PlusSession.display_interface),(0x1820,6))
  self.assertEqual((Mk3Session.product,Mk3Session.display_interface),(0x1600,5))
  with patch('app.mk3_protocol.Path.read_text',return_value='HID_ID=0003:000017CC:00001820'),patch('app.mk3_protocol.os.open',return_value=99) as opened:
   with self.assertRaises(ValueError):open_device('/dev/hidraw1')
   opened.assert_not_called();self.assertEqual(open_device('/dev/hidraw1',product=0x1820),99)
  with self.assertRaises(ValueError):DisplayUSB(0x1820,5)
  with self.assertRaises(ValueError):DisplayUSB(0x1600,6)
