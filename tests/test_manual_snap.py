import array
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave
from app.model import Application

class ManualSnapTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.a=Application(Path(self.temp.name))
        sample=Path(self.temp.name)/'sample.wav'
        with wave.open(str(sample),'wb') as w:
            w.setparams((1,2,1000,0,'NONE','not compressed'));w.writeframes(array.array('h',[0]*1000).tobytes())
        self.a.track().update(sample=str(sample),start=0,end=1000)
        self.a.page='CHOP';self.a.slice_mode='MANUAL';self.a.slice_auto_snap=True
    def tearDown(self):self.temp.cleanup()
    def test_analysis_required_and_nearest_transient(self):
        a=self.a;a.slicing_pad(0,100)
        self.assertIsNone(a.live_chop_started);self.assertEqual(a.actions[-1][0],'analyze_slices')
        a.slice_transients[a.transient_key()]=[0,200,500,800]
        with patch('app.slicing.time.monotonic',side_effect=[10,10.46,10.79]):
            a.slicing_pad(0,100);a.slicing_pad(1,100);a.slicing_pad(2,100)
        self.assertEqual(a.track()['slices'],[[0,500],[500,800],[800,1000]])
    def test_analysis_invalidated_by_trim_and_toggle_preserves_markers(self):
        a=self.a;a.slice_transients[a.transient_key()]=[0,200]
        a.track()['start']=100;a.slicing_pad(0,100)
        self.assertIsNone(a.live_chop_started)
        a.track()['slices']=[[100,500],[500,1000]];a.slice_field=1
        a.slicing_rotate(-1)
        self.assertFalse(a.slice_auto_snap);self.assertEqual(a.track()['slices'],[[100,500],[500,1000]])

    def test_existing_pad_retriggers_without_erasing_and_new_cuts_use_new_anchor(self):
        a=self.a;a.slice_auto_snap=False
        with patch('app.slicing.time.monotonic',side_effect=[10,10.2,10.7,11,11.3]):
            a.slicing_pad(0,100);a.slicing_pad(1,100);a.slicing_pad(2,100)
            self.assertEqual(a.track()['slices'],[[0,200],[200,700],[700,1000]])
            a.slicing_pad(1,100)
            track,token=a.actions[-1][1]
            self.assertEqual((track['start'],track['end']),(200,1000))
            self.assertEqual(a.track()['slices'],[[0,200],[200,700],[700,1000]])
            a.slicing_pad(3,100)
        self.assertEqual(a.track()['slices'],[[0,200],[200,500],[500,700],[700,1000]])

    def test_natural_end_allows_restart_from_any_pad_and_preserves_slices(self):
        a=self.a;a.slice_auto_snap=False;a.track()['slices']=[[0,200],[200,700],[700,1000]]
        with patch('app.slicing.time.monotonic',return_value=10):a.pad_on(1)
        self.assertIsNone(a.live_chop_position(11))
        with patch('app.slicing.time.monotonic',return_value=12):a.pad_on(0)
        self.assertEqual(a.live_chop_position(12.1),100)
        self.assertEqual(a.track()['slices'],[[0,200],[200,700],[700,1000]])
        token=a.live_chop_token;a.live_chop_event({'status':'finished','token':token,'frame':1000})
        self.assertIsNone(a.live_chop_started)
        with patch('app.slicing.time.monotonic',return_value=13):a.pad_on(2)
        self.assertEqual(a.live_chop_position(13.1),800)

    def test_shift_mute_and_delete_all_stop_preview_then_allow_fresh_start(self):
        a=self.a;a.slice_auto_snap=False;a.track()['slices']=[[0,200],[200,1000]]
        a.pad_on(1);old_token=a.live_chop_token;a.button('SHIFT',True);a.button('MUTE',True)
        self.assertIsNone(a.live_chop_started)
        self.assertIn(('preview_stop',None),a.actions)
        self.assertEqual(a.actions[-1][0],'panic')  # Global choke also stops other voices.
        a.live_chop_event({'status':'playing','token':old_token,'frame':300})
        self.assertIsNone(a.live_chop_started)
        a.button('SHIFT',False);a.slice_edit=True;a.button('SHIFT',True);a.button('F3',True)
        self.assertEqual(a.track()['slices'],[[0,1000]]);self.assertEqual((a.slice_index,a.slice_bank),(0,0))
        a.button('SHIFT',False);a.button('F1',True);a.pad_on(0)
        self.assertIsNotNone(a.live_chop_started)

    def test_mode_manual_keeps_proposed_markers_and_bank_two_replays(self):
        a=self.a;a.slice_auto_snap=False;a.track()['slices']=[[i*50,(i+1)*50] for i in range(20)]
        a.build_slices();self.assertEqual(len(a.track()['slices']),20)
        a.slice_bank=1;a.pad_on(0)
        track,token=a.actions[-1][1];self.assertEqual((track['start'],track['end']),(800,1000))
        a.live_chop_event({'status':'finished','token':token,'frame':1000})
        self.assertEqual(len(a.track()['slices']),20)

    def test_no_cut_after_sample_end_and_empty_delete_is_safe(self):
        from app.model import validate_project
        a=self.a;a.slice_auto_snap=False
        with patch('app.slicing.time.monotonic',return_value=10):a.slicing_pad(0,100)
        with patch('app.slicing.time.monotonic',return_value=12):a.slicing_pad(1,100)
        self.assertEqual(a.track()['slices'],[[0,1000]]);self.assertIsNone(a.live_chop_started)
        a.track().update(sample=None,start=0,end=0,slices=[]);a.slice_edit=True;a.shift=True;a.slicing_button('F3',True)
        self.assertEqual(a.track()['slices'],[]);validate_project(a.project)
