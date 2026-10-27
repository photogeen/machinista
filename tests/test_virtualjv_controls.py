import json,tempfile,unittest
from pathlib import Path
from app.model import Application
from app.mk2_session import Mk2Session
from app.controller_inputs import ControllerInputs
from app.mk2_display import snapshot
from app.control_display import control_state
from app.virtualjv_controls import URI

class VirtualJVControlsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        folder=self.root/'presets/virtualjv/prepared';folder.mkdir(parents=True)
        (folder/'catalog.json').write_text(json.dumps({'banks':[{'id':0,'name':'Internal A','patches':['Grand Piano','Rhodes'],'drums':1},{'id':6,'name':'SR-JV80-04 Vintage Synth','patches':['Vintage One','SimpleEP+Pad','Last Patch'],'drums':0}]}))
        self.a=a=Application(self.root);a.page='PLUGIN';a.control_level=2
        ports=[dict(index=i+3,symbol=k,name=k.upper(),min=0,max=28 if k=='bank' else 255 if k=='program' else 1,default=0,integer=k!='gain',toggle=k=='rhythm') for i,k in enumerate(('bank','program','rhythm','gain'))]
        a.plugin_catalog=[dict(uri=URI,name='VirtualJV',kind='INSTRUMENT',supported=True,ports=ports)]
        a.track()['plugins']=[dict(uri=URI,kind='INSTRUMENT',controls=dict(bank=6,program=1,rhythm=0,gain=.7))]
        self.session=Mk2Session(self.root,a,ControllerInputs(a),{});self.addCleanup(self.session.close)
    def test_both_displays_receive_names_and_mikro_uses_name_value(self):
        s=snapshot(self.session.surface)
        self.assertEqual(s['plugin_names'],('SR-JV80-04 Vintage Synth','SimpleEP+Pad'))
        self.assertEqual(s['fields'][0],('BANK','6'))
        self.assertEqual(s['fields'][1],('PATCH','1'))
        self.a.plugin_param=1;self.assertEqual(control_state(self.a)['value'],'SimpleEP+Pad')
    def test_raw_knobs_need_32_counts_and_sparse_bank_ids_are_skipped(self):
        c=self.a.plugin_selected()['controls']
        self.session.rotate_raw(2,31);self.assertEqual(c['program'],1)
        self.session.rotate_raw(2,1);self.assertEqual(c['program'],2)
        self.session.rotate_raw(1,-32);self.assertEqual(c['bank'],0);self.assertEqual(c['program'],1)
        self.session.rotate_raw(1,32);self.assertEqual(c['bank'],6)
    def test_missing_catalog_falls_back_to_numbers_and_other_plugins_are_unmodified(self):
        from app.virtualjv_controls import controls,names,_cache
        from app.ni_display import plugin_value
        port=dict(symbol='program',name='Patch',default=0,min=0,max=255,integer=True)
        other={'uri':'urn:other','controls':{}}
        self.assertIs(controls(self.root,other,[port])[0],port)
        (self.root/'presets/virtualjv/prepared/catalog.json').unlink();_cache.clear()
        self.assertIsNone(names(self.root,self.a.plugin_selected()))
        self.assertEqual(plugin_value(self.a.plugin_controls()[1],1),'1')
    def test_prepared_names_never_change_the_saved_numeric_controls(self):
        before=dict(self.a.plugin_selected()['controls']);self.a.plugin_controls();snapshot(self.session.surface)
        self.assertEqual(self.a.plugin_selected()['controls'],before)

    def test_bank_change_discards_partial_preset_travel_but_preset_edits_keep_it(self):
        c=self.a.plugin_selected()['controls'];c.update(bank=0,program=0)
        self.session.rotate_raw(2,31);self.session.rotate_raw(1,32)
        self.assertEqual(c['bank'],6)
        self.session.rotate_raw(2,1);self.assertEqual(c['program'],0)
        self.session.rotate_raw(2,32);self.assertEqual(c['program'],1)
        self.session.rotate_raw(2,31);self.assertEqual(c['program'],2)
