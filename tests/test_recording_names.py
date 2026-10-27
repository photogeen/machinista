"""Recording names stay readable and never replace existing audio."""
from pathlib import Path
import tempfile
import unittest
from app.audio import reserve_recording_path


class RecordingNamesTests(unittest.TestCase):
    def test_sequence_preserves_files_and_extends_past_99(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            first = reserve_recording_path(folder)
            self.assertEqual(first.name, 'Sample01.wav')
            first.write_bytes(b'existing recording')
            self.assertEqual(reserve_recording_path(folder).name, 'Sample02.wav')
            self.assertEqual(first.read_bytes(), b'existing recording')
            (folder/'Sample99.wav').touch()
            self.assertEqual(reserve_recording_path(folder).name, 'Sample100.wav')
