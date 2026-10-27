import tempfile
import time
import unittest
from app.model import Application
from app.display_budget import DisplayBudget
from app.ni_display import frame
from app.pattern_display import pattern_state,pattern_frame
from app.step_display import StepDisplay,step_state,step_frame

class PatternDisplayTests(unittest.TestCase):
    def setUp(self):
        self.root=tempfile.TemporaryDirectory();self.addCleanup(self.root.cleanup)
        self.a=Application(self.root.name);self.a.double_pattern();self.a.page='PATTERN';self.a.button('ENTER',True)
        self.a.playing=True;self.worker=StepDisplay();self.addCleanup(self.worker.close)
    def receive(self):
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            pixels=self.worker.poll()
            if pixels is not None:return pixels
            time.sleep(.002)
        self.fail('Pattern display worker did not deliver frame')
    def test_follow_and_playhead_progress_even_when_budget_always_refuses(self):
        budget=DisplayBudget();budget.measured(.1);frames=[]
        for phase,first,x in ((0,0,29),(396,16,32),(768,0,29)):
            self.a.clock_phase=phase;self.a.follow_pattern_grid();state=pattern_state(self.a)
            self.assertEqual(state['first'],first+1);self.assertEqual(state['playhead'],x)
            self.assertFalse(budget.available(1,1.006,True));self.assertTrue(self.worker.submit(state))
            pixels=self.receive();self.assertEqual(pixels,bytes(frame(self.a)));frames.append(pixels)
        self.assertNotEqual(frames[0],frames[1]);self.assertEqual(frames[0],frames[2])
    def test_note_selection_and_keyboard_snapshots_keep_original_pixels(self):
        a=self.a;a.put_note(0,0,{'velocity':100,'probability':100,'note':60,'length':24})
        a.grid_notes=True;a.grid_note=60;a.grid_selected=set(a.event_notes());a.message='TEST'
        state=pattern_state(a);expected=bytes(frame(a));self.assertTrue(self.worker.submit(state))
        a.grid_selected.clear();a.message='';a.grid_note=72
        self.assertEqual(self.receive(),expected);self.assertEqual(pattern_frame(state),expected)
    def test_switching_between_step_and_pattern_cannot_publish_stale_frame(self):
        self.assertTrue(self.worker.submit(pattern_state(self.a)));self.worker.invalidate()
        deadline=time.monotonic()+3
        while self.worker.busy and time.monotonic()<deadline:
            self.assertIsNone(self.worker.poll());time.sleep(.002)
        self.assertFalse(self.worker.busy)
        self.a.page='STEP';state=step_state(self.a);self.assertTrue(self.worker.submit(state))
        self.assertEqual(self.receive(),step_frame(state))
