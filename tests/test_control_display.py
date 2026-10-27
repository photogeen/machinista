import copy
import pickle
import unittest
from tests import test_live_display as live_tests
from app.control_display import PARAMETER_PAGES
from app.live_display import live_state,live_frame
from app.navigation import CONTROL_PAGES


class ControlDisplayTests(unittest.TestCase):
    setUp=live_tests.LiveDisplayTests.setUp
    receive=live_tests.LiveDisplayTests.receive
    submit=live_tests.LiveDisplayTests.submit
    def test_all_bus_parameter_counters_update_without_audio_clock_budget(self):
        a=self.a
        for level in range(3):
            a.control_level=level
            for page in CONTROL_PAGES:
                with self.subTest(level=level,page=page):
                    a.page=page;a.clock_phase=0;first=self.submit()
                    a.clock_phase=396;second=self.submit()
                    self.assertNotEqual(first,second)
                    a.clock_phase=768;self.assertEqual(first,self.submit())
    def test_sound_knob_and_page_changes_render_during_playback(self):
        a=self.a;a.page='PAD';a.control_level=2
        before=self.submit();a.rotate(5);self.assertNotEqual(before,self.submit())
        a.button('NAV RIGHT',True);self.assertNotEqual(before,self.submit())
        a.page='TEMPO';before=self.submit();a.rotate(5)
        self.assertNotEqual(before,self.submit())
    def test_control_snapshots_are_small_immutable_and_survive_view_changes(self):
        a=self.a
        for page in PARAMETER_PAGES:
            a.page=page;state=live_state(a);saved=copy.deepcopy(state)
            a.track()['gain']+=1;a.clock_phase+=24
            self.assertEqual(state,saved)
            self.assertLess(len(pickle.dumps(state)),1024)
            self.assertEqual(self.submit(),live_frame(live_state(a)))
        a.page='PAD';self.assertTrue(self.worker.submit(live_state(a)))
        self.worker.invalidate();self.assertIsNone(self.receive_discarded())
        a.page='MIXER';self.assertEqual(self.submit(),live_frame(live_state(a)))
    def receive_discarded(self):
        import time
        deadline=time.monotonic()+3
        while self.worker.busy and time.monotonic()<deadline:
            self.assertIsNone(self.worker.poll());time.sleep(.002)
        self.assertFalse(self.worker.busy)
