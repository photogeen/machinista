import threading
import time
import unittest
from app.device_monitor import DeviceMonitor

class DeviceMonitorTests(unittest.TestCase):
    def test_slow_scan_is_nonblocking_and_reports_hotplug_results(self):
        start=threading.Event();release=threading.Event()
        def scan():start.set();release.wait(2);return (['audio'],['midi'],['usb'])
        monitor=DeviceMonitor(scan);self.addCleanup(monitor.close);self.addCleanup(release.set)
        self.assertIsNone(monitor.poll(0));self.assertTrue(start.wait(1))
        self.assertIsNone(monitor.poll(.5));release.set()
        monitor.future.result(timeout=1)
        self.assertEqual(monitor.poll(.6),(['audio'],['midi'],['usb']));self.assertIsNone(monitor.future)
        self.assertIsNone(monitor.poll(1.1));self.assertIsNotNone(monitor.future)
    def test_failed_scan_can_retry_without_losing_worker(self):
        def scan():raise OSError('media unavailable')
        monitor=DeviceMonitor(scan);self.addCleanup(monitor.close);monitor.poll(0)
        try:monitor.future.result(timeout=1)
        except OSError:pass
        with self.assertRaises(OSError):monitor.poll(.2)
        self.assertIsNone(monitor.poll(1.1));self.assertIsNotNone(monitor.future)
