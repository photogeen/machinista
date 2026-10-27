import copy,json,struct,tempfile,unittest
from pathlib import Path
from app.model import Application,validate_project
from app.plugin_profiles import profile,banks,_cache,names
from app.plugin_bank_import import decode_obxd,import_bank
from app.audio import AudioBackend
from app.mk2_display import snapshot
from app.mk2_session import Mk2Session
from app.controller_inputs import ControllerInputs
from app.control_display import control_state
from app.ni_display import plugin_value

URI='urn:machinista:ports:obxd-2dat'

def chunk(xml):
    b=xml.encode();payload=b'VC2!'+struct.pack('<I',len(b))+b+b'\0'
    header=bytearray(160);header[:4]=b'CcnK';header[8:12]=b'FBCh';header[16:20]=b'Obxd';struct.pack_into('>I',header,156,len(payload))
    return bytes(header)+payload

class PluginProfilesTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);_cache.clear();self.p=profile(URI)
        self.data=chunk('<Datsounds><programs><program programName="Bass 12=ok" 2="0.7" 44="0.25"/><program programName="Pad" 2="0.4"/></programs></Datsounds>')
        self.result=import_bank(self.root,'obxd','Test.fxb',self.data)
        self.a=a=Application(self.root);a.page='PLUGIN';a.control_level=2
        self.meta=dict(uri=URI,name='OB-Xd',kind='INSTRUMENT',supported=True,ports=[dict(index=v['index'],symbol=v['symbol'],name=v['symbol'].upper(),default=v['default'],min=0,max=1) for v in self.p['parameters']])
        a.plugin_catalog=[self.meta];a.track()['plugins']=[dict(uri=URI,kind='INSTRUMENT',controls={v['symbol']:v['default'] for v in self.p['parameters']})]
    def test_fxb_names_engine_indices_and_rejection(self):
        b=banks(self.root,self.p)[0];self.assertEqual(len(b['patches']),2);self.assertEqual(b['patches'][0]['name'],'Bass 12=ok');self.assertEqual(b['patches'][0]['controls']['volume'],.7)
        for data in (self.data[:-1],self.data.replace(b'Obxd',b'Nope'),chunk('<!DOCTYPE Datsounds [<!ENTITY x "oops">]><Datsounds 2="1"/>'),chunk('<Datsounds 2="NaN"/>'),chunk('<Datsounds 2="2"/>'),b'bad'):
            with self.subTest(data=data[:30]),self.assertRaises(ValueError):import_bank(self.root,'obxd','bad.fxb',data)
    def test_complete_controls_and_no_mutation_when_rendered(self):
        before=copy.deepcopy(self.a.track()['plugins']);controls=self.a.plugin_controls()
        self.assertEqual(len(controls),len(self.p['pages'])*8);self.assertEqual(len({v['symbol'] for v in controls}),79)
        self.assertEqual(self.a.track()['plugins'],before)
        session=Mk2Session(self.root,self.a,ControllerInputs(self.a),{});self.addCleanup(session.close)
        self.assertEqual(snapshot(session.surface)['plugin_names'],('Init','Init'))
        self.assertEqual(control_state(self.a)['value'],'Init')
    def test_patch_turns_use_deliberate_travel_and_persist_without_bank(self):
        a=self.a;s=Mk2Session(self.root,a,ControllerInputs(a),{});self.addCleanup(s.close)
        s.rotate_raw(1,-31);self.assertNotIn('profile_preset',a.plugin_selected())
        s.rotate_raw(1,-1);self.assertEqual(names(self.root,a.plugin_selected()),('Test','Bass 12=ok'))
        s.rotate_raw(2,32);self.assertEqual(a.plugin_selected()['controls']['volume'],.4)
        self.assertEqual(names(self.root,a.plugin_selected()),('Test','Pad'))
        self.assertNotIn('@bank',a.plugin_selected()['controls']);validate_project(a.project);a.save()
        Path(self.result['path']).unlink();_cache.clear();b=Application(self.root)
        selected=b.track()['plugins'][0];self.assertEqual(selected['controls']['volume'],.4);self.assertEqual(names(self.root,selected),('MISSING BANK','Pad'))
    def test_normalized_choices_and_no_automation_of_selectors(self):
        a=self.a;self.assertIsNone(a.automation_descriptor());self.assertIsNone(a.selection_parameter())
        a.plugin_param=next(i for i,p in enumerate(a.plugin_controls()) if p['symbol']=='voice_count');a.plugins_rotate(-1);self.assertAlmostEqual(a.plugin_selected()['controls']['voice_count'],6/7)
        self.assertEqual(plugin_value(a.plugin_controls()[a.plugin_param],6/7),'7')
        self.assertIsNotNone(a.automation_descriptor())
    def test_snapshot_parameter_changes_never_recreate_instance(self):
        a=self.a;backend=AudioBackend.__new__(AudioBackend);backend.sample_rate=44100;backend.plugin_chains={};backend.plugin_metadata=[self.meta];commands=[];backend.command=commands.append
        backend.plugins(0,a.track()['plugins']);a.plugins_rotate(1);backend.plugins(0,a.track()['plugins']);a.plugin_param=1;a.plugins_rotate(1);backend.plugins(0,a.track()['plugins'])
        self.assertEqual(sum(v.startswith('plugins ') for v in commands),1)
        self.assertFalse(any('@patch' in v or '@bank' in v for v in commands))
    def test_json_validation_and_unknown_plugin_fallback(self):
        data=json.loads(Path(self.result['path']).read_text());data['patches'][0]['controls'].pop('volume')
        with self.assertRaises(ValueError):import_bank(self.root,'obxd','bad.json',json.dumps(data).encode())
        from app.plugin_profiles import controls
        ports=[dict(symbol='test')];self.assertIs(controls(self.a,dict(uri='urn:unknown'),ports),ports)
    def test_fxp_float_parameters(self):
        header=bytearray(56);header[:4]=b'CcnK';header[8:12]=b'FxCk';header[16:20]=b'Obxd';struct.pack_into('>I',header,24,80);header[28:32]=b'Test'
        data=bytes(header)+struct.pack('>80f',*([.5]*80));b=decode_obxd(data,self.p,'FXP')
        self.assertEqual(b['patches'][0]['controls']['cutoff'],.5)


class WebBankTests(unittest.TestCase):
    def test_data_only_upload_list_and_safe_delete(self):
        import io
        from app.web_plugin_banks import listing,upload,delete
        with tempfile.TemporaryDirectory() as root:
            data=chunk('<Datsounds programName="Soft Pad" 2="0.5"/>')
            r=upload(root,'Test.fxb','obxd',io.BytesIO(data),len(data))
            self.assertEqual(next(v for v in listing(root) if v['id']=='obxd')['banks'][0]['patches'],1)
            for identifier in ('../escape','init','/tmp/x'):
                with self.assertRaises(ValueError):delete(root,'obxd',identifier)
            with self.assertRaises(ValueError):upload(root,'bad.fxb','obxd',io.BytesIO(data),len(data)+1)
            with self.assertRaises(ValueError):upload(root,'bad.so','obxd',io.BytesIO(data),len(data))
            delete(root,'obxd',r['id']);self.assertEqual(len(next(v for v in listing(root) if v['id']=='obxd')['banks']),1)

class WebBankHttpTests(unittest.TestCase):
    from tests.test_web_server import WebHttpTests as _base
    setUp=_base.setUp
    stop=_base.stop
    request=_base.request
    def test_upload_requires_token_and_returns_imported_bank(self):
        from urllib.parse import urlencode
        data=chunk('<Datsounds programName="Bright" 2="0.7"/>');url='/api/plugin-banks/upload?'+urlencode(dict(profile='obxd',name='Bank.fxb'))
        self.assertEqual(self.request('POST',url,data)[0],403)
        status,_,body=self.request('POST',url,data,{'X-Machinista-Token':self.library.token})
        self.assertEqual(status,200);result=json.loads(body);self.assertEqual(result['patches'],1)
        self.assertEqual(next(v for v in json.loads(self.request('GET','/api/plugin-banks')[2]) if v['id']=='obxd')['banks'][0]['name'],'Bank')
        delete='/api/plugin-banks/delete?'+urlencode(dict(profile='obxd',id=result['id']))
        self.assertEqual(self.request('POST',delete)[0],403)
        self.assertEqual(self.request('POST',delete,headers={'X-Machinista-Token':self.library.token})[0],200)

if __name__=='__main__':unittest.main()
