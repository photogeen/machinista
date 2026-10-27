import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from app.model import Application,validate_project
from app.polyphony import note_id,event_key
from app.ni_display import frame

class PolyphonyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.a=Application(self.temp.name);self.a.performance()['root']=36;self.a.keyboard_root=36
    def add(self,pad,tick,note,velocity,length):
        event=dict(note=note,velocity=velocity,length=length,probability=100,_id=note_id());key=event_key(pad,tick,event)
        self.a.put_event(key,event);return key
    def record_two(self):
        a=self.a;a.fixed_velocity=False;a.keyboard_enabled=True;a.playing=a.recording=True;a.step=a.clock_phase=0
        with patch('app.model.time.monotonic',return_value=10):a.pad_on(0,51);a.pad_on(4,109)
        return a
    def test_recording_velocity_and_release_length_are_independent(self):
        a=self.record_two()
        with patch('app.surface.time.monotonic',return_value=10+.2):a.release_pad(0)
        with patch('app.surface.time.monotonic',return_value=10+.7):a.release_pad(4)
        events={v['note']:v for v in a.event_notes().values()}
        self.assertEqual(set(events),{36,40});self.assertEqual(events[36]['velocity'],51);self.assertEqual(events[40]['velocity'],109)
        self.assertGreater(events[40]['length'],events[36]['length']);self.assertEqual(len(a.undo),1)
        a.recording=False;a.actions=[];a.clock_phase=383;a.step=15;a.clock_tick()
        self.assertIn(('event_hit',(0,0,51,36)),a.actions);self.assertIn(('event_hit',(0,0,109,40)),a.actions)
        gates=[v for k,v in a.actions if k=='note_gate'];self.assertEqual({v[3] for v in gates},{events[36]['length'],events[40]['length']})
    def test_chord_press_records_and_releases_every_generated_note(self):
        a=self.a;a.keyboard_enabled=True;a.playing=a.recording=True;a.step=a.clock_phase=0
        a.performance().update(chord_mode='HARM',chord_type='MAJOR')
        with patch('app.model.time.monotonic',return_value=10):a.pad_on(0,83)
        with patch('app.surface.time.monotonic',return_value=10+.4):a.release_pad(0)
        values=list(a.event_notes().values());self.assertEqual({v['note'] for v in values},{36,40,43})
        self.assertEqual(len({v['length'] for v in values}),1);self.assertEqual(values[0]['length'],round(.4/a.clock_interval()))
    def test_step_undo_redo_only_affects_one_voice_and_take_undo_all(self):
        a=self.record_two();a.release_pad(0);a.release_pad(4);before=copy.deepcopy(a.event_notes())
        a.undo_action(step=True);self.assertEqual([v['note'] for v in a.event_notes().values()],[36])
        a.undo_action(redo=True,step=True);self.assertEqual(a.event_notes(),before)
        a.undo_action();self.assertFalse(a.event_notes());a.undo_action(redo=True);self.assertEqual(a.event_notes(),before)
    def test_piano_grid_marks_and_changes_one_pitch_without_neighbor(self):
        a=self.a;k1=self.add(0,24,60,53,13);k2=self.add(0,24,64,111,70)
        a.page='PATTERN GRID';a.grid_notes=True;a.grid_note=64;a.grid_step=1
        self.assertEqual(a.grid_cursor_targets(),{k2});a.button('F2',True);a.button('F3',True)
        a.grid_field=2;a.rotate(-20);self.assertEqual(a.event_notes()[k2]['velocity'],91)
        self.assertEqual(a.event_notes()[k1]['velocity'],53);frame(a)
        a.delete_grid_events();self.assertEqual(set(a.event_notes()),{k1})
    def test_quantize_can_merge_time_cells_without_losing_notes(self):
        a=self.a;k1=self.add(0,22,60,53,13);k2=self.add(0,26,64,111,70);a.quantize_pattern(100)
        events=a.event_notes();self.assertEqual({k[1] for k in events},{24});self.assertEqual(len(events),2)
        self.assertEqual({v['velocity'] for v in events.values()},{53,111});self.assertEqual({v['length'] for v in events.values()},{13,70})
    def test_copy_paste_transpose_nudge_keep_per_note_properties(self):
        a=self.a;k1=self.add(0,24,60,53,13);k2=self.add(0,24,64,111,70);a.grid_selected={k2}
        a.move_shortcut_events(transpose=12);self.assertEqual(a.event_notes()[k2]['note'],76);self.assertEqual(a.event_notes()[k1]['note'],60)
        a.move_shortcut_events(delta=24);new=(0,48,k2[2]);self.assertIn(new,a.event_notes())
        a.copy_shortcut_events();a.pattern=1;a.grid_context=(0,1);a.paste_shortcut_events()
        values=list(a.event_notes().values());self.assertEqual(len(values),1);self.assertEqual(values[0]['length'],70);self.assertEqual(values[0]['velocity'],111)
        self.assertNotEqual(values[0]['_id'],k2[2])
    def test_keyboard_live_erase_only_removes_matching_independent_voice(self):
        a=self.a;k1=self.add(0,1,36,51,13);k2=self.add(0,1,40,109,70)
        a.keyboard_enabled=True;a.playing=True;a.clock_tick();a.button('ERASE',True);a.pad_on(4);a.actions=[];a.clock_tick()
        self.assertEqual(set(a.event_notes()),{k1});self.assertIn(('event_hit',(0,0,51,36)),a.actions)
        self.assertFalse(any(k=='event_hit' and v[3]==40 for k,v in a.actions))
        a.button('ERASE',False);a.undo_action();self.assertEqual(set(a.event_notes()),{k1,k2})
    def test_legacy_chord_migration_and_json_round_trip_preserve_musical_fields(self):
        a=self.a;a.put_note(0,0,dict(note=60,chord=[60,64,67],velocity=83,length=71,probability=42))
        validate_project(a.project);a.poly_cache.clear();voices=a.event_notes()
        self.assertEqual({v['note'] for v in voices.values()},{60,64,67});self.assertTrue(all(v['velocity']==83 and v['length']==71 and v['probability']==42 for v in voices.values()))
        path=Path(self.temp.name)/'projects/current.json';path.parent.mkdir(exist_ok=True);path.write_text(json.dumps(a.project))
        b=Application(self.temp.name);self.assertEqual(b.event_notes(),voices)
    def test_primary_deletion_preserves_neighbor_identity_and_pattern_double_has_new_ids(self):
        a=self.a;k1=self.add(0,0,60,53,13);k2=self.add(0,0,64,111,70);a.remove_event(k1)
        self.assertEqual(set(a.event_notes()),{k2});a.double_pattern();events=a.event_notes()
        self.assertEqual(len(events),2);self.assertEqual(len({k[2] for k in events}),2);self.assertEqual({v['velocity'] for v in events.values()},{111})
    def test_drum_overdub_updates_one_hit_instead_of_adding_duplicate(self):
        a=self.a;a.playing=a.recording=True;a.step=a.clock_phase=0;a.fixed_velocity=False
        a.pad_on(2,51);a.release_pad(2);a.pad_on(2,109);a.release_pad(2)
        self.assertEqual(len(a.event_notes()),1);self.assertEqual(next(iter(a.event_notes().values()))['velocity'],109)

    def test_invalid_polyphony_and_legacy_chords_are_rejected(self):
        a=self.a;k=self.add(0,0,60,80,24)
        for value in ([60,128],[],"60",[True]):
            project=copy.deepcopy(a.project);project['groups'][0]['events']['0:0:0']['chord']=value
            with self.assertRaises(ValueError):validate_project(project)
        project=copy.deepcopy(a.project);child=dict(note=64,velocity=0,length=24,probability=100,_id=note_id())
        project['groups'][0]['events']['0:0:0']['poly']={child['_id']:child}
        with self.assertRaises(ValueError):validate_project(project)
    def test_cell_limit_and_legacy_tick_playback(self):
        a=self.a
        for i in range(128):self.add(0,0,i,80,24)
        self.assertFalse(a.note_capacity([(0,0,note_id())]));self.assertTrue(a.note_capacity([(0,24,note_id())]))
        validate_project(a.project);a.playing=True;a.step=-1;a.actions=[];a.tick()
        self.assertEqual(len([v for k,v in a.actions if k=='event_hit']),128)

    def test_same_pitch_can_be_focused_and_edited_individually(self):
        a=self.a;k1=self.add(0,24,60,53,13);k2=self.add(0,24,60,111,70)
        a.page='PATTERN GRID';a.grid_notes=True;a.grid_note=60;a.grid_step=1
        a.button('SHIFT',True);a.button('NAV RIGHT',True);a.button('SHIFT',False)
        focused=next(iter(a.grid_cursor_targets()));other=({k1,k2}-{focused}).pop()
        before=copy.deepcopy(a.event_notes()[other]);a.button('ENTER',True);a.grid_field=2;a.rotate(-10)
        self.assertEqual(a.event_notes()[other],before);frame(a)
        a.delete_grid_events();self.assertEqual(set(a.event_notes()),{other})
    def test_playback_assigns_distinct_tokens_to_same_pitch_and_next_loop(self):
        a=self.a;self.add(0,0,60,53,13);self.add(0,0,60,111,70);a.playing=True;a.clock_tick()
        gates=[v for k,v in a.actions if k=='note_gate'];self.assertEqual(len({v[4] for v in gates}),2)
        first={v[4] for v in gates};a.actions=[];a.clock_phase=383;a.step=15;a.clock_tick()
        self.assertFalse(first & {v[4] for k,v in a.actions if k=='note_gate'})
