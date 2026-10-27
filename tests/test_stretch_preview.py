import array
import copy
from concurrent.futures import Future
import math
from pathlib import Path
import shutil
import tempfile
import unittest
import wave
from unittest.mock import patch
from app.model import Application
from app.ni_display import softkey_label
from app.stretch_preview import StretchPreview,render_stretch_preview,prepare_stretch_preview,stretch_key
from app.audio import AudioBackend

class FakeWorker:
    def __init__(self):self.calls=[]
    def submit(self,function,*args):
        f=Future();self.calls.append((f,function,args));return f
    def shutdown(self,**kwargs):pass

class StretchPreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.source=self.root/'tone.wav';values=array.array('h',[round(10000*math.sin(2*math.pi*440*i/44100)) for i in range(11025)])
        with wave.open(str(self.source),'wb') as w:w.setparams((1,2,44100,0,'NONE','not compressed'));w.writeframes(values.tobytes())
        self.track={'sample':str(self.source),'start':0,'end':11025,'selection_start':0,'selection_end':11025,'stretch_ratio':200,'stretch_pitch':12}
    def tearDown(self):self.temp.cleanup()
    def jobs(self):
        j=StretchPreview(self.root/'cache');j.worker.shutdown();j.worker=FakeWorker();self.addCleanup(j.cleanup);self.addCleanup(j.close);return j
    def test_pad_auditions_selected_sound_without_mutating_or_applying(self):
        a=Application(self.root);a.page='STRETCH';a.pad=2;a.keyboard_enabled=True;a.fixed_velocity=False
        a.track().update(self.track);before=copy.deepcopy(a.project);a.actions=[];a.pad_on(10,83)
        action,(track,context,velocity)=a.actions[-1]
        self.assertEqual(action,'stretch_preview');self.assertEqual(context,(0,0,2,0));self.assertEqual(velocity,83)
        self.assertEqual(a.project,before);self.assertEqual(track['stretch_pitch'],12)
        a.button('F3',True);self.assertIn(('preview_stop',None),a.actions);self.assertEqual(a.page,'SAMPLE EDIT')
    def test_stale_requests_are_coalesced_and_cached_without_repeated_render(self):
        j=self.jobs();context=(0,0,2,0);first=dict(self.track);second=dict(first,stretch_pitch=7)
        j.request(first,context,70);j.request(second,context,90)
        self.assertEqual(len(j.worker.calls),1)
        j.worker.calls[0][0].set_result(dict(first,sample='render1.wav'))
        self.assertIsNone(j.poll(stretch_key(second,context)));self.assertEqual(len(j.worker.calls),2)
        j.worker.calls[1][0].set_result(dict(second,sample='render2.wav'))
        rendered,velocity,error=j.poll(stretch_key(second,context));self.assertEqual(rendered['sample'],'render2.wav');self.assertEqual(velocity,90);self.assertIsNone(error)
        self.assertEqual(j.request(second,context,80)[1],80);self.assertEqual(len(j.worker.calls),2)
    def test_leave_change_or_project_switch_discards_pending_playback(self):
        for context in (None,(1,0,2,0),(0,0,3,0),(0,0,2,1)):
            with self.subTest(context=context):
                j=self.jobs();j.request(self.track,(0,0,2,0),100)
                j.worker.calls[0][0].set_result(self.track)
                active=None if context is None else j.active_key(self.track,context)
                self.assertIsNone(j.poll(active));self.assertIsNone(j.latest)
    def test_active_key_does_not_query_disk_on_each_ui_tick(self):
        j=self.jobs();j.request(self.track,(0,0,2,0),100)
        with patch.object(Path,'stat',side_effect=AssertionError('UI disk read')):
            self.assertIsNotNone(j.active_key(self.track,(0,0,2,0)))
    def test_unchanged_preview_uses_original_and_keeps_project_untouched(self):
        source=dict(self.track,stretch_ratio=100,stretch_pitch=0);before=copy.deepcopy(source)
        preview=render_stretch_preview(source,self.root/'preview')
        self.assertEqual(preview['sample'],str(self.source));self.assertEqual(source,before)
    def test_worker_prepares_pcm_and_backend_audition_needs_no_conversion(self):
        folder=self.root/'preview';folder.mkdir()
        preview=prepare_stretch_preview(dict(self.track,stretch_ratio=100,stretch_pitch=0),folder)
        self.assertEqual(Path(preview['_preview_pcm']).stat().st_size,11025*8)
        backend=AudioBackend.__new__(AudioBackend);backend.loaded={};commands=[];backend.command=commands.append
        with patch('app.audio.convert_sample',side_effect=AssertionError('UI conversion')):
            backend.stretch_preview(preview,83)
        self.assertTrue(commands[0].startswith('load '));self.assertTrue(commands[-1].startswith('hit '))
    @unittest.skipUnless(shutil.which('rubberband'),'Rubber Band CLI required')
    def test_actual_preview_doubles_length_and_pitch_preserving_original(self):
        original=self.source.read_bytes();preview=render_stretch_preview(self.track,self.root/'preview')
        self.assertEqual(self.source.read_bytes(),original)
        with wave.open(preview['sample'],'rb') as w:
            frames=w.getnframes();samples=array.array('h');samples.frombytes(w.readframes(frames));self.assertEqual(w.getframerate(),44100)
        self.assertLess(abs(frames-22050),100)
        samples=samples[frames//4:frames*3//4];crossings=sum(samples[i]<=0<samples[i+1] for i in range(len(samples)-1))
        frequency=crossings*44100/len(samples);self.assertLess(abs(frequency-880),40)
        self.assertEqual(preview['end'],frames)
    def test_regular_and_compact_softkey_ink_is_centered_in_each_rectangle(self):
        for left,tab_width in ((1,41),(44,41),(87,40)):
            for text in ('NORM','STRETCH','TRUNC','FADE IN','DUPLICATE','APPLY'):
                with self.subTest(left=left,text=text):
                    p=bytearray([1]*8192);softkey_label(p,left,tab_width,text,0)
                    xs=[x for y in range(3,8) for x in range(128) if not p[y*128+x]]
                    self.assertTrue(xs);self.assertLessEqual(abs((min(xs)+max(xs))-(2*left+tab_width-1)),1)
                    self.assertGreater(min(xs),left);self.assertLess(max(xs),left+tab_width-1)
