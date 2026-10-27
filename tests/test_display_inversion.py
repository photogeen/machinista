import copy,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from app.model import Application
from app.controller_settings import controller_context
from app.controller_inputs import ControllerInputs
from app.mk2_surface import Mk2Surface
from app.mk1_session import Mk1Surface
from app.mk2_display import snapshot,Mk2Renderer
from app.controller_output import ControllerOutput

class DisplayInversionTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.a=Application(self.temp.name);self.inputs=ControllerInputs(self.a)
 def test_per_device_edit_reset_persistence_and_unchanged_defaults(self):
  a=self.a
  self.assertFalse(a.settings['display_invert'])
  for source in ('mikro','mk1','mk2'):
   with controller_context(a,source):
    a.page='INVERT';before=copy.deepcopy(a.settings);a.rotate(1)
    key='display_invert' if source=='mikro' else 'invert'
    values=a.settings if source=='mikro' else a.settings['controllers'][source]
    self.assertIs(values[key],True)
    if source!='mikro':self.assertEqual(a.settings['display_invert'],before['display_invert'])
    for other in ('mk1','mk2'):
     if other!=source:self.assertEqual(a.settings['controllers'][other],before['controllers'][other])
    self.assertIn(('display_settings',None) if source=='mikro' else ('controller_display_settings',source),a.actions)
    loaded=Application(self.temp.name);self.assertIs((loaded.settings if source=='mikro' else loaded.settings['controllers'][source])[key],True)
    a.button('SHIFT',True);a.button('F1',True);a.button('F1',False);a.button('SHIFT',False);self.assertIs(values[key],False)
 def test_menu_and_fullsize_encoder_field_follow_source(self):
  a=self.a;a.settings_folder='SYSTEM';a.settings_section='DISPLAY'
  for source in ('mikro','mk1','mk2'):
   with controller_context(a,source):self.assertIn('INVERT',a.setting_entries())
  for surface in (Mk1Surface(a,self.inputs),Mk2Surface(a,self.inputs)):
   a.page='INVERT';self.assertEqual(surface.fields()[5].label,'INVERT')
   from app.mk2_encoders import choice_binding
   self.assertTrue(choice_binding(surface,surface.fields()[5]))
   surface.rotate(6,1);self.assertEqual(surface.fields()[5].value,'ON')
   other='mk2' if surface.source=='mk1' else 'mk1'
   self.assertTrue(snapshot(surface)['display_invert']);surface.softkey(1)
   self.assertFalse(a.settings['controllers'][surface.source]['invert'])
   self.assertFalse(a.settings['controllers'][other]['invert'])
 def test_all_dual_screen_pixels_and_boot_are_complemented_once(self):
  r=Mk2Renderer();self.addCleanup(r.close);a=self.a;surface=Mk2Surface(a,self.inputs)
  for page in ('PAD','SAMPLER','BROWSE','SAMPLING','SAMPLE EDIT','CHOP','ZONE','STEP','MIXER','SYSTEM','INVERT'):
   a.page=page;s=snapshot(surface);normal=r(s);s['display_invert']=True;inverted=r(s)
   for first,second in zip(normal,inverted):self.assertEqual(bytes(v^1 for v in first),bytes(second),page)
  with patch.object(r.boot,'active',return_value=True):
   s['display_invert']=False;normal=r(s);s['display_invert']=True;inverted=r(s)
   for first,second in zip(normal,inverted):self.assertEqual(bytes(v^1 for v in first),bytes(second))
 def test_mikro_output_refreshes_cached_frame_without_touching_leds(self):
  sent=[];configured=[];frame=bytes([0,1])*4096
  out=ControllerOutput(0,lambda p:[p],lambda fd,p:sent.append(p),lambda fd,*v:configured.append(v));self.addCleanup(out.close)
  def wait(count):
   deadline=time.monotonic()+2
   while out.frames<count and out.error is None and time.monotonic()<deadline:time.sleep(.001)
   self.assertIsNone(out.error);self.assertGreaterEqual(out.frames,count)
  out.submit(frame,b'LED');wait(1)
  out.display_settings(100,42,True);wait(2)
  self.assertEqual(sent[-1],bytes(v^1 for v in frame));self.assertEqual(out.last_pixels,frame)
  out.display_settings(100,42,False);wait(3);out.close()
  self.assertEqual(sent,[b'LED',frame,bytes(v^1 for v in frame),frame]);self.assertEqual(configured,[(100,42),(100,42)])
 def test_boolean_settings_reject_numeric_or_string_values(self):
  from app.storage import save_json
  for source in ('mikro','mk1','mk2'):
   data=copy.deepcopy(self.a.settings)
   if source=='mikro':data['display_invert']='ON'
   else:data['controllers'][source]['invert']=1
   save_json(Path(self.temp.name)/'config/settings.json',data)
   with self.assertRaises(ValueError):Application(self.temp.name)

if __name__=='__main__':unittest.main()
