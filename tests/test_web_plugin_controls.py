import tempfile,unittest,copy
from app.model import Application
from app.web_plugin_controls import apply_parameters
class PluginControlTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.a=Application(self.tmp.name)
  self.a.plugin_catalog=[dict(uri='test',ports=[dict(symbol='bank',min=0,max=28,integer=True),dict(symbol='gain',min=0,max=1)])]
  self.a.track()['plugins']=[dict(uri='test',kind='INSTRUMENT',controls={'bank':0,'gain':.7})]
 def request(self,**updates):return dict(slot=0,uri='test',controls=updates)
 def test_applies_to_current_sound_without_changing_ui_focus(self):
  self.a.control_level=0;page=self.a.page;revision=self.a.revision
  apply_parameters(self.a,self.request(bank=6,gain=.4))
  self.assertEqual(self.a.page,page);self.assertGreater(self.a.revision,revision)
  self.assertEqual(self.a.track()['plugins'][0]['controls'],dict(bank=6,gain=.4))
  self.assertEqual(self.a.actions[-1][0],'plugins');self.assertEqual(self.a.actions[-1][1][0],0)
 def test_invalid_updates_are_atomic(self):
  original=copy.deepcopy(self.a.track())
  for updates in ({'bank':6,'gain':2},{'bank':.5},{'gain':float('nan')},{'unknown':0}):
   with self.assertRaises(ValueError):apply_parameters(self.a,self.request(**updates))
   self.assertEqual(self.a.track(),original)
 def test_wrong_slot_and_replaced_plugin_cannot_be_edited(self):
  for request in (dict(slot=-1,uri='test',controls={'bank':1}),dict(slot=0,uri='other',controls={'bank':1})):
   with self.assertRaises(ValueError):apply_parameters(self.a,request)
 def test_runtime_rpc_keeps_context_and_stop_guards(self):
  import queue,time
  from unittest.mock import Mock
  from app.sound_runtime import SoundRuntime
  audio=Mock();audio.native_capture=None;runtime=SoundRuntime(self.tmp.name,self.a,audio,Mock())
  try:
   coordinates=dict(group=self.a.group,pad=self.a.pad,generation=self.a.project_generation,revision=self.a.revision)
   done=queue.Queue();value=dict(operation='plugin_parameters',**coordinates,**self.request(bank=6))
   runtime.requests.put((value,done,time.monotonic()+4));runtime.poll(time.monotonic());self.assertTrue(done.get()['ok'])
   done=queue.Queue();runtime.requests.put((value,done,time.monotonic()+4));runtime.poll(time.monotonic());self.assertIn('Selected Sound changed',done.get()['error'])
   value['revision']=self.a.revision;self.a.playing=True
   done=queue.Queue();runtime.requests.put((value,done,time.monotonic()+4));runtime.poll(time.monotonic());self.assertIn('Stop playback',done.get()['error'])
  finally:runtime.close()
