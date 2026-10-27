from pathlib import Path
import json
import tempfile
import threading
import time
import unittest
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.mk2_surface import Mk2Surface
from app.mk2_display import snapshot,Mk2Renderer
from app.bluetooth_midi import BluetoothMidi,command
from app.ble_midi_bridge import discover_ble,parse_ports,parse_connections

class BluetoothMidiTests(unittest.TestCase):
    def test_saved_enable_retries_when_service_starts_later(self):
        calls=[]
        def call(c):
            calls.append(c['op'])
            if len(calls)==1:raise OSError('service not ready')
            return {'enabled':True,'devices':[]}
        backend=BluetoothMidi(call)
        try:
            backend.submit('on');backend.poll(0)
            deadline=time.monotonic()+1
            while not backend.future.done() and time.monotonic()<deadline:time.sleep(.001)
            self.assertEqual(backend.poll(.1)['error'],'BLUETOOTH UNAVAILABLE')
            backend.poll(.5);self.assertEqual(calls,['on'])
            backend.poll(.7)
            deadline=time.monotonic()+1
            while not backend.future.done() and time.monotonic()<deadline:time.sleep(.001)
            self.assertTrue(backend.poll(.8)['enabled']);self.assertEqual(calls,['on','on'])
        finally:backend.close()

    def test_controller_controls_keep_usb_preferences_and_projects_intact(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=Application(tmp);a.page='BLUETOOTH MIDI'
            before=json.dumps(a.project,sort_keys=True);midi=(a.settings['midi_in'],a.settings['midi_out'])
            a.bluetooth_status={'enabled':False,'devices':[dict(address='AA:BB:CC:DD:EE:FF',name='Keys',connected=False),dict(address='11:22:33:44:55:66',name='Piano',connected=True)]}
            s=Mk2Surface(a,ControllerInputs(a))
            self.assertEqual(s.softkeys()[:4],('ON/OFF','PAIR','SCAN','BACK'))
            s.softkey(0);self.assertEqual(a.actions.pop(),('bluetooth',('on',None)))
            s.softkey(1);self.assertEqual(a.actions.pop(),('bluetooth',('pair',None)))
            s.softkey(2);self.assertEqual(a.actions.pop(),('bluetooth',('scan',None)))
            s.rotate(1,1);self.assertEqual(a.bluetooth_index,1)
            s.softkey(5);self.assertEqual(a.actions.pop(),('bluetooth',('disconnect','11:22:33:44:55:66')))
            a.bluetooth_index=0;s.softkey(4);self.assertEqual(a.actions.pop(),('bluetooth',('connect','AA:BB:CC:DD:EE:FF')))
            r=Mk2Renderer()
            try:self.assertEqual(tuple(map(len,r(snapshot(s)))),(16384,16384))
            finally:r.close()
            self.assertEqual(before,json.dumps(a.project,sort_keys=True));self.assertEqual(midi,(a.settings['midi_in'],a.settings['midi_out']))
            a.shift=True;a.settings_button('F2',True);self.assertEqual(a.actions.pop(),('bluetooth',('pair',None)))
            a.settings_button('F3',True);self.assertEqual(a.page,'SETTINGS');self.assertEqual(a.settings_folder,'MIDI')

    def test_slow_service_never_blocks_input_and_queue_is_bounded(self):
        entered=threading.Event();release=threading.Event()
        def call(c):entered.set();release.wait(2);return {'enabled':True,'devices':[]}
        backend=BluetoothMidi(call)
        try:
            backend.submit('on');started=time.monotonic();backend.poll(0)
            self.assertLess(time.monotonic()-started,.05);self.assertTrue(entered.wait(1))
            for i in range(50):backend.submit('connect',str(i))
            self.assertEqual(len(backend.queue),8);self.assertIsNone(backend.poll(.1))
            release.set();deadline=time.monotonic()+1;result=None
            while result is None and time.monotonic()<deadline:
                result=backend.poll(.2);time.sleep(.001)
            self.assertTrue(result['enabled'])
        finally:release.set();backend.close()

    def test_virtual_ports_require_correct_card_identity_and_valid_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);proc=root/'proc';dev=root/'dev';card=proc/'card7'
            card.mkdir(parents=True);dev.mkdir();(card/'id').write_text('maschineBLE')
            (dev/'midiC7D0').touch();(dev/'midiC7D2').touch();manifest=root/'ports.json'
            manifest.write_text(json.dumps([dict(slot=0,key='ble:server',name='Machinista'),dict(slot=2,key='ble:AA:BB:CC:DD:EE:FF',name='Keys'),dict(slot=20,key='ble:server',name='Invalid')]))
            ports=discover_ble(proc,dev,manifest)
            self.assertEqual([p.key for p in ports],['ble:server','ble:AA:BB:CC:DD:EE:FF'])
            self.assertEqual(ports[1].path,str(dev/'midiC7D2'))
            (card/'id').write_text('USBKeyboard');self.assertEqual(discover_ble(proc,dev,manifest),[])

    def test_alsa_parser_ignores_subscriptions_and_preserves_device_names(self):
        ports=parse_ports("client 36: 'Virtual Raw MIDI 5-0' [type=kernel,card=5]\n    0 'Virtual Raw MIDI 5-0'\n        Connecting To: 128:0\nclient 128: 'BlueALSA' [type=user,pid=33]\n    0 'BLE MIDI Server '\n")
        self.assertEqual(ports,[(36,0,'Virtual Raw MIDI 5-0','Virtual Raw MIDI 5-0'),(128,0,'BlueALSA','BLE MIDI Server')])
        self.assertEqual(parse_connections("client 36: 'Virtual Raw MIDI 5-0' [type=kernel,card=5]\n    0 'VirMIDI 5-0'\n        Connecting To: 128:0, 129:2\n"),{((36,0),(128,0)),((36,0),(129,2))})
