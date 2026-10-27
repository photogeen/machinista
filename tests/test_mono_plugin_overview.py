import copy
import tempfile
import unittest
from unittest.mock import patch
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.mk1_session import Mk1Surface
from app.mk2_surface import Mk2Surface
from app.mk2_display import snapshot, Mk2Renderer
from app.plugin_profiles import profile
from app.mono_instrument_icons import ICONS, kind, overview

SYNTH='urn:machinista:instrument:synth'

class MonoPluginOverviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=Application(self.tmp.name);self.a.control_level=2;self.a.page='PLUGIN'
        self.s=Mk2Surface(self.a,ControllerInputs(self.a))
        self.r=Mk2Renderer();self.addCleanup(self.r.close)
        p=profile(SYNTH)
        self.a.plugin_catalog=[dict(uri=SYNTH,name='Machinista Synth',kind='INSTRUMENT',supported=True,ports=p['parameters']),
            dict(uri='urn:filter',name='Lowpass Filter',kind='EFFECT',supported=True,ports=[]),
            dict(uri='urn:echo',name='Delay',kind='EFFECT',supported=True,ports=[])]
        self.a.track()['plugins']=[dict(uri=SYNTH,kind='INSTRUMENT',controls={},bypass=False),
            dict(uri='urn:filter',kind='EFFECT',controls={}),dict(uri='urn:echo',kind='EFFECT',controls={})]
    def press(self,key):self.s.button(key,True);self.s.button(key,False)
    def crop(self,p,x,y,w,h):return b''.join(p[yy*256+x:yy*256+x+w] for yy in range(y,y+h))

    def test_numeric_bank_patch_and_right_names_survive_first_page_icon(self):
        with patch('app.plugin_profiles.names',return_value=('Factory Bank Name','Soft Saw Keys')):
            state=snapshot(self.s)
        self.assertEqual(state['fields'][0],('BANK','1'))
        self.assertEqual(state['fields'][1],('PATCH','1'))
        self.assertEqual(state['plugin_names'],('Factory Bank Name','Soft Saw Keys'))
        self.assertEqual(state['mono_plugin']['icon'],'synth')
        with patch('app.synth_display.draw') as draw:
            left,right=self.r.draw(state)
            draw.assert_not_called()  # First-page OSC levels must not overwrite icon/names.
        without=dict(state);without.pop('mono_plugin');without.pop('synth_graph',None)
        baseline=self.r.draw(without)
        self.assertEqual(right,baseline[1])
        self.assertEqual(self.crop(left,2,46,252,15),self.crop(baseline[0],2,46,252,15))
        expected=b''.join(row.encode().translate(bytes.maketrans(b'01',b'\x00\x01')) for row in ICONS['synth'])
        self.assertEqual(self.crop(left,17,25,32,20),expected)

    def test_only_loaded_neighbours_show_arrows(self):
        for index,flags in ((0,(False,True)),(1,(True,True)),(2,(True,False))):
            self.a.plugin_slot=index
            state=snapshot(self.s);item=state['mono_plugin'];self.assertEqual((item['left'],item['right']),flags)
            left,_=self.r.draw(state)
            self.assertEqual(bool(any(self.crop(left,3,31,4,7))),flags[0])
            self.assertEqual(bool(any(self.crop(left,248,31,4,7))),flags[1])
        self.a.track()['plugins']=self.a.track()['plugins'][:1];self.a.plugin_slot=0
        item=snapshot(self.s)['mono_plugin'];self.assertFalse(item['left']);self.assertFalse(item['right'])

    def test_master_arrows_and_f7_f8_choose_same_slots_without_model_mutation(self):
        before=copy.deepcopy(self.a.project);actions=list(self.a.actions)
        self.a.plugin_param=24
        self.press('MASTER RIGHT');self.assertEqual((self.a.plugin_slot,self.a.plugin_param),(1,0))
        self.press('DISPLAY 8');self.assertEqual(self.a.plugin_slot,2)
        self.press('MASTER RIGHT');self.assertEqual((self.a.page,self.a.plugin_slot),('PLUGIN',2))
        self.press('MASTER LEFT');self.assertEqual(self.a.plugin_slot,1)
        self.press('DISPLAY 7');self.assertEqual(self.a.plugin_slot,0)
        self.press('MASTER LEFT');self.assertEqual(self.a.plugin_slot,0)
        self.assertEqual(before,self.a.project);self.assertEqual(actions,self.a.actions)
        self.s.button('MASTER RIGHT',True);self.s.button('MASTER RIGHT',True)
        self.assertEqual(self.a.plugin_slot,1);self.s.button('MASTER RIGHT',False)
        self.assertNotIn('NAV RIGHT',self.a.held_buttons)

    def test_f8_still_opens_add_plugin_after_last_slot(self):
        self.a.plugin_slot=2
        self.press('DISPLAY 8')
        self.assertEqual((self.a.page,self.a.plugin_slot),('PLUGIN BROWSE',3))
        self.assertEqual(len(self.a.track()['plugins']),3)

    def test_sample_source_and_effect_chain_both_directions(self):
        a=self.a;a.track()['sample']='missing-fixture.wav';a.track()['plugins']=a.track()['plugins'][1:];a.page='SAMPLER'
        item=snapshot(self.s)['mono_plugin'];self.assertTrue(item['source']);self.assertTrue(item['right'])
        self.press('DISPLAY 8');self.assertEqual((a.page,a.plugin_slot),('PLUGIN',0))
        self.assertTrue(snapshot(self.s)['mono_plugin']['left'])
        self.press('MASTER LEFT');self.assertEqual(a.page,'SAMPLER')
        self.press('DISPLAY 7');self.assertEqual(a.page,'SAMPLER')

    def test_audio_loop_has_visible_slot_shortcuts(self):
        a=self.a;a.track()['sample']='fixture.wav';a.track()['plugins']=a.track()['plugins'][1:];a.page='AUDIO LOOP'
        a.track()['playback_mode']='AUDIO'
        self.assertEqual(self.s.softkeys()[6:],('<','>'))
        self.press('DISPLAY 8');self.assertEqual(a.page,'PLUGIN')
        self.press('DISPLAY 7');self.assertEqual(a.page,'AUDIO LOOP')

    def test_other_pages_and_shift_actions_remain_available(self):
        self.a.plugin_param=8;self.assertNotIn('mono_plugin',snapshot(self.s))
        with patch('app.synth_display.draw',wraps=__import__('app.synth_display',fromlist=['draw']).draw) as draw:
            self.r.draw(snapshot(self.s));self.assertEqual(draw.call_count,1)
        self.a.page='CHANNEL';self.a.channel_page=0
        self.press('DISPLAY 8');self.assertEqual(self.a.page,'GROOVE')
        self.a.page='PLUGIN';self.a.plugin_param=0;self.a.shift=True
        self.press('MASTER RIGHT');self.assertEqual(self.a.plugin_param,1);self.assertEqual(self.a.plugin_slot,0)
        self.a.shift=False;self.press('DISPLAY 6');self.assertEqual(self.a.page,'PLUGIN')
        self.a.track()['plugins']=[];self.a.page='CHANNEL';self.press('DISPLAY 6')
        self.assertEqual(self.a.page,'PLUGIN BROWSE')

    def test_mk1_f7_f8_and_its_confirmation_binding_remain_separate(self):
        self.s=Mk1Surface(self.a,ControllerInputs(self.a))
        self.press('DISPLAY 8');self.assertEqual(self.a.plugin_slot,1)
        self.press('DISPLAY 7');self.assertEqual(self.a.plugin_slot,0)
        self.assertIn('mono_plugin',snapshot(self.s))
        self.a.page='PLUGIN BROWSE';self.assertIsNotNone(self.s.confirm_action())

    def test_scope_isolation_and_empty_chain(self):
        self.a.control_level=1;self.a.plugin_slot=0
        self.assertIsNone(overview(self.a));self.press('MASTER RIGHT');self.assertEqual(self.a.page,'PLUGIN')
        self.assertNotIn('mono_plugin',snapshot(self.s))
        self.a.plugin_target()['plugins']=[dict(uri='urn:echo',kind='EFFECT',controls={})]
        self.assertEqual(snapshot(self.s)['mono_plugin']['name'],'Delay')
        self.a.control_level=2;self.a.plugin_slot=0
        self.assertEqual(snapshot(self.s)['mono_plugin']['name'],'Machinista Synth')

    def test_mk3_does_not_receive_monochrome_state(self):
        from app.mk3_surface import Mk3Surface
        from app.mk3_state import snapshot as color_snapshot
        s=Mk3Surface(self.a,ControllerInputs(self.a))
        state=color_snapshot(s);self.assertNotIn('mono_plugin',state);self.assertIn('chain_cards',state)

    def test_f8_label_follows_loaded_chain_and_preserves_shift_actions(self):
        for surface_type in (Mk1Surface,Mk2Surface):
            self.s=surface_type(self.a,ControllerInputs(self.a))
            self.a.page='PLUGIN'
            for index,expected in ((0,'>'),(1,'>'),(2,'ADD PLUG')):
                self.a.plugin_slot=index
                self.assertEqual(self.s.softkeys()[7],expected)
                self.assertEqual(snapshot(self.s)['keys'][7],expected)
            self.a.shift=True
            self.assertNotEqual(self.s.softkeys()[7],'ADD PLUG')
            self.a.shift=False
            self.a.track()['sample']='fixture.wav';self.a.page='SAMPLER'
            self.assertEqual(self.s.softkeys()[7],'>')
        self.a.track()['plugins']=[]
        self.assertEqual(self.s.softkeys()[7],'ADD PLUG')
        self.a.page='AUDIO LOOP';self.a.track()['playback_mode']='AUDIO'
        self.assertEqual(self.s.softkeys()[7],'ADD PLUG')
        self.a.page='CHANNEL';self.assertEqual(self.s.softkeys()[7],'>')

    def test_channel_wide_graphic_preserves_right_route_title_and_footers(self):
        for surface_type in (Mk1Surface,Mk2Surface):
            self.s=surface_type(self.a,ControllerInputs(self.a))
            self.a.page='CHANNEL';self.a.channel_page=0
            state=snapshot(self.s);self.assertEqual(state['mono_channel_art'],'synth')
            left,right=self.r.draw(state)
            plain=dict(state);plain.pop('mono_channel_art')
            baseline=self.r.draw(plain)
            self.assertEqual(right,baseline[1])
            self.assertEqual(self.crop(left,2,1,252,22),self.crop(baseline[0],2,1,252,22))
            self.assertEqual(self.crop(left,2,46,252,15),self.crop(baseline[0],2,46,252,15))
            self.assertTrue(all(left[25*256+x] for x in range(4,108)))
        self.a.channel_page=1;self.assertNotIn('mono_channel_art',snapshot(self.s))

    def test_channel_classification_handles_sample_empty_effect_and_group_routing(self):
        self.a.page='PAD';self.a.channel_page=0
        self.a.track()['plugins']=[]
        state=snapshot(self.s);self.assertIsNone(state['mono_channel_art'])
        left,_=self.r.draw(state);self.assertFalse(any(self.crop(left,2,24,252,22)))
        self.a.track()['plugins']=[dict(uri='urn:echo',kind='EFFECT',controls={})]
        self.assertEqual(snapshot(self.s)['mono_channel_art'],'delay')
        self.a.track()['sample']='fixture.wav'
        state=snapshot(self.s);self.assertIsNone(state['mono_channel_art'])
        self.assertEqual(state['sound_wave'][0],'fixture.wav')
        with patch('app.fokus_mk2.sample_wave') as wave:
            self.r.draw(state);self.assertEqual(wave.call_count,1)
        self.a.track()['sample']=None
        self.a.project['groups'][1]['plugins']=[dict(uri=SYNTH,kind='INSTRUMENT',controls={})]
        self.a.track()['routing']={'midi_target':'GROUP 1'}
        self.assertEqual(snapshot(self.s)['mono_channel_art'],'synth')
        self.a.project['groups'][1]['plugins']=[]
        self.a.project['groups'][1]['routing']={'midi_target':'GROUP 1'}
        self.assertEqual(snapshot(self.s)['mono_channel_art'],'delay')
        self.a.track()['routing']={'midi_target':'GROUP -1'}
        self.assertEqual(snapshot(self.s)['mono_channel_art'],'delay')
        self.a.track()['zones']=[{}];self.assertIsNone(snapshot(self.s)['mono_channel_art'])

    def test_icons_are_native_binary_and_category_specific(self):
        for rows in ICONS.values():
            self.assertEqual(len(rows),20)
            self.assertTrue(all(len(row)==32 and set(row)<={'0','1'} for row in rows))
        for uri,name,k,expected in (('urn:dexed','Dexed','INSTRUMENT','fm'),('','OB-Xd','INSTRUMENT','synth'),
                ('','Filter','EFFECT','filter'),('','Delay','EFFECT','delay'),('','Reverb','EFFECT','reverb')):
            self.assertEqual(kind(uri,name,k),expected)
