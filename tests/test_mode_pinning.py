"""Controller transitions: pinning is separate from SHIFT playing shortcuts."""
import tempfile
import unittest
from app.model import Application


class ModePinningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = Application(self.temp.name)

    def tap(self, key):
        self.app.button(key, True)
        self.app.button(key, False)

    def test_four_modes_share_hold_pin_close_reopen_unpin(self):
        a = self.app;a.controller_source='mk2'
        for key, page in [('SCENE', 'SCENE'), ('PATTERN', 'PATTERN'),
                          ('PAD MODE', 'PAD CONFIG'), ('VIEW', 'VIEW NAV')]:
            with self.subTest(key=key):
                a.page = 'BROWSE'
                a.button(key, True)
                self.assertEqual(a.page, page)
                a.button(key, False)
                self.assertEqual(a.page, 'BROWSE')
                a.button(key, True)
                self.tap('MAIN')
                a.button(key, False)
                self.assertEqual(a.page, page)
                self.assertIn(key, Application(self.temp.name).pinned_modes)
                self.tap(key)
                self.assertEqual(a.page, 'BROWSE')
                self.tap(key)
                self.assertEqual(a.page, page)
                a.button(key, True)  # close, then reopen while holding to unpin
                a.button(key, False)
                a.button(key, True)
                self.tap('MAIN')
                a.button(key, False)
                self.assertEqual(a.page, 'BROWSE')
                self.assertNotIn(key, Application(self.temp.name).pinned_modes)

    def test_unpinned_pattern_can_exit_after_editor_back(self):
        a=self.app;a.page='SAMPLER'
        a.button('PATTERN',True);self.tap('ENTER');a.button('PATTERN',False)
        self.assertEqual(a.page,'PATTERN GRID')
        self.tap('PATTERN');self.assertEqual(a.page,'PATTERN')
        self.tap('PATTERN');self.assertEqual(a.page,'SAMPLER')
        self.assertNotIn('PATTERN',a.pinned_modes)
        self.assertNotIn('PATTERN',a.mode_origins)

    def test_full_size_controllers_exit_unpinned_pattern_after_editor(self):
        from app.controller_inputs import ControllerInputs
        from app.mk2_surface import Mk2Surface
        from app.mk1_session import Mk1Surface
        for surface_type in (Mk2Surface,Mk1Surface):
            with self.subTest(surface=surface_type.__name__),tempfile.TemporaryDirectory() as root:
                a=Application(root);a.page='SAMPLER'
                surface=surface_type(a,ControllerInputs(a))
                def tap(name):surface.button(name,True);surface.button(name,False)
                surface.button('PATTERN',True);surface.softkey(4)
                surface.button('PATTERN',False)
                self.assertEqual(a.page,'PATTERN GRID')
                tap('PATTERN');self.assertEqual(a.page,'PATTERN')
                tap('PATTERN');self.assertEqual(a.page,'SAMPLER')
                self.assertNotIn('PATTERN',a.pinned_modes)
                surface.button('PATTERN',True);surface.softkey(0)
                surface.button('PATTERN',False)
                self.assertEqual(a.page,'PATTERN');self.assertIn('PATTERN',a.pinned_modes)
                tap('PATTERN');self.assertEqual(a.page,'SAMPLER')
                surface.button('PATTERN',True);surface.softkey(0)
                surface.button('PATTERN',False)
                self.assertEqual(a.page,'SAMPLER');self.assertNotIn('PATTERN',a.pinned_modes)

    def test_stale_self_origin_does_not_trap_pinned_pattern(self):
        a=self.app;a.page='PATTERN';a.mode_origins['PATTERN']='PATTERN'
        a.pinned_modes.add('PATTERN')
        self.tap('PATTERN');self.assertEqual(a.page,'PAD')
        self.assertIn('PATTERN',a.pinned_modes)

    def test_direct_mode_page_can_close_without_changing_pin(self):
        for mode,page in (('PATTERN','PATTERN'),('SCENE','SCENE'),('PAD MODE','PAD CONFIG')):
            with self.subTest(mode=mode):
                a=self.app;a.page=page;a.mode_origins.clear();a.pinned_modes.clear()
                self.tap(mode);self.assertEqual(a.page,'PAD')
                self.assertFalse(a.pinned_modes)

    def test_shift_does_not_pin_view_in_navigation_or_wave(self):
        a = self.app
        for origin in ('PAD', 'SAMPLE EDIT', 'CHOP'):
            with self.subTest(origin=origin):
                a.page = origin
                a.button('VIEW', True)
                self.tap('SHIFT')
                self.assertNotIn('VIEW', a.pinned_modes)
                a.button('VIEW', False)
                self.assertEqual(a.page, origin)
                self.assertFalse(a.wave_view())

    def test_shift_pad_mode_toggles_keyboard_and_survives_release(self):
        a = self.app
        for origin in ('PAD', 'SAMPLER', 'PATTERN GRID', 'SAMPLE EDIT'):
            with self.subTest(origin=origin):
                a.page = origin
                a.keyboard_enabled = False
                a.velocities16 = True
                a.button('SHIFT', True)
                self.tap('PAD MODE')
                self.assertEqual(a.page, origin)
                self.assertTrue(a.keyboard_enabled)
                self.assertFalse(a.velocities16)
                self.tap('PAD MODE')
                self.assertFalse(a.keyboard_enabled)
                a.button('SHIFT', False)
                self.assertEqual(a.page, origin)
                self.assertEqual(a.pinned_modes, set())

    def test_shift_pattern_uses_normal_mode_toggle_and_keeps_pin(self):
        a = self.app
        a.page = 'SAMPLER'
        a.button('PATTERN', True)
        self.tap('MAIN')
        a.button('PATTERN', False)
        a.button('SHIFT', True)
        self.tap('PATTERN')
        self.assertEqual(a.page, 'SAMPLER')
        self.tap('PATTERN')
        self.assertEqual(a.page, 'PATTERN')
        self.assertIn('PATTERN', a.pinned_modes)
        a.button('SHIFT', False)

    def test_wave_main_pin_unpin_and_settings_and_mixer_shortcuts(self):
        a = self.app;a.controller_source='mk2'
        a.page = 'SAMPLE EDIT'
        a.button('VIEW', True)
        self.tap('MAIN')
        a.button('VIEW', False)
        self.assertTrue(a.wave_view())
        self.tap('VIEW')
        self.assertFalse(a.wave_view())
        a.button('VIEW', True)
        self.tap('MAIN')
        a.button('VIEW', False)
        self.assertFalse(a.wave_view())
        self.assertNotIn('VIEW', a.pinned_modes)
        a.page = 'PAD'
        a.button('SHIFT', True)
        self.tap('MAIN')
        self.assertEqual(a.page, 'SETTINGS')
        a.button('SHIFT', False)
        a.page = 'PAD'
        a.button('SHIFT', True)
        self.tap('VIEW')
        a.button('SHIFT', False)
        self.assertEqual(a.page, 'MIXER')
        self.assertNotIn('VIEW', a.pinned_modes)
