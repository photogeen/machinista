"""Partition transport must survive lsblk JSON without a NAME column."""
import json,unittest
from types import SimpleNamespace
from unittest.mock import patch
from tools.mount_usb import scan_devices,candidates

class UsbMediaScanTests(unittest.TestCase):
 def test_partition_inherits_usb_from_explicit_tree_output(self):
  disk=dict(path='/dev/sda',tran='usb',fstype=None,uuid=None)
  part=dict(path='/dev/sda1',tran=None,fstype='exfat',uuid='6AE0-7733',label='test',mountpoints=[])
  def lsblk(command,**kwargs):
   return SimpleNamespace(stdout=json.dumps(dict(blockdevices=[dict(disk,children=[part])] if '--tree' in command else [disk,part])))
  with patch('tools.mount_usb.subprocess.run',side_effect=lsblk):self.assertEqual(scan_devices(),[part])
 def test_usb_formats_do_not_include_internal_boot_or_swap(self):
  for fs in ('exfat','vfat','ext4','ntfs3'):
   part=dict(path='/dev/sda1',tran=None,fstype=fs,uuid='ABCD-1234')
   devices=[dict(path='/dev/sda',tran='usb',children=[part]),dict(path='/dev/mmcblk0',tran='mmc',children=[dict(path='/dev/mmcblk0p1',fstype='vfat',uuid='BOOT')]),dict(path='/dev/zram0',fstype='swap',uuid='SWAP')]
   self.assertEqual(candidates(devices),[part])
 def test_usb_disk_without_partition_table_is_supported(self):
  device=dict(path='/dev/sda',tran='usb',fstype='exfat',uuid='AAAA-BBBB')
  self.assertEqual(candidates([device]),[device])
