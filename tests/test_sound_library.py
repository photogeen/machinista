import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
import wave
from app.sound_library import SoundLibrary,mapping
from app.browser import Browser,Source
from app.model import Application,validate_project
from app.presets import read_preset,preset_snapshot

class SoundLibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name).resolve();self.a=Application(self.root);self.lib=SoundLibrary(self.root)
        self.sample=self.root/'samples/Test.wav'
        with wave.open(str(self.sample),'wb') as w:w.setparams((1,2,44100,0,'NONE','none'));w.writeframes(b'\x10\x10'*4096)
    def opener(self,ref):
        return self.lib.opened_asset(ref['sound'],ref['path']) if ref.get('sound') else self.sample.open('rb')
    def draft(self):return dict(name='Warm EP',folder='Keys/Electric',tags=['warm','piano'],sampler={'type':'ADSR','release':180},zones=[dict(asset={'name':'Test.wav'},root=n,key_lo=n-6,key_hi=n+5,vel_lo=1,vel_hi=127) for n in (36,48,60,72,84)])
    def test_sound_owns_samples_and_is_valid_portable_preset(self):
        d=self.lib.save(self.draft(),self.opener);row=self.lib.row(d['id']);self.assertEqual(row['zones'],5);self.assertEqual(d['zones'][0]['label'],'Test.wav')
        link=self.lib.folder/row['link'];target=read_preset(link,'SOUND',self.root)
        self.assertEqual(len(target['zones']),5);self.assertTrue(all(Path(z['sample']).is_relative_to(self.lib.bundle(d['id'])) for z in target['zones']))
        self.sample.unlink();self.assertTrue(Path(target['sample']).exists());self.assertEqual(target['sampler']['release'],180)
    def test_edit_rename_folder_move_preserves_loaded_asset_paths(self):
        d=self.lib.save(self.draft(),self.opener);old=self.lib.read(d['id']);d['name']='New EP';d['folder']='Synths';d['zones'][0]['root']=35
        new=self.lib.save(d,self.opener);self.assertEqual(self.lib.row(d['id'])['folder'],'Synths');self.assertFalse((self.lib.folder/'Keys/Electric/Warm EP.sound').exists())
        self.assertTrue(all(Path(z['sample']).exists() for z in old['zones']));self.assertEqual(new['zones'][0]['root'],35)
        with self.assertRaises(ValueError):self.lib.save(d,self.opener)
    def test_invalid_paths_ranges_names_ids_and_symlinks_rejected(self):
        for key,value in [('name','../bad'),('folder','../bad'),('tags',['x'*41])]:
            d=self.draft();d[key]=value
            with self.assertRaises(ValueError):self.lib.save(d,self.opener)
        d=self.draft();d['zones'][0]['key_lo']=128
        with self.assertRaises(ValueError):self.lib.save(d,self.opener)
        with self.assertRaises(ValueError):self.lib.opened_asset('a'*32,'../../etc/passwd')
        store=self.lib.folder/'.library'
        if not store.exists():store.mkdir(parents=True)
        link=store/'a'*0 if False else store/('a'*32)
        link.symlink_to(self.root/'samples',target_is_directory=True)
        with self.assertRaises(ValueError):self.lib.bundle('a'*32)
    def test_browser_sounds_category_folders_and_loading_retains_zone_controller(self):
        d=self.lib.save(self.draft(),self.opener);a=self.a;a.browser.refresh([]);a.browser.directory=None
        entries=a.browser.entries();self.assertIn(self.lib.folder,entries);self.assertEqual(a.browser.label(self.lib.folder),'SOUNDS')
        a.browser.directory=self.lib.folder/'Keys/Electric';entries=a.browser.entries();self.assertEqual(len(entries),1);self.assertEqual(a.browser.label(entries[0]),'Warm EP')
        a.page='BROWSE';a.enter();action,request=a.actions[-1];self.assertEqual(action,'preset_load')
        target=read_preset(request['path'],'SOUND',self.root);a.finish_preset_load(request,target);self.assertEqual(len(a.track()['zones']),5)
        a.open_sampling_page('ZONE');a.zone_page=4;a.zone_field=0;a.rotate(1);self.assertEqual(a.zone()['key_lo'],31)
    def test_midpoint_mapping_no_key_gaps_and_preserves_velocity_layers(self):
        rows=[dict(root=n,vel_lo=lo,vel_hi=hi) for n in (48,60,72) for lo,hi in ((1,64),(65,127))];mapped=mapping(rows)
        self.assertEqual([(r['key_lo'],r['key_hi']) for r in mapped[::2]],[(0,54),(55,66),(67,127)])
        self.assertEqual([r['vel_hi'] for r in mapped],[64,127]*3)
    def test_save_lv2_patch_keeps_state_and_full_strip_not_sampled(self):
        project,_=preset_snapshot(self.a,'SOUND');track=project['groups'][0]['pads'][0];state=self.root/'projects/state';state.mkdir(parents=True);(state/'state.ttl').write_text('opaque plugin patch state')
        track['plugins']=[dict(uri='urn:test:synth',kind='INSTRUMENT',controls={'cutoff':123.0},bypass=False,state=str(state/'state.ttl')),dict(uri='urn:test:effect',kind='EFFECT',controls={'mix':.3},bypass=True,state=str(state/'state.ttl'))]
        result=self.lib.save_project(project,dict(name='Live Synth',folder='Synths',tags=['pad']))
        self.assertEqual(result['kind'],'LV2');self.assertEqual(result['zones'],[])
        row=self.lib.row(result['id']);loaded=read_preset(self.lib.folder/row['link'],'SOUND',self.root)
        self.assertEqual([p['uri'] for p in loaded['plugins']],['urn:test:synth','urn:test:effect']);self.assertEqual(loaded['plugins'][0]['controls'],{'cutoff':123.0});self.assertIsNone(loaded['sample']);self.assertEqual(Path(loaded['plugins'][0]['state']).read_text(),'opaque plugin patch state')
        result.update(name='Renamed synth',folder='Pads');self.lib.save(result,self.opener);self.assertEqual(self.lib.read(result['id'])['plugins'][1]['bypass'],True)

if __name__=='__main__':unittest.main()

class SoundWebTests(SoundLibraryTests):
    def test_web_save_info_csrf_and_current_strip_preservation(self):
        from app.web_server import Library,Server
        from http.client import HTTPConnection
        import threading,time
        from unittest.mock import patch
        library=Library(self.root,source_scan=lambda:[]);server=Server(('127.0.0.1',0),library);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        def http(method,url,value=None,auth=True):
            c=HTTPConnection('127.0.0.1',server.server_port,timeout=5);c.request(method,url,json.dumps(value) if value is not None else None,{'X-Machinista-Token':library.token} if auth else {});r=c.getresponse();data=r.read();status=r.status;c.close();return status,json.loads(data) if data[:1] in (b'{',b'[') else data
        ref=dict(source='sd',path='',name='Test.wav');self.assertEqual(http('POST','/api/sounds/sample-info',ref)[1]['frames'],4096)
        d=self.draft()
        for row in d['zones']:row['asset']=ref
        self.assertEqual(http('POST','/api/sounds/save',d,False)[0],403);self.assertEqual(http('POST','/api/sounds/save',d)[0],200)
        for _ in range(200):
            data=http('GET','/api/sounds')[1]
            if not data['busy']:break
            time.sleep(.005)
        self.assertEqual(data['job']['state'],'DONE');self.assertEqual(len(data['sounds']),1)
        identity=data['sounds'][0]['id'];draft=http('GET','/api/sounds/item?id='+identity)[1];self.assertEqual(len(draft['zones']),5)
        (self.root/'web').mkdir(exist_ok=True);(self.root/'web/sounds.js').write_bytes((Path(__file__).resolve().parents[1]/'web/sounds.js').read_bytes())
        self.assertEqual(http('GET','/sounds.js')[0],200)
