"""Calf controller pages retain real LV2 values and all DSP controls."""
import copy,json,tempfile,unittest
from pathlib import Path
from app.model import Application,validate_project
from app.plugin_profiles import profiles,controls,names,rotate,validate_bank
from app.ni_display import plugin_value

class CalfProfilesTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.a=Application(self.tmp.name)
  self.profiles=[p for p in profiles() if p['id'].startswith('calf-')]
 def test_all_pages_cover_real_ports_without_mutating_sound(self):
  self.assertEqual(len(self.profiles),11)
  for p in self.profiles:
   with self.subTest(plugin=p['id']):
    selected=dict(uri=p['uri'],kind='EFFECT',controls={v['symbol']:v['default'] for v in p['parameters']});before=copy.deepcopy(selected)
    view=controls(self.a,selected,p['parameters'])
    self.assertEqual(len(view),8*len(p['pages']))
    self.assertEqual({v['symbol'] for v in view if not v['symbol'].startswith('@')},{v['symbol'] for v in p['parameters']})
    self.assertEqual(selected,before);self.assertEqual(names(self.a.root,selected),('Init','Init'))
    self.assertEqual([v['profile_action'] for v in view[:2]],['bank','patch'])
 def test_filter_choices_units_and_logarithmic_turns(self):
  a=self.a;p=next(v for v in self.profiles if v['id']=='calf-filter');a.control_level=2;a.page='PLUGIN';a.plugin_catalog=[dict(uri=p['uri'],name=p['title'],kind='EFFECT',supported=True,ports=p['parameters'])];a.track()['plugins']=[dict(uri=p['uri'],kind='EFFECT',controls={v['symbol']:v['default'] for v in p['parameters']})]
  ports=a.plugin_controls();mode=next(v for v in ports if v['symbol']=='mode');self.assertEqual(len(mode['choices']),13);self.assertEqual(plugin_value(mode,0),'LP 12 DB')
  a.plugin_param=next(i for i,v in enumerate(ports) if v['symbol']=='freq');old=a.plugin_selected()['controls']['freq'];a.plugins_rotate(1);self.assertGreater(a.plugin_selected()['controls']['freq'],old);a.plugins_rotate(-1);self.assertAlmostEqual(a.plugin_selected()['controls']['freq'],old)
  self.assertEqual(plugin_value(next(v for v in ports if v['symbol']=='level_out'),1),'+0.0 DB');self.assertEqual(plugin_value(next(v for v in ports if v['symbol']=='freq'),2000),'2.00 KHZ');validate_project(a.project)
 def test_banks_validate_complete_controls(self):
  for p in self.profiles:
   bank=dict(schema=1,uri=p['uri'],name='Test',patches=[dict(name='Test',controls={v['symbol']:v['default'] for v in p['parameters']})]);validate_bank(bank,p)
   bank['patches'][0]['controls'].pop(next(iter(bank['patches'][0]['controls'])))
   with self.assertRaises(ValueError):validate_bank(bank,p)
 def test_units_preserve_toggle_enum_and_integer_percent(self):
  self.assertEqual(plugin_value(dict(unit='ms'),1.5),'1.5 MS');self.assertEqual(plugin_value(dict(unit='s'),1.5),'1.50 S')
  self.assertEqual(plugin_value(dict(unit='amplitude_db'),.5),'-6.0 DB');self.assertEqual(plugin_value(dict(unit='amplitude_db'),0),'-INF DB')
  self.assertEqual(plugin_value(dict(min=0,max=1),.504),'50%');self.assertEqual(plugin_value(dict(toggle=True),1),'ON')

 def test_color_speed_noise_names_and_tuning_units(self):
  tape=next(p for p in self.profiles if p['id']=='calf-tapesimulator')
  speed=next(v for v in tape['parameters'] if v['symbol']=='speed');self.assertEqual(plugin_value(speed,1),'FAST')
  vinyl=next(p for p in self.profiles if p['id']=='calf-vinyl')
  tuning=next(v for v in vinyl['parameters'] if v['symbol']=='pitch5');self.assertEqual(tuning['name'],'CRACKLE TUNE');self.assertEqual(plugin_value(tuning,.5),'+600 CT')
  rpm=next(v for v in vinyl['parameters'] if v['symbol']=='speed');self.assertEqual(plugin_value(rpm,45),'45 RPM')
  for p in (tape,vinyl):
   mix=next(v for v in p['parameters'] if v['symbol'] in ('mix','drone'))
   self.assertEqual(plugin_value(mix,.504),'50%')
