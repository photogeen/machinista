import tempfile
import unittest
from app.model import Application
from app.performance import PARAMETER_PLAY_PAGES
from app.leds import led_report,OFF,DIM,FULL


class VelocityLevelsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.a=Application(self.temp.name)

    def enable(self):
        a=self.a;a.pad=2;a.button('PAD MODE',True);a.button('F2',True);a.button('F2',False);a.button('PAD MODE',False)
        self.assertTrue(a.velocities16);self.assertFalse(a.fixed_velocity)
        return a

    def test_all_levels_persist_after_leaving_pad_mode_and_on_parameter_pages(self):
        a=self.enable()
        for page in ('PAD','PAD CONFIG','MIXER')+PARAMETER_PLAY_PAGES:
            with self.subTest(page=page):
                a.page=page
                for slot in range(16):
                    a.actions=[];a.pad_on(slot,1 if slot%2 else 127)
                    self.assertIn(('hit',(0,2,round(127*(slot+1)/16))),a.actions)
                    self.assertEqual(a.pad,2)
                    a.release_pad(slot)
                    self.assertIn(('note_off',(0,2,a.track().get('note',38))),a.actions)

    def test_levels_record_to_selected_sound_and_loop_with_velocity(self):
        a=self.enable();a.playing=a.recording=True;a.clock_tick();a.clock_last=None
        for slot in (0,7,15):
            a.pad_on(slot,100);a.release_pad(slot)
            self.assertEqual(a.notes()[(2,a.clock_phase)]['velocity'],round(127*(slot+1)/16))
            for _ in range(24):a.clock_tick()
        self.assertEqual({key[0] for key in a.notes()},{2})
        a.recording=False;a.actions=[]
        for _ in range(384):a.clock_tick()
        velocities={v[2] for k,v in a.actions if k=='hit' and v[:2]==(0,2)}
        self.assertTrue({8,64,127}<=velocities)

    def test_keyboard_fixed_velocity_and_levels_remain_mutually_exclusive(self):
        a=self.enable();a.page='PAD CONFIG';a.button('F3',True);a.button('F3',False)
        self.assertFalse(a.velocities16);self.assertTrue(a.fixed_velocity)
        a.button('F2',True);a.button('F2',False);a.button('F1',True);a.button('F1',False)
        self.assertTrue(a.keyboard_enabled);self.assertFalse(a.velocities16)

    def test_leds_show_all_velocity_pads_for_focused_sound_only(self):
        a=self.enable();a.page='SAMPLER';channels={(slot,'orange'):slot for slot in range(16)}
        a.track().update(sample='kick.wav',start=0,end=100)
        self.assertEqual(list(led_report(a,channels,now=100)[1:17]),[DIM]*16)
        a.pad_on(12);self.assertEqual(led_report(a,channels,now=100)[13],FULL)
        a.release_pad(12);a.track().update(sample=None,end=0)
        self.assertEqual(list(led_report(a,channels,now=100)[1:17]),[OFF]*16)

    def test_shift_pad_mode_disables_velocity_levels_when_enabling_keyboard(self):
        a=self.enable();a.button('SHIFT',True);a.button('PAD MODE',True)
        self.assertTrue(a.keyboard_enabled);self.assertFalse(a.velocities16)
