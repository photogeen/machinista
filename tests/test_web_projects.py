import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from app.model import new_project,validate_project
from app.assets import resolve_assets
from app.web_server import Library


def zipped(items):
 out=io.BytesIO()
 with zipfile.ZipFile(out,'w') as z:
  for name,value in items:z.writestr(name,value)
 return out.getvalue()

class ProjectTransferTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  (self.root/'projects').mkdir();(self.root/'samples').mkdir();self.library=Library(self.root,lambda:[])
  self.project=new_project();self.project.update(name='MY BEAT',file_id='PROJECT-0001')
  (self.root/'samples/kick.wav').write_bytes(b'sample bytes')
  self.project['groups'][0]['pads'][0]['sample']=str(self.root/'samples/kick.wav')
  self.saved=json.dumps(self.project).encode();(self.root/'projects/PROJECT-0001.json').write_bytes(self.saved);(self.root/'projects/current.json').write_bytes(self.saved)
 def test_saved_list_json_and_portable_roundtrip_keep_active_project_untouched(self):
  self.assertEqual(len(self.library.projects.list()),2)
  with self.library.projects.download('PROJECT-0001.json','json') as (f,mime,name):self.assertEqual(json.load(f)['name'],'MY BEAT');self.assertEqual(mime,'application/json')
  with self.library.projects.download('PROJECT-0001.json') as (f,mime,name):body=f.read()
  with zipfile.ZipFile(io.BytesIO(body)) as z:
   document=json.loads(z.read('Project.json'));self.assertEqual(document['groups'][0]['pads'][0]['sample'],'samples/0001.wav')
   self.assertEqual(z.read('samples/0001.wav'),b'sample bytes')
  result=self.library.projects.upload('beat.zip',io.BytesIO(body),len(body))
  self.assertEqual(result['name'],'MY BEAT IMPORT 2');self.assertNotEqual(result['id'],'PROJECT-0001.json')
  uploaded=resolve_assets(json.loads((self.root/'projects'/result['id']).read_text()),self.root/'projects');validate_project(uploaded)
  self.assertEqual(Path(uploaded['groups'][0]['pads'][0]['sample']).read_bytes(),b'sample bytes')
  self.assertEqual((self.root/'projects/current.json').read_bytes(),self.saved);self.assertEqual((self.root/'projects/PROJECT-0001.json').read_bytes(),self.saved)
 def test_json_import_accepts_existing_local_samples_but_not_external_files(self):
  result=self.library.projects.upload('beat.json',io.BytesIO(self.saved),len(self.saved));self.assertTrue((self.root/'projects'/result['id']).exists())
  self.project['groups'][0]['pads'][0]['sample']='/etc/passwd';bad=json.dumps(self.project).encode()
  with self.assertRaises(PermissionError):self.library.projects.upload('bad.json',io.BytesIO(bad),len(bad))
 def test_plugin_state_and_resources_roundtrip_without_bundling_plugin_binaries(self):
  state=self.root/'projects/state/0';state.mkdir(parents=True);(state/'state.ttl').write_text('state');(state/'resource.bin').write_bytes(b'data')
  self.project['groups'][0]['pads'][0]['plugins']=[dict(uri='urn:test:effect',kind='EFFECT',state=str(state/'state.ttl'))]
  (self.root/'projects/PROJECT-0001.json').write_text(json.dumps(self.project))
  with self.library.projects.download('PROJECT-0001.json') as (f,_,__):body=f.read()
  result=self.library.projects.upload('beat.zip',io.BytesIO(body),len(body));project=resolve_assets(json.loads((self.root/'projects'/result['id']).read_text()),self.root/'projects')
  target=Path(project['groups'][0]['pads'][0]['plugins'][0]['state']);self.assertEqual(target.read_text(),'state');self.assertEqual((target.parent/'resource.bin').read_bytes(),b'data')
 def test_traversal_symlinks_and_duplicate_archive_paths_are_rejected(self):
  bad=[zipped([('../escape','bad')]),zipped([('/escape','bad')]),zipped([('same','1'),('same','2')])]
  out=io.BytesIO()
  with zipfile.ZipFile(out,'w') as z:
   item=zipfile.ZipInfo('link');item.create_system=3;item.external_attr=0o120777<<16;z.writestr(item,'/etc/passwd')
  bad.append(out.getvalue())
  for body in bad:
   with self.assertRaises(ValueError):self.library.projects.upload('bad.zip',io.BytesIO(body),len(body))
  self.assertEqual(len(self.library.projects.list()),2);self.assertFalse(list((self.root/'projects').glob('.web-project-*')))
 def test_bundle_cannot_reference_files_outside_it(self):
  for path in ('/etc/passwd','../samples/kick.wav'):
   self.project['groups'][0]['pads'][0]['sample']=path;body=zipped([('Project.json',json.dumps(self.project))])
   with self.assertRaises(ValueError):self.library.projects.upload('bad.zip',io.BytesIO(body),len(body))
 def test_download_never_follows_symlinks_or_reads_settings(self):
  target=self.root/'samples/kick.wav';target.unlink();target.symlink_to('/etc/passwd')
  with self.assertRaises(OSError):
   with self.library.projects.download('PROJECT-0001.json'):pass
  for identity in ('../config/settings.json','settings.json','/etc/passwd'):
   with self.assertRaises(ValueError):self.library.projects.document(identity)
 def test_incomplete_malformed_missing_assets_and_concurrent_uploads_are_clean(self):
  for body,length in ((b'{}',2),(b'no',3),(b'not zip',7)):
   with self.assertRaises(ValueError):self.library.projects.upload('bad.zip',io.BytesIO(body),length)
  self.project['groups'][0]['pads'][0]['sample']='missing.wav';body=zipped([('Project.json',json.dumps(self.project))])
  with self.assertRaises(FileNotFoundError):self.library.projects.upload('bad.zip',io.BytesIO(body),len(body))
  self.library.upload_lock.acquire()
  try:
   with self.assertRaises(BlockingIOError):self.library.projects.upload('beat.json',io.BytesIO(self.saved),len(self.saved))
  finally:self.library.upload_lock.release()
  self.assertFalse(list((self.root/'projects').glob('import-*')));self.assertFalse(list((self.root/'projects').glob('.web-project-*')))
