import copy
import tempfile
import time
import unittest
from app.model import Application
from app.display_budget import DisplayBudget
from app.live_display import ASYNC_PAGES,live_state,live_frame
from app.step_display import StepDisplay


class LiveDisplayTests(unittest.TestCase):
    def setUp(self):
        self.root=tempfile.TemporaryDirectory();self.addCleanup(self.root.cleanup)
        self.a=Application(self.root.name);self.a.double_pattern();self.a.playing=True
        self.worker=StepDisplay();self.addCleanup(self.worker.close)
        self.budget=DisplayBudget();self.budget.measured(.1)
    def receive(self):
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            pixels=self.worker.poll()
            if pixels is not None:return pixels
            time.sleep(.002)
        self.fail('Live frame not delivered')
    def submit(self):
        self.assertIn(self.a.page,ASYNC_PAGES)
        self.assertFalse(self.budget.available(1,1.002,True))
        state=live_state(self.a);self.assertTrue(self.worker.submit(state))
        return self.receive()
    def test_mixer_updates_meters_while_clock_budget_refuses_every_frame(self):
        a=self.a;a.page='MIXER';a.mixer_levels={0:(.5,.25)};a.mixer_master=(.5,.25)
        sounding=self.submit();a.mixer_levels={};a.mixer_master=(0,0)
        silent=self.submit();self.assertNotEqual(sounding,silent)
        a.pad=8;a.group=1;a.mixer_levels={24:(.8,.6)}
        bank=self.submit();self.assertNotEqual(silent,bank)
    def test_master_mixer_has_stereo_scope_and_live_peak_parameter_state(self):
        from app.layout import MASTER
        a=self.a;a.page='MIXER';a.mixer_level=0
        a.mixer_levels={MASTER:(.5,.2)};a.mixer_peaks={MASTER:(.8,.4)}
        before=copy.deepcopy(a.project);state=live_state(a)
        self.assertTrue(state['master_mixer']);self.assertEqual(state['levels'],((.5,.2),))
        self.assertEqual(state['mixer_value'],'100%');sounding=self.submit()
        a.mixer_levels={};a.mixer_peaks={};silent=self.submit()
        self.assertNotEqual(sounding,silent)
        for field in (1,2):
            a.mixer_field=field;other=self.submit()
            self.assertNotEqual(silent,other)
            self.assertEqual(len(other),8192)
            self.assertEqual(other[:128],bytes([1])*128)
            self.assertEqual(other[-128:],bytes([1])*128)
        self.assertEqual(a.project,before)

    def test_view_pattern_progress_and_zoom_keep_up_during_playback(self):
        a=self.a;a.page='VIEW NAV';a.view_target='PAT';frames=[]
        for phase,first in ((0,0),(396,16),(768,0)):
            a.clock_phase=phase;a.follow_pattern_grid();self.assertEqual(a.view_first,first)
            self.assertIsNotNone(a.pattern_playhead_x());frames.append(self.submit())
        self.assertNotEqual(frames[0],frames[1]);self.assertEqual(frames[0],frames[2])
        a.view_count=8;self.assertNotEqual(frames[2],self.submit())
        a.navigation_pad(2);self.assertFalse(a.grid_follow);first=a.view_first
        a.clock_phase=396;a.follow_pattern_grid();self.assertEqual(a.view_first,first)
    def test_pattern_and_scene_counters_advance_in_worker(self):
        a=self.a
        for page in ('PATTERN','SCENE'):
            a.page=page;a.clock_phase=0;first=self.submit()
            a.clock_phase=396;self.assertNotEqual(first,self.submit())
    def test_meter_snapshot_is_small_immutable_and_old_views_are_discarded(self):
        a=self.a;a.page='MIXER';a.mixer_levels={0:[.8,.4]};a.mixer_master=[.8,.4]
        state=live_state(a);snapshot=copy.deepcopy(state)
        a.mixer_levels[0][0]=0;a.mixer_master[0]=0
        self.assertEqual(state,snapshot)
        self.assertNotIn('project',state);self.assertLess(len(__import__('pickle').dumps(state)),1024)
        self.assertTrue(self.worker.submit(state));self.worker.invalidate()
        deadline=time.monotonic()+3
        while self.worker.busy and time.monotonic()<deadline:
            self.assertIsNone(self.worker.poll());time.sleep(.002)
        self.assertFalse(self.worker.busy)
        a.page='VIEW NAV';a.view_target='SCENE';a.project['song']=[0,1,2]
        self.assertEqual(self.submit(),live_frame(live_state(a)))
