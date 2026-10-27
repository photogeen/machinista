import copy
import tempfile
import unittest
from unittest.mock import patch
from app.model import Application
from app.ni_display import frame

class RecordingWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.a=Application(self.temp.name)
        self.a.fixed_velocity=False
    def tearDown(self):self.temp.cleanup()
    def press(self,name):
        self.a.button(name,True);self.a.button(name,False)
    def shortcut(self,pad):
        self.a.button('SHIFT',True);self.a.pad_on(pad);self.a.release_pad(pad);self.a.button('SHIFT',False)
    def record(self):
        a=self.a;self.press('REC');self.press('PLAY');a.clock_tick()
        for pad,tick in ((0,0),(1,24),(2,48)):
            a.clock_phase=tick;a.clock_last=None;a.pad_on(pad,80+pad);a.release_pad(pad)
    def test_take_and_step_pad_commands_are_distinct_and_redo_durations(self):
        self.record();a=self.a;recorded=copy.deepcopy(a.notes())
        self.shortcut(2);self.assertEqual(set(a.notes()),{(0,0),(1,24)})
        self.shortcut(3);self.assertEqual(a.notes(),recorded)
        self.shortcut(0);self.assertEqual(a.notes(),{})
        self.shortcut(1);self.assertEqual(a.notes(),recorded)
        self.shortcut(2);self.assertNotIn((2,48),a.notes())
        self.shortcut(3);self.assertEqual(a.notes(),recorded)
    def test_step_redo_after_take_undo_restores_notes_one_at_a_time(self):
        self.record();a=self.a;original=copy.deepcopy(a.notes())
        self.shortcut(0)
        for count in (1,2,3):self.shortcut(3);self.assertEqual(len(a.notes()),count)
        self.assertEqual(a.notes(),original)
    def test_step_undo_across_take_boundary_can_redo_previous_edit_and_take(self):
        a=self.a;a.remember();a.project['name']='CHANGED';self.record()
        for _ in range(4):self.shortcut(2)
        self.assertEqual(a.project['name'],'UNTITLED')
        self.shortcut(3);self.assertEqual(a.project['name'],'CHANGED')
        self.shortcut(1);self.assertEqual(len(a.notes()),3)
    def test_step_edit_session_supports_take_and_single_action_undo(self):
        a=self.a;a.page='STEP';a.pad_on(0);a.pad_on(1);a.pad_on(2)
        self.shortcut(2);self.assertEqual(set(a.notes()),{(0,0),(0,24)})
        self.shortcut(3);self.assertEqual(len(a.notes()),3)
        self.shortcut(0);self.assertEqual(a.notes(),{})
        self.shortcut(1);self.assertEqual(len(a.notes()),3)
    def test_record_hold_presets_grid_and_release_back_to_sound(self):
        a=self.a
        with patch('app.recording.time.monotonic',return_value=10):a.button('REC',True)
        a.record_prepare_tick(10.99);self.assertFalse(a.record_prepare)
        a.record_prepare_tick(11);self.assertEqual(a.page,'RECORD PREPARE');self.assertFalse(a.recording)
        self.press('F2');self.assertEqual(a.pattern_steps(),64)
        self.press('NAV RIGHT');a.rotate(1);self.assertEqual(a.timing()['grid'],'1/32')
        self.assertEqual(len(frame(a)),8192)
        a.button('REC',False);self.assertEqual(a.page,'PAD');self.assertTrue(a.recording)
    def test_prepare_does_not_freeze_playback_and_count_in_restarts_on_release(self):
        a=self.a;a.playing=True
        with patch('app.recording.time.monotonic',return_value=10):a.button('REC',True)
        a.record_prepare_tick(11);a.clock_tick();self.assertEqual(a.clock_phase,0)
        a.button('REC',False);self.assertTrue(a.recording)
        self.press('REC');a.button('SHIFT',True)
        with patch('app.recording.time.monotonic',return_value=20):a.button('REC',True)
        a.record_prepare_tick(21);self.assertEqual(a.count_remaining,0)
        a.button('REC',False);self.assertEqual(a.count_remaining,384)
    def test_replace_only_selected_sound_preserves_new_notes_and_ends_at_loop(self):
        a=self.a
        for pad,tick in ((0,0),(0,24),(1,24)):a.put_note(pad,tick,{'velocity':100,'probability':100})
        a.pad=0;a.playing=True;a.clock_phase=12;a.step=0
        a.button('ERASE',True);self.press('REC');a.button('ERASE',False)
        self.assertIsNotNone(a.replace_context)
        a.clock_phase=23;a.clock_tick();self.assertNotIn((0,24),a.notes());self.assertIn((1,24),a.notes())
        a.clock_last=None;a.record_pad_note(0,90);self.assertIn((0,24),a.notes())
        a.clock_phase=383;a.step=15;a.clock_tick();self.assertIsNone(a.replace_context)
        self.assertIn((0,0),a.notes());self.assertTrue(a.recording)
    def test_replace_never_erases_fresh_forward_quantized_note(self):
        a=self.a;a.put_note(0,24,{'velocity':50,'probability':100});a.pad=0
        a.playing=True;a.step=0;a.clock_phase=13
        a.button('ERASE',True);self.press('REC');a.button('ERASE',False)
        a.clock_last=None;a.record_pad_note(0,90)
        a.clock_phase=23;a.clock_tick();self.assertEqual(a.notes()[(0,24)]['velocity'],90)
    def test_replace_cancels_on_erase_seek_mode_stop_or_focus(self):
        for name in ('ERASE','TRANSPORT RIGHT','SAMPLING','PLAY'):
            with self.subTest(name=name):
                a=Application(self.temp.name);a.playing=True;a.recording=True;a.step=0;a.begin_replace()
                a.button(name,True);self.assertIsNone(a.replace_context)
        a=self.a;a.playing=a.recording=True;a.begin_replace();a.group=1;a.clock_tick()
        self.assertIsNone(a.replace_context)
    def test_save_clears_take_and_step_history(self):
        self.record();a=self.a;notes=copy.deepcopy(a.notes());a.save()
        self.assertFalse(a.recording_history);self.shortcut(2);self.shortcut(0);self.assertEqual(a.notes(),notes)
    def test_sampler_envelope_fields_follow_ni_type_and_keep_hidden_values(self):
        a=self.a;a.page='SAMPLER';a.sampler_page=1
        a.track()['sampler']={'type':'ONESHOT','release':321}
        keys=lambda:[f[0] for f in a.sampler_fields()]
        self.assertEqual(keys(),['tune','reverse','type'])
        a.track()['sampler']['type']='AHD'
        self.assertEqual(keys(),['tune','reverse','type','attack','hold','decay'])
        a.track()['sampler']['type']='ADSR'
        self.assertEqual(keys(),['tune','reverse','type','attack','decay','sustain','release'])
        self.assertEqual(a.track()['sampler']['release'],321)
        a.sampler_field=6;a.track()['sampler']['type']='ONESHOT'
        self.assertEqual(a.sampler_parameter()[0],'type')
    def test_replace_count_in_and_multi_sound_erasure_are_undoable(self):
        a=self.a;a.selected_pads={0,1};a.pad=0
        for pad in (0,1,2):a.put_note(pad,0,{'velocity':80,'probability':100})
        original=copy.deepcopy(a.notes())
        a.button('SHIFT',True);a.button('ERASE',True);self.press('REC')
        a.button('ERASE',False);a.button('SHIFT',False)
        self.assertEqual(a.count_remaining,384);self.assertIsNotNone(a.replace_context)
        for _ in range(385):a.clock_tick()
        self.assertEqual(set(a.notes()),{(2,0)})
        self.shortcut(0);self.assertEqual(a.notes(),original)
    def test_new_note_after_step_undo_discards_redo_branch(self):
        self.record();a=self.a;self.shortcut(2);a.clock_phase=72;a.clock_last=None
        a.pad_on(3,91);a.release_pad(3);self.shortcut(3)
        self.assertEqual(set(a.notes()),{(0,0),(1,24),(3,72)})
