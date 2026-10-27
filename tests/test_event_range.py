import copy,tempfile,unittest
from unittest.mock import Mock
from app.model import Application
from app.mk3_surface import Mk3Surface
from app.controller_inputs import ControllerInputs
from app.mk3_state import event_state
from app.mk3_display import Mk3Renderer
from app.mk3_graphics import ACCENT,INK

class EventRangeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.a=Application(self.tmp.name);self.s=Mk3Surface(self.a,ControllerInputs(self.a));self.a.page='PATTERN GRID';self.a.grid_notes=False
  for pad,tick,note in ((0,0,60),(0,24,64),(1,24,36),(15,48,42),(0,96,67)):
   self.a.put_note(pad,tick,dict(note=note,length=24,velocity=90,probability=100))
 def test_hold_select_encoder_grows_shrinks_and_release_keeps_selection(self):
  a=self.a;before=copy.deepcopy(a.project);self.s.button('SELECT',True)
  self.assertEqual(a.page,'PATTERN GRID');self.assertFalse(a.grid_follow)
  self.s.rotate(0,2);self.assertEqual(a.grid_selection_range,(0,72));self.assertEqual(len(a.grid_selected),2)
  self.assertTrue(all(k[0]==a.pad for k in a.grid_selected))
  self.assertEqual(event_state(a)['selection_range'],(0,72))
  self.s.rotate(0,-2);self.assertEqual(a.grid_selection_range,(0,24));self.assertEqual(len(a.grid_selected),1)
  selected=set(a.grid_selected);self.s.button('SELECT',False)
  self.assertIsNone(a.grid_selection_range);self.assertEqual(a.grid_selected,selected);self.assertEqual(a.project,before)
 def test_reverse_range_and_melodic_scope_includes_different_pitches(self):
  a=self.a;a.grid_step=2;a.grid_notes=True;a.pad=0
  self.s.button('SELECT',True);self.s.rotate(0,-2)
  self.assertEqual(a.grid_selection_range,(0,72));self.assertEqual(len(a.grid_selected),2)
  self.assertTrue(all(k[0]==0 for k in a.grid_selected));self.s.button('SELECT',False)
 def test_notes_crossing_range_boundary_are_included_and_edit_page_does_not_edit(self):
  a=self.a;a.put_note(0,0,dict(note=60,length=96,velocity=90,probability=100));a.page='GRID EDIT';a.grid_step=1
  before=copy.deepcopy(a.project);self.s.button('SELECT',True);self.s.rotate(0,1)
  self.assertIn(next(k for k in a.event_notes() if k[:2]==(0,0)),a.grid_selected)
  self.assertEqual(a.project,before);self.s.button('SELECT',False)
 def test_select_still_opens_normal_select_mode_outside_editor(self):
  a=self.a;a.page='PAD';self.s.button('SELECT',True);self.assertEqual(a.page,'SELECT')
  self.s.button('SELECT',False);self.assertEqual(a.page,'PAD')
 def test_all_selected_notes_get_an_outline(self):
  a=self.a;a.grid_selected={k for k in a.event_notes() if k[0] in (0,1)};a.grid_step=12
  r=Mk3Renderer();self.addCleanup(r.close);r.accent=ACCENT;p=Mock();q=Mock();state=event_state(a)
  r.events(p,q,state)
  borders=[c for c in p.rect.call_args_list if len(c.args)==7 and c.args[4] is None and c.args[5]==INK and c.args[6]==2]
  self.assertEqual(len(borders),sum(e[3] or e[4] for e in state['notes']))
  self.assertGreaterEqual(len(borders),3)

 def test_display_select_hold_position_and_event_encoders_select_without_editing(self):
  for encoder in (0,1,5):
   with self.subTest(encoder=encoder):
    a=self.a;a.grid_step=0;a.grid_selected.clear();before=copy.deepcopy(a.project)
    self.s.button('DISPLAY 1',True)
    self.assertEqual(event_state(a)['selection_range'],(0,24))
    self.s.rotate(encoder,2)
    self.assertEqual(a.grid_selection_range,(0,72));self.assertEqual(len(a.grid_selected),2)
    self.s.button('DISPLAY 1',False)
    self.assertIsNone(a.grid_selection_range);self.assertEqual(len(a.grid_selected),2)
    self.assertEqual(a.project,before)
 def test_display_select_tap_still_toggles_current_note(self):
  for expected in (True,False):
   self.s.button('DISPLAY 1',True);self.s.button('DISPLAY 1',False)
   self.assertEqual(bool(self.a.grid_selected),expected)
 def test_physical_select_position_encoder_and_disconnect(self):
  a=self.a;before=copy.deepcopy(a.project);self.s.button('SELECT',True);self.s.rotate(5,2)
  self.assertEqual(len(a.grid_selected),2);self.assertEqual(a.project,before)
  self.s.disconnect();self.assertIsNone(a.grid_range_anchor);self.assertIsNone(a.grid_selection_range)
  self.s.button('DISPLAY 1',True);self.s.rotate(1,1);self.s.disconnect()
  self.assertIsNone(a.grid_range_anchor);self.assertNotIn('EVENT RANGE SELECT',a.held_buttons)

 def test_drum_range_reanchors_when_selected_pad_changes(self):
  a=self.a;self.s.button('SELECT',True);self.s.rotate(0,2)
  a.pad=1;self.s.rotate(0,-2)
  self.assertTrue(a.grid_selected)
  self.assertTrue(all(k[0]==1 for k in a.grid_selected))
  self.s.button('SELECT',False)
