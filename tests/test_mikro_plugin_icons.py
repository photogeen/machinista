"""Mikro variant B: immutable overview detail and native-pixel drawing."""
import copy
import pickle
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from app.model import Application
from app.control_display import control_state,control_frame
from app.mono_instrument_icons import SMALL_ICONS
from app.plugin_profiles import profile
from app.fokus import control

SYNTH='urn:machinista:instrument:synth'
class MikroPluginIconTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=Application(self.tmp.name);self.a.control_level=2;self.a.page='PLUGIN'
        self.a.plugin_catalog=[dict(uri=SYNTH,name='Machinista Synth',kind='INSTRUMENT',supported=True,ports=profile(SYNTH)['parameters'])]
        self.a.track()['plugins']=[dict(uri=SYNTH,kind='INSTRUMENT',controls={})]
    def crop(self,frame,x,y,w,h):return b''.join(frame[yy*128+x:yy*128+x+w] for yy in range(y,y+h))
    def test_both_mikros_show_native_icon_and_keep_header_footer_pages_and_model(self):
        a=self.a
        for model in ('mikro','mikro_mk2'):
            a.mikro_model=model;before=copy.deepcopy(a.project);actions=list(a.actions)
            with patch('app.plugin_profiles.names',return_value=('Factory','Warm Saw Keys')):
                state=control_state(a)
            self.assertEqual(state['micro_overview'],dict(icon='synth',name='Warm Saw Keys',role='SOUND'))
            self.assertEqual(state['pages'],(0,8))
            with patch('app.synth_display.draw') as graph:
                frame=control(state);graph.assert_not_called()
            plain=dict(state);plain.pop('micro_overview');baseline=control(plain)
            self.assertEqual(frame[:24*128],baseline[:24*128])
            self.assertEqual(frame[46*128:],baseline[46*128:])
            expected=b''.join(bytes(0 if b=='1' else 1 for b in row) for row in SMALL_ICONS['synth'])
            self.assertEqual(self.crop(frame,4,27,16,16),expected)
            self.assertEqual(a.project,before);self.assertEqual(a.actions,actions)
    def test_later_native_graphs_and_existing_encoder_selection_are_preserved(self):
        a=self.a;a.plugin_param=8
        state=control_state(a);self.assertNotIn('micro_overview',state)
        with patch('app.synth_display.draw') as graph:
            control(state);graph.assert_called_once()
        parameter=a.plugin_param;a.rotate(1)
        self.assertEqual(a.plugin_param,parameter)
        self.assertEqual(state['pages'][1],8)
    def test_generic_effects_choose_symbols_and_bypass_is_visible(self):
        for title,kind in (('Stereo Delay','delay'),('Reverb','reverb'),('Lowpass Filter','filter')):
            a=self.a;a.plugin_catalog=[dict(uri='urn:fx',name=title,kind='EFFECT',supported=True,ports=[])]
            a.track()['plugins']=[dict(uri='urn:fx',kind='EFFECT',controls={},bypass=True)]
            detail=control_state(a)['micro_overview']
            self.assertEqual(detail,dict(icon=kind,name=title,role='BYPASSED'))
    def test_useful_meters_latency_and_parameter_plots_take_priority(self):
        with patch('app.ducktor.view',return_value={'depth':10,'input_db':-12,'reduction':3,'source':'KICK'}):
            self.assertNotIn('micro_overview',control_state(self.a))
        with patch('app.synth_display.view',return_value=dict(title='Waveform',points=(0,.5,0,-.5))):
            self.assertNotIn('micro_overview',control_state(self.a))
        self.a.plugin_latency_ms=20
        self.assertNotIn('micro_overview',control_state(self.a))
    def test_channel_routing_sampler_and_sample_edit_are_untouched(self):
        a=self.a;a.track().update(sample='fixture.wav',start=0,end=100)
        for page in ('PAD','CHANNEL','INPUT','SAMPLER','PAD CONFIG'):
            a.page=page;self.assertNotIn('micro_overview',control_state(a))
        a.page='CHANNEL';state=control_state(a)
        self.assertEqual(state['sound_wave'][0],'fixture.wav')
        a.page='SAMPLER';self.assertIn('sampler_values',control_state(a))
    def test_snapshot_is_detached_small_and_does_no_drawing_file_io(self):
        state=control_state(self.a);saved=copy.deepcopy(state)
        self.a.track()['plugins'][0]['bypass']=True;self.a.plugin_param=8
        self.assertEqual(state,saved);self.assertLess(len(pickle.dumps(state)),2048)
        with patch.object(Path,'open',side_effect=AssertionError('renderer may not load images')):
            frame=control_frame(state)
        self.assertEqual(len(frame),8192);self.assertLessEqual(set(frame),{0,1})
    def test_long_name_is_clipped_above_parameter_footer(self):
        state=control_state(self.a);state['micro_overview']['name']='A very long synthesizer patch name '*5
        frame=control(state)
        self.assertTrue(all(frame[y*128] and frame[y*128+127] for y in range(64)))
        plain=dict(state);plain.pop('micro_overview')
        self.assertEqual(frame[46*128:],control(plain)[46*128:])
