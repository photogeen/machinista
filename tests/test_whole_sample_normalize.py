import array
import copy
import hashlib
import tempfile
import unittest
import wave
from pathlib import Path
from app.model import Application,validate_project
from app.sample_edit import process_sample

class WholeSampleNormalizeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.a=Application(self.root);self.path=self.root/'source.wav'
        with wave.open(str(self.path),'wb') as w:
            w.setparams((1,2,1000,0,'NONE','not compressed'));w.writeframes(array.array('h',[1000]*250+[2000]*250+[3000]*250+[4000]*250).tobytes())
        self.a.track().update(sample=str(self.path),start=0,end=1000,slices=[[0,250],[250,500],[500,750],[750,1000]])
        self.a.apply_slices(0,0,'NONE');self.original=hashlib.sha256(self.path.read_bytes()).hexdigest()
    def run_normalize(self):
        old,processing=self.a.sample_process_request('NORMALIZE')
        path,frames=process_sample(processing,'NORMALIZE',self.root/'edited')
        return old,path,frames
    def test_focused_slice_does_not_limit_normalize_and_all_inherit(self):
        a=self.a;a.zone_index=2;a.open_sampling_page('SAMPLE EDIT')
        a.track()['zones'][2].update(tune=7,gain=73,pan=-20)
        a.track().update(selection_start=510,selection_end=520)
        before=copy.deepcopy(a.project);old,path,frames=self.run_normalize()
        self.assertTrue(a.finish_sample_process(a.track(),old,'NORMALIZE',path,frames))
        t=a.track();self.assertEqual(t['slice_source']['sample'],str(path))
        for index,z in enumerate(t['zones']):
            self.assertEqual(z['sample'],str(path))
            expected=copy.deepcopy(before['groups'][0]['pads'][0]['zones'][index]);expected['sample']=str(path)
            self.assertEqual(z,expected)
        self.assertEqual(t['slices'],before['groups'][0]['pads'][0]['slices'])
        with wave.open(str(path),'rb') as w:v=array.array('h',w.readframes(1000))
        self.assertGreater(v[100],7000);self.assertGreater(v[900],30000)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(),self.original)
        validate_project(a.project);a.undo_action();self.assertEqual(a.project,before)
    def test_previously_individually_normalized_zone_is_replaced_from_canonical_source(self):
        a=self.a;old=copy.deepcopy(a.track());old.update(start=0,end=250,selection_start=0,selection_end=250)
        single,_=process_sample(old,'NORMALIZE',self.root/'edited');a.track()['zones'][0]['sample']=str(single)
        a.zone_index=0;a.open_sampling_page('SAMPLE EDIT');_,processing=a.sample_process_request('NORMALIZE')
        self.assertEqual(processing['sample'],str(self.path));self.assertEqual((processing['selection_start'],processing['selection_end']),(0,1000))
        original_single=single.read_bytes();old,path,frames=self.run_normalize()
        self.assertTrue(a.finish_sample_process(a.track(),old,'NORMALIZE',path,frames))
        self.assertTrue(all(z['sample']==str(path) for z in a.track()['zones']))
        self.assertEqual(single.read_bytes(),original_single)
        a.save();b=Application(self.root);self.assertTrue(all(z['sample']==str(path) for z in b.track()['zones']))
    def test_concurrent_slice_edits_reject_stale_result(self):
        a=self.a;old,path,frames=self.run_normalize();a.track()['zones'][1]['start']+=1
        before=copy.deepcopy(a.project)
        self.assertFalse(a.finish_sample_process(a.track(),old,'NORMALIZE',path,frames));self.assertEqual(a.project,before)
    def test_unsliced_normalize_ignores_slice_selection(self):
        a=Application(self.root/'plain');a.track().update(sample=str(self.path),start=0,end=1000,selection_start=0,selection_end=20)
        old,processing=a.sample_process_request('NORMALIZE');self.assertEqual(processing['selection_end'],1000)
        path,frames=process_sample(processing,'NORMALIZE',self.root/'edited')
        self.assertTrue(a.finish_sample_process(a.track(),old,'NORMALIZE',path,frames));self.assertEqual(a.track()['end'],1000)
