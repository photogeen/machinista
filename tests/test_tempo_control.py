import tempfile
import unittest
from app.model import Application
from app.ni_display import frame

class TempoControlTests(unittest.TestCase):
    def test_shortcut_coarse_fine_push_bounds_and_persistence(self):
        with tempfile.TemporaryDirectory() as root:
            a=Application(root);a.page='SAMPLER'
            a.button('MAIN',True);a.button('MAIN',False);a.button('F3',True)
            self.assertEqual(a.page,'TEMPO')
            a.rotate(-24);self.assertEqual(a.project['tempo'],96)
            a.button('SHIFT',True);a.rotate(1);a.rotate(1);a.button('SHIFT',False)
            self.assertEqual(a.project['tempo'],96.02)
            a.button('ENCODER PUSH',True);a.rotate(-1);a.button('ENCODER PUSH',False)
            self.assertEqual(a.page,'TEMPO');self.assertFalse(a.encoder_held)
            self.assertEqual(a.project['tempo'],96.01)
            a.rotate(1);self.assertEqual(a.project['tempo'],97.01)
            self.assertEqual(a.display()[1],['97.01 BPM'])
            self.assertEqual(len(frame(a)),8192)
            a.save();self.assertEqual(Application(root).project['tempo'],97.01)
            a.rotate(999);self.assertEqual(a.project['tempo'],240)
            a.button('SHIFT',True);a.rotate(1);self.assertEqual(a.project['tempo'],240)
            a.rotate(-999999);self.assertEqual(a.project['tempo'],40)
            a.button('SHIFT',False);a.button('MAIN',True);self.assertEqual(a.page,'SAMPLER')
    def test_shortcut_does_not_intercept_mode_pinning(self):
        with tempfile.TemporaryDirectory() as root:
            a=Application(root);a.button('SCENE',True);a.button('SHIFT',True);a.button('MAIN',True)
            self.assertEqual(a.page,'SCENE');self.assertIn('SCENE',a.pinned_modes)

    def test_main_master_controls_and_shift_settings_return(self):
        with tempfile.TemporaryDirectory() as root:
            a=Application(root);original_gain=a.track()['gain']
            a.button('MAIN',True);a.button('MAIN',False)
            self.assertEqual(a.softkeys(),('VOLUME','SWING','TEMPO'))
            a.button('F1',True);a.rotate(-5)
            self.assertEqual(a.project['gain'],95);self.assertEqual(a.track()['gain'],original_gain)
            a.button('F2',True);a.rotate(12)
            self.assertEqual(a.project['groove']['amount'],12)
            a.button('SHIFT',True);a.button('MAIN',True);a.button('MAIN',False);a.button('SHIFT',False)
            self.assertEqual(a.page,'SETTINGS');self.assertEqual(a.softkeys(),('AUDIO','MIDI','SYSTEM'))
            a.button('SHIFT',True);a.button('MAIN',True);a.button('MAIN',False);a.button('SHIFT',False)
            self.assertEqual(a.page,'GROOVE');self.assertEqual(a.softkeys(),('VOLUME','SWING','TEMPO'))
            a.button('MAIN',True);self.assertEqual(a.page,'PAD');self.assertEqual(a.control_level,2)
