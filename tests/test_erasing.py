import copy
import tempfile
import unittest
from unittest.mock import patch
from app.model import Application,validate_project
from app.leds import led_report,OFF,FULL

class ErasingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.a=Application(self.temp.name)
    def note(self,pad,tick,group=0,**fields):
        self.a.put_note(pad,tick,dict(velocity=95,probability=100,length=12,**fields),group=group)
    def test_live_erase_without_rec_removes_only_passed_events_and_never_hits(self):
        a=self.a;self.note(2,1);self.note(2,24);self.note(3,1);before=copy.deepcopy(a.project)
        a.playing=True;a.clock_tick();a.button('ERASE',True);a.actions=[];a.pad_on(2)
        self.assertFalse(a.recording);self.assertFalse(a.actions)
        a.clock_tick();self.assertNotIn((2,1),a.notes());self.assertIn((3,1),a.notes());self.assertIn((2,24),a.notes())
        a.release_pad(2)
        for _ in range(24):a.clock_tick()
        self.assertIn((2,24),a.notes());a.button('ERASE',False);a.undo_action();self.assertEqual(a.project,before)
    def test_keyboard_erase_only_held_pitch_preserves_other_chord_notes(self):
        a=self.a;a.pad=2;a.keyboard_enabled=True;a.keyboard_root=36
        self.note(2,1,note=36,chord=[36,40,43]);self.note(3,1,note=36)
        a.playing=True;a.clock_tick();a.button('ERASE',True);a.pad_on(4);a.clock_tick()
        self.assertEqual(a.notes()[(2,1)]['chord'],[36,43]);self.assertIn((3,1),a.notes())
        self.assertFalse(any(k=='event_hit' and v[:2]==(0,2) and v[3]==40 for k,v in a.actions))
        a.release_pad(4);a.button('ERASE',False);a.undo_action()
        self.assertEqual(a.notes()[(2,1)]['chord'],[36,40,43])
    def test_select_erase_clears_sound_events_without_samples_or_other_patterns(self):
        a=self.a;self.note(2,0);self.note(2,23);self.note(3,0);a.track()['sample']='keep.wav'
        a.put_note(2,0,dict(velocity=99,probability=100),pattern=1)
        a.button('SELECT',True);a.button('ERASE',True);a.actions=[];a.pad_on(2)
        self.assertEqual(set(a.notes()),{(3,0)});self.assertIn((2,0),a.notes(pattern=1));self.assertEqual(a.track()['sample'],'keep.wav')
        self.assertFalse(any(k in ('hit','event_hit','midi_note') for k,v in a.actions));validate_project(a.project)
    def test_select_erase_leds_show_events_including_empty_sound_slots(self):
        a=self.a;self.note(3,0);a.button('SELECT',True);a.button('ERASE',True)
        channels={(slot,'orange'):slot for slot in range(16)}
        r=led_report(a,channels,100);self.assertEqual(r[4],FULL);self.assertEqual(r[3],OFF)
        a.pad_on(3);self.assertEqual(led_report(a,channels,100)[4],OFF)
    def test_erase_group_at_playhead_preserves_other_groups(self):
        a=self.a;self.note(1,1,group=1);self.note(2,1,group=1);self.note(2,1)
        a.active_clips[1]=True;a.playing=True;a.clock_tick();a.button('ERASE',True);a.button('GROUP',True);a.pad_on(13);a.clock_tick()
        self.assertFalse(a.notes(1));self.assertIn((2,1),a.notes());self.assertEqual(a.group,0)
        a.release_pad(13);a.button('GROUP',False);a.button('ERASE',False)
    def test_erase_with_record_enabled_does_not_record_struck_pad(self):
        a=self.a;self.note(2,24);a.playing=a.recording=True;a.clock_tick();a.button('ERASE',True);a.actions=[];a.pad_on(2)
        self.assertNotIn((2,0),a.notes());self.assertFalse(a.actions)
        for _ in range(24):a.clock_tick()
        self.assertNotIn((2,24),a.notes())
    def test_stopped_locate_uses_step_grid_and_erases_selected_sounds_only(self):
        a=self.a;a.pad=2;a.selected_pads={2,3};a.clock_phase=0;a.step=0
        for pad in (2,3,4):
            self.note(pad,12);self.note(pad,24);self.note(pad,25)
        before=copy.deepcopy(a.project);a.button('ERASE',True);a.button('TRANSPORT RIGHT',True);a.button('TRANSPORT RIGHT',False)
        self.assertEqual(a.clock_phase,24)
        self.assertEqual(set(a.notes()),{(2,25),(3,25),(4,12),(4,24),(4,25)})
        a.button('ERASE',False);a.undo_action();self.assertEqual(a.project,before)
    def test_velocity_levels_erase_focused_sound_and_release_erase_stops_deletion(self):
        a=self.a;a.velocities16=True;a.pad=2;self.note(2,1);self.note(2,2);self.note(15,1)
        a.playing=True;a.clock_tick();a.button('ERASE',True);a.pad_on(15);a.clock_tick();a.button('ERASE',False);a.clock_tick()
        self.assertNotIn((2,1),a.notes());self.assertIn((15,1),a.notes());self.assertIn((2,2),a.notes())
    def test_groove_erase_happens_before_shifted_playback(self):
        a=self.a;self.note(2,48);a.timing()['swing']=100
        # Groove may additionally use per-Sound/Group settings; use its real position.
        due=a.groove_position(0,2,48,a.pattern_ticks());a.clock_phase=due-1;a.step=a.clock_phase//24;a.playing=True
        a.button('ERASE',True);a.pad_on(2);a.actions=[];a.clock_tick()
        self.assertNotIn((2,48),a.notes());self.assertFalse(any(k in ('hit','event_hit') for k,v in a.actions))
    def test_project_reinitialization_clears_held_erase_targets(self):
        a=self.a;a.button('ERASE',True);a.pad_on(2);self.assertTrue(a.erase_targets)
        a.init_workspaces();self.assertFalse(a.erase_targets)

    def test_live_erase_updates_cached_indices_without_rescanning_pattern_each_tick(self):
        a=self.a;self.note(2,1);self.note(2,24);a.playing=True;a.clock_tick()
        a.button('ERASE',True);a.pad_on(2);a.clock_tick()
        with patch.object(a,'notes',side_effect=AssertionError('pattern rescan during cached erase')):
            for _ in range(24):a.clock_tick()
        self.assertFalse(a.notes())
