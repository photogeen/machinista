import copy,tempfile,unittest
from pathlib import Path
from app.plugin_units import normalized,advance
from app.ni_display import plugin_value
from app.model import Application,validate_project
from app.plugin_profiles import profiles,profile,controls
from app.mk2_session import Mk2Session
from app.controller_inputs import ControllerInputs
from app.mk2_display import snapshot
from app.control_display import control_state

class PluginUnitsTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.a=a=Application(self.tmp.name);a.page='PLUGIN';a.control_level=2
  self.port=dict(index=3,symbol='amount',name='AMOUNT',default=.5,min=0,max=1)
  a.plugin_catalog=[dict(uri='urn:test:continuous',name='Test',supported=True,kind='EFFECT',ports=[self.port])]
  a.track()['plugins']=[dict(uri='urn:test:continuous',kind='EFFECT',controls={'amount':.5})]
 def test_percent_display_only_applies_to_continuous_unit_ranges(self):
  for value,label in [(0,'0%'),(.5,'50%'),(.71642,'72%'),(.001,'0%'),(1,'100%')]:self.assertEqual(plugin_value(self.port,value),label)
  for change in ({'toggle':True},{'integer':True},{'choices':[(0,'ZERO'),(1,'ONE')]},{'min':-1},{'max':2},{'choice':True}):self.assertFalse(normalized(dict(self.port,**change)),change)
  self.assertEqual(plugin_value(dict(self.port,toggle=True),1),'ON')
  self.assertEqual(plugin_value(dict(self.port,choices=[(.5,'HALF')]),.5),'HALF')
 def test_equal_steps_clamp_and_reverse_without_binary_drift(self):
  value=0
  for i in range(100):value=advance(self.port,value,1);self.assertEqual(value,(i+1)/100)
  for i in range(100):value=advance(self.port,value,-1);self.assertEqual(value,(99-i)/100)
  self.assertEqual(advance(self.port,.999,10),1);self.assertEqual(advance(self.port,.001,-10),0)
  self.assertEqual(advance(self.port,.71642,1),.72642)
 def test_native_values_and_precise_imported_patch_are_not_scaled_by_render(self):
  a=self.a;a.plugin_selected()['controls']['amount']=.716421
  before=copy.deepcopy(a.track()['plugins']);self.assertEqual(control_state(a)['value'],'72%');self.assertEqual(a.track()['plugins'],before)
  a.plugins_rotate(1);self.assertEqual(a.plugin_selected()['controls']['amount'],.726421)
  a.encoder_held=True;a.plugins_rotate(1);self.assertEqual(a.plugin_selected()['controls']['amount'],.727421)
  validate_project(a.project);a.save();self.assertEqual(Application(self.tmp.name).track()['plugins'][0]['controls']['amount'],.727421)
 def test_mk2_normal_shift_fine_and_direction_travel(self):
  a=self.a;s=Mk2Session(a.root,a,ControllerInputs(a),{});self.addCleanup(s.close)
  s.rotate_raw(1,7);self.assertEqual(a.plugin_selected()['controls']['amount'],.5)
  s.rotate_raw(1,1);self.assertEqual(a.plugin_selected()['controls']['amount'],.51);self.assertEqual(snapshot(s.surface)['fields'][0],('AMOUNT','51%'))
  a.shift=True;s.rotate_raw(1,8);self.assertEqual(a.plugin_selected()['controls']['amount'],.511)
  a.shift=False;s.rotate_raw(1,-8);self.assertEqual(a.plugin_selected()['controls']['amount'],.501)
 def test_partial_unit_range_and_integer_percent_labels(self):
  gain=dict(self.port,max=2,unit='percent')
  self.assertTrue(normalized(gain));self.assertEqual(plugin_value(gain,1),'100%');self.assertEqual(plugin_value(gain,2),'200%');self.assertEqual(advance(gain,1,1),1.01)
  p=dict(self.port,min=.01)
  self.assertTrue(normalized(p));self.assertEqual(plugin_value(p,.4),'40%')
  self.assertEqual(advance(p,.01,-1),.01);self.assertEqual(advance(p,.01,1),.02)
  for value in (0,.001,.125,.71642,.999,1):self.assertNotIn('.',plugin_value(self.port,value))
 def test_cent_units_native_conversion_and_fine_control(self):
  from app.plugin_units import cents,advance_cents
  for uri,symbol,start,scale,offset in [('urn:machinista:ports:obxd-2dat','tune',.5,200,-100),('urn:machinista:ports:obxd-2dat','osc1p',0,4800,0),('https://github.com/dcoredump/dexed.lv2','master_tune',0,200,0),('urn:machinista:ports:raffosynth','tuning0',0,100,0)]:
   p=profile(uri);meta=next(dict({'min':0,'max':1},**v) for v in p['parameters'] if v['symbol']==symbol) if p['id']=='obxd' else next(v for v in p['parameters'] if v['symbol']==symbol)
   port=dict(meta,**p['overrides'][symbol]);self.assertFalse(normalized(port))
   self.assertEqual(cents(port,start),0);self.assertEqual(plugin_value(port,start),'0 CT')
   new=advance_cents(port,start,1);self.assertAlmostEqual(cents(port,new),1,places=7);self.assertEqual(plugin_value(port,new),'+1 CT')
   fine=advance_cents(port,new,1,True);self.assertAlmostEqual(cents(port,fine),1.1,places=7);self.assertEqual(plugin_value(port,fine),'+1.1 CT')
   self.assertEqual(advance_cents(port,port['max'],1000),port['max'])
  a=self.a;a.plugin_catalog[0]['ports'][0].update(unit='cents',display_scale=200,display_offset=-100)
  a.plugins_rotate(1);self.assertAlmostEqual(a.plugin_selected()['controls']['amount'],.505)
  a.encoder_held=True;a.plugins_rotate(-1);self.assertAlmostEqual(a.plugin_selected()['controls']['amount'],.5045)
 def test_priority_pages_and_distinct_overview_labels(self):
  p=profile('urn:machinista:ports:obxd-2dat');self.assertEqual(p['pages'][0]['controls'],['@bank','@patch','volume','cutoff','resonance','envelope_amt','latk','lrel']);self.assertEqual(p['pages'][1]['title'],'ENVELOPES')
  p=profile('https://github.com/dcoredump/dexed.lv2');self.assertEqual(p['pages'][1]['title'],'OPERATOR LEVELS');self.assertEqual(p['pages'][2]['title'],'OP1 ENV')
  selected=dict(uri=p['uri'],controls={});view=controls(self.a,selected,p['parameters']);labels=[v['name'] for v in view[8:14]];self.assertEqual(labels,[f'OP{i} LEVEL' for i in range(1,7)])
  p=profile('urn:machinista:ports:raffosynth');self.assertEqual(p['pages'][1]['title'],'ENVELOPES');self.assertEqual(p['pages'][2]['title'],'OSC MIXER')
 def test_all_synth_parameters_remain_reachable_and_pages_align(self):
  for p in profiles():
   if p['provider']!='parameter-bank':continue
   pages=p.get('web_pages',p['pages'])
   self.assertEqual({v['symbol'] for v in p['parameters']},{s for v in pages for s in v['controls'] if not s.startswith('@')})
   self.assertTrue(all(len(page['controls'])==8 for page in p['pages']))

if __name__=='__main__':unittest.main()
