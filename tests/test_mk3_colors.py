import copy,tempfile,unittest
from pathlib import Path
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.mk3_surface import Mk3Surface
from app.mk3_state import snapshot,event_state,tick_text,length_text
from app.mk3_display import Mk3Renderer
from app.mk3_graphics import GROUPS
from app.mk3_style import parameter_color,CYAN,PURPLE,YELLOW,GREEN

class ColorEventsTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.a=Application(self.tmp.name);self.s=Mk3Surface(self.a,ControllerInputs(self.a))
  self.a.set_pattern_length(32);self.a.page='PATTERN GRID';self.a.grid_notes=True;self.a.grid_note=60;self.a.view_count=32;self.a.view_first=0
 def note(self,tick,note=60,length=96,velocity=96,index=1,pad=0):
  identity=f'{index:032x}';key=(pad,tick,identity)
  self.a.put_event(key,dict(note=note,length=length,velocity=velocity,probability=100,_id=identity))
  return key
 def test_polyphony_length_selection_and_real_detail(self):
  first=self.note(384,index=1);self.note(384,note=64,index=2);self.note(384,note=67,index=3,pad=1)
  self.a.grid_selected={first};self.a.grid_step=16
  self.a.playing=True;self.a.active_patterns[self.a.group]=self.a.pattern;self.a.active_clips[self.a.group]=True;self.a.clock_phase=384
  state=snapshot(self.s);g=state['events_native']
  self.assertEqual(len(g['notes']),2) # current Sound only, polyphonic notes retained
  self.assertEqual(g['detail']['pitch'],'C3');self.assertEqual(g['detail']['position'],'2.1.1')
  self.assertEqual(g['detail']['length'],'1/4');self.assertEqual(g['detail']['velocity'],96)
  self.assertEqual(g['playhead'],384);self.assertEqual(state['fields'][6][1],'C3')
  self.assertTrue(any(v[3] for v in g['notes']))
  self.a.playing=False
  self.assertEqual(event_state(self.a)['playhead'],384)
  self.assertEqual(snapshot(self.s)['events_native']['playhead'],384)
 def test_duration_crossing_view_edge_and_hidden_playhead(self):
  self.note(0,length=192);self.a.view_first=4;self.a.clock_phase=0;self.a.playing=True
  g=event_state(self.a);self.assertTrue(g['notes']);self.assertEqual(g['notes'][0][1:3],(0,192));self.assertIsNone(g['playhead'])
 def test_empty_cell_does_not_display_invented_event(self):
  g=event_state(self.a);self.assertIsNone(g['detail']);self.assertEqual(g['notes'],())
 def test_snapshot_is_detached_and_preserves_pattern_data(self):
  self.note(48);before=copy.deepcopy(self.a.project);state=snapshot(self.s)
  self.assertEqual(self.a.project,before);self.a.track()['gain']=20
  self.assertEqual(state['events_native']['velocities'][0][1],96)
 def test_group_mixer_reports_real_mute_solo_and_color_identity(self):
  self.a.page='MIXER';self.a.mixer_level=1
  self.a.project['groups'][1]['mute']=True;self.a.project['groups'][2]['solo']=True
  s=snapshot(self.s);m=s['mixer'];self.assertTrue(m['status'][1][0]);self.assertTrue(m['status'][2][1]);self.assertEqual(m['colors'][:3],(0,1,2))
 def test_time_and_semantic_roles(self):
  self.assertEqual(tick_text(385),'2.1.1+1');self.assertEqual(length_text(96),'1/4')
  self.assertEqual(parameter_color('cutoff'),YELLOW);self.assertEqual(parameter_color('attack'),PURPLE)
  self.assertEqual(parameter_color('position'),CYAN);self.assertEqual(parameter_color('gain'),GREEN)
 def test_all_workspaces_and_sampler_sections_render(self):
  from app.ui_inventory import PAGES
  r=Mk3Renderer();self.addCleanup(r.close);self.a.sample_delete_index=0
  self.a.confirmation=('TEST',lambda:None,'PAD')
  for page in PAGES:
   with self.subTest(page=page):
    self.a.page=page
    if page=='CONFIRM':self.a.confirm('TEST',lambda:None)
    result=r(snapshot(self.s));self.assertEqual(tuple(map(len,result)),(261120,261120))
  # A real indexed sample exercises native 460-column drawing and markers.
  import wave,time
  from unittest.mock import patch
  path=Path(self.tmp.name)/'wave.wav'
  with wave.open(str(path),'wb') as wav:
   wav.setparams((1,1,8000,0,'NONE','not compressed'));wav.writeframes(bytes(range(256))*16)
  deadline=time.monotonic()+3;envelope=None
  while envelope is None and time.monotonic()<deadline:
   envelope=r.waveforms.envelope(path,columns=460);time.sleep(.001)
  self.assertIsNotNone(envelope);self.assertEqual(len(envelope.peaks),460)
  with patch('app.waveform_index.wave.open',side_effect=AssertionError('Waveform reread')):
   self.assertEqual(len(r.waveforms.envelope(path).peaks),120)
  self.a.page='SAMPLE EDIT';self.a.track().update(sample=str(path),start=0,end=4096)
  self.assertEqual(len(r(snapshot(self.s))[0]),261120)
  self.a.page='SAMPLER'
  for section in range(6):
   self.a.sampler_page=section;self.assertEqual(len(r(snapshot(self.s))[0]),261120)
 def test_display_group_chips_match_identity_and_keep_black_pixel_margin(self):
  from PIL import ImageColor
  self.a.page='CHANNEL';self.a.group=5;r=Mk3Renderer();self.addCleanup(r.close)
  left,right=r.draw(snapshot(self.s));self.assertEqual(left.getpixel((153,38)),ImageColor.getrgb(GROUPS[5]))
  from app.mk3_graphics import BG
  self.assertEqual(left.getpixel((479,271)),ImageColor.getrgb(BG))
