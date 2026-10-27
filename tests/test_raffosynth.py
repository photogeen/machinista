import copy,io,json,tempfile,unittest
from pathlib import Path
from app.model import Application,validate_project
from app.plugin_profiles import profile,names,_cache
from app.plugin_bank_import import import_bank
from app.mk2_session import Mk2Session
from app.controller_inputs import ControllerInputs
from app.mk2_display import snapshot
from app.control_display import control_state
from app.raffosynth_banks import decode_dat
from app.audio import AudioBackend

URI='urn:machinista:ports:raffosynth'
ORDER=[f'{f}{n}' for n in range(4) for f in ('oscButton','range','tuning','wave','vol')]+['filter_cutoff','filter_attack','filter_decay','filter_sustain','filter_release','filter_resonance','attack','decay','sustain','release','glide','volume']

class RaffoTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);_cache.clear();self.p=profile(URI)
  self.a=a=Application(self.root);a.page='PLUGIN';a.control_level=2
  self.meta=dict(uri=URI,name='RaffoSynth',kind='INSTRUMENT',supported=True,ports=copy.deepcopy(self.p['parameters']))
  a.plugin_catalog=[self.meta];a.track()['plugins']=[dict(uri=URI,kind='INSTRUMENT',controls={s['symbol']:s['default'] for s in self.p['parameters']})]
  self.data=' '.join(str(a.plugin_selected()['controls'][k]) for k in ORDER).encode()
 def test_dat_original_gui_order_preserves_every_parameter(self):
  p=decode_dat(self.data,self.p,'Bass');self.assertEqual(p['patches'][0]['controls'],self.a.plugin_selected()['controls'])
  self.assertEqual(p['patches'][0]['name'],'Bass')
 def test_dat_invalid_values_and_truncation_are_rejected(self):
  for data in (self.data+b' 1',b'1 2',self.data.replace(b'3000',b'NaN'),b'\xff',self.data.replace(b'3000',b'999999')):
   with self.subTest(data=data[:30]),self.assertRaises(ValueError):import_bank(self.root,'raffosynth','Bad.dat',data)
  p=decode_dat(self.data,self.p,'One');p['patches'][0]['controls']['wave0']=4
  with self.assertRaises(ValueError):import_bank(self.root,'raffosynth','Bad.json',json.dumps(p).encode())
 def test_all_controls_and_fixed_eight_encoder_pages(self):
  c=self.a.plugin_controls();self.assertEqual(len(c),len(self.p['pages'])*8);self.assertEqual({v['symbol'] for v in c},{v['symbol'] for v in self.meta['ports']}|{'@bank','@patch'})
  self.assertTrue(all(len(p['controls'])==8 for p in self.p['pages']))
 def test_bank_patch_names_deliberate_knob_travel_and_persistence(self):
  bank=decode_dat(self.data,self.p,'Live');bank['patches'].append(copy.deepcopy(bank['patches'][0]));bank['patches'][1].update(name='Warm');bank['patches'][1]['controls']['filter_cutoff']=1200
  result=import_bank(self.root,'raffosynth','Bank.json',json.dumps(bank).encode());a=self.a;s=Mk2Session(self.root,a,ControllerInputs(a),{});self.addCleanup(s.close)
  s.rotate_raw(1,-31);self.assertNotIn('profile_preset',a.plugin_selected());s.rotate_raw(1,-1);s.rotate_raw(2,32)
  self.assertEqual(snapshot(s.surface)['plugin_names'],('Live','Warm'));a.plugin_param=1;self.assertEqual(control_state(a)['value'],'Warm')
  validate_project(a.project);a.save();Path(result['path']).unlink();_cache.clear();b=Application(self.root);self.assertEqual(b.track()['plugins'][0]['controls']['filter_cutoff'],1200);self.assertEqual(names(self.root,b.track()['plugins'][0]),('MISSING BANK','Warm'))
 def test_choice_steps_follow_actual_waveforms(self):
  a=self.a;a.plugin_param=next(i for i,p in enumerate(a.plugin_controls()) if p['symbol']=='wave0');a.plugins_rotate(-1)
  self.assertEqual(control_state(a)['value'],'SAW');a.plugins_rotate(-1);self.assertEqual(control_state(a)['value'],'TRIANGLE')
 def test_snapshot_changes_do_not_recreate_native_plugin(self):
  import_bank(self.root,'raffosynth','Bass.dat',self.data);a=self.a
  backend=AudioBackend.__new__(AudioBackend);backend.sample_rate=44100;backend.plugin_chains={};backend.plugin_metadata=[self.meta];commands=[];backend.command=commands.append
  backend.plugins(0,a.track()['plugins']);a.plugins_rotate(1);backend.plugins(0,a.track()['plugins']);self.assertEqual(sum(c.startswith('plugins ') for c in commands),1)
 def test_web_import_formats(self):
  from app.web_plugin_banks import upload
  self.assertEqual(upload(self.root,'Bass.dat','raffosynth',io.BytesIO(self.data),len(self.data))['patches'],1)
  with self.assertRaises(ValueError):upload(self.root,'Bass.syx','raffosynth',io.BytesIO(self.data),len(self.data))

if __name__=='__main__':unittest.main()
