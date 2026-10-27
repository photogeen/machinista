import copy,tempfile,unittest
from unittest.mock import patch
from pathlib import Path
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.mk3_surface import Mk3Surface
from app.mk3_state import snapshot,chain_state
from app.mk3_display import Mk3Renderer

class ChainCardsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=Application(self.tmp.name);self.a.control_level=2
        self.s=Mk3Surface(self.a,ControllerInputs(self.a));self.r=Mk3Renderer();self.addCleanup(self.r.close)
    def press(self,key):self.s.button(key,True);self.s.button(key,False)
    def plugins(self):
        self.a.track()['plugins']=[dict(uri='urn:machinista:instrument:synth',kind='INSTRUMENT',controls={}),dict(uri='urn:filter',kind='EFFECT',controls={}),dict(uri='urn:delay',kind='EFFECT',controls={})]
    def test_channel_entry_has_no_phantom_sampler(self):
        self.a.page='CHANNEL';self.press('PLUG-IN');self.assertEqual(self.a.page,'PLUGIN BROWSE')
        self.plugins();self.a.page='CHANNEL';self.press('PLUG-IN')
        state=snapshot(self.s);self.assertEqual(self.a.page,'PLUGIN');self.assertFalse(self.a.sampler_slot_present())
        self.assertEqual(state['chain_cards']['selected'],0);self.assertEqual(state['chain_cards']['items'][0]['art'],'machinista-synth')
        self.a.track()['plugins'][0]['kind']='EFFECT';self.a.page='CHANNEL';self.press('PLUG-IN')
        self.assertEqual(self.a.page,'PLUGIN');self.assertEqual(snapshot(self.s)['chain_cards']['items'][0]['art'],'generic-filter')
    def test_sample_source_is_numbered_and_4d_moves_to_effect_and_back(self):
        self.a.track()['sample']='sample.wav';self.a.track()['plugins']=[dict(uri='urn:filter',kind='EFFECT',controls={})]
        self.press('PLUG-IN');self.assertEqual(self.a.page,'SAMPLER')
        state=snapshot(self.s);self.assertEqual([v['name'] for v in state['chain_cards']['items']],['SAMPLER','urn:filter'])
        self.press('MASTER RIGHT');self.assertEqual((self.a.page,self.a.plugin_slot),('PLUGIN',0))
        self.press('MASTER LEFT');self.assertEqual(self.a.page,'SAMPLER')
    def test_all_four_directions_select_slots_and_keep_audio_untouched(self):
        self.plugins();self.press('PLUG-IN');project=copy.deepcopy(self.a.project);actions=list(self.a.actions)
        for key,index in [('MASTER RIGHT',1),('MASTER DOWN',2),('MASTER DOWN',2),('MASTER UP',1),('MASTER LEFT',0),('MASTER LEFT',0)]:
            self.a.plugin_param=16;self.press(key);self.assertEqual(self.a.plugin_slot,index)
            self.assertEqual(chain_state(self.s)['selected'],index)
        self.assertEqual(project,self.a.project);self.assertEqual(actions,self.a.actions)
        self.s.button('MASTER RIGHT',True);self.s.button('MASTER RIGHT',True);self.assertEqual(self.a.plugin_slot,1)
        self.s.button('MASTER RIGHT',False)
    def test_effect_only_sound_present_and_external_input_retained(self):
        self.a.track()['plugins']=[dict(uri='urn:filter',kind='EFFECT',controls={})]
        self.a.track().setdefault('routing',{})['input']='EXT. 1/2';before=copy.deepcopy(self.a.track())
        self.assertTrue(self.a.sound_present(0));self.assertFalse(self.a.sound_present(1))
        from app.leds import led_report,DIM,OFF
        self.a.page='PAD';self.a.pad=2
        report=led_report(self.a,{(slot,'orange'):slot for slot in range(16)},now=1)
        self.assertEqual(report[1],DIM);self.assertEqual(report[2],OFF)
        self.a.pad=0
        self.press('PLUG-IN');self.r.images(snapshot(self.s));self.assertEqual(before,self.a.track())
    def test_animation_is_renderer_only_bounded_and_context_safe(self):
        self.plugins();self.press('PLUG-IN')
        with patch('app.mk3_display.time.monotonic',return_value=10):first=self.r.images(snapshot(self.s))
        self.press('MASTER RIGHT');state=snapshot(self.s)
        with patch('app.mk3_display.time.monotonic',return_value=11):start=self.r.images(state)
        self.assertTrue(self.r.needs_refresh)
        with patch('app.mk3_display.time.monotonic',return_value=11.09):middle=self.r.images(state)
        self.assertNotEqual(start[0].tobytes(),middle[0].tobytes())
        # Slot names and footer parameters remain stationary through the slide.
        self.assertEqual(start[0].crop((8,86,472,110)).tobytes(),middle[0].crop((8,86,472,110)).tobytes())
        self.assertEqual(start[0].crop((0,216,480,272)).tobytes(),middle[0].crop((0,216,480,272)).tobytes())
        with patch('app.mk3_display.time.monotonic',return_value=11.3):self.r.images(state)
        self.assertIsNone(self.r.chain_transition)
        state['chain_cards']['context']=(999,2,0,1);self.r.images(state);self.assertIsNone(self.r.chain_transition)
    def test_single_plugin_no_navigation_arrows_and_right_preset_names_survive(self):
        self.plugins();self.a.track()['plugins']=self.a.track()['plugins'][:1]
        from app.plugin_profiles import profile
        uri='urn:machinista:instrument:synth';ports=profile(uri)['parameters']
        self.a.plugin_catalog=[dict(uri=uri,name='Machinista Synth',kind='INSTRUMENT',supported=True,ports=ports)]
        self.press('PLUG-IN')
        state=snapshot(self.s);self.assertEqual(len(state['chain_cards']['items']),1)
        left,right=self.r.images(state)
        from PIL import ImageColor
        from app.mk3_graphics import BG
        for box in [(10,140,26,170),(454,140,470,170)]:
            self.assertEqual(left.crop(box).getextrema(),tuple((v,v) for v in ImageColor.getrgb(BG)))
        self.assertIn('plugin_names',state);self.assertTrue(any(lo!=hi for lo,hi in right.crop((12,62,468,182)).getextrema()))

    def test_chain_art_only_on_first_page_later_pages_restore_both_displays(self):
        self.plugins()
        from app.plugin_profiles import profile
        uri='urn:machinista:instrument:synth';ports=profile(uri)['parameters']
        self.a.plugin_catalog=[dict(uri=uri,name='Machinista Synth',kind='INSTRUMENT',supported=True,ports=ports)]
        self.press('PLUG-IN')
        first=snapshot(self.s);self.assertIn('chain_cards',first)
        self.r.images(first)
        self.s.change_page(1);later=snapshot(self.s)
        self.assertEqual(later['page_index'],1);self.assertNotIn('chain_cards',later)
        with patch.object(self.r,'synth_plot',wraps=self.r.synth_plot) as graph:
            left,right=self.r.images(later)
            self.assertEqual(graph.call_count,1)
            # Detailed oscillator/envelope graph is back on the left display.
            self.assertEqual(graph.call_args.args[0].image.tobytes(),self.r.cached_images[0].tobytes())
        self.assertIsNone(self.r.chain_transition)
        self.assertEqual(len(later['fields']),8)
        self.s.change_page(-1);self.assertIn('chain_cards',snapshot(self.s))
        self.a.track()['plugins']=[];self.a.track()['sample']='fixture.wav'
        self.a.page='SAMPLER';self.a.sampler_page=0
        self.assertIn('chain_cards',snapshot(self.s))
        self.s.change_page(1);sampler=snapshot(self.s)
        self.assertNotIn('chain_cards',sampler);self.assertIn('sampler_values',sampler)

    def test_first_page_bank_and_patch_names_are_not_overpainted_by_osc_levels(self):
        self.plugins()
        from app.plugin_profiles import profile
        uri='urn:machinista:instrument:synth';ports=profile(uri)['parameters']
        self.a.plugin_catalog=[dict(uri=uri,name='Machinista Synth',kind='INSTRUMENT',supported=True,ports=ports)]
        self.press('PLUG-IN');state=snapshot(self.s)
        self.assertIn('levels',state['synth_graph']);self.assertIn('plugin_names',state)
        state['plugin_names']=('Synth Keys','BRASS Bright Stab')
        with patch.object(self.r,'synth_plot',side_effect=AssertionError('unused oscillator meter')):
            left,right=self.r.images(state)
        self.r.cached_images=None
        without_graph=dict(state);without_graph.pop('synth_graph')
        self.assertEqual(right.tobytes(),self.r.images(without_graph)[1].tobytes())
        renamed=dict(without_graph,plugin_names=('Synth Pads','Cloud Veil'))
        self.assertNotEqual(right.crop((12,62,468,182)).tobytes(),self.r.images(renamed)[1].crop((12,62,468,182)).tobytes())
