import array
import copy
from pathlib import Path
import json
import shutil
import tempfile
import unittest
import wave
from app.model import Application,validate_project
from app.assets import collect_project,resolve_assets,relative_assets
from app.routing import build_graph,route_defaults
from app.audio import AudioBackend

class PluginRoutingAssetsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.a=Application(self.root)
        self.meta={'uri':'urn:test:gain','name':'Test Gain','kind':'EFFECT','supported':True,'ports':[{'index':0,'symbol':'gain','name':'Gain','default':1,'min':0,'max':2}]}
        self.a.plugin_catalog=[self.meta]
    def tearDown(self):self.temp.cleanup()
    def test_plugin_selection_parameter_and_macro_roundtrip(self):
        a=self.a;a.button('SHIFT',True);a.button('BROWSE',True);a.button('SHIFT',False)
        self.assertEqual(a.page,'PLUGIN BROWSE');a.button('F2',True);self.assertEqual(a.page,'PLUGIN')
        a.rotate(10);self.assertAlmostEqual(a.track()['plugins'][0]['controls']['gain'],1.2)
        a.page='MACRO';a.button('SHIFT',True);a.button('F2',True);a.button('SHIFT',False);a.button('ENTER',True);a.rotate(50)
        self.assertEqual(a.track()['plugins'][0]['controls']['gain'],1)
        validate_project(a.project);a.save();b=Application(self.root);self.assertEqual(b.track()['plugins'][0]['controls']['gain'],1)
        self.assertEqual(b.track()['macros']['0']['value'],50)
    def test_routing_order_and_feedback_rejection(self):
        a=self.a;a.track()['routing']=dict(route_defaults(a.track()),aux1_dest='SOUND 1',aux1_level=50,aux1_pre=True)
        nodes,order=build_graph(a.project);self.assertLess(order.index(0),order.index(1))
        a.project['groups'][0]['pads'][1]['routing']=dict(dest='SOUND 0')
        with self.assertRaises(ValueError):build_graph(a.project)
    def test_audio_plugin_updates_use_stable_symbols_and_no_reinstantiation(self):
        backend=AudioBackend.__new__(AudioBackend);backend.sample_rate=48000;backend.plugin_chains={};backend.plugin_metadata=[self.meta];commands=[];backend.command=commands.append
        chain=[{'uri':'urn:test:gain','controls':{'gain':1.5},'kind':'EFFECT','bypass':False}]
        backend.plugins(0,chain);backend.plugins(0,chain)
        self.assertEqual(sum(c.startswith('plugins ') for c in commands),1);self.assertIn('plugin_param 0 0 0 1.5',commands)
    def test_collected_project_is_portable_and_source_is_unchanged(self):
        sample=self.root/'samples/test.wav'
        with wave.open(str(sample),'wb') as w:w.setparams((1,2,44100,0,'NONE','not compressed'));w.writeframes(array.array('h',[1000]*100).tobytes())
        track=self.a.track();track.update(sample=str(sample),start=0,end=100)
        from app.sampler import default_zone
        track['zones']=[default_zone(track)];original=copy.deepcopy(self.a.project)
        bundle=self.root/'bundle';manifest=collect_project(original,bundle);self.assertEqual(self.a.project,original)
        destination=self.root/'moved';shutil.move(str(bundle),destination);sample.unlink()
        restored=resolve_assets(json.loads((destination/'Project.json').read_text()),destination)
        self.assertTrue(Path(restored['groups'][0]['pads'][0]['sample']).is_file())
        self.assertEqual(len(list((destination/'samples').glob('*.wav'))),1);validate_project(restored)
