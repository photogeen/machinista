import copy
import tempfile
import unittest
from app.model import Application,validate_project

class ModulationHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.a=Application(self.temp.name)
        self.a.page='SAMPLER';self.a.sampler_page=1;self.a.sampler_field=0;self.a.playing=True
    def record(self,count=4,delta=1):
        a=self.a;a.button('SHIFT',True)
        for i in range(count):a.clock_phase=i*24;a.rotate(delta)
        a.button('SHIFT',False)
    def lanes(self):return self.a.project['groups'][0].get('automation',{})
    def test_gesture_is_one_take_and_round_trip_restores_stable_base(self):
        a=self.a
        for lane in a.project["groups"][0]["patterns"][0]:lane.extend([False]*16)
        a.project["groups"][0]["pattern_lengths"]["0"]=32
        self.record(20);self.assertEqual(len(a.undo),1)
        before=copy.deepcopy(self.lanes());self.assertEqual(len(next(iter(before.values()))['points']),20)
        a.undo_action();self.assertFalse(self.lanes());self.assertEqual(a.track().get('sampler',{}).get('tune',0),0)
        a.undo_action(True);self.assertEqual(self.lanes(),before);self.assertEqual(a.track().get('sampler',{}).get('tune',0),0)
        a.save();b=Application(a.root);self.assertEqual(b.project['groups'][0]['automation'],before);self.assertEqual(b.track()['sampler']['tune'],0);validate_project(b.project)
    def test_shift_release_starts_next_take_and_existing_points_restore(self):
        a=self.a;self.record(2);first=copy.deepcopy(self.lanes());a.clock_phase=48;a.automation_tick()
        self.record(2);self.assertEqual(len(a.undo),2);a.undo_action();self.assertEqual(self.lanes(),first)
        a.undo_action();self.assertFalse(self.lanes());a.undo_action(True);self.assertEqual(self.lanes(),first)
    def test_step_undo_redo_and_same_tick_merge_do_not_erase_neighbors(self):
        a=self.a;a.button('SHIFT',True);a.clock_phase=0;a.rotate(1);a.rotate(2)
        a.clock_phase=24;a.rotate(1)
        meta=a.recording_history[id(a.undo[-1])];self.assertEqual(len(meta['changes']),2)
        a.undo_action(step=True);lane=next(iter(self.lanes().values()));self.assertEqual(lane['points'],{'0':3})
        a.undo_action(step=True);self.assertFalse(self.lanes())
        a.undo_action(redo=True,step=True);self.assertEqual(next(iter(self.lanes().values()))['points'],{'0':3})
        a.undo_action(redo=True,step=True);self.assertEqual(next(iter(self.lanes().values()))['points'],{'0':3,'24':4})
    def test_mixed_note_and_modulation_take_preserves_held_voices_on_modulation_undo(self):
        a=self.a;a.recording=True;a.step=a.clock_phase=0;a.pad_on(0,90)
        notes=copy.deepcopy(a.event_notes());self.assertTrue(a.live_notes)
        a.button('SHIFT',True);a.rotate(1);self.assertEqual(len(a.undo),1)
        a.undo_action(step=True);self.assertFalse(self.lanes());self.assertEqual(a.event_notes(),notes);self.assertTrue(a.live_notes)
        a.release_pad(0);a.undo_action();self.assertFalse(a.event_notes());a.undo_action(True)
        self.assertEqual(len(a.event_notes()),1)
    def test_channel_modulation_and_ordinary_edit_have_distinct_history(self):
        a=self.a;a.page='CHANNEL';a.control_level=2;a.channel_field=a.channel_fields().index('gain');base=a.track()['gain']
        self.record(3,-1);self.assertEqual(len(a.undo),1);self.assertTrue(self.lanes());validate_project(a.project)
        a.undo_action();self.assertFalse(self.lanes());self.assertEqual(a.track()['gain'],base)
        a.shift=False;a.rotate(-1);a.rotate(-1);self.assertEqual(len(a.undo),2)
    def test_undo_boundary_rebuilds_modulation_future_for_step_redo(self):
        a=self.a;a.playing=False;a.rotate(2);a.playing=True
        self.record(2);future=copy.deepcopy(self.lanes())
        a.undo_action(step=True);a.undo_action(step=True);self.assertFalse(self.lanes())
        a.undo_action(step=True);self.assertEqual(a.track().get('sampler',{}).get('tune',0),0)
        a.undo_action(redo=True,step=True);a.undo_action(redo=True,step=True);a.undo_action(redo=True,step=True)
        self.assertEqual(self.lanes(),future)
    def test_new_branch_after_step_undo_discards_old_point_redo(self):
        a=self.a;a.button('SHIFT',True);a.clock_phase=0;a.rotate(1);a.clock_phase=24;a.rotate(1)
        a.undo_action(step=True);a.clock_phase=48;a.rotate(3);a.undo_action(redo=True,step=True)
        points=next(iter(self.lanes().values()))['points'];self.assertNotIn('24',points);self.assertIn('48',points)

    def test_plugin_modulation_keeps_uri_and_base_across_take_undo(self):
        a=self.a;a.page='PLUGIN';a.control_level=2
        a.track()['plugins']=[dict(uri='urn:test',kind='EFFECT',controls={'gain':1},bypass=False)]
        a.plugin_catalog=[dict(uri='urn:test',ports=[dict(symbol='gain',default=1,min=0,max=10)])]
        self.record(3);self.assertEqual(len(a.undo),1)
        lane=next(iter(self.lanes().values()));self.assertEqual(lane['uri'],'urn:test')
        self.assertEqual(lane['base'],1);validate_project(a.project)
        a.undo_action();self.assertFalse(self.lanes());self.assertEqual(a.track()['plugins'][0]['controls']['gain'],1)
        a.undo_action(True);self.assertEqual(next(iter(self.lanes().values()))['uri'],'urn:test')
        self.assertEqual(a.track()['plugins'][0]['controls']['gain'],1)
    def test_save_ends_history_and_next_gesture_undo_keeps_saved_points(self):
        a=self.a;self.record(2);saved=copy.deepcopy(self.lanes());a.save();self.assertFalse(a.recording_history)
        self.record(3);self.assertEqual(len(a.undo),1);a.undo_action();self.assertEqual(self.lanes(),saved)
