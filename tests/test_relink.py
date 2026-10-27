import array
import copy
from pathlib import Path
import tempfile
import unittest
import wave
from app.model import Application
from app.relink import sample_requirements,missing_samples,find_replacements,validate_replacement
from app.browser import Source
from app.sampler import default_zone

class RelinkTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve();self.a=Application(self.root)
        self.old=str(self.root/'removed/Kick.wav');self.a.track().update(sample=self.old,start=10,end=100)
        self.a.track()['zones']=[dict(default_zone(self.a.track()),start=20,end=80,loop_start=20,loop_end=80)]
        self.a.track()['slice_source']={'sample':self.old,'start':0,'end':120}
    def wav(self,path,frames=150):
        path.parent.mkdir(parents=True,exist_ok=True)
        with wave.open(str(path),'wb') as w:w.setparams((1,2,44100,0,'NONE','not compressed'));w.writeframes(array.array('h',[1000]*frames).tobytes())
        return path
    def scan(self):
        a=self.a;a.request_missing_check(True);action,(context,rows)=a.actions.pop();self.assertEqual(action,'missing_check')
        a.finish_missing_check(context,missing_samples(rows));return context,a.missing_rows[0]
    def test_scan_deduplicates_tracks_zones_and_source_uses_longest_required_range(self):
        self.a.project['groups'][1]['pads'][4].update(sample=self.old,start=0,end=110)
        context,row=self.scan();self.assertEqual(len(self.a.missing_rows),1);self.assertEqual(row['end'],120);self.assertEqual(row['slots'],[(0,0),(1,4)])
        self.assertEqual(self.a.page,'MISSING SAMPLES');self.assertFalse(self.a.relink_busy)
    def test_search_casefold_duplicates_no_auto_apply_short_and_symlink_rejected(self):
        a=self.wav(self.root/'usb/A/KICK.WAV');b=self.wav(self.root/'usb/B/Kick.wav');self.wav(self.root/'usb/short/Kick.wav',20)
        outside=self.wav(self.root/'elsewhere/Kick.wav');(self.root/'usb/escape').symlink_to(outside.parent,target_is_directory=True)
        _,row=self.scan();before=copy.deepcopy(self.a.project)
        result=find_replacements(row,[self.root/'usb',self.root/'usb/A'])
        self.assertEqual(result['paths'],sorted([str(a),str(b)],key=str.casefold));self.assertFalse(result['limited']);self.assertEqual(self.a.project,before)
        self.assertTrue(find_replacements(row,[self.root/'usb'],max_files=0)['limited'])
    def test_apply_updates_all_exact_references_preserves_edits_notes_other_samples_and_undo(self):
        a=self.a;a.project['groups'][1]['pads'][4].update(sample=self.old,start=0,end=110)
        other=self.wav(self.root/'samples/Other/Kick.wav');a.project['groups'][0]['pads'][2].update(sample=str(other),start=0,end=150)
        a.track()['slices']=[[10,50],[50,100]];a.track()['zones'][0]['gain']=70;a.lane()[2]=True
        context,row=self.scan();candidate=self.wav(self.root/'usb/Kick.wav');before=copy.deepcopy(a.project)
        a.finish_relink_apply(context,row,validate_replacement(row,candidate))
        restored=copy.deepcopy(a.project)
        for obj in [restored['groups'][0]['pads'][0],restored['groups'][0]['pads'][0]['zones'][0],restored['groups'][0]['pads'][0]['slice_source'],restored['groups'][1]['pads'][4]]:obj['sample']=self.old
        self.assertEqual(restored,before);self.assertTrue(a.dirty)
        self.assertEqual(a.project['groups'][0]['pads'][2]['sample'],str(other))
        a.undo_action();self.assertEqual(a.project,before)
    def test_manual_renamed_file_header_validation_and_persistence(self):
        context,row=self.scan();path=self.wav(self.root/'samples/New Name.wav');a=self.a
        a.relink_row=row;a.open_relink_browser();a.relink_browser.directory=a.samples
        a.button('ENTER',True);self.assertEqual(a.page,'CONFIRM');a.button('F2',True)
        action,(ctx,missing,chosen)=a.actions.pop();self.assertEqual(action,'relink_validate')
        a.finish_relink_apply(ctx,missing,validate_replacement(missing,chosen));a.save()
        self.assertEqual(Application(self.root).track()['sample'],str(path))
        with self.assertRaises(ValueError):validate_replacement(row,self.wav(self.root/'short.wav',30))
    def test_truncated_or_invalid_wav_does_not_replace_and_project_load_queues_check(self):
        a=self.a;_,row=self.scan();path=self.wav(self.root/'bad.wav');path.write_bytes(path.read_bytes()[:60])
        with self.assertRaises(ValueError):validate_replacement(row,path)
        a.project['file_id']='PROJECT-0001';a.save();a.actions.clear();a.load_project(a.root/'projects/PROJECT-0001.json')
        self.assertTrue(any(k=='missing_check' for k,v in a.actions));self.assertFalse(a.playing)
    def test_stale_result_resumed_transport_changed_candidate_and_original_return_are_rejected(self):
        a=self.a;context,row=self.scan();candidate=self.wav(self.root/'usb/Kick.wav');result=validate_replacement(row,candidate);before=copy.deepcopy(a.project)
        a.playing=True;a.finish_relink_apply(context,row,result);self.assertEqual(a.project,before);a.playing=False
        a.revision+=1;a.finish_relink_apply(context,row,result);self.assertEqual(a.project,before);a.revision-=1
        candidate.write_bytes(candidate.read_bytes()+b'extra');a.finish_relink_apply(context,row,result);self.assertEqual(a.project,before)
        result=validate_replacement(row,candidate);self.wav(Path(self.old));a.finish_relink_apply(context,row,result);self.assertEqual(a.project,before);self.assertIn('ORIGINAL AVAILABLE',a.message)
    def test_controller_full_menu_search_results_cancel_browse_and_display(self):
        from app.project_manager import MANAGE
        from app.ni_display import frame
        a=self.a;a.button('SHIFT',True);a.button('MAIN',True);a.button('SHIFT',False);a.button('F3',True);a.menu=a.setting_entries().index('PROJECT SETTINGS');a.button('ENTER',True);a.menu=a.setting_entries().index('PROJECT');a.button('ENTER',True);a.button('F3',True)
        a.manage_index=MANAGE.index('RELINK SAMPLES');a.button('F2',True)
        _,(context,rows)=a.actions.pop();a.finish_missing_check(context,missing_samples(rows));self.assertEqual(len(frame(a)),8192)
        before=copy.deepcopy(a.project);a.button('F2',True);self.assertEqual(a.page,'RELINK RESULTS')
        _,(ctx,row,roots)=a.actions.pop();path=self.wav(self.root/'samples/Kick.wav');a.finish_relink_search(ctx,find_replacements(row,roots));self.assertEqual(len(frame(a)),8192)
        a.button('F2',True);self.assertEqual(a.page,'CONFIRM');a.button('F1',True);self.assertEqual(a.project,before)
        a.button('F3',True);self.assertEqual(a.page,'RELINK BROWSE');self.assertEqual(len(frame(a)),8192)
    def test_audio_loader_missing_primary_does_not_block_available_zones_or_later_sounds(self):
        from app.audio import AudioBackend
        from app.layout import ZONE_BASE
        a=self.a;path=self.wav(self.root/'samples/zone.wav');a.track()['zones'][0]['sample']=str(path)
        audio=AudioBackend.__new__(AudioBackend);audio.loaded={0:('old',0,0)};messages=[];commands=[];audio.command=commands.append;audio.on_message=messages.append
        audio.cache=self.root/'cache';audio.cache.mkdir();audio.load(0,0,a.track())
        self.assertIn('clear 0',commands);self.assertNotIn(0,audio.loaded);self.assertIn(ZONE_BASE,audio.loaded);self.assertEqual(messages,['SAMPLE MISSING/INVALID'])
        audio.load(0,1,dict(a.track(),sample=str(path),zones=[]));self.assertIn(1,audio.loaded)
