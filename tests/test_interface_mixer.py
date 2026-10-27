import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app.interface_mixer import parse_controls,verified_card,set_control,InterfaceMixer,context,value_text,db_text
from app.devices import AudioDevice
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.mk2_surface import Mk2Surface
from app.mk2_encoders import quantum
from app.mk2_display import snapshot,Mk2Renderer
from app.ni_display import frame

USB=AudioDevice('1234:5678:serial:pcm0','USB Interface','plughw:2,0','plughw:2,0')
CONTENTS="""Simple mixer control 'Headphone',0
  Capabilities: pvolume pswitch
  Playback channels: Front Left - Front Right
  Limits: Playback 0 - 255
  Front Left: Playback 128 [50%] [-12.00dB] [on]
  Front Right: Playback 153 [60%] [-10.00dB] [off]
Simple mixer control 'Mic',1
  Capabilities: cvolume cswitch
  Capture channels: Mono
  Limits: Capture 0 - 10
  Mono: Capture 3 [30%] [6.00dB] [on]
Simple mixer control 'Input Source',0
  Capabilities: enum
  Items: 'Mic' 'Line'
  Item0: 'Mic'
Simple mixer control 'Capture Enable',0
  Capabilities: cswitch
  Capture channels: Mono
  Mono: Capture [off]
Simple mixer control 'Duplex',0
  Capabilities: pvolume cvolume
  Limits: Playback 0 - 255 Capture 0 - 20
  Front Left: Playback 128 [50%] [-12.00dB]
  Front Left: Capture 10 [50%] [0.00dB]
"""

class InterfaceMixerTests(unittest.TestCase):
    def app(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        a=Application(tmp.name);a.audio=USB;a.page='INTERFACE MIXER'
        a.interface_mixer_context=context(USB);a.interface_mixer_controls=parse_controls(CONTENTS)
        return a

    def test_parse_actual_channels_directions_switches_db_and_discrete_steps(self):
        controls=parse_controls(CONTENTS)
        self.assertEqual(len(controls),7)
        self.assertEqual(value_text(controls[0]),'50 - 60%')
        self.assertEqual(controls[0]['db'],('-12.00dB','-10.00dB'))
        self.assertEqual(db_text(controls[0]),'-12/-10dB')
        self.assertEqual(controls[1]['value'],0)
        self.assertEqual(controls[2]['name'],'Mic 2')
        self.assertEqual(controls[2]['step'],10)
        self.assertEqual(controls[-1]['step'],5)
        self.assertEqual(controls[-1]['direction'],'Capture')
        self.assertEqual(parse_controls(''),[])

    def test_commands_never_unmute_as_side_effect_of_level(self):
        with patch('app.interface_mixer.run') as run:
            set_control(USB,('Headphone',0,'Playback','level'),57)
            self.assertEqual(run.call_args.args,(USB,'sset',"'Headphone',0",'playback','57%'))
            set_control(USB,('Mic',1,'Capture','switch'),1)
            self.assertEqual(run.call_args.args,(USB,'sset',"'Mic',1",'capture','on'))

    def test_identity_rechecked_before_each_command_not_just_card_number(self):
        with patch('app.interface_mixer.usb_identity',return_value=('1234:5678:serial','USB')),patch.object(Path,'exists',return_value=True):
            self.assertEqual(verified_card(USB),'2')
        with patch('app.interface_mixer.usb_identity',return_value=('OTHER','USB')),patch('app.interface_mixer.subprocess.run') as run:
            with self.assertRaises(ValueError):set_control(USB,('Mic',0,'Capture','level'),100)
            run.assert_not_called()

    def test_ui_clamps_steps_selects_controls_and_does_not_edit_project(self):
        a=self.app();before=copy.deepcopy(a.project)
        a.button('NAV RIGHT',True);self.assertEqual(a.interface_mixer_index,1)
        a.rotate(1);self.assertEqual(a.interface_control()['value'],1)
        a.button('NAV RIGHT',True);a.rotate(1)
        self.assertEqual(a.interface_control()['value'],40)
        a.rotate(100);self.assertEqual(a.interface_control()['value'],100)
        self.assertEqual(a.project,before)
        self.assertEqual(a.actions[-1][0],'interface_mixer')
        a.audio=None;a.rotate(-1);self.assertEqual(a.interface_control()['value'],100)
        a.button('ENTER',True);self.assertEqual(a.page,'SETTINGS')

    def test_mk2_fields_pages_and_detached_render(self):
        a=self.app();s=Mk2Surface(a,ControllerInputs(a))
        self.assertEqual(quantum(s,s.fields()[0]),32)
        self.assertEqual(quantum(s,s.fields()[1]),8)
        s.rotate(1,1);self.assertEqual(a.interface_mixer_index,1)
        self.assertEqual(quantum(s,s.fields()[1]),32)
        s.rotate(2,1);self.assertEqual(a.interface_control()['value'],1)
        s.change_page(1);self.assertEqual(a.interface_mixer_index,2)
        self.assertEqual(s.page_state(),(2,7))
        state=snapshot(s);a.interface_control()['value']=0
        self.assertEqual(state['interface_mixer'][3],'30%')
        renderer=Mk2Renderer();self.addCleanup(renderer.close)
        self.assertEqual(len(renderer(state)),2)
        self.assertEqual(len(frame(a)),8192)

    def test_all_settings_preview_without_recording_or_destructive_pad_shortcuts(self):
        from app.settings_menu import SETTINGS_VIEWS
        a=self.app();inputs=ControllerInputs(a);a.playing=a.recording=True;a.step=0
        before=copy.deepcopy(a.project)
        for page in SETTINGS_VIEWS:
            a.page=page
            inputs.pad_on('mk2',3,100)
            self.assertTrue(any(action=='controller_hit' for action,_ in a.actions),page)
            inputs.pad_off('mk2',3);a.actions=[]
        self.assertEqual(a.project,before)
        a.page='AUDIO';a.keyboard_enabled=True;inputs.pad_on('mikro',1,90)
        self.assertTrue(any(action=='controller_hit' for action,_ in a.actions))
        inputs.pad_off('mikro',1);self.assertEqual(a.project,before)

    def test_worker_coalesces_different_controls_and_discards_stale_device_results(self):
        worker=InterfaceMixer();self.addCleanup(worker.close)
        controls=parse_controls(CONTENTS)
        with patch('app.interface_mixer.read_controls',return_value=controls),patch('app.interface_mixer.set_control') as apply:
            with worker.condition:
                worker.update(USB,0,False)
                worker.submit(USB,controls[0]['id'],10)
                worker.submit(USB,controls[0]['id'],20)
                worker.submit(USB,controls[2]['id'],40)
            result=worker.results.get(timeout=2)
            self.assertFalse(result[3]);self.assertEqual(apply.call_count,2)
            self.assertEqual(apply.call_args_list[0].args[-1],20)
            worker.results.put(result);worker.update(None,3,False)
            self.assertIsNone(worker.poll())

    def test_worker_timeout_reported_without_blocking_ui(self):
        worker=InterfaceMixer();self.addCleanup(worker.close)
        with patch('app.interface_mixer.read_controls',side_effect=OSError('removed')):
            worker.update(USB,0,True)
            self.assertEqual(worker.results.get(timeout=2)[3],'MIXER UNAVAILABLE')
