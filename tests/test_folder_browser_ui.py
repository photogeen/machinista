import array
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
import wave
from app.model import Application
from app.ni_display import frame

class FolderBrowserUiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.a=Application(self.temp.name)
        self.folder=self.a.samples/'Drums';self.folder.mkdir()
        (self.folder/'More').mkdir()
        for name in ('Kick.wav','Snare.wav','Tom.wav','Zap.wav'):
            with wave.open(str(self.folder/name),'wb') as w:
                w.setparams((1,2,44100,0,'NONE','not compressed'));w.writeframes(array.array('h',[10]*100).tobytes())
        (self.folder/'ignore.txt').touch()
    def tearDown(self):self.temp.cleanup()
    def open_drums(self):
        a=self.a;a.button('BROWSE',True);a.button('ENTER',True)
        a.browser_index=a.entries().index(self.folder);a.button('ENTER',True)
    def test_encoder_scroll_and_enter_load_are_one_list_without_automatic_assignment(self):
        self.open_drums();a=self.a
        self.assertEqual(a.softkeys(),('BACK','OPEN','PREH'))
        self.assertEqual([p.name for p in a.entries()],['More','Kick.wav','Snare.wav','Tom.wav','Zap.wav'])
        a.rotate(2);self.assertEqual(a.browser.selected().name,'Snare.wav')
        self.assertEqual(a.softkeys(),('BACK','LOAD','PREH'));self.assertIsNone(a.track()['sample'])
        a.button('ENTER',True);self.assertEqual(Path(a.track()['sample']).name,'Snare.wav')
        self.assertEqual(a.page,'BROWSE');self.assertEqual(a.browser_index,2)
        self.assertEqual(len(frame(a)),8192)
    def test_back_preserves_parent_selection_and_reopening_preserves_folder_position(self):
        self.open_drums();a=self.a;a.rotate(3)
        a.button('BROWSE',True);a.button('BROWSE',True)
        self.assertEqual(a.browser.directory,self.folder);self.assertEqual(a.browser_index,3)
        a.button('F1',True);self.assertEqual(a.browser.selected(),self.folder)
        a.button('F1',True);self.assertIsNone(a.browser.directory)
        self.assertEqual(a.browser.selected(),a.samples)
    def test_prehear_follows_files_and_stops_on_folder_or_back(self):
        self.open_drums();a=self.a;a.audio=SimpleNamespace();a.button('F3',True);a.actions=[]
        a.rotate(1);self.assertEqual(a.actions[-1],('preview',self.folder/'Kick.wav'))
        a.rotate(1);self.assertEqual(a.actions[-1],('preview',self.folder/'Snare.wav'))
        a.rotate(-2);self.assertEqual(a.actions[-1],('preview_stop',None))
        a.button('F1',True);self.assertEqual(a.actions[-1],('preview_stop',None))
        self.assertTrue(a.browser.prehear);self.assertEqual(a.active_softkeys(),{2})
        a.button('F3',True);self.assertFalse(a.browser.prehear)
    def test_open_empty_folder_does_not_assign_or_crash(self):
        self.open_drums();a=self.a;a.button('F2',True)
        self.assertEqual(a.browser.directory,self.folder/'More')
        self.assertEqual(a.softkeys(),('BACK','-','PREH'))
        a.button('ENTER',True);self.assertEqual(a.message,'EMPTY FOLDER')
        self.assertIsNone(a.track()['sample']);self.assertEqual(len(frame(a)),8192)
