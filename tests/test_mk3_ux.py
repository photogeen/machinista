import copy,random,struct,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
from app.mk3_regions import regions
from app.mk3_protocol import display_packet,LED_NAMES
from app.mk3_display import Mk3Renderer
from app.mk3_state import snapshot
from app.mk3_surface import Mk3Surface
from app.model import Application
from app.controller_inputs import ControllerInputs

class RegionsTests(unittest.TestCase):
 def apply(self,old,new):
  result=bytearray(old)
  rectangles=regions(old,new)
  for x,y,w,h,data in rectangles:
   self.assertEqual(len(data),w*h*2);self.assertEqual(w%2,0)
   self.assertTrue(display_packet(data,0,x,y,w,h))
   for row in range(h):result[(y+row)*960+x*2:(y+row)*960+(x+w)*2]=data[row*w*2:(row+1)*w*2]
  self.assertEqual(bytes(result),new)
  return rectangles
 def test_arbitrary_changes_roundtrip_and_unchanged_no_packets(self):
  rng=random.Random(29);old=bytes(261120);new=bytearray(old)
  for _ in range(600):i=rng.randrange(261120);new[i]=rng.randrange(256)
  self.apply(old,bytes(new));self.assertEqual(regions(old,old),[])
 def test_moving_playhead_uses_narrow_rectangle_not_full_strips(self):
  old=bytearray(261120);new=bytearray(old)
  for y in range(96,208):old[y*960+100*2:y*960+100*2+2]=b'\xff\xff';new[y*960+104*2:y*960+104*2+2]=b'\xff\xff'
  rects=self.apply(bytes(old),bytes(new));self.assertEqual(len(rects),1)
  self.assertLess(sum(len(r[4]) for r in rects),2000)
 def test_pixel_at_each_edge_is_preserved(self):
  old=bytes(261120);new=bytearray(old)
  for x,y in ((0,0),(479,0),(0,271),(479,271)):new[y*960+x*2:y*960+x*2+2]=b'\x01\x02'
  self.apply(old,bytes(new))

class Mk3UXTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.a=Application(self.tmp.name);self.inputs=ControllerInputs(self.a);self.s=Mk3Surface(self.a,self.inputs)
 def press(self,name):self.s.button(name,True);self.s.button(name,False)
 def test_slice_arrows_focus_end_start_without_changing_parameter_pages(self):
  a=self.a;a.page='CHOP';a.track().update(sample=None,start=0,end=16000,slices=[[0,8000],[8000,16000]])
  a.slice_mode='MANUAL';a.slice_index=1;self.s.slice_subpage=2;a.slice_edit=False
  self.press('PAGE RIGHT');self.assertTrue(a.slice_edit);self.assertTrue(a.slice_focus_end);self.assertEqual(self.s.slice_subpage,2)
  self.press('MASTER LEFT');self.assertFalse(a.slice_focus_end);self.assertEqual(a.slice_field,1)
  self.s.button('SHIFT',True);self.press('PAGE LEFT');self.s.button('SHIFT',False)
  self.assertFalse(a.slice_edit);self.assertEqual(self.s.slice_subpage,1)
 def test_4d_up_down_select_pitch_and_preserve_position_notes_and_sound(self):
  a=self.a;a.page='PATTERN GRID';a.grid_notes=True;a.grid_note=60;a.grid_step=3
  before=copy.deepcopy(a.project);self.press('MASTER UP');self.assertEqual((a.grid_note,a.grid_step,a.pad),(61,3,0));self.assertFalse(a.grid_follow)
  self.press('MASTER DOWN');self.assertEqual(a.grid_note,60);self.assertEqual(a.project,before)
  a.grid_notes=False;self.press('MASTER UP');self.assertEqual((a.pad,a.grid_step),(1,3))
 def test_cache_reuses_static_scene_but_updates_playhead_and_invalidates_note_edit(self):
  a=self.a;a.page='PATTERN GRID';a.grid_notes=True;a.grid_note=60;a.playing=True;a.active_clips[0]=True;a.active_patterns[0]=a.pattern
  a.put_note(0,0,dict(note=60,length=96,velocity=96,probability=100))
  r=Mk3Renderer();self.addCleanup(r.close);one=r(snapshot(self.s));count=r.scene_renders
  a.clock_phase=24;two=r(snapshot(self.s));self.assertEqual(r.scene_renders,count);self.assertNotEqual(one,two)
  a.put_note(0,24,dict(note=62,length=48,velocity=70,probability=100));r(snapshot(self.s));self.assertGreater(r.scene_renders,count)
 def test_all_sixteen_pad_cells_are_together_on_right(self):
  a=self.a;a.page='PATTERN';r=Mk3Renderer();self.addCleanup(r.close);left,right=r.draw(snapshot(self.s))
  # Last cell uses rightmost column; no second half is lost across displays.
  from app.mk3_graphics import BG
  from PIL import ImageColor
  self.assertNotEqual(right.getpixel((370,100)),ImageColor.getrgb(BG))
 def test_event_pad_rows_ascend_visually_and_up_matches_labels(self):
  from app.mk3_state import event_state
  from app.pattern_display import pattern_state
  a=self.a;a.page='PATTERN GRID';a.grid_notes=False;a.pad=0
  self.assertEqual([r[0] for r in event_state(a)['rows']],['08','07','06','05','04','03','02','01'])
  self.assertEqual([r[0] for r in pattern_state(a)['rows']],['05','04','03','02','01'])
  self.press('MASTER UP');self.assertEqual(a.pad,1)
  self.assertTrue(event_state(a)['rows'][-2][1])
  self.press('MASTER DOWN');self.assertEqual(a.pad,0)
  a.pad=15;self.assertEqual(event_state(a)['rows'][0],('16',True))
 def test_event_buttons_describe_edit_add_done_and_selection(self):
  a=self.a;a.page='PATTERN GRID';a.grid_notes=False;a.grid_step=0
  a.put_note(0,0,dict(note=36,length=24,velocity=90,probability=100))
  self.assertEqual(self.s.softkeys()[:2],('SELECT','EDIT'))
  self.s.softkey(0);state=snapshot(self.s)
  self.assertEqual(state['keys'][0],'SELECTED');self.assertIn(0,state['active_left'])
  self.s.softkey(1);self.assertEqual(a.page,'GRID EDIT')
  self.assertEqual(self.s.softkeys()[1],'DONE');self.assertIn(1,snapshot(self.s)['active_left'])
  self.s.softkey(1);self.assertEqual(a.page,'PATTERN GRID')
  self.s.softkey(0);self.assertEqual(self.s.softkeys()[0],'SELECT');self.assertNotIn(0,snapshot(self.s)['active_left'])
  a.grid_step=4;self.assertEqual(self.s.softkeys()[1],'ADD NOTE')
  before=len(a.event_notes());self.s.softkey(1)
  self.assertEqual(len(a.event_notes()),before+1);self.assertEqual(self.s.softkeys()[1],'DONE')
 def test_led_active_is_full_brightness_inactive_half_and_disabled_off(self):
  from app.mk3_session import Mk3Session
  session=Mk3Session(self.tmp.name,self.a,self.inputs,{})
  self.addCleanup(session.close);session.palette=[(0,0,0)]+[(127,64,0)]*16
  self.a.page='BROWSE';reports=session.reports(1);mono=reports[0][1:]
  self.assertEqual(mono[LED_NAMES.index('BROWSE')],127);self.assertEqual(mono[LED_NAMES.index('STEP')],48)
  self.assertEqual(mono[LED_NAMES.index('PAGE LEFT')],0)

class FullFrameFallbackTests(unittest.TestCase):
 def test_each_changed_frame_replaces_entire_display(self):
  from app.mk3_output import Mk3Output
  output=Mk3Output.__new__(Mk3Output)
  output.last={};output.closing=False;output.usb=Mock();output.usb_bytes=0;output.usb_packets=0
  old=bytes(480*272*2);new=bytearray(old);new[12345]=255;new=bytes(new)
  output.changed_frame(1,old);output.changed_frame(1,new);output.changed_frame(1,new)
  self.assertEqual(output.usb.send.call_count,2)
  for call,pixels in zip(output.usb.send.call_args_list,(old,new)):
   self.assertEqual(call.args[0],display_packet(pixels,1,compress=True))
   self.assertEqual(struct.unpack('>4H',call.args[0][8:16]),(0,0,480,272))

class DisplayCommandStreamTests(unittest.TestCase):
 def test_packet_contains_one_literal_then_blit_and_end(self):
  # Independently parse the documented stream, rather than comparing the
  # implementation with itself. No skip/cursor commands around pixel data.
  pixels=bytes(range(256))*(480*272*2//256)
  for display in (0,1):
   packet=display_packet(pixels,display)
   self.assertEqual(packet[:8],bytes((0x84,0,display,0x60,0,0,0,0)))
   self.assertEqual(struct.unpack('>4H',packet[8:16]),(0,0,480,272))
   command=int.from_bytes(packet[16:20],'big')
   self.assertEqual(command>>24,0)
   count=(command&0xffffff)*4
   self.assertEqual(count,len(pixels))
   self.assertEqual(packet[20:20+count],pixels)
   self.assertEqual(packet[20+count:],bytes.fromhex('0300000040000000'))

class NativeDisplayTests(unittest.TestCase):
 def decode(self,packet):
  pos=16;data=bytearray()
  while True:
   opcode=packet[pos];count=int.from_bytes(packet[pos+1:pos+4],'big');pos+=4
   if opcode==3:
    self.assertEqual(packet[pos:],bytes.fromhex('40000000'));break
   self.assertIn(opcode,(0,1));self.assertGreater(count,0)
   if opcode==0:data+=packet[pos:pos+4*count];pos+=4*count
   else:data+=packet[pos:pos+4]*count;pos+=4
  return bytes(data)
 def test_compressed_full_frames_roundtrip_no_skip_and_fallback(self):
  from app import mk3_pixels
  rng=random.Random(71)
  frames=[bytes(261120),bytes([255])*261120,bytes(rng.randrange(256) for _ in range(261120))]
  frames.append(b''.join((b'\x12\x34\x56\x78'*80,frames[2][:800]))*192)
  for raw in frames:
   if len(raw)!=261120:raw=(raw+frames[2])[:261120]
   self.assertEqual(self.decode(display_packet(raw,0,compress=True)),raw)
  with patch.object(mk3_pixels,'lib',None):
   self.assertEqual(display_packet(frames[0],0,compress=True),display_packet(frames[0],0))
 def test_native_pack_matches_reference_and_inversion(self):
  from PIL import Image
  from app import mk3_pixels
  from app.mk3_graphics import rgb565
  rng=random.Random(21);rgb=bytes(rng.randrange(256) for _ in range(480*272*3));im=Image.frombytes('RGB',(480,272),rgb)
  for invert in (False,True):
   accelerated=rgb565(im,invert)
   with patch.object(mk3_pixels,'lib',None):self.assertEqual(accelerated,rgb565(im,invert))
 def test_cached_text_matches_direct_drawing(self):
  from app.mk3_graphics import Canvas,font
  from PIL import ImageDraw,ImageChops
  a=Canvas();b=Canvas()
  for y,text in enumerate(['Machinista','Cutoff 25%','C#3','Rhodes Z','Überblick']):
   a.text(20,y*35,text,18,True)
   ImageDraw.Draw(b.image).text((20,y*35),text,font=font(18,True),fill='#f1f4f7')
  self.assertIsNone(ImageChops.difference(a.image,b.image).getbbox())
