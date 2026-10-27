import tempfile,time,wave,array
from concurrent.futures import Future
from pathlib import Path
from unittest.mock import patch
import unittest
from app.mk3_waveforms import Mk3Waveforms
from app.waveform_index import WaveformIndex,IndexedWaveforms
from app.waveform import read_envelope
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.mk3_surface import Mk3Surface
from app.mk3_state import snapshot
from app.mk3_display import Mk3Renderer

class Mk3WaveformTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.reader=Mk3Waveforms();self.addCleanup(self.reader.close)
 def wav(self,name='sample.wav',frames=3000):
  path=self.root/name
  with wave.open(str(path),'wb') as w:
   w.setparams((2,2,48000,0,'NONE','NONE'));w.writeframes(array.array('h',((i*7879)%60000-30000 for i in range(frames*2))).tobytes())
  return path
 def ready(self,path,reader=None):
  reader=reader or self.reader;deadline=time.monotonic()+3
  while True:
   value=reader.envelope(path,columns=460)
   if value is not None:return value
   self.assertLess(time.monotonic(),deadline);time.sleep(.001)
 def test_prefetch_is_async_and_keeps_index_ready_without_building_view(self):
  path=self.wav();future=Future();index=WaveformIndex(path)
  with patch.object(self.reader.worker,'submit',return_value=future) as submit:
   self.reader.prefetch(path);self.assertIs(self.reader.future,future);self.assertFalse(self.reader.cache)
   future.set_result(index);self.reader.collect();self.assertEqual(self.reader.revision,1);self.assertFalse(self.reader.views)
   env=self.reader.envelope(path,columns=460);self.assertEqual(env,index.envelope(columns=460));self.assertEqual(submit.call_count,1)
 def test_pad_switches_retain_more_than_two_assets_and_reuse_exact_views(self):
  paths=[self.wav(f'{i}.wav') for i in range(4)]
  with patch('app.waveform_index.wave.open',wraps=wave.open) as opened:
   results=[self.ready(path) for path in paths]
   self.assertEqual(opened.call_count,4)
   for path,expected in zip(paths,results):self.assertIs(self.reader.envelope(path,columns=460),expected)
   self.assertEqual(opened.call_count,4)
  self.assertEqual(len(self.reader.cache),4)
  # Legacy controller reader keeps its two-file policy.
  legacy=IndexedWaveforms();self.addCleanup(legacy.close)
  for path in paths:self.ready(path,legacy)
  self.assertEqual(len(legacy.cache),2)
 def test_zoom_scroll_cache_matches_pcm_and_is_bounded(self):
  path=self.wav();self.ready(path)
  index=next(iter(self.reader.cache.values()))
  with patch.object(index,'envelope',wraps=index.envelope) as calculate:
   a=self.reader.envelope(path,13,2099,460)
   for _ in range(20):self.assertIs(self.reader.envelope(path,13,2099,460),a)
   self.assertEqual(calculate.call_count,1)
  self.assertEqual(a,read_envelope(path,460,13,2099))
  for start in range(80):self.reader.envelope(path,start,2000,460)
  self.assertLessEqual(len(self.reader.views),64)
 def test_replaced_sample_invalidates_index_and_envelope(self):
  path=self.wav();old=self.ready(path);self.wav(frames=4000);new=self.ready(path)
  self.assertEqual(new.frames,4000);self.assertNotEqual(new,old)
 def test_index_count_and_byte_budget_remain_bounded(self):
  for i in range(18):self.ready(self.wav(f'{i}.wav',100))
  self.assertEqual(len(self.reader.cache),16)
  self.reader.budget=1024;self.ready(self.wav('large.wav',2000))
  self.assertEqual(len(self.reader.cache),1)
 def test_mk3_preloads_selected_sample_outside_waveform_views(self):
  a=Application(self.root);a.track()['sample']=str(self.wav());a.page='PLUGIN';a.control_level=2
  s=Mk3Surface(a,ControllerInputs(a));r=Mk3Renderer();self.addCleanup(r.close)
  state=snapshot(s);self.assertEqual(state['wave_preload'],a.track()['sample'])
  with patch.object(r.waveforms,'prefetch',wraps=r.waveforms.prefetch) as prefetch:r.images(state)
  prefetch.assert_called_once_with(a.track()['sample'])
 def test_completed_load_in_cursor_overlay_still_requests_full_waveform_redraw(self):
  path=self.wav();a=Application(self.root);a.track()['sample']=str(path);a.page='CHANNEL';a.control_level=2
  s=Mk3Surface(a,ControllerInputs(a));r=Mk3Renderer();self.addCleanup(r.close)
  state=snapshot(s);state['wave_cursor']=100;future=Future();index=WaveformIndex(path)
  overlay=r.playback_overlay
  def complete(images,state):
   future.set_result(index)
   return overlay(images,state)
  with patch.object(r.waveforms.worker,'submit',return_value=future),patch.object(r,'playback_overlay',side_effect=complete):
   first=r.images(state)
  self.assertTrue(r.needs_refresh);count=r.scene_renders
  second=r.images(state);self.assertEqual(r.scene_renders,count+1)
  self.assertNotEqual(first[0].tobytes(),second[0].tobytes())
 def test_pending_waveform_has_no_flashing_loading_label(self):
  r=Mk3Renderer();self.addCleanup(r.close)
  from app.mk3_graphics import Canvas
  with patch.object(r.waveforms,'envelope',return_value=None),patch.object(Canvas,'text') as text:
   r.wave(Canvas(),('pending.wav',0,None),{})
  self.assertFalse(text.called)
