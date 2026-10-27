import array
import copy
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import wave
from app.model import Application,validate_project
from app.sampler import zones,default_zone
from app.audio import AudioBackend
from app.layout import ZONE_BASE
from app.ni_display import frame
from app.sample_edit import process_sample
from app.slicing import detect_slices

class SamplerZonesTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.a=Application(self.root)
        self.path=self.root/'samples/source.wav'
        with wave.open(str(self.path),'wb') as w:w.setparams((1,2,10000,0,'NONE','not compressed'));w.writeframes(array.array('h',[0]*1000+[20000]*100+[0]*8900).tobytes())
        self.a.track().update(sample=str(self.path),start=0,end=10000,note=36)
    def tearDown(self):self.temp.cleanup()
    def test_sampler_pages_and_zone_mapping_survive_project_roundtrip(self):
        a=self.a;a.page='SAMPLER';a.rotate(1);self.assertEqual(a.track()['sampler']['polyphony'],16)
        a.button('NAV',True);a.button('NAV RIGHT',True);a.button('NAV RIGHT',False);a.button('NAV',False)
        self.assertEqual((a.page,a.sampler_page),('SAMPLER',1));a.rotate(2);self.assertEqual(a.track()['sampler']['tune'],2)
        a.page='SAMPLING';a.button('NAV',True);a.pad_on(15);a.button('NAV',False);self.assertEqual(a.page,'ZONE')
        a.track()['zones']=[default_zone(a.track())];a.zone_page=4;a.zone_field=0;a.rotate(40);self.assertEqual(a.zone()['key_lo'],40)
        validate_project(a.project);a.save();loaded=Application(self.root);self.assertEqual(loaded.track()['zones'],a.track()['zones'])
        self.assertEqual(len(frame(a)),8192)
    def test_slices_are_markers_and_apply_sound_preserves_asset(self):
        a=self.a;a.page='CHOP';a.slice_count=4;a.build_slices();self.assertEqual(a.slice_ranges(),[[0,2500],[2500,5000],[5000,7500],[7500,10000]])
        a.apply_slices(0,0,'NONE');self.assertEqual(len(a.track()['zones']),4)
        self.assertEqual([z['root'] for z in a.track()['zones']],[0,1,2,3]);self.assertTrue(all(z['sample']==str(self.path) for z in a.track()['zones']))
        validate_project(a.project)

    def test_zone_remove_shortcut_removes_selected_slice_zone(self):
        a=self.a;a.track()['zones']=[default_zone(a.track()) for _ in range(2)]
        a.page='ZONE';a.zone_index=1;a.button('SHIFT',True);a.button('F3',True);a.button('SHIFT',False)
        self.assertEqual(len(a.track()['zones']),1);self.assertEqual(a.track()['sample'],str(self.path))
        a.zone_index=0;a.button('SHIFT',True);a.button('F3',True);a.button('SHIFT',False)
        self.assertEqual(a.track()['zones'],[]);self.assertIsNone(a.track()['sample'])
    def test_live_chop_and_independent_boundary_edit(self):
        a=self.a;a.page='CHOP';a.slice_mode='MANUAL'
        with patch('app.slicing.time.monotonic',return_value=10):a.pad_on(0)
        with patch('app.slicing.time.monotonic',return_value=10.25):a.pad_on(1)
        self.assertEqual(a.slice_ranges(),[[0,2500],[2500,10000]])
        a.slice_edit=True;a.slice_field=1;a.slice_index=1;a.rotate(1)
        self.assertEqual(a.slice_ranges()[0][1],a.slice_ranges()[1][0])
        first=copy.deepcopy(a.slice_ranges()[1]);a.slice_index=0;a.slice_field=2;a.rotate(-1)
        self.assertEqual(a.slice_ranges()[1],first)
    def test_detection_finds_transient_and_layered_audio_routes_notes(self):
        found=detect_slices(self.a.track(),80,False);self.assertTrue(any(900<=a<=1100 for a,b in found[1:]))
        track=self.a.track();z=default_zone(track);z.update(key_lo=36,key_hi=36,vel_lo=80)
        track['zones']=[z];backend=AudioBackend.__new__(AudioBackend);backend.command=lambda s:commands.append(s);backend.loaded={};backend.cache=self.root/'cache';backend.cache.mkdir();commands=[]
        backend.load(0,0,track);commands.clear();backend.hit(0,0,50,track);self.assertEqual(commands,[])
        backend.hit(0,0,100,track);self.assertTrue(any(c.startswith(f'hit {ZONE_BASE} ') for c in commands));backend.note_off(0,0,36);self.assertIn(f'off {ZONE_BASE} 36',commands)
    def test_cut_copy_paste_duplicate_keep_original_unchanged(self):
        original=self.path.read_bytes();track=dict(self.a.track(),selection_start=1000,selection_end=2000);folder=self.root/'edited';clipboard=self.root/'clip.wav'
        _,count=process_sample(track,'COPY',folder,clipboard);self.assertEqual(count,10000)
        path,count=process_sample(track,'CUT',folder,clipboard);self.assertEqual(count,9000)
        _,count=process_sample(track,'PASTE',folder,clipboard);self.assertEqual(count,11000)
        _,count=process_sample(track,'DUPLICATE',folder,clipboard);self.assertEqual(count,11000)
        self.assertEqual(self.path.read_bytes(),original)
    def test_invalid_zone_is_rejected(self):
        z=default_zone(self.a.track());z['key_hi']=-1;self.a.track()['zones']=[z]
        with self.assertRaises(ValueError):validate_project(self.a.project)
