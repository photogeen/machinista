import copy
from pathlib import Path
import tempfile
import unittest
from app.model import Application
from app.storage import save_json
from app.controller_inputs import ControllerInputs
from app.mk2_surface import Mk2Surface
from app.mk2_display import snapshot,Mk2Renderer
from app.control_display import control_state
from app.ni_display import frame
from app.group_delete import blank_group,group_used

class KeyboardNoteDisplayTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.a=Application(self.temp.name);self.a.page='PAD CONFIG';self.a.keyboard_enabled=True
  self.s=Mk2Surface(self.a,ControllerInputs(self.a))
 def test_new_project_starts_on_c3_and_labels_both_surfaces(self):
  a=self.a
  self.assertEqual(a.keyboard_root,60);self.assertEqual(a.performance_notes(0),[60]);self.assertEqual(a.performance_notes(12),[72])
  self.assertEqual(self.s.fields()[0].value,'C3');self.assertEqual(control_state(a)['value'],'C3')
  self.s.rotate(1,1);self.assertEqual(self.s.fields()[0].value,'C#3');self.assertEqual(a.performance_notes(0),[61])
  self.assertEqual(control_state(a)['value'],'C#3');self.assertEqual(len(frame(a)),8192)
  renderer=Mk2Renderer();self.addCleanup(renderer.close);renderer(snapshot(self.s))
 def test_saved_roots_and_slice_note_zero_are_preserved(self):
  a=self.a
  for root in (0,24,36,48,72):
   a.performance()['root']=root;a.init_performance()
   self.assertEqual(a.keyboard_root,root);self.assertEqual(a.performance_notes(0),[root])
   save_json(a.project_path,a.project);loaded=Application(self.temp.name)
   self.assertEqual(loaded.keyboard_root,root)
 def test_partial_legacy_defaults_fill_only_missing_values(self):
  a=self.a;a.project['groups'][0]['performance']={'scale':'MINOR'};a.init_performance()
  self.assertEqual(a.keyboard_root,60);self.assertEqual(a.performance()['scale'],'MINOR')
  a.ensure_group_bank(1);self.assertEqual(a.project['groups'][8]['performance']['root'],60)
  self.assertEqual(blank_group()['performance']['root'],60);self.assertFalse(group_used(blank_group()))
 def test_custom_chord_note_editors_show_notes_not_midi_numbers(self):
  a=self.a
  a.performance().update(chord_mode='CUSTOM',root=60,custom={'name':'Test','root':60,'chords':[{'input':60,'notes':[60,64,67]}]})
  self.s.pad_page=2
  fields=self.s.fields();self.assertEqual(fields[1].value,'C3');self.assertEqual(fields[2].value,'C3')
  a.pad_field=12;self.assertEqual(control_state(a)['value'],'C3')
  a.pad_field=13;self.assertEqual(control_state(a)['value'],'C3')
