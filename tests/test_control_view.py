import tempfile
import unittest
from app.model import Application
from app.ni_display import frame

class ControlViewTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.a=Application(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def sampler(self):
        a=self.a;a.track()['sample']='fixture.wav';a.button('NAV',True);a.button('F3',True);a.button('NAV',False)
        self.assertEqual(a.page,'SAMPLER')
    def test_default_output_has_pan_routing_and_aux_pages(self):
        a=self.a;a.button('NAV RIGHT',True);a.rotate(10)
        self.assertEqual(a.track()['routing']['pan'],10);self.assertEqual(a.track()['gain'],80)
        self.assertEqual(a.automation_descriptor(),(0,'routing',-1,'pan'))
        a.button('NAV',True);a.button('NAV RIGHT',True);a.button('NAV',False)
        self.assertEqual((a.page,a.channel_page),('CHANNEL',1))
        self.assertEqual(a.softkeys(),('MASTER','GROUP','SOUND'))
    def test_level_tabs_restore_sound_sampler_page_and_parameter(self):
        a=self.a;self.sampler();a.button('NAV',True)
        a.button('NAV RIGHT',True);a.button('NAV RIGHT',True);a.button('NAV',False)
        self.assertEqual(a.sampler_page,2)
        for i in range(5):a.button('NAV RIGHT',True)
        self.assertEqual(a.sampler_field,5)
        a.button('F2',True);self.assertEqual((a.control_level,a.page),(1,'PAD'))
        a.button('F1',True);self.assertEqual((a.control_level,a.page),(0,'PAD'))
        a.button('F3',True)
        self.assertEqual((a.control_level,a.page,a.sampler_page,a.sampler_field),(2,'SAMPLER',2,5))
        self.assertEqual(a.active_softkeys(),{2})
    def test_return_from_sampling_and_browse_restores_control_view(self):
        a=self.a;self.sampler();a.sampler_page=2;a.sampler_field=5
        for key in ('BROWSE','SAMPLING'):
            a.button(key,True);a.button(key,False);a.button(key,True);a.button(key,False)
            self.assertEqual(a.page,'SAMPLER');self.assertEqual((a.sampler_page,a.sampler_field),(2,5))
        self.assertEqual(len(frame(a)),8192)
    def test_nav_release_without_selection_change_keeps_current_view(self):
        a=self.a;self.sampler();a.sampler_page=3;a.sampler_field=2
        a.button('NAV',True);a.button('NAV',False)
        self.assertEqual((a.page,a.sampler_page,a.sampler_field),('SAMPLER',3,2))
        a.button('NAV RIGHT',True);self.assertEqual(a.sampler_field,3)
        a.button('NAV',True);a.button('NAV RIGHT',True);a.button('NAV',False)
        self.assertEqual((a.sampler_page,a.sampler_field),(4,0))
    def test_plugin_tabs_do_not_remove_and_ni_bypass_chord_works(self):
        a=self.a;a.track()['sample']='fixture.wav';a.track()['plugins']=[{'uri':'urn:test','kind':'EFFECT','controls':{},'bypass':False}]
        a.page='PLUGIN';a.plugin_slot=0;a.button('F2',True)
        self.assertEqual(a.control_level,1);self.assertEqual(len(a.project['groups'][0]['pads'][0]['plugins']),1)
        a.button('F3',True);self.assertEqual(a.page,'PLUGIN')
        a.button('NAV',True);a.button('SHIFT',True);a.pad_on(13)
        self.assertTrue(a.track()['plugins'][0]['bypass'])
        a.button('SHIFT',False);a.button('NAV',False)
        a.button('SHIFT',True);a.button('BROWSE',True);a.button('SHIFT',False)
        a.rotate(-1);self.assertEqual(a.plugin_browser_index,-1)
        a.button('ENTER',True);self.assertEqual(a.page,'CONFIRM');a.button('F2',True)
        self.assertEqual(a.track()['plugins'],[])
