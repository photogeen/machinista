import unittest
from unittest.mock import patch
from app.mk2_protocol import ButtonsDecoder,display_reports,led_reports,send

class Mk2ProtocolTests(unittest.TestCase):
 def report(self,buttons=0,master=0,knob=0):
  return bytes([1])+buttons.to_bytes(7,'little')+bytes([master])+knob.to_bytes(2,'little')+bytes(14)
 def test_edges_and_counter_wrap(self):
  d=ButtonsDecoder();self.assertEqual(d.decode(self.report(master=15,knob=999)),[])
  e=d.decode(self.report((1<<39)|(1<<7),0,0))
  self.assertIn(('button','SHIFT',True),e);self.assertIn(('button','DISPLAY 8',True),e)
  self.assertIn(('encoder',0,1),e);self.assertIn(('encoder',1,1),e)
  self.assertEqual(len(d.decode(self.report())),2)
 def test_invalid_reports_do_not_mutate_baseline(self):
  d=ButtonsDecoder();d.decode(self.report(master=1));self.assertEqual(d.decode(self.report(master=16)),[])
  self.assertIn(('encoder',0,1),d.decode(self.report(master=2)))
 def test_rgb_and_transport_offsets_and_descriptor_lengths(self):
  mono,groups,pads=led_reports({'PLAY':45,'DISPLAY 8':20},{0:(12,23,34)},{'H':(1,2,3)})
  self.assertEqual(tuple(map(len,(mono,groups,pads))),(32,57,49))
  self.assertEqual(mono[16],20);self.assertEqual(groups[53],45)
  self.assertEqual(groups[43:49],bytes((1,2,3))*2)
  self.assertEqual(pads[37:40],bytes((12,23,34)))
 def test_two_displays_row_bit_order(self):
  p=bytearray(256*64);p[0]=p[-1]=1
  left=display_reports(p,0);right=display_reports(p,1)
  self.assertEqual(len(left),8);self.assertTrue(all(len(r)==265 for r in left+right))
  self.assertEqual(left[0][9],128);self.assertEqual(left[-1][-1],1)
  self.assertEqual(right[0][0],0xe1)
  with patch('app.mk2_protocol.os.write',return_value=265):send(4,left[0])
  with self.assertRaises(ValueError):send(4,bytes([0x80])*61)
