import configparser
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,Mock
import queue
import threading
from app.network_manager import Manager,hotspot_name,credentials,fields

class NetworkTests(unittest.TestCase):
    def manager(self):
        m=Manager.__new__(Manager);m.interface='wlan0';m.ssid='Machinista-ABCD';m.ap_uuid='ap';m.jobs=queue.Queue(maxsize=1);m.lock=threading.Lock();m.busy=False;m.message='';m.last_try=0;m.down_since=None
        m.refresh_smb=Mock()
        return m
    def test_device_unique_name_escaping_and_validation(self):
        self.assertEqual(hotspot_name('dc:a6:32:12:ab:cd'),'Machinista-ABCD')
        self.assertEqual(fields(r'Home\: Studio:70:WPA2'),['Home: Studio','70','WPA2'])
        self.assertEqual(credentials('My Router','machinista'),('My Router','machinista'))
        for ssid,password in [('', '12345678'),('a'*33,''),('x\n','12345678'),('SSID','short'),('SSID','x\n'*5)]:
            with self.assertRaises(ValueError):credentials(ssid,password)
    def test_profile_secrets_are_private_and_not_command_arguments(self):
        m=self.manager();m.nm=Mock(return_value='')
        with tempfile.TemporaryDirectory() as folder:
            m.profiles=Path(folder);m.profile('ap',m.ssid,'machinista')
            path=m.profiles/'machinista-hotspot.nmconnection'
            cfg=configparser.ConfigParser(interpolation=None);cfg.read(path)
            self.assertEqual(cfg['wifi-security']['psk'],'machinista')
            self.assertEqual(cfg['ipv4']['method'],'shared')
            self.assertEqual(path.stat().st_mode&0o777,0o600)
            self.assertNotIn('machinista',str(m.nm.call_args.args[:-1]))
            m.profile('infrastructure','Space: Router',r'ab cd\ef')
            self.assertEqual((m.profiles/'machinista-home.nmconnection').stat().st_mode&0o777,0o600)
    def test_router_connection_never_disrupted_by_watchdog(self):
        m=self.manager();m.active=Mock(return_value='home');m.scan=Mock();m.fallback=Mock()
        m.tick(1000);m.scan.assert_not_called();m.fallback.assert_not_called()
    def test_lost_router_returns_to_hotspot_even_if_scan_fails(self):
        m=self.manager();m.active=Mock(return_value=None);m.scan=Mock(side_effect=OSError());m.fallback=Mock();m.clients=Mock(return_value=[])
        m.tick(100);m.fallback.assert_not_called()
        m.tick(116);m.fallback.assert_called_once()
    def test_visible_saved_router_is_retried_and_failed_join_returns_to_ap(self):
        m=self.manager();m.active=Mock(return_value='ap');m.scan=Mock(return_value={'networks':[{'ssid':'Home'}]});m.clients=Mock(return_value=[('home','Home')]);m.activate=Mock();m.fallback=Mock()
        m.tick(100);m.activate.assert_called_once_with('home');m.fallback.assert_not_called()
        m.activate.side_effect=OSError();m.tick(161);m.fallback.assert_called_once()
    def test_connect_ack_then_failure_fallback_and_retry_allowed(self):
        m=self.manager();m.profile=Mock(return_value='home');m.activate=Mock(side_effect=OSError());m.fallback=Mock()
        self.assertTrue(m.submit('Home','machinista')['ok'])
        with self.assertRaises(ValueError):m.submit('Other','machinista')
        with patch('app.network_manager.time.sleep'):m.tick(100)
        m.fallback.assert_called_once();self.assertFalse(m.busy)
        self.assertNotIn('machinista',m.message)
        self.assertTrue(m.submit('Other','machinista')['ok'])
