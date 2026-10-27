from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from app.model import Application
from app.storage import save_json
sys.path.insert(0, str(Path(__file__).resolve().parent.parent/'tools'))
from mikro_settings import configure_display
from machinista import display_pixels


class DisplaySettingsTests(unittest.TestCase):
    def test_edit_persist_bounds_reset_and_existing_settings(self):
        with tempfile.TemporaryDirectory() as root:
            save_json(Path(root)/'config/settings.json', {'audio': 'AUTO', 'midi_in': 'OFF', 'midi_out': 'OFF', 'midi_channel': 3})
            app = Application(root)
            app.button('SHIFT', True);app.button('MAIN', True);app.button('SHIFT', False)
            app.button('F3', True)
            self.assertIn('>DISPLAY', app.display()[1])
            app.button('ENTER', True)
            self.assertIn('>BRIGHTNESS', app.display()[1])
            app.button('ENTER', True)
            app.rotate(-30)
            self.assertEqual(app.settings['display_brightness'], 70)
            self.assertIn(('display_settings', None), app.actions)
            self.assertEqual(len(display_pixels(app)), 8192)
            app.button('ENTER', True)
            app.rotate(1)
            app.button('ENTER', True)
            app.rotate(999)
            self.assertEqual(app.settings['display_contrast'], 100)
            app.rotate(-999)
            self.assertEqual(app.settings['display_contrast'], 0)
            app.button('SHIFT', True)
            app.button('F1', True)
            app.button('SHIFT', False)
            self.assertEqual(app.settings['display_contrast'], 42)
            app.button('F3', True)
            self.assertEqual(app.page, 'SETTINGS')
            reopened = Application(root)
            self.assertEqual(reopened.settings['display_brightness'], 70)
            self.assertEqual(reopened.settings['display_contrast'], 42)
            self.assertEqual(reopened.settings['midi_channel'], 3)

    def test_feature_changes_only_two_fields_and_checks_readback(self):
        original = bytearray.fromhex('f880004000010001502a00')
        changed = original.copy()
        changed[8:10] = bytes((70, 50))
        with patch('mikro_settings.read_feature', side_effect=[original.copy(), changed]), patch('mikro_settings.write_feature') as write:
            configure_display(4, 70, 50)
            write.assert_called_once_with(4, changed)
        with patch('mikro_settings.read_feature', side_effect=[original.copy(), original.copy()]), patch('mikro_settings.write_feature'):
            with self.assertRaises(OSError):
                configure_display(4, 70, 50)
        with self.assertRaises(ValueError):
            configure_display(4, 101, 50)
