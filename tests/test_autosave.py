from pathlib import Path
import copy
import json
import tempfile
import time
import unittest
from unittest.mock import Mock
from app.autosave import Autosave,recover
from app.model import Application,validate_project
from app.controller_inputs import ControllerInputs
from app.mk2_surface import Mk2Surface

class AutosaveTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.a=Application(self.root);self.audio=Mock()
        self.saver=Autosave(self.root,interval=1);self.addCleanup(self.saver.close)
    def checkpoint(self):
        self.saver.poll(self.a,self.audio,0);self.saver.poll(self.a,self.audio,2)
        if self.saver.future:self.saver.future.result(timeout=2)
    def test_recovery_preserves_undo_dirty_and_manual_save(self):
        a=self.a;a.save();original=a.project_path.read_bytes()
        a.remember();a.project['tempo']=131.25;undo=copy.deepcopy(a.undo)
        self.checkpoint()
        self.assertEqual(a.project_path.read_bytes(),original)
        self.assertEqual(a.undo,undo);self.assertTrue(a.dirty)
        loaded=Application(self.root);self.assertEqual(loaded.project['tempo'],131.25)
        self.assertEqual(loaded.message,'AUTOSAVE RECOVERED')
        a.save();self.assertEqual(Application(self.root).message,'')
    def test_off_and_busy_defer_background_save(self):
        a=self.a;a.settings['autosave']='OFF';self.checkpoint()
        self.assertFalse((self.root/'projects/.autosave').exists())
        a.settings['autosave']='ON';self.saver.poll(a,self.audio,5)
        self.saver.poll(a,self.audio,7,busy=True);self.assertIsNone(self.saver.future)
        self.saver.poll(a,self.audio,8);self.saver.future.result(timeout=2)
        self.assertTrue((self.root/'projects/.autosave/CURRENT.json').exists())
    def test_late_checkpoint_cannot_override_newer_manual_save(self):
        a=self.a;a.save();old=copy.deepcopy(a.project)
        from app.autosave import stamp
        baseline={'current.json':stamp(a.project_path)}
        a.project['tempo']=140;a.save()
        path=self.root/'projects/.autosave/CURRENT.json'
        self.saver.write(old,path,[],baseline)
        self.assertEqual(Application(self.root).project['tempo'],140)
    def test_deleted_named_project_is_not_resurrected(self):
        a=self.a;a.project['file_id']='PROJECT-0001';a.save();self.checkpoint()
        a.delete_project(a.active_project_file())
        self.assertFalse((self.root/'projects/PROJECT-0001.json').exists())
        self.assertEqual(Application(self.root).project['name'],'UNTITLED')
    def test_invalid_checkpoint_is_ignored(self):
        a=self.a;a.save();folder=self.root/'projects/.autosave';folder.mkdir()
        for text in ('broken','[]','{"baseline":null,"project":null}'):
            (folder/'CURRENT.json').write_text(text)
            self.assertEqual(Application(self.root).project,a.project)
    def test_autosave_toggle_persists(self):
        a=self.a;a.open_settings('SYSTEM');a.menu=a.setting_entries().index('PROJECT SETTINGS');a.button('ENTER',True)
        a.button('ENTER',True);self.assertEqual(a.page,'AUTOSAVE')
        a.rotate(-1);self.assertEqual(Application(self.root).settings['autosave'],'OFF')
    def test_folder_back_dac_and_mk2_back_key(self):
        a=self.a;a.open_settings('AUDIO');a.menu=a.setting_entries().index('DAC');a.button('ENTER',True)
        self.assertEqual(a.setting_entries(),('HEADPHONE LEVEL','SPEAKER LEVEL','INPUT GAIN','BACK'))
        a.menu=3;a.button('ENTER',True);self.assertIsNone(a.settings_section)
        a.open_settings('SYSTEM');a.menu=a.setting_entries().index('POWER');a.button('ENTER',True)
        a.button('NAV LEFT',True);self.assertIsNone(a.settings_section)
        a.menu=a.setting_entries().index('POWER');a.button('ENTER',True)
        surface=Mk2Surface(a,ControllerInputs(a));self.assertEqual(surface.softkeys()[3],'BACK')
        surface.softkey(3);self.assertIsNone(a.settings_section)
    def test_all_unpinned_modes_return_on_release_on_both_controllers(self):
        from app.surface import TEMPORARY
        for name,target in TEMPORARY.items():
            if name=='VIEW':continue
            for source in ('mikro','mk2'):
                a=Application(self.root);a.pinned_modes.clear();a.page='PAD'
                inputs=ControllerInputs(a);inputs.button(source,name,True)
                self.assertEqual(a.page,target,(name,source))
                inputs.button(source,name,False);self.assertEqual(a.page,'PAD',(name,source))

    def test_plugin_state_is_complete_before_checkpoint_publication(self):
        from app.layout import bus_targets
        a=self.a;a.track()['plugins']=[dict(uri='urn:test',kind='EFFECT',controls={},bypass=False)]
        def write_states(project):
            for target in bus_targets(project).values():
                for plugin in target.get('plugins',[]):
                    path=Path(plugin['state']);path.parent.mkdir(parents=True,exist_ok=True);path.write_text('state')
        self.audio.save_plugin_state.side_effect=write_states
        self.checkpoint()
        checkpoint=json.loads((self.root/'projects/.autosave/CURRENT.json').read_text())
        from app.assets import resolve_assets
        project=resolve_assets(checkpoint['project'],self.root/'projects')
        state=Path(project['groups'][0]['pads'][0]['plugins'][0]['state'])
        self.assertTrue(state.is_file())
        self.assertNotIn('.autosave',str(a.track()['plugins'][0].get('state','')))
