import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools.check_public_source import audit
from tools import prepare_github

class PublicSourceAuditTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
 def write(self,name,body):
  path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True)
  path.write_bytes(body if isinstance(body,bytes) else body.encode());return path
 def test_private_keys_connections_and_user_data_are_rejected(self):
  self.write('app/config.py','target="192.168.'+'10.170"')
  self.write('key.txt','-----BEGIN '+'OPENSSH PRIVATE KEY-----')
  self.write('samples/personal.wav',b'RIFF')
  result=audit(self.root);self.assertFalse(result['ok'])
  self.assertTrue(any('development connection' in e for e in result['errors']))
  self.assertTrue(any('private key' in e for e in result['errors']))
  self.assertTrue(any('local data directory' in e for e in result['errors']))
 def test_native_binaries_serials_and_external_plugins_are_rejected(self):
  self.write('tools/engine',b'\x7fELFfixture')
  self.write('captures/map.json',json.dumps({'device':{'serial':'private-unit'}}))
  self.write('assets/vendor.lv2/plugin.so',b'\x7fELFfixture')
  errors=audit(self.root)['errors'];self.assertTrue(any('serial' in e for e in errors));self.assertTrue(any('native executable' in e for e in errors))
  self.assertTrue(any('external plug-in bundle' in e for e in errors))
 def test_default_network_settings_and_original_sysex_fixture_are_permitted(self):
  self.write('README.md','http://10.42.0.1:8080; password machinista; http://machinista.local:8080')
  self.write('tests/data/dexed-warm-circuits/Machinista-Warm-Circuits.syx',b'\xf0fixture\xf7')
  self.assertTrue(audit(self.root)['ok'])
 def test_symlink_escape_is_rejected(self):
  path=self.root/'outside';path.symlink_to('/etc/hosts')
  self.assertTrue(any('symlink' in e for e in audit(self.root)['errors']))
 def test_export_sanitizes_only_copy_and_refuses_existing_destination(self):
  source=self.root/'source';source.mkdir();dest=self.root/'publication'
  for directory in ('app','src','web','tests','deploy','.github','tools','assets/branding','assets/fonts','assets/instrument-art','assets/manual-web','docs','captures'):(source/directory).mkdir(parents=True,exist_ok=True)
  for name in prepare_github.DOCS:(source/'docs'/(name+'.md')).write_text('Public documentation')
  for name in ('README.md','CMakeLists.txt','THIRD_PARTY_NOTICES.md','CONTRIBUTING.md','SECURITY.md','LICENSING.md','LICENSE.md','.gitignore','.gitattributes','.python-version','requirements-dev.txt'):(source/name).write_text('')
  for name in prepare_github.MAPS:(source/'captures'/name).write_text(json.dumps(dict(device=dict(serial='original-unit'),evidence=['private-log'],buttons=[])))
  (source/'samples').mkdir();(source/'samples/private.wav').write_bytes(b'private')
  with patch('tools.prepare_github.factory_files',return_value=()):result=prepare_github.prepare(source,dest)
  self.assertFalse(result['published']);self.assertFalse((dest/'samples').exists())
  for name in prepare_github.MAPS:
   self.assertNotIn('serial',json.loads((dest/'captures'/name).read_text())['device'])
   self.assertEqual(json.loads((source/'captures'/name).read_text())['device']['serial'],'original-unit')
  with self.assertRaises(FileExistsError):prepare_github.prepare(source,dest)
