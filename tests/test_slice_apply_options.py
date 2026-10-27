import array
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
import wave
from app.model import Application,validate_project
from app.ni_display import frame

class SliceApplyOptionsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.a=Application(self.root);self.path=self.root/'loop.wav'
        with wave.open(str(self.path),'wb') as wav:
            wav.setparams((2,2,1000,0,'NONE','not compressed'));wav.writeframes(array.array('h',[1000,-1000]*2000).tobytes())
        self.original=hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.a.track().update(sample=str(self.path),start=0,end=2000,slices=[[0,500],[500,1000],[1000,1500],[1500,2000]])
        self.a.project['tempo']=120;self.a.open_sampling_page('CHOP')
    def test_controller_single_slice_export_does_not_replace_other_slots_or_pattern(self):
        a=self.a;before=copy.deepcopy(a.project);a.pad_on(2);a.button('F2',True)
        self.assertEqual(a.page,'SLICE TARGET');self.assertEqual(a.softkeys(),('EDIT','APPL.TO','APPLY'))
        a.pad_on(5);a.button('F1',True);self.assertEqual(a.page,'CHOP');self.assertEqual(a.softkeys()[2],'APPLY')
        a.button('F3',True);self.assertEqual(a.page,'CONFIRM');a.button('F2',True)
        target=a.project['groups'][0]['pads'][5]
        self.assertEqual((target['start'],target['end'],target['note']),(1000,1500,41))
        self.assertEqual(len(target['zones']),1);self.assertFalse(a.keyboard_enabled)
        self.assertEqual(a.project['groups'][0]['patterns'],before['groups'][0]['patterns'])
        self.assertEqual(a.project['groups'][0]['pads'][0],before['groups'][0]['pads'][0])
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(),self.original)
        a.undo_action();self.assertEqual(a.project,before)
    def test_single_apply_cancel_keeps_markers_and_return_path(self):
        a=self.a;before=copy.deepcopy(a.project);a.button('F2',True);a.button('F1',True)
        a.button('F2',True);self.assertEqual(a.page,'SLICE TARGET');self.assertFalse(a.slice_single_apply)
        a.button('F2',True);self.assertEqual(a.page,'CHOP');self.assertEqual(a.project,before)
    def test_target_group_selection_preserves_source_and_exports_to_chosen_group(self):
        a=self.a;source=copy.deepcopy(a.track());a.button('F2',True)
        a.button('GROUP',True);a.pad_on(13);a.button('GROUP',False)
        self.assertEqual(a.page,'SLICE TARGET');self.assertEqual(a.slice_target_group,1)
        self.assertIsNone(a.slice_target_sound);self.assertEqual(a.group,0);self.assertEqual(a.track(),source)
        a.button('F3',True);a.button('F2',True)
        self.assertEqual(a.group,1);self.assertFalse(a.keyboard_enabled)
        self.assertEqual(a.project['groups'][0]['pads'][0],source)
        self.assertEqual([(t['start'],t['end']) for t in a.project['groups'][1]['pads'][:4]],[(0,500),(500,1000),(1000,1500),(1500,2000)])
    def test_target_encoder_banks_sound_selection_and_cancel(self):
        a=self.a;a.ensure_group_bank(1);a.button('F2',True);before=copy.deepcopy(a.project)
        a.button('GROUP',True);a.rotate(10);self.assertEqual(a.slice_target_group,10)
        a.pad_on(15);self.assertEqual(a.slice_target_group,11)
        a.pad_on(0);self.assertEqual(a.slice_target_group,11);self.assertIsNone(a.slice_target_sound)
        a.button('SHIFT',True);a.button('NAV LEFT',True);a.button('SHIFT',False)
        self.assertEqual(a.slice_target_group,3);a.button('GROUP',False)
        a.pad_on(6);self.assertEqual(a.slice_target_sound,6);self.assertEqual(a.group,0)
        a.button('F2',True);self.assertEqual(a.page,'CHOP');self.assertEqual(a.project,before)
    def test_target_layout_has_separate_rows_and_group_target_leds(self):
        from unittest.mock import patch
        from app.leds import led_report,DIM,FULL
        from app import ni_display
        a=self.a;a.button('F2',True)
        with patch.object(ni_display,'label',wraps=ni_display.label) as draw:
            frame(a)
        targets=[c for c in draw.call_args_list if c.args[3] in ('A: ALL SOUNDS','GROUP + PAD: TARGET')]
        self.assertEqual([c.args[2] for c in targets],[25,34])
        self.assertTrue(all(c.kwargs['font']=='regular5' for c in targets))
        channels={(s,'orange'):s for s in range(16)}|{(s,'blue'):16+s for s in range(16)}
        a.button('GROUP',True);a.pad_on(13)
        report=led_report(a,channels,now=100)
        self.assertEqual(list(report[1:17]),[0]*16)
        self.assertEqual(report[16+13+1],FULL);self.assertEqual(report[16+12+1],DIM)
        a.button('GROUP',False);a.pad_on(6)
        report=led_report(a,channels,now=100)
        self.assertEqual(report[7],FULL);self.assertEqual(report[1],DIM)
    def test_auto_manual_adjust_grid_and_persistence(self):
        a=self.a;self.assertEqual(a.slice_bpm(),120)
        a.slice_mode='GRID';a.slice_grid=4;a.build_slices();self.assertEqual(a.slice_ranges()[0],[0,500])
        a.slice_field=3;a.rotate(1);self.assertEqual(a.slice_bpm(),240);self.assertEqual(a.slice_ranges()[0],[0,250])
        a.rotate(-2);self.assertEqual(a.slice_bpm(),60);self.assertEqual(a.slice_ranges()[0],[0,1000])
        a.slice_field=2;a.rotate(1);self.assertEqual(a.slice_bpm(),120)
        a.slice_field=3;a.rotate(-20);self.assertEqual(a.slice_bpm(),100)
        a.button('SHIFT',True);a.rotate(1);a.button('SHIFT',False);self.assertEqual(a.slice_bpm(),100.01)
        a.save();b=Application(self.root);self.assertEqual(b.slice_bpm(),100.01);validate_project(b.project)
    def test_pattern_creation_uses_source_bpm_instead_of_project_bpm(self):
        a=self.a;a.track()['slice_options']['bpm_mode']='MANUAL';a.track()['slice_options']['manual_bpm']=60
        a.project['tempo']=180;a.apply_slices(0,1,'CREATE')
        self.assertEqual(sorted(key[1] for key in a.event_notes()),[0,48,96,144])
    def test_mono_on_assigns_voice_and_choke_mono_off_preserves_source(self):
        a=self.a;a.track()['sampler']={'polyphony':8};a.track()['choke_group']=0
        a.slice_field=4;a.rotate(-1);a.apply_slices(0,None,'NONE')
        self.assertTrue(all(t['sampler']['polyphony']==8 and t['choke_group']==0 for t in a.project['groups'][0]['pads'][:4]))
        a.open_sampling_page('CHOP');a.track()['slices']=[[0,250],[250,500]];a.slice_field=4;a.rotate(1)
        a.apply_slices(0,None,'NONE')
        self.assertTrue(all(t['sampler']['polyphony']==1 and t['choke_group']==1 for t in a.project['groups'][0]['pads'][:2]))
        with wave.open(str(self.path),'rb') as wav:self.assertEqual(wav.getnchannels(),2)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(),self.original)
    def test_validation_and_display_all_five_parameters(self):
        a=self.a
        for index in range(5):a.slice_field=index;self.assertEqual(len(frame(a)),8192)
        a.track()['slice_options']['manual_bpm']=float('nan')
        with self.assertRaises(ValueError):validate_project(a.project)
