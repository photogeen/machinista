import unittest
from app.midi import MidiBackend

class MidiMessagesTests(unittest.TestCase):
    def test_running_status_and_interleaved_clock_keep_note_off(self):
        midi=MidiBackend()
        self.assertEqual(midi.parse(bytes([0x90,36,100,37,0xf8,90,36,0])),[(0,100),(1,90)])
        self.assertEqual(midi.take_events(),[(0x90,(36,100)),(0xf8,()),(0x90,(37,90)),(0x90,(36,0))])
        self.assertEqual(midi.parse(bytes([0x80,37])),[])
        midi.parse(bytes([0]));self.assertEqual(midi.take_events(),[(0x80,(37,0))])
    def test_channel_filter_pitchbend_and_system_common_cancel_running_status(self):
        midi=MidiBackend();midi.channel=2
        midi.parse(bytes([0x91,36,100,0xe2,0,64,0xf0,1,2,3,0xb2,123,0]))
        self.assertEqual(midi.take_events(),[(0xe2,(0,64)),(0xb2,(123,0))])
