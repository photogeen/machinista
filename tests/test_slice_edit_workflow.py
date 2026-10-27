import array
import copy
from pathlib import Path
import tempfile
import unittest
import wave
from app.model import Application,validate_project
from app.assets import collect_project,resolve_assets
from app.storage import load_json
from app.sample_edit import process_sample

class SliceEditWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.a=Application(self.root)
        self.sample=self.root/'sample.wav'
        with wave.open(str(self.sample),'wb') as w:
            w.setparams((1,2,1000,0,'NONE','not compressed'));w.writeframes(array.array('h',range(1000)).tobytes())
        self.ranges=[[0,250],[250,500],[500,750],[750,1000]]
        self.a.track().update(sample=str(self.sample),start=0,end=1000,slices=copy.deepcopy(self.ranges))
        self.a.slice_mode='MANUAL';self.a.apply_slices(0,0,'NONE')
    def tearDown(self):self.temp.cleanup()
    def test_zone_edit_and_return_to_slice_preserve_whole_session(self):
        a=self.a;a.open_sampling_page('ZONE');a.button('F2',True)
        self.assertEqual((a.track()['start'],a.track()['end']),(250,500))
        a.open_sampling_page('SAMPLE EDIT');a.sample_field=0;a.rotate(1)
        self.assertEqual(a.track()['zones'][1]['start'],283)
        self.assertEqual(a.track()['zones'][0]['start'],0)
        a.button('NAV',True);a.pad_on(14);a.button('NAV',False)
        self.assertEqual(a.slice_ranges(),self.ranges)
        self.assertEqual((a.track()['start'],a.track()['end']),(0,1000))
        a.apply_slices(0,0,'NONE')
        self.assertEqual(a.track()['zones'][1]['start'],283)
        a.save();restored=Application(self.root);restored.open_sampling_page('CHOP')
        self.assertEqual(restored.slice_mode,'MANUAL');self.assertEqual(restored.slice_ranges(),self.ranges)
        validate_project(restored.project)
    def test_sampling_edit_pads_audition_slices_without_selecting_other_sounds(self):
        a=self.a;a.zone_index=1;a.open_sampling_page('SAMPLE EDIT');a.actions=[]
        a.pad_on(2)
        self.assertEqual((a.pad,a.zone_index),(0,1))
        self.assertEqual(a.actions[-1][0],'slice_play')
        self.assertEqual((a.actions[-1][1]['start'],a.actions[-1][1]['end']),(500,750))
        a.actions=[];a.pad_on(7);self.assertEqual(a.actions,[])
        a.sample_field=0;a.rotate(1000);a.sample_field=1;a.rotate(-1000)
        self.assertLess(a.track()['zones'][1]['start'],a.track()['zones'][1]['end']);validate_project(a.project)

    def test_manual_limit_rotation_does_not_regenerate_or_add_undo(self):
        a=self.a;a.open_sampling_page('CHOP');a.slice_field=0;count=len(a.undo)
        a.rotate(1);a.rotate(1)
        self.assertEqual(a.slice_ranges(),self.ranges);self.assertEqual(len(a.undo),count)

    def test_switching_from_grid_or_detect_to_manual_starts_with_full_sample(self):
        a=self.a;a.open_sampling_page('CHOP');a.slice_field=0
        a.track().pop('slice_manual',None)
        a.slice_mode='GRID';a.track()['slice_mode']='GRID';a.slice_grid=4;a.build_slices()
        self.assertGreater(len(a.slice_ranges()),1)
        a.rotate(1)  # GRID -> DETECT
        a.rotate(1)  # DETECT -> MANUAL
        self.assertEqual(a.slice_mode,'MANUAL')
        self.assertEqual(a.slice_ranges(),[[0,1000]])

    def test_manual_cuts_survive_auto_preview_and_can_be_removed(self):
        a=self.a;a.open_sampling_page('CHOP');a.slice_field=0
        a.rotate(1)  # MANUAL -> GRID, retaining the manual draft
        self.assertGreater(len(a.slice_ranges()),1)
        a.rotate(-1)  # GRID -> MANUAL
        self.assertEqual(a.slice_ranges(),self.ranges)
        a.save();a=Application(self.root);a.open_sampling_page('CHOP')
        self.assertEqual(a.slice_ranges(),self.ranges)
        a.slice_edit=True;a.slice_index=1;a.button('F3',True)
        self.assertEqual(len(a.slice_ranges()),3)
        a.button('SHIFT',True);a.button('F3',True);a.button('SHIFT',False)
        self.assertEqual(a.slice_ranges(),[[0,1000]])
    def test_start_only_moves_joined_previous_end_and_end_stays_independent(self):
        a=self.a;a.open_sampling_page('CHOP');a.slice_edit=True;a.slice_index=1;a.slice_field=1
        a.rotate(1);self.assertEqual(a.track()['slices'][0][1],a.track()['slices'][1][0])
        a.track()['slices'][0][1]=200;a.rotate(1)
        self.assertEqual(a.track()['slices'][0][1],200)
        a.slice_field=2;a.rotate(-1)
        self.assertEqual(a.track()['slices'][2][0],500)
        a.slice_index=1;a.button('F3',True)
        self.assertEqual(a.slice_count,3);self.assertEqual(a.slice_index,0)
        a.undo_action();self.assertEqual(len(a.track()['slices']),4)
    def test_processing_one_zone_preserves_other_zones_and_reapply_and_portability(self):
        a=self.a;a.zone_index=1;a.open_sampling_page('SAMPLE EDIT')
        before=copy.deepcopy(a.track()['zones']);old=copy.deepcopy(a.track());old['_zone_index']=1
        result,frames=process_sample(old,'TRUNCATE',self.root/'edited')
        self.assertTrue(a.finish_sample_process(a.track(),old,'TRUNCATE',result,frames))
        self.assertEqual((a.track()['zones'][1]['start'],a.track()['zones'][1]['end']),(0,250))
        for i in (0,2,3):self.assertEqual(a.track()['zones'][i],before[i])
        a.open_sampling_page('CHOP');a.apply_slices(0,0,'NONE')
        self.assertEqual(a.track()['zones'][1]['sample'],str(result))
        manifest=collect_project(a.project,self.root/'portable')
        project=resolve_assets(load_json(manifest,{}),manifest.parent);validate_project(project)
        self.assertTrue(Path(project['groups'][0]['pads'][0]['slice_source']['sample']).exists())
        self.assertTrue(Path(project['groups'][0]['pads'][0]['zones'][1]['sample']).exists())
    def test_stale_processing_preserves_latest_zone(self):
        a=self.a;a.zone_index=1;a.open_sampling_page('SAMPLE EDIT');old=copy.deepcopy(a.track());old['_zone_index']=1
        a.track()['zones'][1]['gain']=75;before=copy.deepcopy(a.track())
        self.assertFalse(a.finish_sample_process(a.track(),old,'REVERSE',self.sample,1000))
        self.assertEqual(a.track(),before)
    def test_legacy_applied_slices_survive_zone_selection_and_group_export_has_no_shared_draft(self):
        a=self.a
        for key in ('slice_source','slice_mode','slice_committed'):a.track().pop(key,None)
        a.zone_index=2;a.open_sampling_page('ZONE');a.open_sampling_page('CHOP')
        self.assertEqual(a.slice_ranges(),self.ranges)
        a.apply_slices(0,None,'NONE')
        self.assertNotIn('slices',a.track());self.assertNotIn('slice_source',a.track())
        self.assertEqual((a.track()['start'],a.track()['end']),(0,250))
