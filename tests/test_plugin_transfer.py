import copy
from pathlib import Path
import tempfile
import unittest
from app.model import Application,validate_project
from app.plugins import copy_plugin_state

class PluginTransferTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.a=Application(self.root)
        self.a.page='PLUGIN';self.a.control_level=2
        self.fx=lambda uri:dict(uri=uri,kind='EFFECT',controls={'gain':1},bypass=False)
        self.a.track()['plugins']=[self.fx('urn:a'),self.fx('urn:b')]
    def tearDown(self):self.temp.cleanup()
    def test_copy_paste_keeps_state_independent_and_reindexes_automation(self):
        a=self.a;folder=self.root/'cache/original';folder.mkdir(parents=True);(folder/'state.ttl').write_text('state');(folder/'resource.bin').write_bytes(b'asset')
        a.request_plugin_transfer('COPY');request=a.actions.pop()[1];request['chain'][0]['state']=str(folder/'state.ttl');a.finish_plugin_transfer(request)
        a.project['groups'][0]['automation']={'0:0:plugin:1:gain':{'base':1,'uri':'urn:b','points':{'0':1}}}
        a.plugin_slot=1;a.paste_plugin();paste=a.actions.pop()[1]
        result=copy_plugin_state(paste,self.root);a.finish_plugin_paste(result)
        self.assertEqual([p['uri'] for p in a.track()['plugins']],['urn:a','urn:a','urn:b'])
        copied=Path(a.track()['plugins'][1]['state']);self.assertNotEqual(copied,folder/'state.ttl');self.assertEqual((copied.parent/'resource.bin').read_bytes(),b'asset')
        self.assertIn('0:0:plugin:2:gain',a.project['groups'][0]['automation']);validate_project(a.project)
    def test_move_updates_macro_and_modulation_and_rejects_stale_project(self):
        a=self.a;a.track()['macros']={'0':dict(bus=0,slot=0,symbol='gain',value=50)}
        a.project['groups'][0]['automation']={'0:0:plugin:0:gain':{'base':1,'uri':'urn:a','points':{'0':1}}}
        a.plugin_move_to=1;a.request_plugin_transfer('MOVE');request=a.actions.pop()[1];a.finish_plugin_transfer(request)
        self.assertEqual([p['uri'] for p in a.track()['plugins']],['urn:b','urn:a'])
        self.assertEqual(a.track()['macros']['0']['slot'],1);self.assertIn('0:0:plugin:1:gain',a.project['groups'][0]['automation']);validate_project(a.project)
        before=copy.deepcopy(a.track()['plugins']);a.request_plugin_transfer('MOVE');request=a.actions.pop()[1];a.project_generation+=1;a.finish_plugin_transfer(request)
        self.assertEqual(a.track()['plugins'],before)
    def test_instrument_stays_first_and_slot_limit_does_not_replace(self):
        a=self.a;a.track()['plugins'][0]['kind']='INSTRUMENT';a.plugin_move_to=1;a.request_plugin_transfer('MOVE');a.finish_plugin_transfer(a.actions.pop()[1])
        self.assertEqual(a.track()['plugins'][0]['kind'],'INSTRUMENT')
        a.plugin_clipboard=self.fx('urn:copy');a.track()['plugins']=[self.fx('urn:fx') for _ in range(16)];a.paste_plugin()
        self.assertEqual(len(a.track()['plugins']),16);self.assertEqual(a.message,'MAX 16 PLUGINS')
