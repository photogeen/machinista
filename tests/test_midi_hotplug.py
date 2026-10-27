import errno
import unittest
from types import SimpleNamespace
from unittest.mock import patch, call

from app.midi import MidiBackend


class MidiHotplugTests(unittest.TestCase):
    settings = {'midi_in': 'in', 'midi_out': 'out', 'midi_channel': 1}
    devices = [SimpleNamespace(key='in', path='/a'), SimpleNamespace(key='out', path='/b')]

    def test_partial_open_failure_closes_everything_and_can_retry(self):
        midi = MidiBackend()
        with patch('app.midi.os.open', side_effect=[10, OSError(errno.ENODEV, 'gone')]), patch('app.midi.os.close') as close:
            with self.assertRaises(OSError):midi.configure(self.devices, self.settings)
            close.assert_called_once_with(10)
        self.assertEqual(midi.ports, {})
        self.assertIsNone(midi.input)
        self.assertIsNone(midi.output)
        with patch('app.midi.os.open', side_effect=[11, 12]), patch('app.midi.os.write', return_value=3) as write:
            midi.configure(self.devices, self.settings)
            midi.send(bytes([0x90, 60, 100]))
            self.assertEqual(write.call_args.args[0], 12)
        self.assertEqual(midi.input, '/a')

    def test_disappeared_old_output_does_not_prevent_reconfiguration(self):
        midi = MidiBackend();midi.output = '/old';midi.ports = {'/old': 9}
        midi.tokens.start((0, 60), 1)
        with patch('app.midi.os.write', side_effect=OSError(errno.ENODEV, 'gone')), patch('app.midi.os.close') as close, patch('app.midi.os.open', side_effect=[10, 11]):
            midi.configure(self.devices, self.settings)
            close.assert_called_once_with(9)
        self.assertEqual(midi.output, '/b')
        self.assertFalse(midi.tokens.active)
        self.assertFalse(midi.pending)

    def test_close_detaches_selections_and_pending_notes(self):
        midi = MidiBackend();midi.input = midi.output = '/old';midi.ports = {'/old': 9}
        midi.tokens.start((0, 60), 1);midi.off.append((0, 60, 0, 1))
        with patch('app.midi.os.close') as close:midi.close_ports()
        close.assert_called_once_with(9)
        midi.send(b'abc');self.assertEqual(midi.poll(), [])
        self.assertIsNone(midi.output)
        self.assertFalse(midi.tokens.active)
        self.assertFalse(midi.off)

    def test_missing_descriptor_is_oserror_not_keyerror(self):
        midi = MidiBackend();midi.output = '/old'
        with self.assertRaises(OSError) as caught:midi.send(b'abc')
        self.assertEqual(caught.exception.errno, errno.ENODEV)

    def test_shutdown_after_unplug_closes_ports_and_clears_notes(self):
        midi = MidiBackend();midi.output = '/old';midi.ports = {'/old': 9}
        midi.tokens.start((0, 60), 1)
        with patch('app.midi.os.write', side_effect=OSError(errno.ENODEV, 'gone')), patch('app.midi.os.close') as close:
            midi.close()
            close.assert_called_once_with(9)
        self.assertFalse(midi.tokens.active)
        self.assertEqual(midi.ports, {})

    def test_backpressure_preserves_pending_data(self):
        midi = MidiBackend();midi.output = '/old';midi.ports = {'/old': 9}
        with patch('app.midi.os.write', side_effect=[BlockingIOError(), 2, 1]):
            midi.send(b'abc');self.assertEqual(midi.pending, b'abc')
            midi.flush();self.assertEqual(midi.pending, b'c')
            midi.flush();self.assertFalse(midi.pending)
