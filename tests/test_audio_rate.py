from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from app.audio import AudioBackend
from app.devices import AudioDevice
from app.model import Application,SETTING_PAGES


class AudioRateTests(unittest.TestCase):
    def test_setting_persists_and_blocks_change_during_capture(self):
        with tempfile.TemporaryDirectory() as root:
            app=Application(root);app.page='SETTINGS';app.menu=SETTING_PAGES.index('AUDIO RATE')
            app.button('ENTER',True);self.assertEqual(app.page,'AUDIO RATE')
            app.rotate(-1);self.assertEqual(app.settings['sample_rate'],44100)
            self.assertIn(('audio_rate',44100),app.actions)
            self.assertEqual(Application(root).settings['sample_rate'],44100)
            app.capture_started=1;app.rotate(1)
            self.assertEqual(app.settings['sample_rate'],44100);self.assertEqual(app.message,'STOP RECORDING FIRST')
            app.capture_started=None;app.rotate(1);self.assertEqual(app.settings['sample_rate'],48000)
            app.button('F3',True);self.assertEqual(app.page,'SETTINGS')
    def test_capture_and_playback_request_identical_rates(self):
        with tempfile.TemporaryDirectory() as root:
            backend=AudioBackend.__new__(AudioBackend);backend.root=Path(root);backend.recorder=None;backend.native_capture=None
            backend.sample_rate=48000;backend.plugin_chains={};commands=[];backend.command=commands.append;backend.on_message=lambda m:None
            device=AudioDevice('test','H1','plughw:3,0','plughw:3,0')
            backend.device(device,44100)
            self.assertEqual(commands,['device "plughw:3,0" 44100 0 2 2'])
            with patch('app.audio.subprocess.Popen') as process:
                backend.capture(device.capture,(0,0))
                self.assertIsNone(process.call_args)
                self.assertEqual(commands[-1],'capture_barrier')
                backend.begin_capture()
                args=process.call_args.args[0]
                self.assertEqual(args[args.index('-r')+1],'44100')
                self.assertEqual(args[args.index('-f')+1],'S16_LE')
                self.assertEqual(args[args.index('-c')+1],'2')
            backend.record_errors.close()
