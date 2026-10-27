"""Portable bank integrity, native import and deliberate voice variety."""
import copy,json,tempfile,unittest
from pathlib import Path
from app.dexed_banks import decode_sysex,OP_FIELDS,GLOBAL_FIELDS
from app.plugin_bank_import import import_bank
from app.plugin_profiles import profile,validate_bank,banks
from tools.create_dexed_warm_bank import URI,build,sysex,SPECS,CARRIERS

class WarmCircuitsTests(unittest.TestCase):
 def setUp(self):self.bank,self.manifest=build();self.p=profile(URI)
 def test_full_native_bank_and_meaningful_categories(self):
  self.assertEqual(len(self.bank['patches']),32)
  self.assertIs(validate_bank(self.bank,self.p),self.bank)
  self.assertEqual(len({p['name'] for p in self.bank['patches']}),32)
  self.assertEqual({v['category'] for v in self.manifest},{'Keys','Pads','Bass','Plucks','Leads'})
  self.assertEqual(len({json.dumps(p['controls'],sort_keys=True) for p in self.bank['patches']}),32)
  self.assertGreaterEqual(len({p['controls']['algorithm_num'] for p in self.bank['patches']}),12)
 def test_portable_sysex_preserves_every_dx7_parameter(self):
  data=sysex(self.bank);self.assertEqual(len(data),4104)
  restored=decode_sysex(data,self.p,'Warm Circuits')
  self.assertEqual(len({p['name'] for p in restored['patches']}),32)
  for a,b in zip(self.bank['patches'],restored['patches']):
   for key in [f'op{op}_{field}' for op in range(1,7) for field in OP_FIELDS]+list(GLOBAL_FIELDS):self.assertEqual(a['controls'][key],b['controls'][key])
 def test_json_import_retains_extended_controls_and_full_names(self):
  with tempfile.TemporaryDirectory() as root:
   result=import_bank(root,'dexed','Warm Circuits.json',json.dumps(self.bank).encode())
   self.assertEqual(result['patches'],32);self.assertEqual(len(result['id']),24)
   loaded=next(b for b in banks(root,self.p) if b['id']==result['id'])
   self.assertEqual(loaded['patches'],self.bank['patches'])
   self.assertEqual(loaded['patches'][0]['controls']['transpose'],24)
 def test_no_stuck_envelope_no_fixed_pitch_no_disabled_carriers(self):
  for patch in self.bank['patches']:
   c=patch['controls']
   for op in range(1,7):
    self.assertEqual(c[f'op{op}_eg_level_4'],0)
    self.assertEqual(c[f'op{op}_osc_mode'],0)
   self.assertTrue(any(c[f'op{op}_operator_output_level']>0 for op in CARRIERS[c['algorithm_num']]))
   self.assertEqual(c['polymono'],0);self.assertEqual(c['number_of_voices'],16)
 def test_checked_in_deliverables_match_generator(self):
  root=Path(__file__).resolve().parents[1]/'tests/data/dexed-warm-circuits'
  self.assertEqual(json.loads((root/'Machinista-Warm-Circuits.json').read_text()),self.bank)
  self.assertEqual((root/'Machinista-Warm-Circuits.syx').read_bytes(),sysex(self.bank))
