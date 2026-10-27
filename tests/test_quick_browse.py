"""Quick Browse focuses files without assigning sounds or changing playback."""
import copy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from app.browser import Browser, Source
from tests.test_folder_browser_ui import FolderBrowserUiTests


class QuickBrowseTests(unittest.TestCase):
    setUp = FolderBrowserUiTests.setUp
    tearDown = FolderBrowserUiTests.tearDown
    open_drums = FolderBrowserUiTests.open_drums
    def test_find_current_sample_keeps_sound_and_transport(self):
        self.open_drums();a=self.a;a.rotate(2);a.button('ENTER',True)
        before=copy.deepcopy(a.project);a.playing=a.recording=True;a.actions=[]
        a.button('F1',True);a.button('SHIFT',True);a.actions=[]
        self.assertEqual(a.softkeys(),('BACK','FIND','PREH'))
        a.button('F2',True);a.button('F2',False)
        self.assertEqual(a.browser.selected(),(self.folder/'Snare.wav').resolve())
        self.assertEqual(a.project,before);self.assertTrue(a.playing and a.recording)
        self.assertEqual(a.actions,[('preview_stop',None)])
        a.button('SHIFT',False);self.assertEqual(a.softkeys()[1],'LOAD')

    def test_selected_zone_prehear_and_plugin_shortcut(self):
        self.open_drums();a=self.a;a.rotate(1);a.button('ENTER',True)
        zone=copy.deepcopy(a.track()['zones'][0]);zone['sample']=str((self.folder/'Tom.wav').resolve())
        a.track()['zones'].append(zone);a.zone_index=1
        a.audio=SimpleNamespace();a.browser.prehear=True;a.actions=[]
        a.button('SHIFT',True);a.button('F2',True)
        self.assertEqual(a.browser.selected(),(self.folder/'Tom.wav').resolve())
        self.assertEqual(a.actions,[('preview_stop',None),('preview',(self.folder/'Tom.wav').resolve())])
        a.button('BROWSE',True);self.assertEqual(a.page,'PLUGIN BROWSE')

    def test_project_assets_found_and_external_paths_rejected(self):
        a=self.a;folder=a.root/'projects'/'Example'/'samples';folder.mkdir(parents=True)
        sample=folder/'Collected.wav';sample.write_bytes((self.folder/'Kick.wav').read_bytes())
        a.track()['sample']=str(sample);a.button('BROWSE',True)
        a.button('SHIFT',True);a.button('F2',True)
        self.assertEqual(a.browser.selected(),sample.resolve())
        self.assertEqual(a.browser.title(),'Example/samples')
        self.assertTrue(any(s.name=='PROJECT ASSETS' for s in a.browser.sources))
        old=(a.browser.directory,a.browser.index)
        outside=a.root/'outside.wav';outside.write_bytes(sample.read_bytes());a.track()['sample']=str(outside)
        a.button('F2',True);self.assertEqual(a.message,'SOURCE UNAVAILABLE')
        self.assertEqual((a.browser.directory,a.browser.index),old)

    def test_empty_missing_and_removed_source_keep_assignment(self):
        a=self.a;a.button('BROWSE',True);a.button('SHIFT',True);a.button('F2',True)
        self.assertEqual(a.message,'NO SAMPLE')
        a.track()['sample']=str(self.folder/'Missing.wav');a.button('F2',True)
        self.assertEqual(a.message,'SAMPLE MISSING')
        usb=a.root/'usb';usb.mkdir();sample=usb/'USB.wav';sample.touch()
        a.browser.refresh([Source('USB TEST',usb)]);a.track()['sample']=str(sample)
        a.button('F2',True);self.assertEqual(a.browser.selected(),sample.resolve())
        a.browser.refresh([]);a.button('F2',True)
        self.assertEqual(a.message,'SOURCE UNAVAILABLE');self.assertEqual(a.track()['sample'],str(sample))


class BrowserLocateTests(unittest.TestCase):
    def test_hidden_unsupported_and_escape_do_not_move_browser(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);sd=root/'sd';sd.mkdir();b=Browser(sd)
            for name in ('.hidden.wav','other.txt'):
                path=sd/name;path.touch();self.assertEqual(b.locate(path),'SAMPLE UNAVAILABLE')
                self.assertEqual(b.directory,sd)
            outside=root/'escape.wav';outside.touch();(sd/'link.wav').symlink_to(outside)
            self.assertEqual(b.locate(sd/'link.wav'),'SOURCE UNAVAILABLE')
            self.assertEqual(b.directory,sd)

del FolderBrowserUiTests
