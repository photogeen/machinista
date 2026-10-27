import copy,json,tempfile,unittest
from pathlib import Path
from app import plugin_profiles as profiles
from app.bank_sounds import sync,project
from app.sound_library import SoundLibrary
from app.presets import read_preset
from app.model import Application

class BankSoundTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.p=[p for p in profiles.profiles() if p['id'] in ('machinista-synth','dexed','obxd')];self.entries={}
  for p in self.p:
   folder=profiles.bank_folder(self.root,p);folder.mkdir(parents=True)
   bank=dict(schema=1,uri=p['uri'],name='Warm bank',patches=[dict(name='Init',controls={v['symbol']:v['default'] for v in p['parameters']}),dict(name='Soft Keys',controls={v['symbol']:v['default'] for v in p['parameters']})])
   (folder/'warm.json').write_text(json.dumps(bank));self.entries[p['id']]=profiles.read_banks(self.root,p)
  self.enabled={p['uri'] for p in self.p};self.library=SoundLibrary(self.root)
 def build(self):sync(self.root,self.entries,self.enabled)
 def test_all_three_instruments_are_folders_and_load_exact_controls(self):
  self.build();rows=self.library.scan()['sounds'];self.assertEqual(len(rows),9)
  for p in self.p:
   row=next(r for r in rows if r['folder']==p['title']+'/Warm bank' and r['name']=='Soft Keys')
   track=read_preset(self.library.folder/row['link'],'SOUND',self.root)
   self.assertEqual(track,self.library.read(row['id']));self.assertEqual(track['plugins'][0]['uri'],p['uri'])
   self.assertEqual(track['plugins'][0]['controls'],self.entries[p['id']][1][0]['patches'][0]['controls'])
   self.assertEqual(track['plugins'][0]['profile_preset']['program'],1)
   with self.assertRaisesRegex(ValueError,'editable copy'):self.library.draft(row['id'])
 def test_load_replaces_only_selected_destination_and_opens_plugin(self):
  self.build();row=self.library.scan()['sounds'][0];track=read_preset(self.library.folder/row['link'],'SOUND',self.root)
  a=Application(self.root);a.group=2;a.pad=7;a.page='BROWSE';a.control_last='SAMPLER'
  a.plugin_catalog=[dict(uri=p['uri'],kind='INSTRUMENT',supported=True,ports=p['parameters']) for p in self.p]
  before=copy.deepcopy(a.project)
  request=dict(group=2,pad=7,kind='SOUND',generation=a.project_generation,revision=a.revision)
  a.finish_preset_load(request,track)
  self.assertEqual(a.page,'PLUGIN');self.assertEqual((a.group,a.pad),(2,7))
  before['groups'][2]['pads'][7]=a.project['groups'][2]['pads'][7]
  self.assertEqual(before,a.project)
 def test_refresh_removes_only_owned_files_and_hides_uninstalled_plugins(self):
  self.build();user=self.library.folder/'OB-Xd/Warm bank/My Sound.sound';user.write_text('user data')
  self.enabled={self.p[0]['uri']};self.build()
  self.assertTrue(user.exists());self.assertTrue(all(r['folder'].startswith(self.p[0]['title']+'/') for r in self.library.scan()['sounds']))
 def test_patches_are_snapshots_and_survive_bank_removal(self):
  self.build();row=self.library.scan()['sounds'][0];path=self.library.folder/row['link'];before=read_preset(path,'SOUND',self.root)
  for file in (self.root/'presets/plugin-banks').rglob('*.json'):file.unlink()
  self.assertEqual(read_preset(path,'SOUND',self.root),before)
 def test_existing_user_file_is_never_replaced(self):
  path=self.library.folder/'OB-Xd/Warm bank/001 Soft Keys.sound';path.parent.mkdir(parents=True);path.write_text('my sound')
  self.build();self.assertEqual(path.read_text(),'my sound')
 def test_last_factory_programs_validate(self):
  self.build();row=next(r for r in self.library.scan()['sounds'] if r['kind']=='SYNTH');data=json.loads((self.library.folder/row['link']).read_text());data['program']=263
  self.assertEqual(project(self.root,data)['groups'][0]['pads'][0]['plugins'][0]['profile_preset']['program'],263)

class BankRemovalTests(unittest.TestCase):
 setUp=BankSoundTests.setUp
 build=BankSoundTests.build
 def test_bank_removal_cleans_catalog_immediately_and_stale_worker_cannot_recreate(self):
  from app.web_plugin_banks import delete
  self.build();row=next(r for r in self.library.scan()['sounds'] if r['folder']=='OB-Xd/Warm bank');path=self.library.folder/row['link']
  saved=read_preset(path,'SOUND',self.root);before=copy.deepcopy(saved)
  delete(self.root,'obxd','warm')
  self.assertFalse(path.exists());self.assertFalse(any(r['folder']=='OB-Xd/Warm bank' for r in self.library.scan()['sounds']))
  self.build()  # A worker may still hold the previous in-memory bank snapshot.
  self.assertFalse(path.exists());self.assertEqual(saved,before)
  self.assertTrue(any(r['folder'].startswith('Dexed/') for r in self.library.scan()['sounds']))
 def test_scan_hides_bank_deleted_outside_webui_before_worker_refresh(self):
  self.build();(self.root/'presets/plugin-banks/obxd/warm.json').unlink()
  self.assertFalse(any(r['folder']=='OB-Xd/Warm bank' for r in self.library.scan()['sounds']))
 def test_builtin_categories_and_traversal_cannot_be_deleted(self):
  from app.web_plugin_banks import delete
  for identity in ('init','factory','category-keys','../obxd/warm'):
   with self.assertRaises(ValueError):delete(self.root,'machinista-synth',identity)
 def test_bank_metadata_contains_instrument_and_bank_for_grouped_browser(self):
  self.build();row=next(r for r in self.library.scan()['sounds'] if r['folder']=='OB-Xd/Warm bank')
  self.assertEqual((row['instrument'],row['bank_name']),('OB-Xd','Warm bank'))
