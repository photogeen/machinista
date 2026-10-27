import copy,json,tempfile,unittest
from pathlib import Path
from app.model import Application
from app.synth_library import URI,asset
from app.plugin_profiles import profile,validate_bank,rotate,banks,_cache
from app.web_synth import apply

class SynthBankWavesTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.a=Application(self.root);self.p=profile(URI);self.a.control_level=2
  self.a.plugin_catalog=[dict(uri=URI,name='Synth',kind='INSTRUMENT',supported=True,ports=self.p['parameters'])]
  c={p['symbol']:p['default'] for p in self.p['parameters']};self.a.track()['plugins']=[dict(uri=URI,kind='INSTRUMENT',controls=copy.deepcopy(c))]
  self.row=dict(id='a'*32,name='Tine',frames=8,cycle=1024);asset(self.root,self.row['id']).parent.mkdir(parents=True,exist_ok=True);asset(self.root,self.row['id']).write_bytes(b'fixture')
  wave=copy.deepcopy(c);wave['osc1_wave']=32
  self.bank=dict(schema=1,uri=URI,name='Factory',patches=[dict(name='Tine',controls=wave,synth_waves={'1':self.row}),dict(name='Sine',controls=c)])
  folder=self.root/'presets/plugin-banks/machinista-synth';folder.mkdir(parents=True);(folder/'factory.json').write_text(json.dumps(self.bank));_cache.clear()
 def test_controller_preset_loads_and_clears_assets_and_undo_restores(self):
  a=self.a;s=a.plugin_selected();rotate(a,s,dict(profile_action='bank'),-1)
  self.assertEqual(s['synth_waves'],{'1':self.row});self.assertEqual(s['controls']['osc1_wave'],32)
  rotate(a,s,dict(profile_action='patch'),1);self.assertEqual(s['synth_waves'],{});self.assertNotEqual(s['controls']['osc1_wave'],32)
  self.assertEqual(a.undo[-1]['groups'][0]['pads'][0]['plugins'][0]['synth_waves'],{'1':self.row})
 def test_web_preset_uses_same_asset_binding_and_clears_previous(self):
  a=self.a;apply(a,dict(slot=0,uri=URI,preset=dict(bank='factory',patch=0)));self.assertEqual(a.plugin_selected()['synth_waves'],{'1':self.row})
  apply(a,dict(slot=0,uri=URI,preset=dict(bank='factory',patch=1)));self.assertEqual(a.plugin_selected()['synth_waves'],{})
 def test_missing_asset_never_changes_current_patch_in_controller_or_web(self):
  a=self.a;asset(self.root,self.row['id']).unlink();before=copy.deepcopy(a.project)
  rotate(a,a.plugin_selected(),dict(profile_action='bank'),-1);self.assertEqual(a.project,before);self.assertEqual(a.message,'PRESET WAVE MISSING')
  with self.assertRaises(ValueError):apply(a,dict(slot=0,uri=URI,preset=dict(bank='factory',patch=0)))
  self.assertEqual(a.project,before)
 def test_large_native_bank_keeps_patches_above_midi_program_range_selectable(self):
  b=copy.deepcopy(self.bank);b['patches']=[dict(name=f'Patch {i:03}',controls=copy.deepcopy(self.bank['patches'][1]['controls'])) for i in range(264)]
  validate_bank(b,self.p)
  (self.root/'presets/plugin-banks/machinista-synth/factory.json').write_text(json.dumps(b));_cache.clear()
  apply(self.a,dict(slot=0,uri=URI,preset=dict(bank='factory',patch=263)))
  self.assertEqual(self.a.plugin_selected()['profile_preset']['program'],263)
  rotate(self.a,self.a.plugin_selected(),dict(profile_action='patch'),-1)
  self.assertEqual(self.a.plugin_selected()['profile_preset']['name'],'Patch 262')
  b['patches']*=2
  with self.assertRaises(ValueError):validate_bank(b,self.p)
 def test_native_bank_reordering_follows_saved_name_without_changing_sound(self):
  from app.plugin_profiles import selection
  selected=self.a.plugin_selected();selected['profile_preset']=dict(bank='factory',program=0,name='Sine')
  before=copy.deepcopy(self.a.project)
  self.assertEqual(selection(self.root,selected,self.p)[2],1)
  self.assertEqual(self.a.project,before)
 def test_bank_rejects_path_ids_missing_refs_and_bad_dimensions(self):
  validate_bank(self.bank,self.p)
  for value in ('../../escape','/tmp/table','https://example.com/wave','A'*32):
   b=copy.deepcopy(self.bank);b['patches'][0]['synth_waves']['1']['id']=value
   with self.assertRaises(ValueError):validate_bank(b,self.p)
  for key,value in [('frames',0),('cycle',1)]:
   b=copy.deepcopy(self.bank);b['patches'][0]['synth_waves']['1'][key]=value
   with self.assertRaises(ValueError):validate_bank(b,self.p)
  b=copy.deepcopy(self.bank);b['patches'][0].pop('synth_waves')
  with self.assertRaises(ValueError):validate_bank(b,self.p)
if __name__=='__main__':unittest.main()
