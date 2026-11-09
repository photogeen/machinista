import tempfile
import unittest

from app.controller_inputs import ControllerInputs
from app.jam_session import JamSurface, decode_buttons, decode_strips
from app.model import Application


def packet(byte=0, bits=0, encoder=9):
    report = bytearray(49)
    report[0], report[1] = 1, encoder
    if byte:
        report[byte] = bits
    return report


class JamTests(unittest.TestCase):
    def setUp(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.app = Application(root.name)
        self.inputs = ControllerInputs(self.app)
        self.jam = JamSurface(self.app, self.inputs)

    def tap(self, byte, mask):
        self.jam.feed(packet(byte, mask))
        self.jam.feed(packet())

    def test_captured_report_positions_and_encoder_touch(self):
        buttons, cells, encoder = decode_buttons(packet(16, 0x18))
        self.assertEqual((buttons, cells, encoder), ({'ENCODER PUSH'}, set(), 9))
        self.assertEqual(decode_buttons(packet(16, 0x08))[0], set())
        self.assertEqual(decode_buttons(packet(4, 0x84))[1], {0, 5})
        self.assertEqual(decode_buttons(packet(12, 0x02))[1], {63})
        self.assertIsNone(decode_buttons(bytes([1, 0])))

    def test_scene_pattern_and_step_actions_preserve_other_controller_view(self):
        a = self.app
        a.page = 'PLUGIN'
        self.tap(2, 0x04)  # Scene 2
        self.tap(5, 0x08)  # Row 2, column 2
        self.assertEqual((a.scene, a.group, a.pattern), (1, 1, 1))
        self.assertEqual(a.project['scenes'][1][1], 1)
        self.tap(3, 0x02)  # STEP
        self.tap(4, 0x04)
        self.assertIn((a.pad, 0), a.notes())
        self.assertEqual(self.jam.led_frame()[66+9] & 3, 2)
        self.tap(4, 0x04)
        self.assertNotIn((a.pad, 0), a.notes())
        self.assertEqual(a.page, 'PLUGIN')

    def test_transport_and_shift_are_shared_without_losing_other_owner(self):
        self.tap(15, 0x04)
        self.assertTrue(self.app.playing)
        self.tap(15, 0x08)
        self.assertTrue(self.app.recording)
        self.inputs.button('mk2', 'SHIFT', True)
        self.jam.feed(packet(15, 0x02))
        self.jam.disconnect()
        self.assertTrue(self.app.shift)
        self.inputs.button('mk2', 'SHIFT', False)
        self.assertFalse(self.app.shift)

    def test_strips_use_primary_contact_and_led_banks(self):
        self.tap(14, 0x01)  # LEVEL
        report = bytearray(49)
        report[0] = 2
        report[3:5] = (512).to_bytes(2,'little')
        report[5:7] = (900).to_bytes(2,'little')
        self.assertEqual(decode_strips(report), (512,0,0,0,0,0,0,0))
        self.jam.feed(report)
        self.assertEqual(self.app.project['groups'][0]['gain'], 50)
        frame = self.jam.led_frame()
        self.assertEqual((len(frame), frame[0], frame[66], frame[147]), (237,128,129,130))
        self.assertEqual(sum(bool(v) for v in frame[148:159]), 6)
