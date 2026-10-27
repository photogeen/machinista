import io
import json
import os
from pathlib import Path
import struct
import tarfile
import tempfile
import unittest
from unittest.mock import patch,MagicMock
import zipfile
from app.lv2_manager import Manager,elf,unpack,MAX_ARCHIVE,needed_libraries
from app import lv2_client


def binary(machine=183,bits=64):
    data=bytearray(64);data[:7]=b'\x7fELF'+bytes([2 if bits==64 else 1,1,1]);struct.pack_into('<HH',data,16,3,machine);return bytes(data)


def archive(entries):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:
        for name,data in entries:z.writestr(name,data)
    return out.getvalue()


def package(machine=183,supported=True,uri='urn:test:upload'):
    return archive([('Demo.lv2/manifest.ttl',json.dumps(dict(uri=uri,supported=supported))),('Demo.lv2/plugin.so',binary(machine))])


def fake_probe(paths):
    rows=[]
    for root in paths:
        for b in root.glob('*.lv2'):
            meta=json.loads((b/'manifest.ttl').read_text())
            rows.append(dict(name='Demo',kind='EFFECT',bundle=b.as_uri()+'/',binary=(b/'plugin.so').as_uri(),**meta))
    return rows


class ManagerTests(unittest.TestCase):
    def test_rpc_accepts_empty_status_error_and_rejects_real_errors(self):
        client=MagicMock();client.__enter__.return_value=client
        stream=client.makefile.return_value.__enter__.return_value
        with patch('app.lv2_client.socket.socket',return_value=client):
            stream.readline.return_value=b'{"error":"","bundles":[],"busy":false}\n'
            self.assertEqual(lv2_client.request('status')['bundles'],[])
            stream.readline.return_value=b'{"error":"Invalid ID."}\n'
            with self.assertRaisesRegex(ValueError,'Invalid ID'):lv2_client.request('delete')
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.system=self.root/'system';self.system.mkdir()
        self.manager=Manager(self.root,self.root/'state',self.root/'run',roots=[self.system],probe=fake_probe,target=dict(bits=64,machine=183,endian=1,label='ARM64'))
        self.manager.system_libraries=set();self.runtime(False)
        self.dep=patch('app.lv2_manager.check_dependencies');self.dep.start();self.addCleanup(self.dep.stop)
    def runtime(self,busy=False,uris=()):
        (self.manager.runtime/'in-use.json').write_text(json.dumps(dict(busy=busy,uris=list(uris))))
    def install(self,data):
        key='1'*32;self.manager.jobs[key]={};(self.manager.incoming/(key+'.upload')).write_bytes(data)
        self.manager.install(key,key);return key
    def test_valid_bundle_installs_then_can_be_removed_with_recovery_copy(self):
        key=self.install(package());self.assertEqual(self.manager.jobs[key]['state'],'ACTIVE')
        target=self.manager.active/'Demo.lv2';self.assertEqual((target/'plugin.so').read_bytes(),binary())
        status=self.manager.status();self.assertTrue(status['bundles'][0]['canDelete'])
        self.manager.remove(key,status['bundles'][0]['id']);self.assertFalse(target.exists())
        self.assertTrue(list(self.manager.trash.glob('*/Demo.lv2/plugin.so')))
        self.assertTrue((self.manager.runtime/'revision.json').exists())
    def test_x86_wrong_bitness_and_invalid_binary_never_activate(self):
        for data in (package(62),archive([('Demo.lv2/manifest.ttl','{}'),('Demo.lv2/plugin.so',binary(40,32))]),archive([('Demo.lv2/manifest.ttl','{}'),('Demo.lv2/plugin.so',b'not ELF')])):
            with self.subTest(data=data[:20]),self.assertRaises(ValueError):self.install(data)
            self.assertEqual(list(self.manager.active.iterdir()),[])
    def test_missing_manifest_sources_only_and_unsupported_host_features_fail(self):
        for data in (archive([('Demo.lv2/plugin.so',binary())]),archive([('Demo.lv2/manifest.ttl','{}'),('Demo.lv2/code.cpp','source')]),package(supported=False)):
            with self.assertRaises(ValueError):self.install(data)
            self.assertEqual(list(self.manager.active.iterdir()),[])
    def test_existing_bundle_and_duplicate_uri_are_never_replaced(self):
        self.install(package());original=(self.manager.active/'Demo.lv2/plugin.so').read_bytes()
        with self.assertRaises(ValueError):self.install(package())
        self.assertEqual((self.manager.active/'Demo.lv2/plugin.so').read_bytes(),original)
        other=package().replace(b'Demo.lv2',b'Else.lv2') # ZIP CRC names don't include file names in data
        with self.assertRaises(ValueError):self.install(other)
        self.assertEqual(len(self.manager.catalog),1)
    def test_delete_protects_transport_current_project_and_unknown_paths(self):
        key=self.install(package());identity=self.manager.catalog[0]['id']
        for busy,uris in ((True,()),(False,('urn:test:upload',))):
            self.runtime(busy,uris)
            with self.assertRaises(ValueError):self.manager.remove(key,identity)
            self.assertTrue((self.manager.active/'Demo.lv2').exists())
        (self.manager.runtime/'in-use.json').unlink()
        with self.assertRaises(ValueError):self.manager.remove(key,identity)
        self.assertFalse(self.manager.status()['bundles'][0]['canDelete'])
    def test_existing_system_bundle_is_listed_and_removable_as_a_whole(self):
        b=self.system/'Existing.lv2';b.mkdir();(b/'manifest.ttl').write_text(json.dumps(dict(uri='urn:test:existing',supported=True)));(b/'plugin.so').write_bytes(binary())
        self.manager.refresh();item=self.manager.status()['bundles'][0];self.assertFalse(item['managed'])
        self.manager.jobs['test']={};self.manager.remove('test',item['id']);self.assertFalse(b.exists())
    def test_rejects_archive_escape_links_duplicate_members_and_oversized_expansion(self):
        samples=self.root/'samples';samples.mkdir();(samples/'keep').write_text('original')
        bad=[archive([('../samples/keep','bad')]),archive([('/absolute','bad')]),archive([('a\\b','bad')]),archive([('same','1'),('same','2')])]
        out=io.BytesIO()
        with tarfile.open(fileobj=out,mode='w:gz') as t:
            item=tarfile.TarInfo('Demo.lv2/link');item.type=tarfile.SYMTYPE;item.linkname='/etc/passwd';t.addfile(item)
        bad.append(out.getvalue())
        for data in bad:
            with self.assertRaises(ValueError):self.install(data)
        with patch('app.lv2_manager.MAX_EXPANDED',1),self.assertRaises(ValueError):self.install(package())
        self.assertEqual((samples/'keep').read_text(),'original')
    def test_zip_symlink_and_nested_bundle_are_rejected(self):
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as z:
            item=zipfile.ZipInfo('Demo.lv2/link');item.create_system=3;item.external_attr=(0o120777<<16);z.writestr(item,'/etc/passwd')
        with self.assertRaises(ValueError):self.install(out.getvalue())
        with self.assertRaises(ValueError):self.install(archive([('A.lv2/manifest.ttl','{}'),('A.lv2/B.lv2/manifest.ttl','{}')]))
    def test_web_stream_checks_limits_incomplete_upload_and_retains_no_failed_payload(self):
        with patch('app.lv2_client.STATE',self.manager.state),patch('app.lv2_client.request',return_value={'busy':False}):
            for name,data,length in [('test.zip',b'a',2),('test.deb',b'a',1),('test.zip',b'',MAX_ARCHIVE+1)]:
                with self.assertRaises(ValueError):lv2_client.upload(name,io.BytesIO(data),length)
            self.assertEqual(list(self.manager.incoming.iterdir()),[])
        with patch('app.lv2_client.STATE',self.manager.state),patch('app.lv2_client.request',side_effect=[{'busy':False},ValueError('busy')]):
            with self.assertRaises(ValueError):lv2_client.upload('test.zip',io.BytesIO(b'a'),1)
        self.assertEqual(list(self.manager.incoming.iterdir()),[])

if __name__=='__main__':unittest.main()
