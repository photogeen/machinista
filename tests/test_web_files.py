import errno
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from app.browser import Source
from app.web_server import Library
from app.web_files import rename_exclusive

class FileTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.samples=self.root/'samples';self.samples.mkdir()
        self.library=Library(self.root,lambda:[]);self.files=self.library.files
        (self.samples/'From').mkdir();(self.samples/'To').mkdir()
        (self.samples/'From/kick.wav').write_bytes(b'audio')
    def test_file_move_never_overwrites(self):
        self.files.move('sd','From','kick.wav','sd','To')
        self.assertEqual((self.samples/'To/kick.wav').read_bytes(),b'audio')
        (self.samples/'From/kick.wav').write_bytes(b'other')
        with self.assertRaises(FileExistsError):self.files.move('sd','From','kick.wav','sd','To')
        self.assertEqual((self.samples/'To/kick.wav').read_bytes(),b'audio')
        self.assertEqual((self.samples/'From/kick.wav').read_bytes(),b'other')
    def test_nested_folder_move_and_descendant_rejection(self):
        (self.samples/'From/Sub').mkdir()
        with self.assertRaises(ValueError):self.files.move('sd','','From','sd','From/Sub')
        self.files.move('sd','','From','sd','To')
        self.assertTrue((self.samples/'To/From/Sub').is_dir())
        self.assertEqual((self.samples/'To/From/kick.wav').read_bytes(),b'audio')
    def test_folder_delete_and_restore_keeps_every_byte_and_is_hidden(self):
        result=self.files.delete('sd','','From')
        self.assertFalse((self.samples/'From').exists())
        self.assertNotIn('.machinista-trash',[x['name'] for x in self.library.list('sd','')['entries']])
        rows=self.files.trash_list('sd')['entries'];self.assertEqual(rows[0]['id'],result['id'])
        self.files.restore('sd',result['id'])
        self.assertEqual((self.samples/'From/kick.wav').read_bytes(),b'audio')
        self.assertEqual(self.files.trash_list('sd')['entries'],[])
    def test_restore_conflict_keeps_recovery_copy(self):
        result=self.files.delete('sd','From','kick.wav')
        (self.samples/'From/kick.wav').write_bytes(b'new')
        with self.assertRaises(FileExistsError):self.files.restore('sd',result['id'])
        self.assertEqual(len(self.files.trash_list('sd')['entries']),1)
        self.assertEqual((self.samples/'From/kick.wav').read_bytes(),b'new')
    def test_empty_destination_folder_is_not_replaced(self):
        (self.samples/'To/From').mkdir()
        with self.assertRaises(FileExistsError):self.files.move('sd','','From','sd','To')
        self.assertTrue((self.samples/'From/kick.wav').exists())
    def test_trash_symlink_cannot_redirect_deletion(self):
        (self.samples/'.machinista-trash').symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(OSError):self.files.delete('sd','From','kick.wav')
        self.assertEqual((self.samples/'From/kick.wav').read_bytes(),b'audio')
    def test_cross_device_nested_symlink_never_reads_external_content(self):
        (self.samples/'From/secret').symlink_to(self.root,target_is_directory=True)
        first=True
        def rename(*args):
            nonlocal first
            if first:first=False;raise OSError(errno.EXDEV,'Different device')
            return rename_exclusive(*args)
        with patch('app.web_files.rename_exclusive',side_effect=rename):
            with self.assertRaises(ValueError):self.files.move('sd','','From','sd','To')
        self.assertTrue((self.samples/'From/kick.wav').exists())
        self.assertEqual(list((self.samples/'To').iterdir()),[])
    def test_paths_symlinks_readonly_and_concurrent_operation_rejected(self):
        (self.samples/'escape').symlink_to(self.root,target_is_directory=True)
        for method in (lambda:self.files.delete('sd','','escape'),lambda:self.files.move('sd','From','kick.wav','sd','escape'),lambda:self.files.delete('sd','..','x.wav')):
            with self.assertRaises((ValueError,OSError)):method()
        self.library.scan=lambda:[Source('RO',self.samples,read_only=True)]
        ro=next(k for k in self.library.sources() if k!='sd')
        with self.assertRaises(PermissionError):self.files.delete(ro,'From','kick.wav')
        self.library.upload_lock.acquire()
        try:
            with self.assertRaises(BlockingIOError):self.files.delete('sd','From','kick.wav')
        finally:self.library.upload_lock.release()
    def test_cross_device_move_and_recovery(self):
        usb=self.root/'usb';usb.mkdir();self.library.scan=lambda:[Source('USB',usb)]
        identity=next(k for k in self.library.sources() if k!='sd')
        first=True
        def rename(*args):
            nonlocal first
            if first:first=False;raise OSError(errno.EXDEV,'Different device')
            return rename_exclusive(*args)
        with patch('app.web_files.rename_exclusive',side_effect=rename):self.files.move('sd','','From',identity,'')
        self.assertEqual((usb/'From/kick.wav').read_bytes(),b'audio')
        self.assertFalse((self.samples/'From').exists())
        trash=self.files.trash_list('sd')['entries'];self.assertEqual(len(trash),1)
        self.files.restore('sd',trash[0]['id']);self.assertEqual((self.samples/'From/kick.wav').read_bytes(),b'audio')
    def test_cross_device_copy_failure_never_removes_original(self):
        with patch('app.web_files.rename_exclusive',side_effect=OSError(errno.EXDEV,'Different device')),patch.object(self.files,'copy_entry',side_effect=OSError('Disk full')):
            with self.assertRaises(OSError):self.files.move('sd','From','kick.wav','sd','To')
        self.assertEqual((self.samples/'From/kick.wav').read_bytes(),b'audio')
        self.assertEqual(list((self.samples/'To').iterdir()),[])
