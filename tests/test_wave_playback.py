import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from app.model import Application
from app.wave_playback import WavePlayback,position
from app.layout import PREVIEW
from app.waveform import Envelope
from app.ni_display import frame
from app.mk2_surface import Mk2Surface
from app.controller_inputs import ControllerInputs
from app.mk2_display import snapshot,Mk2Renderer

class WavePlaybackTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.a=Application(self.tmp.name);self.a.page='SAMPLE EDIT';self.a.track().update(sample='/sample.wav',start=100,end=1100)
  self.commands=[];self.audio=SimpleNamespace(loaded={0:('/sample.wav',1,20)},command=self.commands.append)
  self.w=WavePlayback()
 def test_bounded_watch_and_expiry_reject_old_replies_and_wrong_sample(self):
  a=self.a;w=self.w;w.update(a,self.audio,1)
  self.assertEqual(self.commands,['wave_watch 1 0 0','wave_status'])
  w.update(a,self.audio,1.01);self.assertEqual(len(self.commands),2)
  w.receive(a,dict(kind='wave_position',token=1,frame=300,active=True),1.02)
  self.assertEqual(position(a,'/sample.wav',1.1),300);self.assertIsNone(position(a,'/other.wav',1.1));self.assertIsNone(position(a,'/sample.wav',1.23))
  a.pad=1;w.update(a,self.audio,1.1);self.assertIsNone(a.wave_playback)
  w.receive(a,dict(kind='wave_position',token=1,frame=600,active=True),1.11);self.assertIsNone(a.wave_playback)
  w.receive(a,dict(kind='wave_position',token=2,frame=400,active=True),1.12)
  w.receive(a,dict(kind='wave_position',token=2,frame=0,active=False),1.13);self.assertIsNone(a.wave_playback)
 def test_only_visible_samples_and_selected_sound_are_watched(self):
  a=self.a;a.page='ZONE';a.track()['zones']=[dict(sample='/zone.wav',start=20,end=300,root=60,key_lo=0,key_hi=127,vel_lo=1,vel_hi=127)]
  from app.layout import ZONE_BASE
  self.audio.loaded[ZONE_BASE]=('/zone.wav',1,30)
  self.w.update(a,self.audio,1);self.assertEqual(self.commands[0],f'wave_watch 1 0 {ZONE_BASE}')
  a.page='PAD';a.control_level=0;self.w.update(a,self.audio,2)
  self.assertTrue(self.commands[-1].startswith('wave_watch 0 '))
 def test_stretch_preview_maps_rendered_frames_to_original_range(self):
  self.a.page='STRETCH'
  self.audio.wave_preview=('/sample.wav',100,1100,100,2100)
  self.w.update(self.a,self.audio,1);self.assertIn(f'wave_watch 1 0 {PREVIEW}',self.commands)
  self.w.receive(self.a,dict(kind='wave_position',token=1,frame=1100,active=True),1)
  self.assertEqual(position(self.a,'/sample.wav',1),600)
  self.a.page='PAD';self.a.control_level=2;self.w.update(self.a,self.audio,2)
  self.assertIn('wave_watch 2 0 0',self.commands)
 def test_disabling_wave_page_disables_audio_watch(self):
  self.w.update(self.a,self.audio,1);self.a.page='SETTINGS';self.w.update(self.a,self.audio,2)
  self.assertIsNone(self.a.wave_playback);self.assertTrue(self.commands[-1].startswith('wave_watch 0 '))
 def test_mikro_and_mk2_render_cursor_at_viewport_position(self):
  a=self.a;a.wave_playback=dict(path='/sample.wav',frame=600,stamp=time.monotonic())
  envelope=Envelope(1200,tuple((-.5,.5) for _ in range(120)),100,1100)
  on=frame(a,envelope);a.wave_playback=None;off=frame(a,envelope)
  self.assertTrue(any(on[y*128+64]!=off[y*128+64] for y in range(24,42)))
  a.page='ZONE';a.track()['zones']=[dict(sample='/sample.wav',start=100,end=1100,loop=False)]
  a.wave_playback=dict(path='/sample.wav',frame=600,stamp=time.monotonic());zone_on=frame(a,envelope)
  a.wave_playback=None;zone_off=frame(a,envelope);self.assertNotEqual(zone_on,zone_off)
  a.page='SAMPLE EDIT'
  a.wave_playback=dict(path='/sample.wav',frame=600,stamp=time.monotonic())
  surface=Mk2Surface(a,ControllerInputs(a));state=snapshot(surface)
  state.update(wave=('/sample.wav',100,1100),markers=((100,1100),))
  renderer=Mk2Renderer();self.addCleanup(renderer.close)
  with patch.object(renderer.waveforms,'envelope',return_value=envelope):
   on=renderer(state);off=renderer(dict(state,wave_cursor=None))
  self.assertNotEqual(on[0],off[0])
  state.update(wave_cursor=50)
  with patch.object(renderer.waveforms,'envelope',return_value=envelope):
   self.assertEqual(renderer(state)[0],off[0])
