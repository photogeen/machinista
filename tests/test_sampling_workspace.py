import array
import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import wave
from app.layout import ZONE_BASE
from app.audio import AudioBackend, repair_recording_header
from app.model import Application


class SamplingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve()
        self.app=Application(self.root)
        self.sample=self.root/'samples/recordings/Sample01.wav';self.sample.parent.mkdir()
        with wave.open(str(self.sample),'wb') as wav:
            wav.setparams((2,2,48000,0,'NONE','not compressed'))
            wav.writeframes(array.array('h',[1000,-1000]*480).tobytes())
        self.app.track().update(sample=str(self.sample),start=0,end=480)
    def tearDown(self):self.temp.cleanup()
    def test_nav_held_encoder_and_pads_stay_inside_sampling(self):
        a=self.app;a.button('SAMPLING',True);a.button('SAMPLING',False)
        a.button('NAV',True);self.assertEqual(a.softkeys(),('RECORD','EDIT','SLICE'))
        a.rotate(1);a.button('NAV',False);self.assertEqual(a.page,'SAMPLE EDIT')
        a.button('NAV',True);a.button('NAV RIGHT',True);a.button('NAV',False)
        self.assertEqual((a.page,a.range_page),('SAMPLE EDIT',1))
        a.button('NAV',True);a.pad_on(14);a.button('NAV',False);self.assertEqual(a.page,'CHOP')
        a.button('SAMPLING',True);self.assertEqual(a.page,'PAD')
    def test_trim_changes_ranges_without_reconverting_or_reopening_audio(self):
        backend=AudioBackend.__new__(AudioBackend);backend.cache=self.root/'cache';backend.cache.mkdir()
        backend.loaded={};commands=[];backend.command=commands.append
        track=self.app.track()
        with patch('app.audio.convert_sample',return_value=48000) as convert:
            backend.load(0,0,track)
            for start in range(1,100):
                backend.load(0,0,dict(track,start=start))
            backend.load(0,1,dict(track,start=100,end=200))
            self.assertEqual(convert.call_count,1)
        self.assertEqual(sum(c.startswith('load ') for c in commands),1)
        self.assertIn('assign 1 0',commands)
        self.assertIn('range 1 100 200',commands)
        self.assertIn(f'range {ZONE_BASE+128} 100 200',commands)
        backend.load(0,0,dict(track,sample=None));self.assertIn('clear 0',commands)
        self.assertNotIn(131,backend.loaded)
    def test_removal_keeps_file_and_delete_blocks_other_projects_then_trashes(self):
        a=self.app;a.page='SAMPLE EDIT';a.button('SHIFT',True);a.button('F3',True);a.button('SHIFT',False)
        self.assertEqual(a.page,'SAMPLE DELETE')
        a.button('ENTER',True);self.assertEqual(a.page,'CONFIRM');a.button('F2',True)
        self.assertIsNone(a.track()['sample']);self.assertTrue(self.sample.exists())
        a.undo_action();self.assertEqual(a.track()['sample'],str(self.sample))
        other=copy.deepcopy(a.project);(self.root/'projects').mkdir(exist_ok=True)
        project=self.root/'projects/PROJECT-9999.json';project.write_text(json.dumps(other))
        a.remove_sample(True);self.assertEqual(a.message,'OTHER PROJECT USES IT');self.assertTrue(self.sample.exists())
        project.unlink();a.remove_sample(True)
        self.assertFalse(self.sample.exists());self.assertIsNone(a.track()['sample'])
        self.assertEqual(len(list((self.root/'samples/.trash').glob('*'))),1)
        self.assertIsNone(json.loads(a.project_path.read_text())['groups'][0]['pads'][0]['sample'])
    def test_arecord_unfinished_header_uses_actual_frames(self):
        with self.sample.open('r+b') as stream:
            stream.seek(4);stream.write(struct.pack('<I',0x7fffffff))
            stream.seek(40);stream.write(struct.pack('<I',0x7fffffff))
        self.assertTrue(repair_recording_header(self.sample))
        with wave.open(str(self.sample)) as wav:self.assertEqual(wav.getnframes(),480)
        self.assertFalse(repair_recording_header(self.sample))
