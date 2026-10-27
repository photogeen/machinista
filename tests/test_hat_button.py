import tempfile
import unittest
from app.hat_button import DebouncedPress, apply_presses
from app.model import Application
from app.devices import AudioDevice

HAT=AudioDevice('hat:wm8960:pcm0','ULTRA','plughw:1,0','plughw:1,0',2,2,'HAT')
USB=AudioDevice('usb:pcm0','USB','plughw:2,0','plughw:2,0')

class HatButtonTests(unittest.TestCase):
    def test_bounce_and_hold_emit_one_press_then_rearm_on_stable_release(self):
        s=DebouncedPress(False,0)
        for pressed,now in ((True,.1),(False,.105),(True,.11),(True,.13)):
            self.assertFalse(s.update(pressed,now))
        self.assertTrue(s.update(True,.151))
        self.assertFalse(s.update(True,3))
        for pressed,now in ((False,3.1),(True,3.11),(False,3.12),(False,3.17)):
            self.assertFalse(s.update(pressed,now))
        self.assertFalse(s.update(True,3.3))
        self.assertTrue(s.update(True,3.35))

    def test_short_spike_and_button_held_at_start_do_not_toggle(self):
        s=DebouncedPress(False,0)
        self.assertFalse(s.update(True,.1));self.assertFalse(s.update(False,.12));self.assertFalse(s.update(False,.3))
        s=DebouncedPress(True,0)
        self.assertFalse(s.update(True,1));self.assertFalse(s.update(False,2));self.assertFalse(s.update(False,2.1))
        self.assertFalse(s.update(True,3));self.assertTrue(s.update(True,3.1))

    def test_toggle_reuses_persistent_speaker_mute_without_changing_sound_or_headphone(self):
        with tempfile.TemporaryDirectory() as root:
            a=Application(root);a.refresh_devices([HAT],[])
            a.actions.clear();project=repr(a.project);hp=a.settings['hat_headphone'];sp=a.settings['hat_speaker']
            apply_presses(a,1)
            self.assertTrue(a.settings['hat_speaker_mute']);self.assertFalse(a.settings['hat_headphone_mute'])
            self.assertEqual(a.settings['hat_headphone'],hp);self.assertEqual(a.settings['hat_speaker'],sp)
            self.assertEqual(a.actions,[('codec_levels',None)]);self.assertEqual(repr(a.project),project)
            self.assertTrue(Application(root).settings['hat_speaker_mute'])
            apply_presses(a,1);self.assertFalse(a.settings['hat_speaker_mute'])
            apply_presses(a,2);self.assertFalse(a.settings['hat_speaker_mute'])
            a.audio=USB;a.actions.clear();apply_presses(a,1)
            self.assertFalse(a.settings['hat_speaker_mute']);self.assertEqual(a.actions,[])

if __name__=='__main__':unittest.main()
