import copy,queue,tempfile,time,unittest
from pathlib import Path
from unittest.mock import Mock
from app.model import Application
from app.plugin_profiles import profile
from app.synth_library import URI
from app.web_synth import apply,schema

class WebSynthTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.a=Application(self.root);self.p=profile(URI)
  self.a.plugin_catalog=[dict(uri=URI,name='Machinista Synth',kind='INSTRUMENT',supported=True,ports=self.p['parameters'])]
  self.a.track()['plugins']=[dict(uri=URI,kind='INSTRUMENT',controls={p['symbol']:p['default'] for p in self.p['parameters']})]
 def req(self,**kw):return dict(slot=0,uri=URI,**kw)
 def test_compact_controller_full_web_and_stable_parameters(self):
  self.a.control_level=2
  ports=self.a.plugin_controls();self.assertEqual(len(ports),64);self.assertEqual(len(self.p['pages']),8)
  full=schema(self.root);self.assertEqual(len(full['parameters']),588)
  self.assertEqual({s for p in full['pages'] for s in p['controls'] if not s.startswith('@')},{p['symbol'] for p in full['parameters']})
  self.assertEqual(len(full['previews']),32);self.assertIn('targets',full['choices'])
 def test_live_numeric_edits_keep_focus_and_instance(self):
  a=self.a;a.playing=True;page=a.page;a.control_level=0
  result=apply(a,self.req(controls={'filter2_cutoff':2345,'mod32_amount':.4,'ring4_fine3':3.5}))
  self.assertEqual(a.page,page);self.assertEqual(a.control_level,0);self.assertTrue(result['ok'])
  self.assertEqual(a.track()['plugins'][0]['controls']['filter2_cutoff'],2345)
  self.assertEqual(a.actions[-1][0],'plugins');self.assertEqual(a.actions[-1][1][0],0)
 def test_gesture_has_one_undo_and_advances_revision_each_update(self):
  a=self.a;initial=copy.deepcopy(a.project);n=len(a.undo);rev=a.revision
  for i in range(4):apply(a,self.req(controls={'output':i*.1},gesture='drag-1'))
  self.assertEqual(len(a.undo),n+1);self.assertEqual(a.revision,rev+4);self.assertEqual(a.undo[-1],initial)
  apply(a,self.req(controls={'output':.8},gesture='drag-2'));self.assertEqual(len(a.undo),n+2)
 def test_invalid_edits_are_atomic(self):
  initial=copy.deepcopy(self.a.project)
  for req in (self.req(controls={'unknown':.5}),self.req(controls={'output':float('nan')}),self.req(controls={'mono':.5}),self.req(controls={'output':.1,'osc1_wave':32}),self.req(wave={'osc':1,'id':'a'*32}),self.req(preset={'bank':'missing','patch':0}),self.req(controls={'output':.1},preset={'bank':'init','patch':0}),self.req(controls={'output':.1},gesture=[])):
   with self.assertRaises(ValueError):apply(self.a,req)
   self.assertEqual(self.a.project,initial)
 def test_preset_and_user_wave_use_existing_storage(self):
  from tests.test_native_synth import wav
  from app.synth_library import upload
  import io
  data=wav();row=upload(self.root,'User.wav',io.BytesIO(data),len(data))
  apply(self.a,self.req(wave={'osc':3,'id':row['id']}))
  plugin=self.a.track()['plugins'][0];self.assertEqual(plugin['synth_waves']['3']['id'],row['id']);self.assertEqual(plugin['controls']['osc3_wave'],32)
  apply(self.a,self.req(preset={'bank':'init','patch':0}));self.assertEqual(plugin['profile_preset']['bank'],'init');self.assertEqual(plugin['controls']['osc3_wave'],0)
 def test_runtime_rejects_stale_target_allows_live_synth_only(self):
  from app.sound_runtime import SoundRuntime
  a=self.a;audio=Mock();audio.native_capture=None;runtime=SoundRuntime(self.root,a,audio,Mock());self.addCleanup(runtime.close)
  a.playing=True
  def send(value):
   done=queue.Queue();runtime.requests.put((value,done,time.monotonic()+4));runtime.poll(time.monotonic());return done.get()
  coordinates=dict(group=a.group,pad=a.pad,generation=a.project_generation,revision=a.revision)
  value=dict(operation='synth_edit',**coordinates,**self.req(controls={'filter1_cutoff':1200}))
  self.assertTrue(send(value)['ok']);self.assertIn('Selected Sound changed',send(value)['error'])
  value.update(revision=a.revision,pad=1);self.assertIn('Selected Sound changed',send(value)['error'])
  value.update(pad=a.pad);audio.native_capture={'source':0};self.assertIn('Finish sampling',send(value)['error'])
  audio.native_capture=None;value.update(operation='plugin_parameters');self.assertIn('Stop playback',send(value)['error'])

class WebSynthHttpTests(unittest.TestCase):
 from tests.test_web_server import WebHttpTests as _base
 setUp=_base.setUp
 stop=_base.stop
 request=_base.request
 def test_schema_routes_and_write_token(self):
  import json
  status,_,raw=self.request('GET','/api/synth');data=json.loads(raw)
  self.assertEqual(status,200);self.assertEqual(len(data['parameters']),588)
  status,_,_=self.request('GET','/api/synth/wave?id=../bad');self.assertEqual(status,400)
  body=json.dumps({'operation':'synth_edit','slot':0,'uri':URI,'controls':{'output':.5}})
  self.assertEqual(self.request('POST','/api/sounds/command',body)[0],403)
  from unittest.mock import patch
  with patch.object(self.library.sounds,'command',return_value={'ok':True,'revision':1}) as send:
   status,_,_=self.request('POST','/api/sounds/command',body,{'X-Machinista-Token':self.library.token})
   self.assertEqual(status,200);self.assertEqual(send.call_args.args[0],'synth_edit')
