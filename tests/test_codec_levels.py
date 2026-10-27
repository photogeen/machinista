import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app.model import Application
from app.devices import AudioDevice
from app.codec_levels import CodecLevels, caption

HAT=AudioDevice('hat:wm8960:pcm0','ULTRA','plughw:1,0','plughw:1,0',2,2,'HAT')
USB=AudioDevice('usb:pcm0','USB','plughw:2,0','plughw:2,0')

class CodecLevelTests(unittest.TestCase):
    def test_levels_are_hardware_only_clamped_and_persist(self):
        with tempfile.TemporaryDirectory() as root:
            app=Application(root);app.refresh_devices([HAT],[])
            project=repr(app.project)
            for page,key,maximum in [('HEADPHONE LEVEL','hat_headphone',127),('SPEAKER LEVEL','hat_speaker',127),('INPUT GAIN','hat_input',63)]:
                app.page=page;app.rotate(1000);self.assertEqual(app.settings[key],maximum)
                app.rotate(-1000);self.assertEqual(app.settings[key],0)
            self.assertEqual(repr(app.project),project)
            self.assertIn(('codec_levels',None),app.actions)
            self.assertEqual(Application(root).settings['hat_headphone'],0)
            app.audio=USB;app.page='INPUT GAIN';app.rotate(5)
            self.assertEqual(app.settings['hat_input'],0)
            self.assertEqual(app.message,'ULTRA HAT ONLY')

    def test_commands_target_only_verified_hat_and_use_raw_values(self):
        values={'hat_headphone':101,'hat_speaker':100,'hat_input':39}
        with patch.object(Path,'read_text',return_value='wm8960soundcard'),patch('app.codec_levels.subprocess.run') as run:
            CodecLevels.apply(HAT,values)
            self.assertEqual([c.args[0] for c in run.call_args_list],[
                ['amixer','-q','-c','1','sset','Playback','255,255'],
                ['amixer','-q','-c','1','sset','Left Output Mixer PCM','on'],
                ['amixer','-q','-c','1','sset','Right Output Mixer PCM','on'],
                ['amixer','-q','-c','1','sset','Left Input Mixer Boost','on'],
                ['amixer','-q','-c','1','sset','Right Input Mixer Boost','on'],
                ['amixer','-q','-c','1','sset','Headphone','101,101'],
                ['amixer','-q','-c','1','sset','Speaker','100,100'],
                ['amixer','-q','-c','1','sset','Capture','39,39']])
        with patch.object(Path,'read_text',return_value='USB'),patch('app.codec_levels.subprocess.run') as run:
            with self.assertRaises(ValueError):CodecLevels.apply(HAT,values)
            run.assert_not_called()

    def test_worker_failure_is_reported_without_leaking_to_main_thread(self):
        import threading
        done=threading.Event()
        def fail(*args):done.set();raise OSError('device gone')
        worker=CodecLevels()
        try:
            with patch.object(worker,'apply',side_effect=fail):
                worker.submit(HAT,{'hat_headphone':101,'hat_speaker':101,'hat_input':39})
                self.assertTrue(done.wait(1))
                # Queue get waits for the worker's completion rather than polling UI.
                self.assertEqual(worker.results.get(timeout=1),(HAT.key,'HARDWARE LEVEL ERROR'))
                worker.submit(USB,{})
        finally:worker.close()

    def test_db_matches_codec_scales(self):
        self.assertEqual(caption('HEADPHONE LEVEL',101),'-20.00 dB')
        self.assertEqual(caption('HEADPHONE LEVEL',0),'MUTE')
        self.assertEqual(caption('INPUT GAIN',39),'+12.00 dB')

    def test_independent_mutes_keep_levels_and_persist_on_both_surfaces(self):
        from app.mk2_surface import Mk2Surface
        from app.controller_inputs import ControllerInputs
        from app.mk2_display import snapshot
        with tempfile.TemporaryDirectory() as root:
            a=Application(root);a.refresh_devices([HAT],[]);a.page='HEADPHONE LEVEL'
            hp,sp=a.settings['hat_headphone'],a.settings['hat_speaker']
            a.settings_button('F1',True)
            self.assertTrue(a.settings['hat_headphone_mute']);self.assertFalse(a.settings['hat_speaker_mute'])
            self.assertEqual(a.settings['hat_headphone'],hp)
            surface=Mk2Surface(a,ControllerInputs(a));state=snapshot(surface)
            self.assertEqual(state['keys'][:2],('HP MUTE','SP MUTE'));self.assertEqual(state['active_left'],(0,))
            a.settings_button('F2',True);self.assertTrue(a.settings['hat_speaker_mute'])
            self.assertEqual(a.settings['hat_speaker'],sp)
            self.assertTrue(Application(root).settings['hat_speaker_mute'])
            a.settings_button('F1',True);self.assertFalse(a.settings['hat_headphone_mute'])
            self.assertEqual(a.settings['hat_headphone'],hp)

    def test_hardware_mute_only_silences_target_output(self):
        values={'hat_headphone':109,'hat_speaker':120,'hat_input':39,'hat_headphone_mute':True,'hat_speaker_mute':False}
        with patch.object(Path,'read_text',return_value='wm8960soundcard'),patch('app.codec_levels.subprocess.run') as run:
            CodecLevels.apply(HAT,values)
            commands=[c.args[0] for c in run.call_args_list]
            self.assertIn(['amixer','-q','-c','1','sset','Headphone','0,0'],commands)
            self.assertIn(['amixer','-q','-c','1','sset','Speaker','120,120'],commands)
            self.assertEqual(values['hat_headphone'],109)
