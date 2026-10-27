import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.model import Application
from app.controller_settings import mikro_display_settings
from app.mikro_mk2_protocol import BUTTON_LEDS,PAD_SLOTS,led_report,send
from app.mikro_session import MikroSession
from app.controller_inputs import ControllerInputs
from tools.mikro_leds import load_pad_channels
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from tools.mikro_settings import configure_display

ROOT=Path(__file__).resolve().parents[1]

class MikroMk2Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=Application(self.tmp.name)
        self.channels=load_pad_channels(ROOT/'captures/mikro-mk1-pad-led-map.json')
        self.buttons=json.loads((ROOT/'captures/mikro-mk1-button-led-map.json').read_text())['buttons']

    def test_buttons_and_every_rgb_pad_have_separate_addresses(self):
        self.assertEqual(len(set(BUTTON_LEDS.values())),28)
        for name,target in BUTTON_LEDS.items():
            raw=bytearray(61);raw[0]=128;raw[1+self.buttons[name]]=31
            actual=led_report(raw,self.channels,self.buttons)
            expected={9,10} if name=='GROUP' else {target+1}
            self.assertEqual({i for i,v in enumerate(actual) if i and v},expected,name)
        for slot in range(16):
            raw=bytearray(61);raw[0]=128;raw[1+self.channels[(slot,'orange')]]=31
            actual=led_report(raw,self.channels,self.buttons)
            self.assertEqual(len(actual),79)
            self.assertEqual({i for i,v in enumerate(actual) if i and v},{31+PAD_SLOTS.index(slot)*3,32+PAD_SLOTS.index(slot)*3})

    def test_group_colors_dim_full_and_off_are_preserved(self):
        raw=bytearray(61);raw[0]=128;i=1+self.channels[(0,'orange')]
        raw[i]=4;dim=led_report(raw,self.channels,self.buttons,1)
        raw[i]=31;full=led_report(raw,self.channels,self.buttons,1)
        self.assertGreater(full[67],dim[67]);self.assertEqual(full[68:70],b'\0\0')
        raw[i]=0;self.assertFalse(any(led_report(raw,self.channels,self.buttons)[1:]))

    def test_output_rejects_wrong_lengths_before_writing(self):
        with patch('app.mikro_mk2_protocol.os.write',return_value=79) as write:
            send(1,bytes([128])+bytes(78));write.assert_called_once()
            for raw in (b'',bytes([128])+bytes(80),bytes([128])+bytes(60)):
                with self.assertRaises(ValueError):send(1,raw)
            self.assertEqual(write.call_count,1)

    def test_display_and_pad_settings_are_saved_separately_from_other_devices(self):
        a=self.a;before=copy.deepcopy(a.settings);a.mikro_model='mikro_mk2'
        a.page='CONTRAST';a.rotate(7)
        self.assertEqual(a.settings['controllers']['mikro_mk2']['display_contrast'],49)
        self.assertEqual(a.settings['display_contrast'],before['display_contrast'])
        a.page='INVERT';a.rotate(1);self.assertEqual(mikro_display_settings(a),(100,49,True))
        a.page='PAD SENS';a.rotate(50)
        self.assertEqual(a.settings['controllers']['mikro_mk2']['pad_sensitivity'],150)
        v=a.pad_velocity(500);a.mikro_model='mikro';self.assertGreater(v,a.pad_velocity(500))
        self.assertEqual(a.settings['controllers']['mk2'],before['controllers']['mk2'])
        reopened=Application(self.tmp.name);reopened.mikro_model='mikro_mk2'
        self.assertEqual(mikro_display_settings(reopened),(100,49,True))

    def test_wire_adapter_changes_only_mk2_output_and_keeps_mikro_workflow(self):
        a=self.a;a.button_led_map=self.buttons
        session=MikroSession(self.tmp.name,a,ControllerInputs(a),None,None,None,None)
        raw=bytes([128])+bytes(60)
        self.assertEqual(session.encode_leds(raw),raw)
        session.model='mikro_mk2';session.channels=self.channels
        self.assertEqual(len(session.encode_leds(raw)),79)
        a.mikro_model='mikro_mk2';a.page='SOUND';a.button('VIEW',True)
        self.assertTrue(a.view_selector);a.rotate(1);a.button('F1',True);a.button('VIEW',False)
        self.assertNotEqual(a.page,'VIEW NAV')

    def test_feature_update_preserves_reserved_fields(self):
        register=bytearray.fromhex('f880004000010001563f00');writes=[]
        def ioctl(fd,request,data,mutate):
            if request&255==7:data[:]=register
            else:writes.append(bytes(data));register[:]=data
            return 11
        with patch('tools.mikro_settings.fcntl.ioctl',side_effect=ioctl):configure_display(1,90,51)
        self.assertEqual(writes,[bytes.fromhex('f8800040000100015a3300')])

if __name__=='__main__':unittest.main()
