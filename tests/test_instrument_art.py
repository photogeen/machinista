import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.mk3_surface import Mk3Surface
from app.mk3_state import snapshot
from app.mk3_display import Mk3Renderer
from app.instrument_art import image,KINDS,_image
from app.mk3_graphics import BG
from PIL import ImageColor

class InstrumentArtworkTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=Application(self.tmp.name);self.a.page='CHANNEL';self.a.control_level=2
        self.s=Mk3Surface(self.a,ControllerInputs(self.a))
        self.r=Mk3Renderer();self.addCleanup(self.r.close)
    def load(self,kind='INSTRUMENT',uri='urn:machinista:instrument:synth'):
        self.a.track()['plugins']=[dict(uri=uri,kind=kind,controls={})]
    def test_native_other_instrument_effect_and_sample_priority(self):
        original=copy.deepcopy(self.a.project)
        self.assertIsNone(snapshot(self.s)['output_art'])
        self.assertEqual(self.a.project,original)
        self.load();self.assertEqual(snapshot(self.s)['output_art'],'machinista-synth')
        self.load(uri='urn:other-synth');self.assertEqual(snapshot(self.s)['output_art'],'generic-synth')
        self.load('EFFECT','urn:filter');self.assertEqual(snapshot(self.s)['output_art'],'generic-filter')
        self.a.track()['sample']='loaded.wav'
        state=snapshot(self.s);self.assertIsNone(state['output_art']);self.assertEqual(state['sound_wave'][0],'loaded.wav')
    def test_group_instrument_link_and_missing_plugin_metadata(self):
        self.a.track()['routing']={'midi_target':'GROUP 1'}
        self.a.project['groups'][1]['plugins']=[dict(uri='urn:group-synth',kind='INSTRUMENT',controls={})]
        self.assertEqual(snapshot(self.s)['output_art'],'generic-synth')
        self.a.project['groups'][1]['plugins'][0]['uri']='urn:machinista:instrument:synth'
        self.assertEqual(snapshot(self.s)['output_art'],'machinista-synth')
    def test_group_and_master_effects_use_their_own_plugin_chain(self):
        self.load()
        self.a.control_level=1
        self.assertIsNone(snapshot(self.s)['output_art'])
        self.a.project['groups'][0]['plugins']=[dict(uri='urn:filter',kind='EFFECT',controls={})]
        self.assertEqual(snapshot(self.s)['output_art'],'generic-filter')
        self.a.control_level=0
        self.assertIsNone(snapshot(self.s)['output_art'])
        self.a.project['plugins']=[dict(uri='urn:master-filter',kind='EFFECT',controls={})]
        self.assertEqual(snapshot(self.s)['output_art'],'generic-filter')

    def test_empty_sound_has_no_left_art_but_right_routing_grid_remains(self):
        left,right=self.r.images(snapshot(self.s))
        expected=ImageColor.getrgb(BG)
        self.assertEqual(left.crop((12,88,468,212)).getextrema(),tuple((v,v) for v in expected))
        self.assertTrue(any(lo!=hi for lo,hi in right.crop((60,84,162,186)).getextrema()))
    def test_assets_fit_display_and_only_decode_once(self):
        _image.cache_clear()
        for kind in KINDS:
            asset=image(kind);self.assertIsNotNone(asset);self.assertEqual(asset.size,(448,120))
            self.assertEqual(asset.mode,'RGBA');self.assertEqual(asset.getchannel('A').getextrema(),(0,255))
            self.assertIs(asset,image(kind))
        self.assertIsNone(image('../outside'))
        self.load()
        with patch('PIL.Image.open',side_effect=AssertionError('image decode repeated')):
            self.r.images(snapshot(self.s));self.a.clock_phase=24;self.r.images(snapshot(self.s))
    def test_art_switches_with_current_sound_and_does_not_change_right_grid(self):
        self.load();first=self.r.images(snapshot(self.s))
        self.load(uri='urn:other-synth');second=self.r.images(snapshot(self.s))
        self.assertNotEqual(first[0].crop((12,88,468,212)).tobytes(),second[0].crop((12,88,468,212)).tobytes())
        self.assertEqual(first[1].tobytes(),second[1].tobytes())
