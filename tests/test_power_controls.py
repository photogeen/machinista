from pathlib import Path
import json
import subprocess
import tempfile
import time
import unittest
from unittest.mock import Mock,patch,call
from app.model import Application
from app.leds import led_report,FULL,OFF
from app.controller_settings import controller_context
from tools.power_service import PowerManager

class PowerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.a=Application(self.root)
        self.run=Mock();self.sync=Mock();self.manager=PowerManager(self.root,self.run,self.sync)
        self.addCleanup(lambda:self.manager.lease.close() if self.manager.lease else None)
        self.status(False)
    def status(self,busy):
        (self.root/'status.json').write_text(json.dumps(dict(updated=time.time(),busy=busy)))
    def test_selected_empty_pad_lights_but_mode_indicators_are_preserved(self):
        a=self.a;channels={(i,'orange'):i for i in range(16)}
        for page in ('PAD','CHANNEL','PLUGIN','SETTINGS','SAMPLING','BROWSE'):
            a.page=page;a.pad=4;report=led_report(a,channels,100)
            self.assertEqual(report[5],FULL,page)
            self.assertEqual(report[6],OFF,page)
        a.page='STEP';self.assertEqual(led_report(a,channels,100)[5],OFF)
        a.page='PAD';a.keyboard_enabled=True
        self.assertEqual(list(led_report(a,channels,100)[1:17]),[OFF]*16)
    def test_system_folders_back_and_controller_local_display(self):
        a=self.a;a.open_settings('SYSTEM')
        self.assertEqual(a.setting_entries(),('DISPLAY','PADS','WORKFLOW','PROJECT SETTINGS','SYSTEM','UPDATE','POWER'))
        a.button('ENTER',True);self.assertEqual(a.settings_title(),'DISPLAY')
        self.assertEqual(a.setting_entries(),('BRIGHTNESS','CONTRAST','INVERT','BACK'))
        with controller_context(a,'mk2'):
            self.assertEqual(a.setting_entries(),('BRIGHTNESS','CONTRAST L','CONTRAST R','INVERT','BACK'))
        a.button('MAIN',True);self.assertIsNone(a.settings_section)
        a.rotate(1);a.button('ENTER',True);self.assertEqual(a.setting_entries(),('PAD SENS','PAD CURVE','BACK'))
        a.button('F1',True);self.assertEqual(a.settings_folder,'AUDIO');self.assertIsNone(a.settings_section)
    def test_controller_confirmation_cancel_and_both_power_operations(self):
        a=self.a
        for index,action in [(0,'reboot'),(1,'shutdown')]:
            a.open_settings('SYSTEM');a.menu=a.setting_entries().index('POWER');a.button('ENTER',True);a.menu=index
            a.button('ENTER',True);self.assertEqual(a.page,'CONFIRM')
            a.button('F1',True);self.assertNotIn(('power',action),a.actions)
            a.button('ENTER',True);a.button('F2',True)
            self.assertIn(('power',action),a.actions);a.actions=[]
    def test_recording_blocks_controller_request(self):
        self.a.recording=True;self.a.request_power('shutdown')
        self.assertNotIn(('power','shutdown'),self.a.actions)
    def test_broker_acceptance_does_not_execute_and_rejects_bad_or_duplicate(self):
        with self.assertRaises(ValueError):self.manager.accept('shutdown; touch /tmp/no')
        self.manager.accept('reboot');self.run.assert_not_called();self.sync.assert_not_called()
        with self.assertRaises(ValueError):self.manager.accept('shutdown')
    def test_busy_stale_and_missing_status_refuse_power(self):
        self.status(True)
        with self.assertRaises(ValueError):self.manager.accept('shutdown')
        (self.root/'status.json').write_text(json.dumps(dict(updated=time.time()-10,busy=False)))
        with self.assertRaises(ValueError):self.manager.accept('shutdown')
        (self.root/'status.json').unlink()
        with self.assertRaises(ValueError):self.manager.accept('shutdown')
        self.run.assert_not_called()
    def test_graceful_stop_sync_power_order(self):
        events=[]
        def execute(args,**kw):
            events.append(args);return subprocess.CompletedProcess(args,0,stdout='success\n')
        run=Mock(side_effect=execute)
        manager=PowerManager(self.root,run,lambda:events.append('sync'))
        for action,target in [('shutdown','poweroff'),('reboot','reboot')]:
            events.clear();manager.pending=None;manager.accept(action);manager.execute(action)
            self.assertEqual(events,[['systemctl','stop','machinista.service'],['systemctl','show','machinista.service','--property=Result','--value'],'sync',['systemctl','--no-block',target]])
        if manager.lease:manager.lease.close()
    def test_stop_failure_aborts_power_and_restores_application(self):
        self.run.side_effect=[subprocess.CalledProcessError(1,'stop'),None]
        self.manager.accept('shutdown');self.manager.execute('shutdown')
        self.assertEqual([c.args[0] for c in self.run.call_args_list],[['systemctl','stop','machinista.service'],['systemctl','start','machinista.service']])
        self.sync.assert_not_called();self.assertIsNone(self.manager.pending)
    def test_record_started_after_confirmation_cancels_before_stop(self):
        self.manager.accept('shutdown');self.status(True);self.manager.execute('shutdown')
        self.run.assert_not_called();self.assertIsNone(self.manager.pending)

    def test_unclean_application_stop_aborts_power(self):
        self.run.return_value=subprocess.CompletedProcess([],0,stdout='timeout\n')
        self.manager.accept('reboot');self.manager.execute('reboot')
        self.sync.assert_not_called()
        self.assertFalse(any('reboot' in c.args[0] for c in self.run.call_args_list))
        self.assertEqual(self.run.call_args.args[0],['systemctl','start','machinista.service'])
