import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from app.storage import SettingsWriter, save_json, _save_json


class RuntimeSettingsWriterTests(unittest.TestCase):
    def test_slow_disk_does_not_block_input_and_latest_snapshot_survives_close(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'settings.json'
            entered=threading.Event();release=threading.Event();writes=[]
            def slow(path,value):
                writes.append(value['level']);entered.set();release.wait(2);_save_json(path,value)
            with patch('app.storage._save_json',side_effect=slow):
                writer=SettingsWriter(path,quiet=0)
                try:
                    state={'level':1};save_json(path,state)
                    self.assertTrue(entered.wait(1))
                    started=time.monotonic()
                    for i in range(2,101):state['level']=i;save_json(path,state)
                    self.assertLess(time.monotonic()-started,.1)
                    state['level']=999  # The queued value must be detached.
                finally:release.set();writer.close()
            self.assertEqual(writes,[1,100]);self.assertEqual(json.loads(path.read_text()),{'level':100})
            save_json(path,{'level':101})
            self.assertEqual(json.loads(path.read_text())['level'],101)

    def test_burst_coalesces_and_close_flushes_before_quiet_period(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'settings.json';writer=SettingsWriter(path,quiet=10)
            with patch('app.storage._save_json',wraps=_save_json) as write:
                for i in range(100):save_json(path,{'value':i})
                writer.close();self.assertEqual(write.call_count,1)
            self.assertEqual(json.loads(path.read_text())['value'],99)

    def test_write_failure_is_reported_on_close(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'settings.json';writer=SettingsWriter(path,quiet=10)
            with patch('app.storage._save_json',side_effect=OSError('disk full')):
                save_json(path,{'x':1})
                with self.assertRaises(OSError):writer.close()
            save_json(path,{'x':2})  # Failed writer is unregistered.
