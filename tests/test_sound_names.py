import copy,tempfile,unittest
from app.model import Application
from app.sound_names import sound_name
from app.ui_context import sound_context
from app.ni_display import name
from app.control_display import control_state
from app.mk2_surface import Mk2Surface
from app.controller_inputs import ControllerInputs
from app.mk2_display import snapshot

SYNTH='urn:machinista:instrument:synth'
class SoundNameTests(unittest.TestCase):
 def app(self,root):
  a=Application(root);a.plugin_catalog=[dict(uri=SYNTH,name='Machinista Synth',kind='INSTRUMENT',ports=[],supported=True),dict(uri='urn:test:dexed',name='Dexed',kind='INSTRUMENT',ports=[],supported=True),dict(uri='urn:test:fx',name='Reverb',kind='EFFECT',ports=[],supported=True)];return a
 def test_current_instrument_overrides_empty_stale_and_custom_labels_without_mutation(self):
  with tempfile.TemporaryDirectory() as r:
   a=self.app(r);t=a.track();t['plugins']=[dict(uri=SYNTH,kind='INSTRUMENT',controls={})]
   for old in ('','JV Part 5','Old Sound'):
    t['name']=old;before=copy.deepcopy(a.project)
    self.assertEqual(sound_name(a),'Machinista Synth');self.assertIn('Machinista Synth',sound_context(a));self.assertEqual(name(a),'Machinista Synth');self.assertEqual(a.project,before)
   t['plugins'][0]['uri']='urn:test:dexed';self.assertEqual(sound_name(a),'Dexed')
   t['plugins']=[];self.assertEqual(sound_name(a),'Old Sound')
 def test_effect_does_not_replace_sample_name_and_orphan_jv_name_is_hidden(self):
  with tempfile.TemporaryDirectory() as r:
   a=self.app(r);t=a.track();t.update(name='JV Part 5',sample='samples/Kick.wav',plugins=[dict(uri='urn:test:fx',kind='EFFECT')])
   self.assertEqual(sound_name(a),'Kick');t['name']='My Kick';self.assertEqual(sound_name(a),'My Kick')
   t.update(sample='',name='JV Rhythm',plugins=[]);self.assertEqual(sound_name(a),'EMPTY')
 def test_linked_group_instrument_and_cycles(self):
  with tempfile.TemporaryDirectory() as r:
   a=self.app(r);a.project['groups'][1]['plugins']=[dict(uri='urn:test:dexed',kind='INSTRUMENT')];a.track().update(name='JV Part 2',routing={'midi_target':'GROUP 1'})
   self.assertEqual(sound_name(a),'Dexed');a.project['groups'][1]['plugins']=[];a.project['groups'][1]['routing']={'midi_target':'GROUP 1'};self.assertEqual(sound_name(a),'EMPTY')
 def test_mikro_and_mk2_snapshots_use_current_plugin_on_old_project(self):
  with tempfile.TemporaryDirectory() as r:
   a=self.app(r);a.track().update(name='JV Part 5',plugins=[dict(uri=SYNTH,kind='INSTRUMENT',controls={})]);a.page='PAD';a.control_level=2
   self.assertIn('Machinista Synth',control_state(a)['title'])
   a.page='PAD CONFIG';self.assertEqual(control_state(a)['sound_name'],'Machinista Synth');a.page='PAD'
   surface=Mk2Surface(a,ControllerInputs(a));self.assertEqual(snapshot(surface)['title'],'Machinista Synth')
 def test_missing_catalog_uses_saved_plugin_name_and_builtin_fallback(self):
  with tempfile.TemporaryDirectory() as r:
   a=self.app(r);a.plugin_catalog=[];a.track()['plugins']=[dict(uri='urn:test:missing',kind='INSTRUMENT',name='My Synth')];self.assertEqual(sound_name(a),'My Synth')
   a.track()['plugins']=[dict(uri=SYNTH,kind='INSTRUMENT')];self.assertEqual(sound_name(a),'Machinista Synth')
if __name__=='__main__':unittest.main()
