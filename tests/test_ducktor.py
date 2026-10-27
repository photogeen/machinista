"""Native sidechain controls share existing persistence, routing and automation."""
import copy,tempfile,unittest
from pathlib import Path
from app.model import Application,validate_project
from app.ducktor import URI,controls,sources,rotate_source,view,poll,receive
from app.plugin_profiles import profile
from app.routing import build_graph
from app.ni_display import plugin_value
from app.control_display import control_state
from app.mk2_display import snapshot
from app.mk2_surface import Mk2Surface
from app.controller_inputs import ControllerInputs

class DucktorTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.a=a=Application(self.tmp.name);a.page='PLUGIN';a.control_level=2;a.pad=1
  self.p=profile(URI);a.plugin_catalog=[dict(uri=URI,name=self.p['title'],builtin=True,kind='EFFECT',sidechain=True,supported=True,ports=self.p['parameters'])]
  a.track()['plugins']=[dict(uri=URI,kind='EFFECT',controls={v['symbol']:v['default'] for v in self.p['parameters']})]
 def test_pages_units_and_no_display_mutation(self):
  a=self.a;before=copy.deepcopy(a.project);ports=a.plugin_controls();self.assertEqual(len(ports),16);self.assertEqual(ports[0]['symbol'],'@source');self.assertEqual({v['symbol'] for v in ports if not v['symbol'].startswith('@')},{v['symbol'] for v in self.p['parameters']})
  for symbol,label in [('threshold','-18.0 DB'),('ratio','6.0:1'),('attack','3.0 MS'),('release','180 MS'),('mix','100%')]:
   p=next(v for v in ports if v['symbol']==symbol);self.assertEqual(plugin_value(p,p['default']),label)
  control_state(a);snapshot(Mk2Surface(a,ControllerInputs(a)));self.assertEqual(a.project,before)
 def test_source_skips_feedback_and_survives_project_save(self):
  a=self.a;selected=a.plugin_selected();items=sources(a);self.assertEqual(items[0],('NONE','NONE'))
  # GROUP A feeds this Sound's destination; own Sound is also invalid. Skip both.
  rotate_source(a,selected,2);self.assertEqual(selected['sidechain'],'SOUND 0');build_graph(a.project)
  rotate_source(a,selected,1);self.assertEqual(selected['sidechain'],'SOUND 2');build_graph(a.project)
  a.plugin_param=1;a.plugins_rotate(-1);self.assertLess(selected['controls']['threshold'],-18);validate_project(a.project);a.save()
  loaded=Application(self.tmp.name);saved=loaded.project['groups'][0]['pads'][1]['plugins'][0]
  self.assertEqual({k:v for k,v in saved.items() if k!='state'},{k:v for k,v in selected.items() if k!='state'});self.assertEqual(Path(saved['state']).resolve(),Path(selected['state']).resolve())
 def test_only_numeric_controls_are_automatable(self):
  a=self.a;self.assertIsNone(a.automation_descriptor());a.plugin_param=1
  descriptor=a.automation_descriptor();self.assertEqual(descriptor,(1,'plugin',0,'threshold'))
  a.automation_set(descriptor,-30);self.assertEqual(a.plugin_selected()['controls']['threshold'],-30)
 def test_meter_polls_are_bounded_and_match_selected_slot(self):
  a=self.a
  class Audio:
   def __init__(self):self.commands=[]
   def command(self,value):self.commands.append(value)
  audio=Audio()
  for n in range(100):poll(a,audio,n/1000)
  self.assertEqual(audio.commands,['ducktor_meter 1 0'])
  self.assertTrue(receive(a,dict(kind='ducktor_meter',bus=0,slot=0,input=1,reduction=12)));self.assertEqual(view(a)['reduction'],0)
  receive(a,dict(kind='ducktor_meter',bus=1,slot=0,input=.5,reduction=9));self.assertAlmostEqual(view(a)['input_db'],-6.0205999);self.assertEqual(view(a)['reduction'],9)
  a.page='PAD';self.assertIsNone(view(a));poll(a,audio,2);self.assertEqual(len(audio.commands),1)
 def test_source_selector_never_becomes_a_native_parameter(self):
  a=self.a;a.plugins_rotate(1);self.assertEqual(a.plugin_selected()['sidechain'],'EXT STEREO');self.assertNotIn('@source',a.plugin_selected()['controls'])
  self.assertTrue(all('@source' not in str(payload) for kind,payload in a.actions if kind=='plugins'))

 def test_group_bank_names_remain_unambiguous(self):
  self.a.ensure_group_bank(1);labels=dict(sources(self.a));self.assertEqual(labels['GROUP 8'],'GROUP A2');self.assertTrue(labels['SOUND 128'].startswith('A2:01 '))
