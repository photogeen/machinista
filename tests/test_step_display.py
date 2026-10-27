import tempfile
import time
import unittest
from app.model import Application
from app.display_budget import DisplayBudget
from app.step_display import StepDisplay,step_state,step_frame

class StepDisplayTests(unittest.TestCase):
    def setUp(self):
        self.root=tempfile.TemporaryDirectory();self.addCleanup(self.root.cleanup)
        self.a=Application(self.root.name);self.a.double_pattern();self.a.page='STEP';self.a.playing=True
        self.worker=StepDisplay();self.addCleanup(self.worker.close)
    def receive(self):
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            pixels=self.worker.poll()
            if pixels is not None:return pixels
            time.sleep(.002)
        self.fail('STEP frame was not delivered')
    def test_bank_counter_and_playhead_continue_with_lcd_budget_blocked(self):
        budget=DisplayBudget();budget.measured(.1)
        for phase,bank in ((0,0),(396,1),(768,0)):
            self.a.clock_phase=phase;self.a.follow_step_view();state=step_state(self.a)
            self.assertEqual(state['bank'],bank)
            self.assertFalse(budget.available(1,1.006,True))
            self.assertTrue(self.worker.submit(state));self.assertEqual(self.receive(),step_frame(state))
        self.assertEqual(self.worker.frames,3)
    def test_snapshot_is_immutable_and_busy_frames_are_dropped(self):
        self.a.put_note(0,0,{'velocity':100,'probability':100,'length':24})
        state=step_state(self.a);self.assertTrue(self.worker.submit(state))
        self.assertFalse(self.worker.submit(state));self.a.bank=1;self.a.message='CHANGED'
        self.assertEqual(self.receive(),step_frame(state))
    def test_view_change_discards_outstanding_old_frame(self):
        self.assertTrue(self.worker.submit(step_state(self.a)));self.worker.invalidate()
        deadline=time.monotonic()+3
        while self.worker.busy and time.monotonic()<deadline:
            self.assertIsNone(self.worker.poll());time.sleep(.002)
        self.assertFalse(self.worker.busy);self.assertEqual(self.worker.frames,0)
        self.a.clock_phase=400;self.a.follow_step_view();state=step_state(self.a)
        self.assertTrue(self.worker.submit(state));self.assertEqual(self.receive(),step_frame(state))
