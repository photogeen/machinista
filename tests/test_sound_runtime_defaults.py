"""Legacy/minimal Sound loads must be playable before any application restart."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from app.model import Application,new_project,validate_project
from app.presets import read_preset
from app.controller_inputs import ControllerInputs

class SoundRuntimeDefaultsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.a=Application(self.root)

    def test_validator_materializes_only_missing_midi_defaults_and_is_idempotent(self):
        p=new_project();p['groups'][0]['pads'][3].update(source='MIDI',note=75,channel=9)
        validate_project(p)
        for g in p['groups']:
            for slot,t in enumerate(g['pads']):
                self.assertIn('source',t);self.assertIn('channel',t);self.assertIn('note',t)
        self.assertEqual((p['groups'][0]['pads'][3]['source'],p['groups'][0]['pads'][3]['note'],p['groups'][0]['pads'][3]['channel']),('MIDI',75,9))
        before=copy.deepcopy(p);validate_project(p);self.assertEqual(p,before)

    def test_minimal_sound_file_load_then_keyboard_from_each_controller(self):
        path=self.root/'minimal/Preset.json';path.parent.mkdir()
        original=new_project();path.write_text(json.dumps(dict(format='Machinista-preset',version=1,kind='SOUND',name='Legacy Sound',project=original)))
        for source in ('mikro','mk2','mk1'):
            a=Application(self.root);t=read_preset(path,'SOUND',self.root)
            a.finish_preset_load(dict(group=0,pad=5,kind='SOUND',generation=a.project_generation,revision=a.revision),t)
            self.assertEqual(a.pad,5);self.assertEqual(a.track()['channel'],1)
            a.keyboard_enabled=True;a.page='PAD';a.actions.clear();inputs=ControllerInputs(a)
            inputs.pad_on(source,0,100)
            hits=[v for k,v in a.actions if k=='controller_hit'];self.assertEqual(len(hits),1)
            self.assertEqual(hits[0][5]['channel'],1)
            inputs.pad_off(source,0);self.assertTrue(any(k=='controller_off' for k,v in a.actions))
        self.assertEqual(json.loads(path.read_text())['project'],original)

    def test_replacement_boundary_normalizes_even_already_read_legacy_target(self):
        a=self.a;t=copy.deepcopy(a.track())
        for key in ('source','note','channel'):t.pop(key)
        a.finish_preset_load(dict(group=0,pad=2,kind='SOUND',generation=a.project_generation,revision=a.revision),t)
        self.assertEqual((a.track()['source'],a.track()['note'],a.track()['channel']),('SAMPLE',38,1))
        a.keyboard_enabled=True;a.page='PAD';a.actions.clear()
        a.pad_on(0,100)
        self.assertTrue(any(k=='midi_note' for k,v in a.actions))

    def test_explicit_invalid_channel_is_not_replaced_with_a_default(self):
        for value in (0,17):
            p=new_project();p['groups'][0]['pads'][0]['channel']=value
            with self.assertRaises(ValueError):validate_project(p)

if __name__=='__main__':unittest.main()
