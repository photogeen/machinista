import tempfile
import unittest
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.mk1_session import Mk1Surface
from app.mk2_surface import Mk2Surface


class TapTempoTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=Application(self.tmp.name);self.inputs=ControllerInputs(self.a)

    def test_full_size_hardware_tap_shortcut_is_global_and_keeps_tempo_overlay(self):
        a=self.a
        for cls in (Mk1Surface,Mk2Surface):
            s=cls(a,self.inputs)
            for page in ('PAD','SAMPLER','SETTINGS','BROWSE','CHOP','LIVE FX','PATTERN GRID'):
                with self.subTest(controller=cls.source,page=page):
                    a.page=page;a.taps=[];a.project['tempo']=120
                    s.master_mode='TEMPO';s.master_page=page
                    s.button('SHIFT',True)
                    for stamp in (10,10.6,11.2):
                        a.input_timestamp=stamp
                        s.button('NOTE REPEAT',True);s.button('NOTE REPEAT',False)
                    s.button('SHIFT',False)
                    self.assertEqual(a.project['tempo'],100)
                    self.assertEqual(a.page,page);self.assertEqual(s.master_mode,'TEMPO')
                    self.assertNotIn('NOTE REPEAT',a.mode_origins)
                    self.assertFalse(s.tap_tempo_held)

    def test_mikro_shift_enter_works_in_workspaces_that_consume_enter(self):
        a=self.a
        for page in ('SETTINGS','BROWSE','CHOP','LIVE FX','PAD CONFIG','PATTERN GRID'):
            with self.subTest(page=page):
                a.page=page;a.taps=[]
                self.inputs.button('mikro','SHIFT',True)
                for stamp in (20,20.4,20.8):
                    a.input_timestamp=stamp
                    self.inputs.button('mikro','ENTER',True);self.inputs.button('mikro','ENTER',False)
                self.inputs.button('mikro','SHIFT',False)
                self.assertEqual(a.project['tempo'],150);self.assertEqual(a.page,page)

    def test_shift_release_before_tap_release_and_plain_note_repeat(self):
        s=Mk1Surface(self.a,self.inputs)
        s.button('SHIFT',True);s.button('NOTE REPEAT',True)
        s.button('SHIFT',False);s.button('NOTE REPEAT',False)
        self.assertFalse(self.inputs.buttons);self.assertFalse(s.tap_tempo_held)
        s.button('NOTE REPEAT',True);self.assertEqual(self.a.page,'NOTE REPEAT')
        s.button('NOTE REPEAT',False);self.assertEqual(self.a.page,'PAD')

    def test_tap_uses_input_time_resets_after_pause_and_rejects_bounce(self):
        a=self.a
        for stamp in (30,30.01,30.5,31):
            a.input_timestamp=stamp;a.button('TAP',True)
        self.assertEqual(a.taps,[30,30.5,31]);self.assertEqual(a.project['tempo'],120)
        a.input_timestamp=35;a.button('TAP',True)
        self.assertEqual(a.taps,[35]);self.assertEqual(a.project['tempo'],120)

    def test_tempo_feedback_is_visible_without_covering_fx_pads(self):
        from app.mk2_display import snapshot,Mk2Renderer
        a=self.a;s=Mk1Surface(a,self.inputs);a.open_live_fx()
        renderer=Mk2Renderer();self.addCleanup(renderer.close)
        before=renderer(snapshot(s))
        a.input_timestamp=20;a.button('TAP',True)
        after=renderer(snapshot(s))
        self.assertNotEqual(before[0],after[0]);self.assertEqual(before[1],after[1])
