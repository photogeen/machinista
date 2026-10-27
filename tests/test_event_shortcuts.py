import copy
from pathlib import Path
import tempfile
import unittest
from app.model import Application,validate_project
from app.leds import led_report,OFF,FULL
from tools.mikro_leds import load_pad_channels
from app.automation import lane_key

class EventShortcutTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.a=Application(self.temp.name)
        for row,tick,note in ((0,0,36),(1,31,40),(1,72,42),(2,120,48)):
            self.a.put_note(row,tick,dict(note=note,velocity=87,probability=80,length=12))
    def tearDown(self):self.temp.cleanup()
    def shortcut(self,pad):
        self.a.button('SHIFT',True);self.a.pad_on(pad-1);self.a.release_pad(pad-1);self.a.button('SHIFT',False)
    def select(self,pad):
        a=self.a;a.button('SHIFT',True);a.button('SELECT',True);a.pad_on(pad-1);a.release_pad(pad-1);a.button('SELECT',False);a.button('SHIFT',False)
    def test_clear_only_selected_sound_events_and_undo_preserves_other_sounds(self):
        a=self.a;a.pad=1;before=copy.deepcopy(a.notes());self.select(2);self.assertEqual(a.grid_selected,{(1,31),(1,72)})
        self.shortcut(9);self.assertEqual(set(a.notes()),{(0,0),(2,120)})
        self.shortcut(1);self.assertEqual(a.notes(),before);self.shortcut(2);self.assertEqual(set(a.notes()),{(0,0),(2,120)})
    def test_clear_without_selection_affects_current_pattern_only_and_preserves_sample(self):
        a=self.a;a.track()['sample']='keep.wav';a.track()['end']=100;a.put_note(0,0,dict(velocity=90,probability=100),pattern=1)
        self.shortcut(9);self.assertEqual(set(a.notes()),{(1,31),(1,72),(2,120)});self.assertTrue(a.notes(pattern=1));self.assertEqual(a.track()['sample'],'keep.wav')
    def test_keyboard_clear_removes_all_pitches_of_focused_sound_only(self):
        a=self.a;a.keyboard_enabled=True;a.pad=1;a.keyboard_root=40
        self.select(1);self.assertEqual(a.grid_selected,{(1,31)})
        self.shortcut(9);self.assertNotIn((1,72),a.notes());self.assertNotIn((1,31),a.notes());self.assertIn((0,0),a.notes())
    def test_copy_paste_retargets_sound_and_retains_event_properties(self):
        a=self.a;a.pad=1;self.select(2);self.shortcut(11);a.pad=4;self.shortcut(12)
        for tick in (31,72):self.assertEqual(a.notes()[(4,tick)],a.notes()[(1,tick)])
        before=copy.deepcopy(a.project);self.shortcut(12);self.assertEqual(a.project,before);self.assertEqual(a.message,'TARGET OCCUPIED')
        validate_project(a.project)
    def test_copy_current_pad_without_selection_and_paste_after_playhead_moves(self):
        a=self.a;a.pad=1;a.grid_selected={(2,120)};a.grid_context=(a.group,a.pattern)
        self.shortcut(11);self.assertEqual(len(a.event_clipboard['notes']),2)
        a.pad_on(5);a.release_pad(5);self.assertEqual(a.pad,5);a.playing=True;a.clock_phase=240;self.shortcut(12)
        for tick in (31,72):self.assertEqual(a.notes()[(5,tick)],a.notes()[(1,tick)])
        self.assertNotIn((6,120),a.notes());self.assertIn((2,120),a.notes())
        self.shortcut(1);self.assertFalse(any(k[0]==5 for k in a.notes()))

    def test_clear_ignores_foreign_event_selection_and_copy_empty_discards_clip(self):
        a=self.a;a.pad=0;a.grid_selected={(1,31),(1,72)};a.grid_context=(a.group,a.pattern)
        self.shortcut(9);self.assertEqual(set(a.notes()),{(1,31),(1,72),(2,120)})
        a.pad=1;self.shortcut(11);a.pad=7;self.shortcut(11)
        self.assertIsNone(a.event_clipboard);a.pad=4;before=copy.deepcopy(a.project)
        self.shortcut(12);self.assertEqual(a.project,before);self.assertEqual(a.message,'COPY FIRST')

    def test_nudge_transpose_and_octaves_only_change_selection(self):
        a=self.a;self.select(2);self.shortcut(8)
        self.assertEqual(a.grid_selected,{(1,55),(1,96)})
        self.shortcut(14);self.assertEqual(a.notes()[(1,55)]['note'],41)
        self.shortcut(16);self.assertEqual(a.notes()[(1,55)]['note'],53)
        self.shortcut(15);self.shortcut(13);self.shortcut(7)
        self.assertEqual(a.notes()[(1,31)]['note'],40);self.assertEqual(a.notes()[(2,120)]['note'],48)
    def test_quantize_full_and_half_follow_selection(self):
        a=self.a;self.select(2);self.shortcut(6)
        self.assertIn((1,27),a.notes());self.assertIn((2,120),a.notes())
        self.shortcut(5);self.assertIn((1,24),a.notes());self.assertIn((1,72),a.notes())
    def test_clear_auto_is_scoped_to_focused_sound(self):
        a=self.a;lanes=a.project['groups'][0].setdefault('automation',{})
        for bus in (0,1):lanes[lane_key(0,(bus,'value',-1,'gain'))]={'base':80,'points':{'0':50}}
        self.shortcut(10)
        self.assertEqual(set(a.project['groups'][0]['automation']),{lane_key(0,(1,'value',-1,'gain'))})
    def test_reset_sound_does_not_undo_on_erase_press_or_delete_sample_file(self):
        a=self.a;sample=Path(self.temp.name)/'keep.wav';sample.touch()
        a.project['groups'][0]['pads'][1].update(sample=str(sample),end=100,plugins=[{'uri':'urn:fx','kind':'EFFECT','controls':{}}])
        before=copy.deepcopy(a.project);a.button('SHIFT',True);a.button('ERASE',True)
        self.assertEqual(a.project,before);a.pad_on(1);a.button('ERASE',False);a.button('SHIFT',False)
        self.assertIsNone(a.track()['sample']);self.assertFalse(a.track().get('plugins'));self.assertTrue(sample.exists())
        channels=load_pad_channels(Path(__file__).resolve().parent.parent/'captures/mikro-mk1-pad-led-map.json')
        self.assertEqual(led_report(a,channels)[channels[(1,'orange')]+1],FULL)  # Selected empty slot stays visible.
        self.shortcut(1);self.assertEqual(a.project,before)
