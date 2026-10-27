import copy
from pathlib import Path
import tempfile
import unittest
import wave
from app.model import Application,SETTING_PAGES
from app.ni_display import frame


class ManualNavigationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.app=Application(self.temp.name)
        self.path=Path(self.temp.name)/'samples/test.wav'
        with wave.open(str(self.path),'wb') as w:
            w.setparams((1,2,48000,0,'NONE','not compressed'));w.writeframes(b'\x00\x00'*4800)
        self.app.track().update(sample=str(self.path),start=0,end=4800)
    def tearDown(self):self.temp.cleanup()
    def test_main_contains_standalone_pages_and_nav_uses_channel_and_sampler(self):
        a=self.app
        for page in ('PROJECT','SYSTEM'):
            a.button('SHIFT',True);a.button('MAIN',True);a.button('MAIN',False);a.button('SHIFT',False);a.open_settings('SYSTEM')
            if page=='PROJECT':a.menu=a.setting_entries().index('PROJECT SETTINGS');a.button('ENTER',True)
            a.menu=a.setting_entries().index(page)
            a.button('ENTER',True);self.assertEqual(a.page,page)
        a.button('SCENE',True);a.button('SHIFT',True)
        self.assertEqual(a.softkeys()[1],'SONG')
        a.button('F2',True);a.button('SHIFT',False);a.button('SCENE',False)
        self.assertEqual(a.page,'SONG')
        self.assertNotIn('SONG',a.setting_entries())
        a.page='PAD';a.button('NAV',True);self.assertEqual(a.page,'PARAM NAV')
        a.button('NAV RIGHT',True);a.button('NAV',False);self.assertEqual((a.page,a.channel_page),('CHANNEL',1))
        a.button('NAV',True);a.button('F3',True);a.button('NAV',False)
        self.assertEqual(a.page,'SAMPLER');a.rotate(1);self.assertEqual(a.track()['sampler']['polyphony'],16)
        a.page='PAD';a.button('NAV',True);a.button('F2',True);a.pad_on(13);a.button('NAV',False)
        self.assertEqual(a.page,'CHANNEL')
        a.page='PAD';a.control_level=0;a.button('NAV',True);a.pad_on(14);a.button('NAV',False)
        self.assertEqual(a.page,'GROOVE')
    def test_view_pattern_zoom_directions_and_pinning_persist(self):
        a=self.app;a.controller_source='mk2';a.double_pattern();a.double_pattern();a.actions.clear();before=copy.deepcopy(a.project)
        a.button('VIEW',True);self.assertEqual(a.page,'VIEW NAV')
        a.button('F2',True);a.pad_on(5);self.assertEqual(a.view_count,8)
        a.pad_on(2);self.assertEqual(a.view_first,2)
        a.pad_on(1);self.assertEqual(a.view_count,16)
        a.button('NAV RIGHT',True);a.rotate(1);self.assertEqual(a.view_first,6)
        a.button('MAIN',True);a.button('MAIN',False);a.button('VIEW',False)
        self.assertEqual(a.page,'VIEW NAV');self.assertIn('VIEW',Application(self.temp.name).pinned_modes)
        a.button('VIEW',True);a.button('VIEW',False);self.assertEqual(a.page,'PAD')
        a.button('VIEW',True);a.button('VIEW',False);self.assertEqual(a.page,'VIEW NAV')
        self.assertEqual(a.project,before);self.assertEqual(a.actions,[])
        self.assertEqual(len(frame(a)),8192)
    def test_wave_selection_retained_and_encoder_uses_zoom_or_scroll(self):
        a=self.app;a.controller_source='mk2';a.page='SAMPLE EDIT';a.button('VIEW',True);a.button('F2',True)
        a.pad_on(5);self.assertEqual(a.wave_bounds(4800),(0,2400))
        a.pad_on(1);self.assertEqual(a.wave_bounds(4800),(0,4800))
        a.button('NAV LEFT',True);a.rotate(1);self.assertEqual(a.wave_bounds(4800),(0,2400))
        a.button('NAV RIGHT',True);a.rotate(1);self.assertEqual(a.wave_bounds(4800),(600,3000))
        a.button('VIEW',False);a.button('VIEW',True);self.assertTrue(a.wave_selected)
        a.button('VIEW',False);self.assertEqual(a.page,'SAMPLE EDIT')
        a.button('VIEW',True);a.button('MAIN',True);a.button('MAIN',False);a.button('VIEW',False)
        a.button('VIEW',True);a.button('VIEW',False);self.assertFalse(a.wave_view())
        a.button('VIEW',True);a.button('VIEW',False);self.assertTrue(a.wave_view())
