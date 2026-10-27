import io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from app.web_virtualjv import VirtualJV
class VirtualJVWebTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.library=Mock(root=Path(self.tmp.name));self.library.sounds.runtime.return_value={'available':True,'busy':False,'playing':False,'recording':False}
  self.addon=VirtualJV(self.library)
 def test_no_addon_in_clean_library(self):
  # A clean test library must not inspect the development Pi's live manager.
  with patch('app.lv2_client.request',return_value={'bundles':[]}):value=self.addon.status()
  self.assertFalse(value['available']);self.assertFalse(value['banks'])
 def test_removed_addon_hides_retained_roms_and_helper(self):
  prepared=self.addon.root/'prepared';prepared.mkdir(parents=True)
  catalog=prepared/'catalog.json';catalog.write_text(json.dumps({'banks':[{'id':0,'patches':['Old']}]}))
  for status in ({'bundles':[]},{'bundles':[{'status':'NOT OK','plugins':[{'uri':'urn:machinista:ports:virtualjv'}]}]}):
   with patch('app.lv2_client.request',return_value=status),patch.object(self.addon,'helper',return_value=Path('leftover-helper')):
    value=self.addon.status();self.assertFalse(value['installed']);self.assertFalse(value['available']);self.assertEqual(value['banks'],[])
   self.assertTrue(catalog.exists())
  with patch('app.lv2_client.request',side_effect=OSError('manager unavailable')):self.assertFalse(self.addon.status()['installed'])
 def test_multi_addon_counts_as_installed_without_prepared_banks(self):
  with patch('app.lv2_client.request',return_value={'bundles':[{'status':'OK','path':str(self.library.root/'multi.lv2'),'plugins':[{'uri':'urn:machinista:ports:virtualjv-multi'}]}]}):value=self.addon.status()
  self.assertTrue(value['installed']);self.assertEqual(value['banks'],[])
 def test_upload_does_not_execute_code_or_overwrite_existing_rom(self):
  self.addon.upload('jv880_rom1.bin',io.BytesIO(b'x'*32768),32768)
  with self.assertRaises(FileExistsError):self.addon.upload('jv880_rom1.bin',io.BytesIO(b'y'*32768),32768)
  self.assertEqual((self.addon.root/'raw/jv880_rom1.bin').read_bytes(),b'x'*32768)
 def test_partial_and_invalid_uploads_do_not_leave_files(self):
  for name,length,data in [('a.bin',32768,b'x'),('../a.bin',32768,b'x'*32768),('a.py',32768,b'x'*32768),('a.bin',50,b'x'*50)]:
   with self.assertRaises(ValueError):self.addon.upload(name,io.BytesIO(data),length)
  self.assertFalse(list(self.addon.root.glob('raw/*')))
 def test_prepare_requires_stopped_transport_and_separate_installed_tool(self):
  with self.assertRaises(ValueError):self.addon.prepare()
  self.library.sounds.runtime.return_value['playing']=True
  with patch('app.web_virtualjv.subprocess.run') as process:
   with self.assertRaises(ValueError):self.addon.prepare()
   process.assert_not_called()
 def test_catalog_and_context_are_returned_without_rom_data(self):
  prepared=self.addon.root/'prepared';prepared.mkdir(parents=True)
  (prepared/'catalog.json').write_text(json.dumps({'banks':[{'id':6,'name':'Vintage','patches':['Example'],'drums':0}]}))
  with patch('app.lv2_client.request',return_value={'bundles':[{'status':'OK','path':str(self.library.root/'test.lv2'),'plugins':[{'uri':'urn:machinista:ports:virtualjv'}]}]}):status=self.addon.status()
  self.assertTrue(status['installed']);self.assertEqual(status['banks'][0]['name'],'Vintage');self.assertNotIn('roms',status)
 def rom_fixture(self):
  raw=self.addon.root/'raw';raw.mkdir(parents=True);(raw/'remove.bin').write_bytes(b'remove');(raw/'keep.bin').write_bytes(b'keep')
  prepared=self.addon.root/'prepared';prepared.mkdir();(prepared/'catalog.json').write_text('{"banks":[]}')
  return raw,prepared
 def test_delete_keeps_other_uploads_and_clears_stale_prepared_data(self):
  raw,prepared=self.rom_fixture()
  with patch.object(self.addon,'helper',return_value=None):self.assertTrue(self.addon.delete('remove.bin')['ok'])
  self.assertFalse((raw/'remove.bin').exists());self.assertEqual((raw/'keep.bin').read_bytes(),b'keep');self.assertFalse(prepared.exists())
 def test_delete_rebuilds_remaining_banks_and_rolls_back_on_failure(self):
  raw,prepared=self.rom_fixture();old=(prepared/'catalog.json').read_bytes()
  with patch.object(self.addon,'helper',return_value=Path('/trusted/tool.py')),patch('app.web_virtualjv.subprocess.run',return_value=Mock(returncode=1,stderr='Invalid expansion descriptor',stdout='')):
   with self.assertRaises(ValueError):self.addon.delete('remove.bin')
  self.assertEqual((raw/'remove.bin').read_bytes(),b'remove');self.assertEqual((prepared/'catalog.json').read_bytes(),old)
  def rebuild(args,**kwargs):
   self.assertFalse((raw/'remove.bin').exists());self.assertTrue((raw/'keep.bin').exists())
   dest=Path(args[-1]);dest.mkdir();(dest/'catalog.json').write_text('{"banks":["remaining"]}')
   return Mock(returncode=0)
  with patch.object(self.addon,'helper',return_value=Path('/trusted/tool.py')),patch('app.web_virtualjv.subprocess.run',side_effect=rebuild):self.addon.delete('remove.bin')
  self.assertEqual(json.loads((prepared/'catalog.json').read_text())['banks'],['remaining'])
  self.assertFalse(list(self.addon.root.glob('.rom-delete-*')))
 def test_delete_missing_base_clears_prepared_banks(self):
  raw,prepared=self.rom_fixture()
  with patch.object(self.addon,'helper',return_value=Path('/trusted/tool.py')),patch('app.web_virtualjv.subprocess.run',return_value=Mock(returncode=1,stderr='Missing/unsupported base ROMs: jv880_rom1.bin',stdout='')):self.addon.delete('remove.bin')
  self.assertFalse(prepared.exists());self.assertTrue((raw/'keep.bin').exists())
 def test_delete_rejects_running_transport_traversal_and_symlinks(self):
  raw,prepared=self.rom_fixture();self.library.sounds.runtime.return_value['playing']=True
  with self.assertRaises(ValueError):self.addon.delete('remove.bin')
  self.library.sounds.runtime.return_value['playing']=False
  (raw/'link.bin').symlink_to(raw/'keep.bin')
  for name in ('../keep.bin','link.bin','.hidden.bin','missing.bin'):
   with self.assertRaises(ValueError):self.addon.delete(name)
  self.assertEqual((raw/'keep.bin').read_bytes(),b'keep');self.assertTrue((raw/'remove.bin').exists());self.assertTrue(prepared.exists())
 def test_http_rom_routes_require_csrf_and_do_not_expose_rom_files(self):
  import threading,urllib.request,urllib.error
  from app.web_server import Library,Server
  library=Library(self.library.root,source_scan=lambda:[]);(self.library.root/'samples').mkdir(exist_ok=True)
  server=Server(('127.0.0.1',0),library);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  try:
   base='http://127.0.0.1:'+str(server.server_address[1]);req=urllib.request.Request(base+'/api/virtualjv/upload?name=test.bin',data=b'x'*32768,method='POST')
   with self.assertRaises(urllib.error.HTTPError) as caught:urllib.request.urlopen(req)
   self.assertEqual(caught.exception.code,403)
   delete=urllib.request.Request(base+'/api/virtualjv/delete?name=test.bin',data=b'',method='POST')
   with self.assertRaises(urllib.error.HTTPError) as denied:urllib.request.urlopen(delete)
   self.assertEqual(denied.exception.code,403)
   delete.add_header('X-Machinista-Token',library.token)
   with patch.object(VirtualJV,'delete',return_value={'ok':True}) as remove:
    with urllib.request.urlopen(delete) as response:self.assertTrue(json.load(response)['ok'])
    remove.assert_called_once_with('test.bin')
   req.add_header('X-Machinista-Token',library.token)
   with urllib.request.urlopen(req) as response:self.assertTrue(json.load(response)['ok'])
   with patch('app.lv2_client.request',return_value={'bundles':[]}):
    with urllib.request.urlopen(base+'/api/virtualjv') as response:self.assertFalse(json.load(response)['installed'])
   self.assertTrue((self.addon.root/'raw/test.bin').exists())
   with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(base+'/presets/virtualjv/raw/test.bin')
  finally:server.shutdown();server.server_close();thread.join()
