import unittest,tempfile,collections
from unittest.mock import Mock
from app.mk3_protocol import Decoder
from app.mk3_pads import Mk3PadTrigger,trigger_threshold
from app.mk3_session import Mk3Session
from app.model import Application


def report(kind,value=0,raw=12):
    return bytes((2,raw,kind|(value>>8),value&255))+bytes(60)


class Mk3PadTests(unittest.TestCase):
    def setUp(self):self.decoder=Decoder();self.trigger=Mk3PadTrigger()
    def play(self,kind,value=0,sensitivity=100,raw=12):
        return [e for event in self.decoder.decode(report(kind,value,raw)) for e in self.trigger.process(event,sensitivity)]
    def test_light_contact_from_actual_capture_triggers_and_releases_once(self):
        # Real Pad1 capture: contact34, pressure41, release. Previously discarded.
        self.assertEqual(self.play(0x40,77),[])
        self.assertEqual([e['kind'] for e in self.play(0,34)],['pad_on'])
        self.assertEqual([e['kind'] for e in self.play(0x40,41)],['pad_pressure'])
        self.assertEqual([e['kind'] for e in self.play(0x20)],['pad_off'])
        self.assertEqual(self.play(0x40),[])
    def test_sensitivity_changes_detection_and_not_velocity(self):
        self.assertEqual(self.play(0,8,sensitivity=50),[])
        self.assertEqual(self.play(0x20),[])
        high=self.play(0,8,sensitivity=150)
        self.assertEqual([e['kind'] for e in high],['pad_on'])
        self.assertEqual([e['kind'] for e in self.play(0x20)],['pad_off'])
        self.assertGreater(trigger_threshold(50),trigger_threshold(100))
        self.assertGreater(trigger_threshold(100),trigger_threshold(150))
    def test_weak_contact_can_cross_threshold_with_pressure(self):
        # Actual capture: contact8 then pressure74. It must not be lost.
        self.assertEqual(self.play(0,8),[])
        self.assertEqual([e['kind'] for e in self.play(0x40,74)],['pad_on'])
        self.assertEqual([e['kind'] for e in self.play(0x40,55)],['pad_pressure'])
        self.assertEqual([e['kind'] for e in self.play(0x20)],['pad_off'])
    def test_firmware_note_on_promotion_does_not_double_contact(self):
        self.play(0,34)
        self.assertEqual(self.play(0x10,426),[])
        self.assertEqual([e['kind'] for e in self.play(0x30)],['pad_off'])
        self.assertEqual(self.trigger.sounding,set())
    def test_empty_pad_report_does_not_arm_a_contact(self):
        self.assertEqual(self.decoder.decode(bytes([2])+bytes(63)),[])
        self.assertEqual(self.play(0x40,2000,raw=0),[])

    def test_repeated_strikes_polyphony_and_no_idle_pressure_trigger(self):
        self.assertEqual(self.play(0x40,2000),[])
        self.assertEqual([e['kind'] for e in self.play(0x10,1000)],['pad_on'])
        self.assertEqual([e['kind'] for e in self.play(0x10,1200)],['pad_off','pad_on'])
        self.assertEqual([e['kind'] for e in self.play(0,50,raw=13)],['pad_on'])
        self.assertEqual(len(self.trigger.sounding),2)
        self.play(0x30);self.play(0x20,raw=13);self.assertEqual(self.trigger.sounding,set())
    def test_session_dispatches_contacts_with_device_local_threshold(self):
        with tempfile.TemporaryDirectory() as d:
            a=Application(d);a.input_timestamp=None;s=Mk3Session.__new__(Mk3Session)
            s.app=a;s.inputs=Mock();s.pad_trigger=Mk3PadTrigger();s.input_lags=collections.deque(maxlen=128)
            a.settings['controllers']['mk3']['pad_sensitivity']=150
            for event in self.decoder.decode(report(0,8)):self.assertTrue(s.handle_event(event))
            s.inputs.pad_on.assert_called_once_with('mk3',0,1)
            for event in self.decoder.decode(report(0x20)):s.handle_event(event)
            s.inputs.pad_off.assert_called_once_with('mk3',0)
