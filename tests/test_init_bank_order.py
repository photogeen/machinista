import copy,json,tempfile,unittest,shutil
from pathlib import Path
from app.plugin_profiles import profiles,bank_folder,banks,selection,names,_cache,rotate
from tools.factory_payload import factory_files
ROOT=Path(__file__).resolve().parents[1]

class InitBankOrderTests(unittest.TestCase):
 def test_all_parameter_bank_instruments_put_init_last_and_preserve_program_ids(self):
  for p in profiles():
   if p['provider']!='parameter-bank':continue
   with self.subTest(plugin=p['id']),tempfile.TemporaryDirectory() as root:
    c={v['symbol']:v['default'] for v in p['parameters']};folder=bank_folder(root,p);folder.mkdir(parents=True)
    data=dict(schema=1,uri=p['uri'],name='Factory',patches=[dict(name='Init',controls=c),dict(name='Warm Pad',controls=c),dict(name='Init Voice',controls=c),dict(name='Bright Lead',controls=c)])
    path=folder/'factory.json';path.write_text(json.dumps(data));before=path.read_bytes()
    available=banks(root,p);self.assertEqual([b['name'] for b in available],['Factory','Init'])
    self.assertEqual([v['name'] for v in available[0]['patches']],['Warm Pad','Bright Lead','Init','Init Voice'])
    for original,patch in enumerate(data['patches']):
     chosen=dict(uri=p['uri'],controls=copy.deepcopy(c),profile_preset=dict(bank='factory',program=original,name=patch['name']))
     _,b,i=selection(root,chosen,p)
     self.assertEqual(available[b]['patches'][i]['_program'],original)
     self.assertEqual(names(root,chosen),('Factory',patch['name']))
     self.assertEqual(chosen['controls'],c)
    self.assertEqual(path.read_bytes(),before)
 def test_legacy_program_without_name_still_selects_same_patch(self):
  p=next(v for v in profiles() if v['id']=='obxd')
  with tempfile.TemporaryDirectory() as root:
   folder=bank_folder(root,p);folder.mkdir(parents=True);c={v['symbol']:v['default'] for v in p['parameters']}
   (folder/'bank.json').write_text(json.dumps(dict(schema=1,uri=p['uri'],name='Bank',patches=[dict(name=n,controls=c) for n in ('Init','Bass')])))
   selected=dict(uri=p['uri'],profile_preset=dict(bank='bank',program=1))
   self.assertEqual(names(root,selected),('Bank','Bass'))
 def test_empty_installation_retains_init(self):
  with tempfile.TemporaryDirectory() as root:
   for p in profiles():
    if p['provider']=='parameter-bank':self.assertEqual([b['name'] for b in banks(root,p)],['Init'])

class FactoryImagePayloadTests(unittest.TestCase):
 def test_clean_payload_contains_all_factory_banks_and_dependencies_only(self):
  files=factory_files(ROOT);paths=[str(p.relative_to(ROOT)) for p in files]
  bank=json.loads((ROOT/'presets/plugin-banks/machinista-synth/factory.json').read_text())
  self.assertEqual(len(bank['patches']),264)
  self.assertEqual(sum(p.startswith('presets/plugin-banks/') for p in paths),14)
  self.assertEqual(sum(p.endswith('.mwave') for p in paths),9)
  self.assertFalse(any('dexed' in p or 'obxd' in p or '.lv2' in p or p.endswith(('.wav','.syx','.rom')) for p in paths))
 def test_fresh_image_payload_resolves_every_factory_patch_without_personal_content(self):
  from app.synth_library import preset_waves
  from app.plugin_profiles import profile
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory)
   for source in factory_files(ROOT):
    target=root/source.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
   p=profile('urn:machinista:instrument:synth');available=banks(root,p)
   self.assertEqual(len(available),14);self.assertEqual(available[-1]['id'],'init')
   self.assertNotIn('factory',[b['id'] for b in available])
   patches=[p for b in available if b['id']!='init' for p in b['patches']]
   self.assertEqual(len(patches),264)
   for patch in patches:preset_waves(root,patch)
   self.assertFalse((root/'projects').exists());self.assertFalse(list(root.rglob('*.lv2')))
 def test_missing_factory_stops_packaging_instead_of_silently_omitting_patches(self):
  with tempfile.TemporaryDirectory() as root:
   with self.assertRaises((OSError,ValueError)):factory_files(root)

class FactoryConsolidationTests(unittest.TestCase):
 def test_legacy_factory_sound_resolves_to_category_without_changing_controls(self):
  from app.plugin_profiles import profile
  p=profile('urn:machinista:instrument:synth')
  factory=json.loads((ROOT/'presets/plugin-banks/machinista-synth/factory.json').read_text())
  for program,patch in enumerate(factory['patches']):
   sound=dict(uri=p['uri'],controls=copy.deepcopy(patch['controls']),synth_waves=copy.deepcopy(patch.get('synth_waves',{})),profile_preset=dict(bank='factory',program=program,name=patch['name']))
   before=copy.deepcopy(sound);available,b,i=selection(ROOT,sound,p)
   self.assertIsNotNone(b);self.assertTrue(available[b]['id'].startswith('category-'))
   self.assertEqual(available[b]['patches'][i]['name'],patch['name']);self.assertEqual(sound,before)
   unnamed=copy.deepcopy(sound);unnamed['profile_preset'].pop('name')
   entries,b,i=selection(ROOT,unnamed,p)
   self.assertEqual(entries[b]['patches'][i]['name'],patch['name'])
 def test_partial_or_custom_factory_is_never_hidden(self):
  from app.plugin_profiles import profile,read_banks
  p=profile('urn:machinista:instrument:synth')
  with tempfile.TemporaryDirectory() as root:
   folder=bank_folder(root,p);folder.mkdir(parents=True)
   data=json.loads((ROOT/'presets/plugin-banks/machinista-synth/factory.json').read_text())
   (folder/'factory.json').write_text(json.dumps(data))
   partial=dict(data,name='Synth Bass',patches=data['patches'][:1])
   (folder/'category-bass.json').write_text(json.dumps(partial))
   self.assertIn('factory',[b['id'] for b in read_banks(root,p)[1]])
