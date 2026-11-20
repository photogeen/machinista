import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from app.model import Application
from app.pad_sensitivity import PadSensitivitySender
from app.mk3_pads import Mk3PadTrigger
from app.mk2_surface import Mk2Surface
from app.controller_inputs import ControllerInputs

class PadSensitivityTests(unittest.TestCase):
    def test_real_settings_encoder_updates_reader_and_reconnect(self):
        with tempfile.TemporaryDirectory() as directory:
            app=Application(directory);surface=Mk2Surface(app,ControllerInputs(app))
            read,write=os.pipe();os.set_blocking(read,False)
            try:
                stream=os.fdopen(write,'wb',buffering=0)
                self.addCleanup(stream.close)
                process=SimpleNamespace(stdin=stream);sender=PadSensitivitySender()
                sender.update(process,app,'mk2');self.assertEqual(os.read(read,100),b'SENS 100\n')
                app.page='PAD SENS';surface.rotate(2,-75)
                sender.update(process,app,'mk2');self.assertEqual(os.read(read,100),b'SENS 25\n')
                sender.update(process,app,'mk2')
                with self.assertRaises(BlockingIOError):os.read(read,100)
                # New reader gets persisted value even when unchanged.
                sender.update(SimpleNamespace(stdin=stream),app,'mk2');self.assertEqual(os.read(read,100),b'SENS 25\n')
                self.assertEqual(Application(directory).settings['controllers']['mk2']['pad_sensitivity'],25)
                sender.update(process,app,'mikro');self.assertEqual(os.read(read,100),b'SENS 100\n')
                app.mikro_model='mikro_mk2';app.settings['controllers']['mikro_mk2']['pad_sensitivity']=75
                sender.update(process,app,'mikro');self.assertEqual(os.read(read,100),b'SENS 75\n')
            finally:os.close(read)
    def test_full_pipe_retries_without_wait(self):
        app=SimpleNamespace(settings={'pad_sensitivity':150})
        process=SimpleNamespace(stdin=SimpleNamespace(fileno=lambda:9))
        sender=PadSensitivitySender()
        with patch('app.pad_sensitivity.os.write',side_effect=[BlockingIOError(),9]) as write:
            sender.update(process,app,'mikro');self.assertIsNone(sender.value)
            sender.update(process,app,'mikro');self.assertEqual(sender.value,150)
            self.assertEqual(write.call_count,2)
    def test_sensitivity_never_changes_velocity_fixed_or_curved(self):
        with tempfile.TemporaryDirectory() as directory:
            a=Application(directory)
            for source in ('mikro','mk1','mk2','mikro_mk2','mk3','plus'):
                values=a.settings if source=='mikro' else a.settings['controllers'][source]
                for curve in ('LINEAR','SOFT','HARD','FIXED'):
                    values['pad_curve']=curve;values['pad_sensitivity']=25
                    before=a.pad_velocity(70,source);values['pad_sensitivity']=200
                    self.assertEqual(a.pad_velocity(70,source),before)
    def test_mk3_firmware_strike_respects_threshold_and_releases_once(self):
        t=Mk3PadTrigger()
        event=dict(kind='pad_on',name='PAD_1',raw_value=30,value=2)
        self.assertEqual(t.process(event,25),[])
        self.assertEqual(t.process(dict(event,kind='pad_off'),25),[])
        self.assertEqual(t.process(event,150),[event])
        t.process(dict(event,kind='pad_pressure'),25)
        self.assertEqual(len(t.process(dict(event,kind='pad_off'),25)),1)
        self.assertEqual(t.process(dict(event,kind='pad_off'),25),[])

    def test_reader_confirms_applied_setting_without_masking_missing_usb_heartbeat(self):
        from app.connection_health import ReaderWatch
        watch=ReaderWatch(report_limit=5);watch.start(0)
        self.assertTrue(watch.receive(dict(kind='reader_pad_sensitivity',value=25),2))
        self.assertEqual(watch.summary(2)['pad_sensitivity'],25)
        self.assertTrue(watch.expired(6))
        with self.assertRaises(ValueError):watch.receive(dict(kind='reader_pad_sensitivity',value=0),6)
        watch.stop();self.assertIsNone(watch.pad_sensitivity)
