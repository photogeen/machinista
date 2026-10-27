import copy,json,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from threading import Event
from unittest.mock import patch
from app import plugin_profiles as profiles
from app.live_banks import LiveBanks

class LiveBankTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.p=profiles.profile('urn:machinista:instrument:synth')
        self.folder=profiles.bank_folder(self.root,self.p);self.folder.mkdir(parents=True)
        self.bank=dict(schema=1,uri=self.p['uri'],name='Own bank',patches=[dict(name='Original',controls={v['symbol']:v['default'] for v in self.p['parameters']})])
        self.file=self.folder/'own.json';self.write()
        with patch.object(profiles,'profiles',return_value=(self.p,)):
            self.live=LiveBanks(self.root)
        self.addCleanup(self.live.close);self.app=SimpleNamespace(playing=False,recording=False)
    def write(self):self.file.write_text(json.dumps(self.bank))
    def wait(self):
        deadline=time.monotonic()+3
        while not self.live.future.done() and time.monotonic()<deadline:time.sleep(.005)
        self.assertTrue(self.live.future.done())
    def test_live_controls_never_read_or_validate_files_even_after_ttl(self):
        expected=profiles.banks(self.root,self.p)
        with patch.object(profiles,'read_banks',side_effect=AssertionError('disk in live path')),patch.object(profiles,'validate_bank',side_effect=AssertionError('validation in live path')):
            for _ in range(100):self.assertIs(profiles.banks(self.root,self.p),expected)
    def test_pending_scan_preserves_catalog_then_switches_atomically(self):
        before=profiles.banks(self.root,self.p);started=Event();finish=Event()
        original=self.live.scan
        def slow():
            started.set();finish.wait(3);return original()
        self.bank['patches'][0]['name']='Updated';self.write()
        with patch.object(self.live,'scan',side_effect=slow):
            self.live.poll(self.app,10);self.assertTrue(started.wait(1))
            self.assertIs(profiles.banks(self.root,self.p),before)
            finish.set();self.wait();self.live.poll(self.app,10.1)
        self.assertEqual(profiles.banks(self.root,self.p)[0]['patches'][0]['name'],'Updated')
    def test_playback_and_recording_defer_scans_and_publication(self):
        for key in ('playing','recording'):
            setattr(self.app,key,True);self.live.poll(self.app,10)
            self.assertIsNone(self.live.future);setattr(self.app,key,False)
        before=profiles.banks(self.root,self.p)
        self.file.unlink();self.live.poll(self.app,10);self.wait()
        self.app.playing=True;self.live.poll(self.app,10.1)
        self.assertIs(profiles.banks(self.root,self.p),before)
        self.app.playing=False;self.live.poll(self.app,10.2)
        self.assertEqual(len(profiles.banks(self.root,self.p)),1)
    def test_unchanged_scan_keeps_bank_identity_and_invalid_bank_is_rejected(self):
        before=profiles.banks(self.root,self.p)
        self.live.poll(self.app,10);self.wait();self.live.poll(self.app,10.1)
        self.assertIs(profiles.banks(self.root,self.p),before)
        self.bank['patches'][0]['controls']['output']=float('nan');self.write()
        self.live.poll(self.app,11);self.wait();self.live.poll(self.app,11.1)
        self.assertEqual(len(profiles.banks(self.root,self.p)),1)
