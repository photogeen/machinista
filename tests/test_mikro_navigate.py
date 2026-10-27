import copy,pickle,tempfile,time,unittest,wave
from pathlib import Path
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.mk2_surface import Mk2Surface
from app.live_display import live_state,live_frame
from app.step_display import StepDisplay
from app.mikro_navigate import VIEWS

class MikroNavigateTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.a=Application(self.tmp.name);self.inputs=ControllerInputs(self.a)
 def press(self,key):self.inputs.button('mikro',key,True)
 def release(self,key):self.inputs.button('mikro',key,False)
 def tap(self,key):self.press(key);self.release(key)
 def test_encoder_previews_four_workspaces_and_release_commits(self):
  a=self.a
  for i,destination in enumerate(VIEWS):
   with self.subTest(destination=destination):
    a.page='SAMPLER';a.actions.clear();before=copy.deepcopy(a.project)
    self.press('VIEW');self.assertEqual(a.page,'VIEW NAV');self.assertEqual(live_state(a)['kind'],'MIKRO NAV')
    for _ in range(i+1):a.rotate(1)
    state=live_state(a);self.assertEqual((state['focus'],state['active']),(i,i));self.assertEqual(a.page,'VIEW NAV')
    self.assertEqual(a.project,before);self.assertFalse(a.actions)
    self.release('VIEW');self.assertEqual(a.page,destination)
 def test_active_view_remains_selected_and_push_or_f3_deselects(self):
  a=self.a
  for destination in VIEWS:
   for key in ('ENCODER PUSH','F3'):
    with self.subTest(destination=destination,key=key):
     a.page='SAMPLER';self.press('VIEW')
     for _ in range(VIEWS.index(destination)+1):a.rotate(1)
     self.release('VIEW');self.press('VIEW')
     self.assertEqual(live_state(a)['active'],VIEWS.index(destination))
     self.release('VIEW');self.assertEqual(a.page,destination)
     self.press('VIEW');self.tap(key);self.assertEqual(live_state(a)['active'],-1)
     self.release('VIEW');self.assertEqual(a.page,'SAMPLER')
 def test_back_clears_all_icons_and_returns_to_sound_after_release(self):
  a=self.a;a.page='SAMPLER';a.remember_control_view();before=copy.deepcopy(a.project)
  for destination in VIEWS:
   with self.subTest(destination=destination):
    self.press('VIEW')
    for _ in range(VIEWS.index(destination)+1):a.rotate(1)
    self.release('VIEW');self.assertEqual(a.page,destination)
    self.press('VIEW');self.tap('F1')
    self.assertEqual(a.page,'VIEW NAV');self.assertEqual((live_state(a)['focus'],live_state(a)['active']),(-1,-1))
    self.release('VIEW');self.assertEqual(a.page,'SAMPLER');self.assertEqual(a.project,before)
    if destination=='LIVE FX':self.assertEqual(a.live_fx_current,0)
 def test_back_cancel_and_stored_pin_do_not_block_release(self):
  a=self.a;a.page='BROWSE';a.pinned_modes.add('VIEW')
  self.press('VIEW');a.rotate(1);self.tap('F1');self.release('VIEW');self.assertEqual(a.page,a.control_home())
  self.press('VIEW');a.rotate(1);self.press('SHIFT');self.release('VIEW');self.release('SHIFT');self.assertEqual(a.page,'SONG')
 def test_fx_state_stays_live_and_switches_off_only_on_commit(self):
  a=self.a;a.page='PAD';a.open_live_fx('PAD');a.live_fx_mode=2;a.live_fx_pad_on(2,90,'mikro');a.live_fx_pad_off(2,'mikro');a.actions.clear()
  self.press('VIEW');self.assertEqual(live_state(a)['active'],3)
  self.release('VIEW');self.assertEqual((a.page,a.live_fx_mode,a.live_fx_current),('LIVE FX',2,3));self.assertFalse(a.actions)
  self.press('VIEW');a.rotate(-1);self.assertEqual(a.live_fx_current,3)
  self.release('VIEW');self.assertEqual(a.page,'PATTERN GRID');self.assertEqual(a.live_fx_current,0)
 def test_wave_and_editor_zoom_remain_contextual_tools(self):
  a=self.a;path=Path(self.tmp.name)/'samples/test.wav'
  with wave.open(str(path),'wb') as w:w.setparams((1,2,48000,0,'NONE','not compressed'));w.writeframes(b'\0\0'*4800)
  a.track().update(sample=str(path),start=0,end=4800);a.page='SAMPLE EDIT'
  self.press('VIEW');self.assertEqual(a.page,'VIEW NAV');self.assertEqual(a.softkeys()[1],'WAVE')
  self.tap('F2');self.assertTrue(a.wave_view());a.rotate(1);self.assertEqual(a.wave_zoom,1)
  self.release('VIEW');self.assertEqual(a.page,'SAMPLE EDIT');self.assertFalse(a.wave_view())
  a.page='PATTERN GRID';before=a.view_count;self.press('VIEW');self.assertEqual(a.softkeys()[1],'GRID')
  self.tap('F2');a.rotate(1);self.assertLess(a.view_count,before)
  self.tap('F1');self.assertEqual(live_state(a)['kind'],'MIKRO NAV');self.release('VIEW');self.assertEqual(a.page,a.control_home())
 def test_batched_turns_and_wave_pin_remain_usable(self):
  a=self.a;a.page='PAD';self.press('VIEW');a.rotate(3);self.assertEqual(a.view_origin,'PATTERN GRID')
  a.rotate(99);self.assertEqual(a.view_origin,'LIVE FX');a.rotate(-99);self.assertEqual(a.view_origin,'SONG')
  self.tap('F1');self.release('VIEW');self.assertEqual(a.page,'PAD')
  a.page='SAMPLE EDIT';self.press('VIEW');self.tap('F2');self.tap('MAIN');self.release('VIEW')
  self.assertTrue(a.wave_view());self.assertTrue(a.wave_view_pinned)
  self.press('VIEW');self.assertEqual(a.page,'VIEW NAV');self.assertFalse(a.wave_view_active)
  self.release('VIEW');self.assertEqual(a.page,'SAMPLE EDIT')
 def test_fullsize_navigate_buttons_keep_their_bindings(self):
  a=self.a;a.page='SAMPLER';s=Mk2Surface(a,self.inputs)
  s.button('NAVIGATE',True);self.assertFalse(a.view_selector);s.softkey(3);s.button('NAVIGATE',False)
  self.assertEqual(a.page,'MIXER')
 def test_icon_snapshots_render_in_detached_worker_and_have_pixel_margin(self):
  a=self.a;a.page='PAD';self.press('VIEW');worker=StepDisplay();self.addCleanup(worker.close)
  frames=[]
  for _ in VIEWS:
   a.rotate(1);state=live_state(a);self.assertLess(len(pickle.dumps(state)),512)
   frame=live_frame(state);self.assertEqual(len(frame),8192);frames.append(frame)
   self.assertTrue(all(frame[y*128] and frame[y*128+127] for y in range(64)))
   self.assertEqual(frame[:128],bytes([1])*128);self.assertEqual(frame[-128:],bytes([1])*128)
  self.assertEqual(len(set(frames)),4);self.assertTrue(worker.submit(live_state(a)))
  deadline=time.monotonic()+3;result=None
  while result is None and time.monotonic()<deadline:result=worker.poll();time.sleep(.002)
  self.assertEqual(result,frames[-1]);self.release('VIEW')

if __name__=='__main__':unittest.main()
