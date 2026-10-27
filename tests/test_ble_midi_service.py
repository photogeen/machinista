"""BlueZ control regressions; exercised on Linux with its system D-Bus module."""
import importlib.util
import unittest
from unittest.mock import MagicMock,patch

@unittest.skipUnless(importlib.util.find_spec('dbus'),'Linux system D-Bus module required')
class ServiceTests(unittest.TestCase):
    def test_display_errors_are_short_and_do_not_leak_dbus_boilerplate(self):
        import dbus
        service=self.service()
        for name,message in [('org.bluez.Error.InProgress','CONNECTION BUSY'),('org.freedesktop.DBus.Error.NoReply','CONNECTION TIMEOUT'),('org.bluez.Error.AuthenticationRejected','PAIRING REJECTED')]:
            with patch('builtins.print'):service.fail(dbus.DBusException('verbose technical details',name=name))
            self.assertEqual(service.error,message)
    def service(self):
        from tools.ble_midi_service import Service
        service=Service.__new__(Service);service.enabled=True;service.error='old';service.scan_until=0
        return service
    def test_repeated_scan_extends_window_without_in_progress_error(self):
        import dbus
        service=self.service();adapter=MagicMock();service.adapter_call=lambda:adapter
        error=dbus.DBusException('Already scanning',name='org.bluez.Error.InProgress');adapter.StartDiscovery.side_effect=error
        with patch('tools.ble_midi_service.time.monotonic',return_value=10):service.scan()
        self.assertEqual(service.scan_until,30);self.assertEqual(service.error,'')
        adapter.SetDiscoveryFilter.assert_called_once()
    def test_other_scan_errors_are_not_hidden(self):
        import dbus
        service=self.service();adapter=MagicMock();service.adapter_call=lambda:adapter
        adapter.StartDiscovery.side_effect=dbus.DBusException('Not ready',name='org.bluez.Error.NotReady')
        with self.assertRaises(dbus.DBusException):service.scan()
        self.assertEqual(service.scan_until,0)
    def test_already_stopped_scan_is_a_normal_end_not_a_connection_error(self):
        import dbus
        service=self.service();service.error='';service.scan_until=20;adapter=MagicMock();service.adapter_call=lambda:adapter
        adapter.StopDiscovery.side_effect=dbus.DBusException('No discovery started',name='org.bluez.Error.Failed')
        service.stop_scan();self.assertEqual(service.scan_until,0);self.assertEqual(service.error,'')
        adapter.StopDiscovery.side_effect=dbus.DBusException('Controller failure',name='org.bluez.Error.Failed')
        with self.assertRaises(dbus.DBusException):service.stop_scan()
    def test_pair_timeout_cancels_only_selected_attempt_before_retry(self):
        import dbus
        service=self.service();service.pending=set();service.suppressed=set();service.bus=MagicMock();service.pair=MagicMock();service.fail=MagicMock()
        address='AA:BB:CC:DD:EE:FF';service.rows=[dict(address=address,path='/device',paired=False)]
        dev=MagicMock()
        with patch('tools.ble_midi_service.dbus.Interface',return_value=dev):
            service.connect(address);self.assertIn(address,service.pending)
            service.connect(address);dev.Pair.assert_called_once()
            dev.Pair.call_args.kwargs['error_handler'](dbus.DBusException('Timeout',name='org.freedesktop.DBus.Error.NoReply'))
            dev.CancelPairing.assert_called_once();self.assertNotIn(address,service.pending)
            service.connect(address);self.assertEqual(dev.Pair.call_count,2)
