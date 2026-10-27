import array
import copy
from pathlib import Path
import sys
import tempfile
import unittest
import wave
from app.model import Application, validate_project
from app.workspaces import SCREENS
from app.sample_edit import process_sample

sys.path.insert(0, str(Path(__file__).resolve().parent.parent/'tools'))
from machinista import display_pixels


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.app = Application(self.root)
        self.wav = self.app.samples/'fixture.wav'
        with wave.open(str(self.wav), 'wb') as wav:
            wav.setnchannels(2); wav.setsampwidth(2); wav.setframerate(48000)
            wav.writeframes(array.array('h', [1000, 2000, -1000, -2000]*400).tobytes())
        self.app.track().update(sample=str(self.wav), start=0, end=800)

    def tearDown(self):
        self.temp.cleanup()

    def test_all_workspaces_are_navigable_and_render_bounded_frames(self):
        for index, page in enumerate(SCREENS):
            self.app.page = 'PAD'
            from app.model import SETTING_PAGES
            self.app.button('SHIFT',True);self.app.button('MAIN',True);self.app.button('MAIN',False);self.app.button('SHIFT',False)
            if page=='SONG':
                self.app.button('SCENE',True);self.app.button('SHIFT',True);self.app.button('F2',True)
                self.app.button('SHIFT',False);self.app.button('SCENE',False)
            else:
                self.app.open_settings('SYSTEM')
                if page=='PROJECT':self.app.menu=self.app.setting_entries().index('PROJECT SETTINGS');self.app.button('ENTER',True)
                self.app.menu=self.app.setting_entries().index(page)
                self.app.button('ENTER',True)
            self.assertEqual(self.app.page, page)
            pixels = display_pixels(self.app)
            self.assertEqual(len(pixels), 8192)
            self.assertTrue(set(pixels) <= {0, 1})

    def test_pattern_length_banks_event_velocity_and_probability(self):
        self.app.page = 'LENGTH'
        self.app.rotate(1)
        self.assertEqual(len(self.app.lane()), 32)
        self.app.page = 'STEP'
        self.app.button('NAV RIGHT', True)
        self.app.pad_on(0)
        self.assertTrue(self.app.lane()[16])
        self.app.page = 'EVENT'
        self.app.event_step = 16
        self.app.button('NAV RIGHT', True)
        self.app.rotate(10)
        self.assertEqual(self.app.event()['velocity'], 110)
        self.app.playing, self.app.step = True, 15
        self.app.actions.clear()
        self.app.tick()
        self.assertIn(('hit', (0, 0, 110)), self.app.actions)
        self.app.button('NAV RIGHT', True)
        self.app.rotate(-100)
        self.app.step, self.app.actions = 15, []
        self.app.tick()
        self.assertNotIn(('hit', (0, 0, 110)), self.app.actions)
        validate_project(self.app.project)

    def test_shorter_pattern_clamps_editor_and_copy_keeps_event_values(self):
        self.app.page = 'LENGTH'
        self.app.rotate(3)
        self.app.event_step, self.app.bank = 63, 3
        self.app.rotate(-3)
        self.app.page = 'EVENT'
        display_pixels(self.app)
        self.assertEqual((self.app.event_step, self.app.bank), (15, 0))
        self.app.project['groups'][0]['events']['0:0:15'] = {'velocity': 73, 'probability': 42}
        self.app.page = 'PATTERN'
        self.app.button('F2', True)
        self.assertEqual(self.app.pattern, 1)
        self.assertEqual(self.app.event(), {'velocity': 73, 'probability': 42})

    def test_chop_requires_confirmation_and_undo_restores_tracks(self):
        before = copy.deepcopy(self.app.project)
        self.app.page = 'CHOP'
        self.app.button('F3', True)
        self.assertEqual(self.app.page, 'CONFIRM')
        self.app.button('F1', True)
        self.assertEqual(self.app.project, before)
        self.app.button('F3', True)
        self.app.button('F2', True)
        self.assertEqual(self.app.page, 'PAD')
        tracks = self.app.project['groups'][0]['pads']
        self.assertEqual([(z['start'],z['end']) for z in tracks[0]['zones']],[(i*100,(i+1)*100) for i in range(8)])
        self.app.button('SHIFT', True)
        self.app.pad_on(0)
        self.assertEqual(self.app.project, before)

    def test_save_as_load_and_new_keep_previous_work(self):
        self.app.page = 'PROJECT'
        self.app.save_as()
        self.app.name_value='FIRST GROOVE';self.app.button('ENTER',True)
        first = self.app.project_files()[0]
        self.app.track()['gain'] = 31
        self.app.dirty = True
        self.app.load_project(first)
        self.assertEqual(self.app.track()['gain'], 80)
        self.app.page = 'PROJECT LOAD'
        self.app.button('F3', True)
        self.assertEqual(self.app.name_value,'')
        self.app.button('F2',True)
        new_name=self.app.name_value;self.app.button('ENTER',True)
        self.assertEqual(self.app.project['name'],new_name)
        self.assertGreaterEqual(len(self.app.project_files()), 2)
        self.assertIsNone(self.app.track()['sample'])

    def test_scene_change_waits_for_pattern_boundary_and_song_stops(self):
        self.app.project['scenes'][1][0] = 2
        self.app.playing = True
        self.app.step = 4
        self.app.select_scene(1)
        self.assertEqual(self.app.scene, 0)
        self.app.step = 15
        self.app.tick()
        self.assertEqual(self.app.scene, 1)
        self.assertEqual(self.app.active_patterns[0], 2)
        self.app.project['song'] = [0]
        self.app.song_playing = True
        self.app.song_bar = 0
        self.app.step = 15
        self.app.tick()
        self.assertFalse(self.app.playing)

    def test_keyboard_chord_and_arp_generate_actual_midi_actions(self):
        self.app.performance()['root']=36;self.app.keyboard_root=36
        self.app.page = 'CHORD'
        self.app.rotate(1)
        self.app.pad_on(0)
        notes = [value[0] for kind, value in self.app.actions if kind == 'midi_note']
        self.assertEqual(notes, [36, 40, 43])
        self.app.actions.clear()
        self.app.page = 'ARP'
        self.app.pad_on(2)
        self.app.button('F1', True)
        self.app.repeat_tick(0)
        self.assertIn(('midi_note', (38, 100, 1)), self.app.actions)

    def test_sample_processing_creates_copy_and_preserves_stereo_frames(self):
        original = self.wav.read_bytes()
        path, frames = process_sample(self.app.track(), 'REVERSE', self.root/'edited')
        self.assertEqual(frames, 800)
        self.assertEqual(self.wav.read_bytes(), original)
        with wave.open(str(path), 'rb') as wav:
            data = array.array('h'); data.frombytes(wav.readframes(1))
            self.assertEqual(list(data), [-1000, -2000])
        path, _ = process_sample(self.app.track(), 'NORMALIZE', self.root/'edited')
        with wave.open(str(path), 'rb') as wav:
            data = array.array('h'); data.frombytes(wav.readframes(wav.getnframes()))
            self.assertGreater(max(data), 32000)

    def test_fx_screen_does_not_claim_available_plugin_processing(self):
        self.app.page = 'FX'
        self.assertIn('NO FX INSTALLED', self.app.display()[1])


if __name__ == '__main__':
    unittest.main()
