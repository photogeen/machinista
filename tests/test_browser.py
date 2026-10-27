from pathlib import Path
import tempfile
import unittest
from app.browser import Browser, Source
from tools.mount_usb import candidates


class BrowserTests(unittest.TestCase):
    def test_sources_folders_selection_and_up(self):
        with tempfile.TemporaryDirectory() as root:
            sd, usb = Path(root)/'sd', Path(root)/'usb'
            sd.mkdir(); usb.mkdir()
            (usb/'Drums').mkdir()
            (usb/'Drums/Kick.wav').touch()
            (usb/'ignored.txt').touch()
            browser = Browser(sd)
            browser.refresh([Source('USB BEATS', usb)])
            browser.directory = None
            self.assertEqual(browser.entries(), [sd, usb])
            browser.index = 1
            browser.open()
            self.assertEqual(browser.entries(), [usb/'Drums'])
            browser.open()
            self.assertEqual(browser.label(browser.selected()), 'Kick.wav')
            self.assertEqual(browser.open(), usb/'Drums/Kick.wav')
            browser.up(); self.assertEqual(browser.directory, usb)
            browser.up(); self.assertIsNone(browser.directory)

    def test_removed_usb_returns_to_sources_and_never_reads_escape(self):
        with tempfile.TemporaryDirectory() as root:
            sd, usb = Path(root)/'sd', Path(root)/'usb'
            sd.mkdir(); usb.mkdir()
            (Path(root)/'outside.wav').touch()
            (usb/'escape.wav').symlink_to(Path(root)/'outside.wav')
            browser = Browser(sd)
            browser.refresh([Source('USB', usb)])
            browser.directory = usb
            self.assertEqual(browser.entries(), [])
            browser.refresh([])
            self.assertIsNone(browser.directory)
            self.assertEqual(browser.error, 'MEDIA REMOVED')
            self.assertEqual(browser.entries(), [sd])

    def test_media_candidates_only_include_usb_data_filesystems(self):
        rows = [{'path': '/dev/mmcblk0', 'tran': None, 'children': [
                    {'path': '/dev/mmcblk0p2', 'fstype': 'ext4', 'uuid': 'sd'}]},
                {'path': '/dev/sda', 'tran': 'usb', 'children': [
                    {'path': '/dev/sda1', 'fstype': 'exfat', 'uuid': 'usb-a'},
                    {'path': '/dev/sda2', 'fstype': 'crypto_LUKS', 'uuid': 'locked'}]}]
        self.assertEqual([d['path'] for d in candidates(rows)], ['/dev/sda1'])


if __name__ == '__main__':
    unittest.main()
