import copy,io,json,math,struct,tempfile,unittest,wave
from pathlib import Path
from app import synth_library as lib
from app.plugin_profiles import profile,validate_bank
from app.model import Application,validate_project
from app.ni_display import plugin_value,frame
from app.mk2_surface import Mk2Surface
from app.mk2_display import snapshot,Mk2Renderer
from app.controller_inputs import ControllerInputs
from app.synth_display import view

def wav(frames=512,channels=1):
 out=io.BytesIO()
 with wave.open(out,'wb') as f:
  f.setnchannels(channels);f.setsampwidth(2);f.setframerate(44100)
  f.writeframes(b''.join(struct.pack('<h',round(20000*math.sin(i*math.tau/512))) * channels for i in range(frames)))
 return out.getvalue()

class NativeSynthTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.a=a=Application(self.root);a.page='PLUGIN';a.control_level=2
  self.p=profile(lib.URI);a.plugin_catalog=[dict(uri=lib.URI,name='Machinista Synth',kind='INSTRUMENT',supported=True,builtin=True,ports=self.p['parameters'])]
  a.track()['plugins']=[dict(uri=lib.URI,kind='INSTRUMENT',controls={p['symbol']:p['default'] for p in self.p['parameters']})]
 def upload(self,title='My Wave.wav',frames=512,cycle=0):
  data=wav(frames);return lib.upload(self.root,title,io.BytesIO(data),len(data),cycle)
 def test_all_pages_presets_and_percent_cents_units(self):
  a=self.a;before=copy.deepcopy(a.project);ports=a.plugin_controls();self.assertEqual(len(self.p['parameters']),588);self.assertEqual(len(ports)%8,0)
  self.assertEqual(len(ports),64);self.assertEqual({s for page in self.p['web_pages'] for s in page['controls'] if not s.startswith('@')},{p['symbol'] for p in self.p['parameters']})
  fine=next(p for p in ports if p['symbol']=='osc1_fine');self.assertIn('CT',plugin_value(fine,1.5))
  level=next(p for p in ports if p['symbol']=='osc1_level');self.assertEqual(plugin_value(level,.65),'65%')
  validate_bank(json.loads((Path(__file__).resolve().parents[1]/'presets/plugin-banks/machinista-synth/factory.json').read_text()),self.p)
  self.assertEqual(a.project,before)
 def test_controls_reuse_static_layout_and_invalidate_only_source_metadata(self):
  from unittest.mock import patch
  from app import plugin_profiles
  a=self.a;selected=a.plugin_selected()
  lib._layout_cache.clear()
  with patch.object(plugin_profiles,'controls',wraps=plugin_profiles.controls) as build:
   first=a.plugin_controls();first_targets=next(p for p in first if p['symbol']=='mod1_target')['choices']
   for value in range(15):
    selected['controls']['filter1_cutoff']=300+value
    ports=a.plugin_controls()
    self.assertIs(next(p for p in ports if p['symbol']=='mod1_target')['choices'],first_targets)
   self.assertEqual(sum(len(c.args)>3 and c.args[3] is False for c in build.call_args_list),1)
   shape=lambda:next(p for p in a.plugin_controls() if p['symbol']=='osc1_shape')
   self.assertTrue(shape()['synth_inactive'])
   selected['controls']['osc1_wave']=4
   self.assertEqual(shape()['name'],'PULSE WIDTH');self.assertFalse(shape().get('synth_inactive'))
   selected['controls']['osc1_wave']=24
   self.assertEqual(shape()['name'],'POSITION');self.assertFalse(shape().get('synth_inactive'))
   self.assertEqual(sum(len(c.args)>3 and c.args[3] is False for c in build.call_args_list),1)
   # An inventory refresh owns new metadata; no stale defaults or references.
   a.plugin_catalog[0]['ports']=copy.deepcopy(a.plugin_catalog[0]['ports'])
   a.plugin_controls();self.assertEqual(sum(len(c.args)>3 and c.args[3] is False for c in build.call_args_list),2)
  self.assertTrue(next(p for p in first if p['symbol']=='osc1_shape')['synth_inactive'])
 def test_cached_bank_and_patch_selectors_follow_preset_and_sound_switches(self):
  a=self.a;selected=a.plugin_selected();a.plugin_controls()
  folder=self.root/'presets/plugin-banks/machinista-synth';folder.mkdir(parents=True)
  factory=json.loads((Path(__file__).resolve().parents[1]/'presets/plugin-banks/machinista-synth/factory.json').read_text())
  (folder/'factory.json').write_text(json.dumps(factory));plugin_profiles=__import__('app.plugin_profiles',fromlist=['_cache']);plugin_profiles._cache.clear()
  selected['profile_preset']=dict(bank='factory',program=2,name=factory['patches'][2]['name'])
  ports=a.plugin_controls();bank=next(p for p in ports if p['symbol']=='@bank');preset=next(p for p in ports if p['symbol']=='@patch')
  self.assertEqual(dict(bank['choices'])[bank['default']],'Machinista Factory')
  self.assertEqual(dict(preset['choices'])[preset['default']],factory['patches'][2]['name'])
  selected['profile_preset'].update(program=4,name=factory['patches'][4]['name'])
  self.assertEqual(next(p for p in a.plugin_controls() if p['symbol']=='@patch')['default'],4)
  a.pad=1;a.track()['plugins']=[copy.deepcopy(selected)];a.plugin_selected()['controls']['osc1_wave']=4
  self.assertEqual(next(p for p in a.plugin_controls() if p['symbol']=='osc1_shape')['name'],'PULSE WIDTH')
  a.pad=0;self.assertTrue(next(p for p in a.plugin_controls() if p['symbol']=='osc1_shape')['synth_inactive'])
 def test_wave_import_selection_keeps_stable_asset_id_and_no_extra_controls(self):
  first=self.upload('Z Wave.wav');second=self.upload('A Wave.wav',1024,512)
  a=self.a;a.plugin_param=next(i for i,p in enumerate(a.plugin_controls()) if p['symbol']=='osc1_wave')
  port=a.plugin_controls()[a.plugin_param];lib.rotate_wave(a,a.plugin_selected(),port,30)
  selected=a.plugin_selected();self.assertEqual(selected['controls']['osc1_wave'],32);self.assertEqual(selected['synth_waves']['1']['id'],second['id'])
  self.assertEqual(plugin_value(a.plugin_controls()[a.plugin_param],32),'A Wave')
  self.assertFalse(any(p.startswith('@') for p in selected['controls']));validate_project(a.project)
  lib.edit(self.root,second['id'],dict(name='Renamed',folder='Digital/Textures',tags=['bright']))
  self.assertIn('Renamed',plugin_value(a.plugin_controls()[a.plugin_param],32));self.assertEqual(selected['synth_waves']['1']['id'],second['id'])
 def test_removal_retains_immutable_asset_and_saved_name(self):
  row=self.upload();a=self.a;selected=a.plugin_selected();selected['controls']['osc1_wave']=32;selected['synth_waves']={'1':dict(id=row['id'],name=row['name'])}
  lib.delete(self.root,row['id']);self.assertFalse(lib.listing(self.root));self.assertTrue(lib.asset(self.root,row['id']).is_file())
  port=next(p for p in a.plugin_controls() if p['symbol']=='osc1_wave');self.assertEqual(plugin_value(port,32),'SAVED: My Wave')
  a.save();b=Application(self.root);self.assertEqual(b.track()['plugins'][0]['synth_waves'],selected['synth_waves'])
 def test_invalid_formats_cycles_nan_and_paths_rejected(self):
  for data,cycle in [(b'no',0),(wav(20),0),(wav(1025),512),(wav(512,2),0)]:
   with self.assertRaises(ValueError):lib.parse_wav(data,cycle)
  blob=bytearray(wav());blob[20:22]=struct.pack('<H',3);blob[34:36]=struct.pack('<H',32)
  with self.assertRaises(ValueError):lib.parse_wav(bytes(blob))
  for identity in ('../outside','g'*32,'a'*31):
   with self.assertRaises(ValueError):lib.asset(self.root,identity)
 def test_non_power_of_two_single_cycles_are_supported(self):
  result,info=lib.parse_wav(wav(600));self.assertEqual(info['cycle'],600);self.assertEqual(len(result),16+600*4)
 def test_explicit_stereo_conversion_and_frame_count(self):
  data=wav(1024,2);result,info=lib.parse_wav(data,512,True)
  self.assertEqual(info['frames'],2);self.assertEqual(result[:8],b'MWAVE001');self.assertEqual(len(result),16+1024*4)
 def test_symlink_catalog_cannot_escape_library(self):
  outside=self.root/'outside';outside.mkdir();base=self.root/'presets/Oscillators';base.parent.mkdir(parents=True,exist_ok=True);base.symlink_to(outside,target_is_directory=True)
  with self.assertRaises(ValueError):self.upload()
 def test_graphic_snapshots_and_all_sections_do_not_mutate_sound(self):
  a=self.a;before=copy.deepcopy(a.project);surface=Mk2Surface(a,ControllerInputs(a));renderer=Mk2Renderer()
  for first in range(0,len(a.plugin_controls()),8):
   a.plugin_param=first
   graph=view(a);self.assertIsNotNone(graph);self.assertTrue('points' in graph or 'levels' in graph or 'route' in graph)
   self.assertEqual(len(frame(a)),8192)
   state=snapshot(surface);renderer(state)
  self.assertEqual(a.project,before)
 def test_wave_selector_is_configuration_numeric_controls_automate(self):
  a=self.a;a.plugin_param=next(i for i,p in enumerate(a.plugin_controls()) if p['symbol']=='osc1_wave');self.assertIsNone(a.automation_descriptor())
  a.plugin_param+=1;self.assertEqual(a.automation_descriptor()[-1],'osc1_semi')
 def test_keyboard_events_keep_selected_synth(self):
  a=self.a;a.pad=0;a.keyboard_enabled=True;a.open_pattern_grid();inputs=ControllerInputs(a);inputs.pad_on('mk2',4,90)
  hit=next(v for k,v in a.actions if k=='controller_hit');self.assertEqual(hit[:2],(0,0));self.assertEqual(hit[6],64)

if __name__=='__main__':unittest.main()

class SynthWebTests(unittest.TestCase):
 from tests.test_web_server import WebHttpTests as _base
 setUp=_base.setUp
 stop=_base.stop
 request=_base.request
 def test_waveform_http_workflow_and_csrf(self):
  body=wav();h={'X-Machinista-Token':self.library.token}
  self.assertEqual(self.request('POST','/api/oscillators/upload?name=Test.wav',body)[0],403)
  status,_,data=self.request('POST','/api/oscillators/upload?name=Test.wav',body,h);self.assertEqual(status,200);row=json.loads(data)
  status,_,data=self.request('GET','/api/oscillators');listing=json.loads(data);self.assertEqual(len(listing['factory']),32);self.assertEqual(len(listing['users']),1)
  self.assertEqual(self.request('POST','/api/oscillators/edit?id='+row['id'],json.dumps(dict(name='Bright',folder='Digital',tags=['sharp'])),h)[0],200)
  self.assertEqual(self.request('POST','/api/oscillators/delete?id='+row['id'],headers=h)[0],200)
  self.assertTrue(lib.asset(self.root,row['id']).is_file());self.assertEqual(json.loads(self.request('GET','/api/oscillators')[2])['users'],[])
  self.assertEqual(self.request('POST','/api/oscillators/upload?name=bad.wav',b'broken',h)[0],400)

class SynthBackendTests(unittest.TestCase):
 def test_native_wave_and_numeric_changes_do_not_rebuild_instrument(self):
  from app.audio import AudioBackend
  with tempfile.TemporaryDirectory() as root:
   data=wav();row=lib.upload(root,'Wave.wav',io.BytesIO(data),len(data));p=profile(lib.URI)
   backend=AudioBackend.__new__(AudioBackend);backend.root=Path(root);backend.sample_rate=48000;backend.plugin_chains={};backend.plugin_metadata=[dict(uri=lib.URI,ports=p['parameters'])];commands=[];backend.command=commands.append
   chain=[dict(uri=lib.URI,kind='INSTRUMENT',controls={v['symbol']:v['default'] for v in p['parameters']},synth_waves={'1':dict(id=row['id'],name=row['name'])})]
   backend.plugins(0,chain);count=len(commands);backend.plugins(0,chain)
   self.assertEqual(sum(c.startswith('plugins ') for c in commands),1);self.assertEqual(sum(c.startswith('synth_wave ') for c in commands),1)
   self.assertFalse(any(c.startswith('plugin_param') for c in commands[count:]));chain[0]['controls']['osc1_fine']=2.5;backend.plugins(0,chain)
   self.assertEqual(sum(c.startswith('plugin_param ') and c.endswith(' 2.5') for c in commands),1)
