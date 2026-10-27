import copy
import tempfile
import unittest
from unittest.mock import patch
from app.model import Application,validate_project
from app.ni_display import frame
from app.timing import RATES

class TimingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.a=Application(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def test_fine_and_triplet_steps_persist_and_play_at_their_exact_ticks(self):
        a=self.a;a.timing()['grid']='1/32';a.page='STEP';a.pad_on(0);a.pad_on(1)
        self.assertEqual(set(a.notes()),{(0,0),(0,12)})
        a.button('NAV RIGHT',True);a.pad_on(0);self.assertIn((0,192),a.notes())
        a.pad_on(0);a.button('NAV LEFT',True)
        a.timing()['grid']='1/16T';a.pad_on(1);self.assertIn((0,16),a.notes())
        validate_project(a.project);a.save();b=Application(self.temp.name)
        self.assertEqual(set(b.notes()),{(0,0),(0,12),(0,16)})
        b.playing=True;hits=[]
        for tick in range(25):
            b.actions=[];b.clock_tick(tick/192)
            if any(action=='hit' for action,_ in b.actions):hits.append(tick)
        self.assertEqual(hits,[0,12,16])
    def test_quantization_strength_selection_collision_and_undo(self):
        a=self.a;a.put_note(0,13,{'velocity':73,'probability':42,'note':60})
        before=copy.deepcopy(a.project);a.quantize_pattern(50)
        self.assertIn((0,19),a.notes());self.assertEqual(a.notes()[(0,19)]['note'],60)
        a.quantize_pattern(100);self.assertIn((0,24),a.notes())
        a.undo_action();self.assertIn((0,19),a.notes());a.undo_action();self.assertEqual(a.project,before)
        a.put_note(0,24,{'velocity':100,'probability':100});before=copy.deepcopy(a.project)
        a.quantize_pattern(100);self.assertEqual(a.project,before);self.assertEqual(a.message,'QUANTIZE COLLISION')
        a.page='PATTERN GRID';a.grid_selected={(0,13)};a.timing()['grid']='1/32'
        a.quantize_pattern(100);self.assertEqual(a.grid_selected,{(0,12)})
    def test_swing_changes_playback_time_and_keeps_beats_and_project_notes(self):
        a=self.a;a.put_note(0,48,{'velocity':100,'probability':100})
        a.timing()['swing']=50;a.playing=True;times=[]
        for tick in range(97):
            a.actions=[];a.clock_tick(tick/192)
            if any(kind=='hit' for kind,_ in a.actions):times.append(tick)
        self.assertEqual(times,[60]);self.assertIn((0,48),a.notes())
        self.assertEqual(a.swing_position(96,384),96)
        self.assertLess(a.swing_position(383,384),384)
    def test_count_in_has_only_clicks_then_records_and_preserves_metronome_switch(self):
        a=self.a;a.put_note(0,0,{'velocity':100,'probability':100})
        a.button('SHIFT',True);a.button('REC',True);a.button('SHIFT',False)
        self.assertFalse(a.recording);clicks=[]
        for tick in range(384):
            a.actions=[];a.clock_tick(tick/192)
            self.assertFalse(any(kind in ('hit','event_hit') for kind,_ in a.actions))
            clicks.extend(value for kind,value in a.actions if kind=='click')
        self.assertEqual(clicks,[(True,35),(False,35),(False,35),(False,35)])
        self.assertTrue(a.playing and a.recording);self.assertFalse(a.timing()['metro'])
        a.actions=[];a.clock_tick(2);self.assertIn(('hit',(0,0,100)),a.actions)
        a.button('SHIFT',True);a.button('PLAY',True);a.button('SHIFT',False)
        self.assertTrue(a.playing);self.assertTrue(a.timing()['metro'])
        a.start_count_in();a.button('PLAY',True);self.assertEqual(a.count_remaining,0);self.assertFalse(a.playing)
    def test_record_quantization_uses_grid_and_grid_off_keeps_fine_position(self):
        a=self.a;a.playing=a.recording=True;a.step=0;a.clock_phase=13
        a.record_pad_note(1,87,64);self.assertIn((1,24),a.notes());self.assertEqual(a.notes()[(1,24)]['note'],64)
        a.timing()['record_quantize']=False;a.record_pad_note(2,91);self.assertIn((2,13),a.notes())
        a.timing()['record_quantize']=True;a.timing()['grid_on']=False;a.record_pad_note(3,92)
        self.assertIn((3,13),a.notes());validate_project(a.project)
    def test_copy_double_clear_and_shorten_keep_fine_events_valid(self):
        a=self.a;a.put_note(0,12,{'velocity':83,'probability':75,'note':55})
        a.double_pattern();self.assertIn((0,396),a.notes())
        a.duplicate_pattern();self.assertIn((0,396),a.notes())
        a.copy_object(('SOUND',0,0),('SOUND',0,2));self.assertIn((2,12),a.notes())
        a.copy_object(('PATTERN',0,1),('PATTERN',0,3));a.pattern=3
        self.assertIn((2,396),a.notes());a.page='LENGTH';a.rotate(-1)
        self.assertNotIn((2,396),a.notes());validate_project(a.project)
        a.clear_pattern();self.assertEqual(a.notes(),{})
    def test_grid_editor_can_select_and_nudge_fine_events(self):
        a=self.a;a.timing()['grid']='1/32';a.page='PATTERN';a.button('ENTER',True)
        a.rotate(1);a.button('ENTER',True);self.assertIn((0,12),a.notes())
        a.timing()['nudge']='1/64';a.button('SHIFT',True);a.rotate(1);a.button('SHIFT',False)
        self.assertIn((0,18),a.notes());a.button('F3',True)
        self.assertEqual({k[:2] for k in a.grid_selected},{(0,18)});p=frame(a);self.assertTrue(all(p[63*128:]))
        a.button('SHIFT',True);a.pad_on(4);a.button('SHIFT',False);self.assertIn((0,24),a.notes())
    def test_grid_and_recording_controls_persist_and_reject_invalid_data(self):
        a=self.a;a.button('GRID',True);a.rotate(1);self.assertEqual(a.timing()['grid'],'1/32')
        a.button('F2',True);a.rotate(40);self.assertEqual(a.timing()['swing'],40)
        a.button('GRID',False);a.button('SHIFT',True);a.button('GRID',True);a.button('SHIFT',False)
        self.assertEqual(a.page,'RECORD SETTINGS');a.button('NAV RIGHT',True);a.rotate(1)
        self.assertEqual(a.timing()['count_bars'],2);a.save()
        b=Application(self.temp.name);self.assertEqual(b.timing()['grid'],'1/32');self.assertEqual(b.timing()['swing'],40)
        b.project['groups'][0]['extra_events']['0:0:384']={'velocity':100,'probability':100}
        with self.assertRaises(ValueError):validate_project(b.project)

    def test_live_quantized_note_is_not_echoed_before_the_next_loop(self):
        a=self.a;a.playing=a.recording=True;a.step=0;a.clock_phase=13;a.clock_last=None
        a.record_pad_note(2,100);a.actions=[]
        for _ in range(11):a.clock_tick()
        self.assertEqual(a.clock_phase,24)
        self.assertFalse(any(k in ('hit','event_hit') for k,_ in a.actions))
        a.recording=False;a.actions=[]
        for _ in range(384):a.clock_tick()
        self.assertEqual(sum(k=='hit' and v[:2]==(0,2) for k,v in a.actions),1)

    def test_recording_from_sound_pad_config_and_tempo_repeats_for_multiple_loops(self):
        for page in ('PAD','SAMPLER','CHANNEL','PLUGIN','PAD CONFIG','TEMPO'):
            with self.subTest(page=page):
                a=Application(self.temp.name);a.page=page;a.main_controls=(page=='TEMPO');a.set_pattern_length(32)
                a.button('REC',True);a.button('PLAY',True);a.clock_tick()
                a.clock_last=None;a.pad_on(2,95);a.release_pad(2)
                self.assertIn((2,0),a.notes())
                a.actions=[]
                for _ in range(768*3):a.clock_tick()
                self.assertEqual(sum(k=='hit' and v[:2]==(0,2) for k,v in a.actions),3)
                self.assertEqual(a.pattern_position(),'1:1:1')
                self.assertEqual(a.transport_title(),'REC P01 1/2 BAR')

    def test_recording_in_empty_scene_activates_clip_and_can_be_undone(self):
        a=self.a;a.fixed_velocity=False;a.activate_scene(1);a.playing=a.recording=True;a.clock_tick();a.clock_last=None
        before=copy.deepcopy(a.project);self.assertFalse(a.active_clips[0])
        a.pad_on(0,90);a.release_pad(0)
        self.assertEqual(a.project['scenes'][1][0],0);self.assertTrue(a.active_clips[0])
        a.actions=[]
        for _ in range(384):a.clock_tick()
        self.assertIn(('hit',(0,0,90)),a.actions)
        a.undo_action();self.assertEqual(a.project,before)

    def test_recording_16_velocities_uses_selected_sound_and_actual_velocity(self):
        a=self.a;a.page='PAD CONFIG';a.velocities16=True;a.pad=2
        a.playing=a.recording=True;a.clock_tick();a.clock_last=None;a.pad_on(7)
        self.assertEqual(a.notes()[(2,0)]['velocity'],64)

    def test_transport_shows_exact_fractional_length_and_local_loop_position(self):
        a=self.a;a.set_pattern_length(66);a.playing=a.recording=True;a.clock_phase=66*24+24
        self.assertEqual(a.transport_title(),'REC P01 1/4.125 BAR')
        self.assertEqual(a.pattern_position(),'1:1:2')

    def test_coarse_pattern_length_lands_on_full_bars_and_fine_keeps_sixteenths(self):
        a=self.a;a.page='PATTERN';a.set_pattern_length(66);a.rotate(-1)
        self.assertEqual(a.pattern_steps(),64)
        a.rotate(1);self.assertEqual(a.pattern_steps(),80)
        a.encoder_held=True;a.rotate(1);self.assertEqual(a.pattern_steps(),81)
        a.encoder_held=False;a.rotate(-1);self.assertEqual(a.pattern_steps(),80)
        a.shift=True;a.rotate(-1);self.assertEqual(a.pattern_steps(),79)
        a.shift=False;a.page='LENGTH';a.rotate(1);self.assertEqual(a.pattern_steps(),80)

    def test_record_take_has_one_undo_and_independent_pattern_storage(self):
        a=self.a;before=copy.deepcopy(a.project);a.playing=a.recording=True;a.step=0;a.clock_last=None
        for tick in (0,24,48):
            a.clock_phase=tick;a.pad_on(tick//24);a.release_pad(tick//24)
        self.assertEqual(len(a.undo),1)
        self.assertEqual(a.undo[0],before)
        a.undo_action();self.assertEqual(a.project,before)
        a.undo_action(True);self.assertEqual(len(a.notes()),3)
        a.reset_recording_take();a.clock_phase=72;a.pad_on(3)
        self.assertEqual(len(a.undo),2)

    def test_clock_stall_keeps_phase_without_playing_stale_notes_in_a_burst(self):
        from app.sequencer_clock import advance_clock
        a=self.a;a.playing=True;a.put_note(0,0,{'velocity':100,'probability':100})
        a.put_note(1,12,{'velocity':100,'probability':100})
        deadline,overrun=advance_clock(a,0,0.1)
        self.assertFalse(overrun);self.assertEqual(a.clock_phase,19)
        self.assertGreater(deadline,0.1)
        self.assertFalse(any(k=='hit' for k,_ in a.actions))
        a.actions=[];deadline,overrun=advance_clock(a,deadline,0.25)
        self.assertTrue(overrun);self.assertEqual(a.clock_phase,48)
        self.assertFalse(any(k=='hit' for k,_ in a.actions))

    def test_short_clock_delay_preserves_notes_and_does_not_drift(self):
        from app.sequencer_clock import advance_clock
        a=self.a;a.playing=True;a.put_note(0,0,{'velocity':100,'probability':100})
        a.put_note(1,24,{'velocity':80,'probability':100})
        deadline,overrun=advance_clock(a,0,.02)
        self.assertFalse(overrun);self.assertIn(('hit',(0,0,100)),a.actions)
        self.assertEqual(a.clock_stats['dropped_ticks'],0)
        self.assertAlmostEqual(deadline,4*a.clock_interval())
        a.actions=[];deadline,overrun=advance_clock(a,deadline,24*a.clock_interval())
        self.assertIn(('hit',(0,1,80)),a.actions)
        self.assertAlmostEqual(deadline,25*a.clock_interval())
        self.assertGreater(a.clock_stats['dropped_ticks'],0)
