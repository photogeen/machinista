"""ULTRA WM8960 fallback without accidentally enabling HDMI/headphone cards."""
from pathlib import Path
import tempfile
import unittest
from app.devices import AudioDevice,discover,choose_audio
from app.model import Application

class HatAudioTests(unittest.TestCase):
    def test_auto_prefers_usb_and_falls_back_but_manual_hat_is_sticky(self):
        hat=AudioDevice('hat:wm8960:pcm0','ULTRA','plughw:1,0','plughw:1,0',2,2,'HAT')
        usb=AudioDevice('usb','USB','plughw:2,0','plughw:2,0')
        self.assertEqual(choose_audio([hat,usb],'AUTO',hat.key),usb)
        self.assertEqual(choose_audio([hat],'AUTO',usb.key),hat)
        self.assertEqual(choose_audio([hat,usb],hat.key,usb.key),hat)
        self.assertIsNone(choose_audio([usb],hat.key))
    def test_discovery_whitelists_codec_and_stable_identity_after_renumber(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);sound=root/'sys';proc=root/'proc';dev=root/'dev';dev.mkdir()
            for number,name in ((0,'Headphones'),(1,'wm8960soundcard'),(2,'vc4hdmi0')):
                (sound/f'card{number}'/'device').mkdir(parents=True)
                card=proc/f'card{number}';(card/'pcm0p').mkdir(parents=True);(card/'pcm0c').mkdir();(card/'id').write_text(name)
            audio,midi=discover(sound,proc,dev);self.assertFalse(midi);self.assertEqual(len(audio),1)
            a=audio[0];self.assertEqual((a.key,a.transport,a.output_channels,a.input_channels),('hat:wm8960:pcm0','HAT',2,2))
            self.assertEqual((a.playback,a.capture),('plughw:1,0','plughw:1,0'))
            (sound/'card1').rename(sound/'card7');(proc/'card1').rename(proc/'card7')
            moved=discover(sound,proc,dev)[0][0];self.assertEqual(moved.key,a.key);self.assertEqual(moved.playback,'plughw:7,0')
    def test_application_hotplug_and_manual_switch(self):
        with tempfile.TemporaryDirectory() as root:
            a=Application(root);hat=AudioDevice('hat:wm8960:pcm0','ULTRA','plughw:1,0','plughw:1,0',2,2,'HAT');usb=AudioDevice('usb','USB','plughw:2,0','plughw:2,0')
            a.refresh_devices([hat],[]);self.assertEqual(a.audio,hat)
            a.refresh_devices([hat,usb],[]);self.assertEqual(a.audio,usb)
            a.refresh_devices([hat],[]);self.assertEqual(a.audio,hat)
            a.settings['audio']=hat.key;a.refresh_devices([hat,usb],[]);self.assertEqual(a.audio,hat)
            a.settings['audio']=usb.key;a.refresh_devices([hat,usb],[]);self.assertEqual(a.audio,usb)
    def test_playback_only_hat_has_no_capture_channels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);card=root/'proc/card1';(card/'pcm0p').mkdir(parents=True);(card/'id').write_text('wm8960soundcard');(root/'sys/card1/device').mkdir(parents=True)
            a=discover(root/'sys',root/'proc',root/'dev')[0][0]
            self.assertIsNone(a.capture);self.assertEqual(a.input_channels,0)
