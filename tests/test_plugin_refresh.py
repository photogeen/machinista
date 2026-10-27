from pathlib import Path
from types import SimpleNamespace
import json
import tempfile
import unittest
from concurrent.futures import Future
from app.plugin_refresh import PluginRefresh

class RefreshTests(unittest.TestCase):
    def test_catalog_refresh_waits_for_stop_and_preserves_project(self):
        from app.model import Application
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);a=Application(root);runtime=root/'runtime';runtime.mkdir()
            (runtime/'revision.json').write_text(json.dumps(dict(revision='new')))
            refresh=PluginRefresh(root,runtime);self.addCleanup(refresh.close)
            audio=SimpleNamespace(recorder=None,plugin_metadata=[])
            original=json.dumps(a.project,sort_keys=True)
            scans=[]
            def scan():scans.append(1);return [dict(uri='urn:new',name='New')]
            refresh.scan=scan;a.playing=True
            refresh.poll(a,audio,1);self.assertEqual(scans,[])
            self.assertTrue(json.loads((runtime/'in-use.json').read_text())['busy'])
            a.playing=False;refresh.poll(a,audio,2);refresh.future.result(timeout=2);refresh.poll(a,audio,3)
            self.assertEqual(a.plugin_catalog,audio.plugin_metadata);self.assertEqual(a.plugin_catalog[0]['uri'],'urn:new')
            self.assertEqual(json.dumps(a.project,sort_keys=True),original)
