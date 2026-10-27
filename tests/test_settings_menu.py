from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
import tempfile
import unittest
from app.model import Application
from app.preferences import PREFERENCES
from app.settings_menu import SETTINGS_FOLDERS
from app.system_info import read_resources, system_page_count
from app.ni_display import frame

class SettingsMenuTests(unittest.TestCase):
    def test_fixed_tabs_folders_back_and_live_changes_persist(self):
        with tempfile.TemporaryDirectory() as root:
            a=Application(root);a.button('SHIFT',True);a.button('MAIN',True);a.button('SHIFT',False)
            a.button('F2',True)
            self.assertEqual(a.softkeys(),('AUDIO','MIDI','SYSTEM'))
            self.assertEqual(a.active_softkeys(),{1})
            self.assertTrue(all(p in a.setting_entries() for p in ('MIDI IN','MIDI OUT','MIDI CHANNEL','MIDI SYNC','MIDI OFFSET')))
            self.assertTrue(all(p in SETTINGS_FOLDERS['MIDI'] for p in PREFERENCES if p.startswith('MIDI ')))
            a.rotate(3);a.button('ENTER',True);self.assertEqual(a.page,'MIDI SYNC')
            a.rotate(1);a.button('MAIN',True)
            self.assertEqual((a.page,a.menu),('SETTINGS',3))
            a.button('F1',True);self.assertEqual(a.setting_entries(),('AUDIO','AUDIO RATE','AUDIO BUFFER','MAIN OUTPUT','CUE OUTPUT','CUE LEVEL','PLUGIN DELAY','DAC','INTERFACE MIXER'))
            a.rotate(2);a.button('ENTER',True);a.rotate(2)
            self.assertEqual(a.settings['audio_buffer'],1024)
            self.assertIn(('audio_buffer',1024),a.actions)
            a.capture_armed=True;a.rotate(1);self.assertEqual(a.settings['audio_buffer'],1024)
            a.capture_armed=False;a.capture_started=1;a.rotate(1);self.assertEqual(a.settings['audio_buffer'],1024)
            a.button('F3',True);self.assertEqual(a.settings_folder,'SYSTEM')
            a.button('ENTER',True);self.assertEqual(a.settings_section,'DISPLAY')
            a.button('ENTER',True);self.assertEqual(a.page,'BRIGHTNESS')
            a.rotate(-10);a.button('MAIN',True);a.button('MAIN',True);a.button('MAIN',True);self.assertEqual(a.page,'PAD')
            reopened=Application(root)
            self.assertEqual(reopened.settings['midi_sync'],'IN')
            self.assertEqual(reopened.settings['audio_buffer'],1024)
            self.assertEqual(reopened.settings['display_brightness'],90)

    def test_system_multiple_usb_pages_removal_and_frame_bounds(self):
        with tempfile.TemporaryDirectory() as root:
            a=Application(root);a.open_settings('SYSTEM');a.menu=a.setting_entries().index('SYSTEM');a.button('ENTER',True)
            disks=[{'name':n,'total':64000000000,'used':16000000000,'percent':25} for n in ('SD CARD','USB A','USB B')]
            a.system_stats={'cpu':37.5,'ram':{'percent':61},'storage':disks}
            self.assertEqual(system_page_count(a.system_stats),4)
            before=frame(a);a.rotate(1);self.assertNotEqual(before,frame(a))
            a.button('NAV RIGHT',True);self.assertEqual(a.system_index,2)
            a.button('NAV RIGHT',True);self.assertEqual(a.system_index,3)
            a.system_stats['storage']=disks[:1];p=frame(a);self.assertEqual(a.system_index,2)
            self.assertEqual(len(p),8192)
            self.assertTrue(all(p[x]==1 and p[63*128+x]==1 for x in range(128)))
            a.button('MAIN',True);self.assertEqual((a.page,a.menu),('SETTINGS',4))

    def test_cpu_delta_available_ram_and_disconnected_usb(self):
        with tempfile.TemporaryDirectory() as root:
            proc=Path(root);(proc/'stat').write_text('cpu  150 0 50 700 0 0 0 0 0 0\n')
            (proc/'meminfo').write_text('MemTotal: 1000 kB\nMemAvailable: 250 kB\n')
            sources=[SimpleNamespace(name='USB A',path=proc),SimpleNamespace(name='USB REMOVED',path=proc/'missing')]
            with patch('app.system_info.shutil.disk_usage',return_value=SimpleNamespace(total=1000,used=400)):
                stats,current=read_resources(proc,sources,(800,650),proc)
            self.assertEqual(stats['cpu'],50)
            self.assertEqual(stats['ram']['percent'],75)
            self.assertEqual([d['name'] for d in stats['storage']],['SD CARD','USB A'])
            self.assertEqual(stats['storage'][1]['percent'],40)
