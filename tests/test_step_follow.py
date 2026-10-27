import tempfile
import unittest
from app.model import Application
from app.ni_display import frame

class StepFollowTests(unittest.TestCase):
    def setUp(self):
        self.root=tempfile.TemporaryDirectory();self.addCleanup(self.root.cleanup)
        self.a=Application(self.root.name);self.a.double_pattern();self.a.page='STEP';self.a.playing=True
    def test_follow_changes_bank_and_wraps_on_clock(self):
        a=self.a;a.clock_phase=383;a.step=15;a.clock_tick();self.assertEqual(a.bank,1)
        a.clock_phase=767;a.step=31;a.clock_tick();self.assertEqual(a.bank,0)
    def test_navigation_pauses_and_follow_resumes_immediately(self):
        a=self.a;a.clock_phase=400;a.follow_step_view();self.assertEqual(a.bank,1)
        a.button('NAV LEFT',True);self.assertFalse(a.follow);self.assertEqual(a.bank,0)
        a.button('F1',True);self.assertTrue(a.follow);self.assertEqual(a.bank,1)
    def test_playhead_uses_ticks_and_inverts_note_pixels(self):
        a=self.a;a.clock_phase=0;self.assertEqual(a.step_playhead_x(),2)
        a.clock_phase=12;self.assertEqual(a.step_playhead_x(),6)
        a.clock_phase=384;a.follow_step_view();self.assertEqual(a.step_playhead_x(),2)
        a.clock_phase=396;a.put_note(0,384,{'velocity':100,'probability':100,'length':24})
        playing=frame(a);a.playing=False;stopped=frame(a)
        self.assertTrue(all(playing[y*128+6]!=stopped[y*128+6] for y in range(34,50)))
    def test_inactive_pattern_has_no_follow_or_playhead(self):
        a=self.a;a.pattern=1;a.bank=0;a.clock_phase=400;a.follow_step_view()
        self.assertEqual(a.bank,0);self.assertIsNone(a.step_playhead_x())
