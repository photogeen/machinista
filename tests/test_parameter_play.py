import tempfile
import unittest
from app.model import Application
from app.performance import PARAMETER_PLAY_PAGES

class ParameterPlayTests(unittest.TestCase):
    def test_sound_pads_play_without_leaving_parameter_page(self):
        with tempfile.TemporaryDirectory() as root:
            a=Application(root);a.fixed_velocity=False
            # A SAMPLER page requires an actual sample on the destination pad.
            a.project['groups'][0]['pads'][3]['sample']='fixture.wav'
            for page in PARAMETER_PLAY_PAGES:
                with self.subTest(page=page):
                    a.page=page;a.actions=[];a.pad_on(3,87)
                    self.assertEqual(a.page,page);self.assertEqual(a.pad,3)
                    self.assertIn(('hit',(0,3,87)),a.actions)
                    a.release_pad(3)
    def test_keyboard_keeps_sound_focus_and_noteoff_on_parameter_pages(self):
        with tempfile.TemporaryDirectory() as root:
            a=Application(root);a.fixed_velocity=False;a.keyboard_enabled=True;a.pad=2;a.keyboard_root=0
            for page in PARAMETER_PLAY_PAGES:
                with self.subTest(page=page):
                    a.page=page;a.actions=[];a.pad_on(3,87)
                    self.assertEqual(a.page,page);self.assertEqual(a.pad,2)
                    self.assertIn(('midi_note',(3,87,1)),a.actions)
                    self.assertIn(3,a.performance_lights)
                    a.release_pad(3)
                    self.assertTrue(any(k=='note_off' for k,v in a.actions))
    def test_select_is_quiet_and_settings_audition(self):
        with tempfile.TemporaryDirectory() as root:
            a=Application(root);a.page='SAMPLER';a.keyboard_enabled=True
            a.button('SELECT',True);a.actions=[];a.pad_on(4)
            self.assertEqual(a.pad,4);self.assertFalse(any(k in ('hit','midi_note') for k,v in a.actions))
            a.release_pad(4);a.button('SELECT',False)
            a.page='SETTINGS';a.actions=[];a.pad_on(3)
            self.assertTrue(any(k in ('hit','midi_note') for k,v in a.actions))
    def test_filter_can_change_while_note_is_held(self):
        with tempfile.TemporaryDirectory() as root:
            a=Application(root);a.page='SAMPLER';a.sampler_page=2;a.sampler_field=4
            a.pad_on(0);a.rotate(1)
            self.assertEqual(a.track()['sampler']['filter'],'LP2')
            self.assertIn(('hit',(0,0,100)),a.actions)
            self.assertTrue(any(k=='load' and v[2]['sampler']['filter']=='LP2' for k,v in a.actions))
            self.assertIn(0,a.live_notes)
