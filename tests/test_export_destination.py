import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from app.browser import Source,mounted_sources
from app.export_destination import ExportLocation
from app.export_midi import render_midi_export
from app.export_audio import render_export
from tools.mount_usb import mount_options,mount_filesystem
from tests import test_export_audio as export_tests
ROOT=export_tests.ROOT


class DestinationTests(unittest.TestCase):
    setUp=export_tests.ExportTests.setUp
    request=export_tests.ExportTests.request
    def usb(self,readonly=False):
        path=self.root/'usb';path.mkdir(exist_ok=True)
        source=Source('USB TEST',path,'mount-45',readonly)
        self.a.browser.refresh([source])
        return source,dict(path=str(path),name=source.name,identity=source.identity,read_only=readonly)
    def test_menu_audio_midi_hotplug_readonly_and_request_snapshot(self):
        a=self.a;source,dest=self.usb();a.open_export();a.export_field=8;a.rotate(1)
        self.assertEqual(a.export_value(),'USB TEST');a.export_request();self.assertEqual(a.actions[-1][1]['destination'],dest)
        a.export_destination['name']='CHANGED';self.assertEqual(a.actions[-1][1]['destination']['name'],'USB TEST')
        a.export_busy=False;a.open_export('MIDI');a.export_field=3;self.assertEqual(a.export_value(),'USB TEST')
        a.browser.refresh([]);self.assertEqual(a.export_value(),'USB REMOVED');a.export_request();self.assertFalse(a.export_busy)
        a.rotate(-1);self.assertEqual(a.export_value(),'SD CARD')
        source,dest=self.usb(True);a.rotate(1);self.assertEqual(a.export_value(),'USB TEST (RO)');a.export_request();self.assertEqual(a.message,'USB READ ONLY')
    def test_kernel_mount_identity_decodes_spaces_and_changes_on_remount(self):
        manifest=self.root/'manifest';proc=self.root/'mountinfo'
        manifest.write_text(json.dumps([dict(name='LABEL',path='/media/USB Drive')]))
        proc.write_text('45 22 8:1 / /media/USB\\040Drive rw,relatime - vfat /dev/sda1 rw\n')
        with patch.object(Path,'is_dir',return_value=True):first=mounted_sources(manifest,proc)[0]
        self.assertFalse(first.read_only)
        proc.write_text('46 22 8:1 / /media/USB\\040Drive ro,relatime - vfat /dev/sda1 ro\n')
        with patch.object(Path,'is_dir',return_value=True):second=mounted_sources(manifest,proc)[0]
        self.assertNotEqual(first.identity,second.identity);self.assertTrue(second.read_only)
    def test_midi_writes_only_usb_and_unique_folders(self):
        source,dest=self.usb();request=self.request(destination=dest)
        with patch('app.export_destination.mounted_sources',return_value=[source]):
            first=render_midi_export(request,self.root);second=render_midi_export(request,self.root)
        self.assertEqual(first.parent,source.path/'Machinista/exports');self.assertNotEqual(first,second)
        self.assertTrue((first/'Notes.mid').is_file());self.assertFalse((self.root/'exports').exists())
    def test_missing_or_replaced_media_never_falls_back_to_sd(self):
        source,dest=self.usb()
        for sources in ([],[Source(source.name,source.path,'replacement')]):
            with patch('app.export_destination.mounted_sources',return_value=sources):
                with self.assertRaisesRegex(ValueError,'REMOVED OR CHANGED'):render_midi_export(self.request(destination=dest),self.root)
        self.assertFalse((self.root/'exports').exists())
    def test_readonly_and_denied_target_fail_before_export(self):
        import errno,os
        source,dest=self.usb()
        with patch('app.export_destination.mounted_sources',return_value=[source]),patch('app.export_destination.os.fstatvfs',return_value=SimpleNamespace(f_flag=os.ST_RDONLY)):
            with self.assertRaisesRegex(ValueError,'USB READ ONLY'):render_midi_export(self.request(destination=dest),self.root)
        with patch('app.export_destination.mounted_sources',return_value=[source]),patch('app.export_destination.os.open',side_effect=PermissionError(errno.EACCES,'denied')):
            with self.assertRaisesRegex(ValueError,'NOT WRITABLE'):render_midi_export(self.request(destination=dest),self.root)
        self.assertEqual(list(source.path.iterdir()),[])

    def test_symlink_destination_is_rejected(self):
        source,dest=self.usb();outside=self.root/'outside';outside.mkdir();(source.path/'Machinista').symlink_to(outside,target_is_directory=True)
        with patch('app.export_destination.mounted_sources',return_value=[source]):
            with self.assertRaises(OSError):ExportLocation(self.root,self.request(destination=dest))
        self.assertEqual(list(outside.iterdir()),[])
    @unittest.skipUnless(Path('/proc/self/fd').is_dir(),'Linux directory pinning required')
    def test_pinned_directory_survives_mount_path_replacement(self):
        source,dest=self.usb()
        with patch('app.export_destination.mounted_sources',return_value=[source]):
            location=ExportLocation(self.root,self.request(destination=dest))
            try:
                old=self.root/'old-usb';source.path.rename(old);source.path.mkdir()
                with self.assertRaisesRegex(ValueError,'REMOVED OR CHANGED'):location.verify()
                (location.base/'proof').write_text('pinned')
                self.assertTrue((old/'Machinista/exports/proof').is_file());self.assertEqual(list(source.path.iterdir()),[])
            finally:location.close()
    def test_mount_policy_and_readonly_fallback_preserve_browsing(self):
        self.assertTrue(mount_options('vfat').startswith('rw,'));self.assertIn('uid=1000',mount_options('exfat'))
        self.assertTrue(mount_options('iso9660').startswith('ro,'));self.assertNotIn('noload',mount_options('ext4'))
        with patch('tools.mount_usb.subprocess.run',side_effect=[SimpleNamespace(returncode=1,stderr='readonly'),SimpleNamespace(returncode=0)]) as run:
            self.assertEqual(mount_filesystem('/dev/sda1',Path('/media/test'),'ext4').returncode,0)
        self.assertIn('ro,nosuid,nodev,noexec,noload',run.call_args_list[1].args[0])


@unittest.skipUnless((ROOT/'build/audio_engine').exists() and Path('/usr/share/alsa/alsa.conf').exists(),'Linux native build required')
class NativeDestinationTests(unittest.TestCase):
    setUp=export_tests.NativeExportTests.setUp
    request=export_tests.ExportTests.request
    usb=DestinationTests.usb
    def test_actual_audio_export_child_uses_pinned_usb_and_preserves_assets(self):
        source,dest=self.usb();original=Path(self.a.track()['sample']).read_bytes()
        with patch('app.export_destination.mounted_sources',return_value=[source]):
            result=render_export(self.request(destination=dest,normalize=True,loop_optimize=True,bits=24),self.root)
        self.assertEqual(result.parent,source.path/'Machinista/exports');self.assertTrue((result/'Mix.wav').is_file())
        self.assertFalse(list(result.glob('*.tmp')));self.assertFalse((self.root/'exports').exists());self.assertEqual(Path(self.a.track()['sample']).read_bytes(),original)
    def test_usb_removal_aborts_render_and_cleans_private_output(self):
        source,dest=self.usb();available=[source]
        class Progress:
            def put(self,text):
                if text.startswith('RENDER'):available.clear()
        with patch('app.export_destination.mounted_sources',side_effect=lambda:available):
            with self.assertRaisesRegex(ValueError,'REMOVED OR CHANGED'):render_export(self.request(destination=dest),self.root,progress=Progress())
        self.assertFalse((self.root/'exports').exists());self.assertEqual(list((source.path/'Machinista/exports').iterdir()),[])
    def test_destination_capacity_failure_cleans_job(self):
        source,dest=self.usb()
        with patch('app.export_destination.mounted_sources',return_value=[source]),patch('app.export_audio.shutil.disk_usage',side_effect=lambda path:SimpleNamespace(free=10**9 if Path(path)==self.root else 0)):
            with self.assertRaisesRegex(ValueError,'FREE SPACE'):render_export(self.request(destination=dest),self.root)
        self.assertEqual(list((source.path/'Machinista/exports').iterdir()),[])
