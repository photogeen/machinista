import copy,io,json,struct,tempfile,time,unittest,wave
from pathlib import Path
from app.soundfont import Font
from app.web_soundfonts import SoundFonts
from app.web_server import Library


def chunk(key,data):return key+struct.pack('<I',len(data))+data+(b'\0' if len(data)&1 else b'')
def chars(s):return s.encode().ljust(20,b'\0')
def sf2(pzones=None,izones=None,custom=False,low24=False,kind=1):
 pzones=pzones if pzones is not None else [[(41,0)]]
 izones=izones if izones is not None else [[(53,0)]]
 def tables(zones,custom=False):
  bag=b'';gens=b''
  for z in zones:
   bag+=struct.pack('<HH',len(gens)//4,0)
   for k,v in z:gens+=struct.pack('<HH',k,v&65535)
  bag+=struct.pack('<HH',len(gens)//4,int(custom));gens+=struct.pack('<HH',60,0)
  mod=(struct.pack('<HHhHH',2,48,10,0,0) if custom else b'')+bytes(10)
  return bag,gens,mod
 pb,pg,pm=tables(pzones);ib,ig,im=tables(izones,custom)
 ph=struct.pack('<20sHHHIII',chars('Test Piano'),0,0,0,0,0,0)+struct.pack('<20sHHHIII',chars('EOP'),0,0,len(pzones),0,0,0)
 inst=struct.pack('<20sH',chars('Instrument'),0)+struct.pack('<20sH',chars('EOI'),len(izones))
 header=struct.pack('<20sIIIIIBbHH',chars('Sample C3'),0,64,16,48,22050,60,-7,0,kind)+struct.pack('<20sIIIIIBbHH',chars('EOS'),110,110,110,110,22050,0,0,0,1)
 pcm=b''.join(struct.pack('<h',((i%16)-8)*1000) for i in range(64))+bytes(92)
 data=chunk(b'LIST',b'INFO'+chunk(b'ifil',struct.pack('<HH',2,4 if low24 else 1))+chunk(b'INAM',b'Test SoundFont\0'))
 data+=chunk(b'LIST',b'sdta'+chunk(b'smpl',pcm)+(chunk(b'sm24',bytes(range(110))) if low24 else b''))
 data+=chunk(b'LIST',b'pdta'+b''.join(chunk(k.encode(),v) for k,v in [('phdr',ph),('pbag',pb),('pmod',pm),('pgen',pg),('inst',inst),('ibag',ib),('imod',im),('igen',ig),('shdr',header)]))
 return chunk(b'RIFF',b'sfbk'+data)

class SoundFontTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.path=self.root/'test.sf2'
 def font(self,**kwargs):self.path.write_bytes(sf2(**kwargs));return Font(self.path)
 def test_global_local_generators_ranges_pitch_envelope_and_pcm(self):
  with self.font(pzones=[[(51,1)],[(41,0),(43,40|(90<<8))]],izones=[[(34,-1200),(43,20|(100<<8)),(44,30|(110<<8))],[(53,0),(54,3),(48,60),(17,-250)]]) as f:
   p=f.plan(0);self.assertEqual(p['zone_count'],1);z=p['zones'][0]
   self.assertEqual((z['key_lo'],z['key_hi'],z['vel_lo'],z['vel_hi']),(40,90,30,110));self.assertAlmostEqual(z['tune'],.93)
   self.assertAlmostEqual(z['gain'],50.118723,places=5);self.assertEqual(z['pan'],-50);self.assertEqual((z['loop_start'],z['loop_end']),(16,48));self.assertEqual(p['sampler']['attack'],500)
   out=self.root/'test.wav';f.extract(z,out)
   with wave.open(str(out)) as w:self.assertEqual(w.getnframes(),64);self.assertEqual(w.getframerate(),22050);self.assertEqual(struct.unpack('<h',w.readframes(1))[0],-8000)
 def test_24_bit_samples_reconstruct_low_bytes(self):
  with self.font(low24=True) as f:
   out=self.root/'24.wav';f.extract(f.plan(0)['zones'][0],out)
   with wave.open(str(out)) as w:self.assertEqual(w.getsampwidth(),3);self.assertEqual(w.readframes(2),b'\x00'+struct.pack('<h',-8000)+b'\x01'+struct.pack('<h',-7000))
 def test_custom_features_are_reported_and_rom_samples_blocked(self):
  with self.font(custom=True,izones=[[(53,0),(54,1),(46,0),(57,3),(56,50)]]) as f:
   p=f.plan(0);self.assertTrue(any('modulators' in w for w in p['warnings']));self.assertTrue(any('Fixed key' in w for w in p['warnings']));self.assertTrue(any('Continuous' in w for w in p['warnings']));self.assertTrue(any('exclusive' in w for w in p['warnings']))
  with self.font(kind=0x8001) as f:self.assertTrue(f.plan(0)['blockers'])
 def test_invalid_offsets_refs_loops_duplicate_generators_and_truncation(self):
  for rows in [[(53,99)],[(53,0),(0,-20)],[(53,0),(54,3),(3,10000)],[(53,0),(53,0)]]:
   with self.font(izones=[rows]) as f:
    with self.assertRaises(ValueError):f.plan(0)
  for data in [sf2()[:-1],b'not an sf2',sf2().replace(b'sfbk',b'WAVE',1),sf2().replace(b'ifil\x04\x00\x00\x00\x02\x00',b'ifil\x04\x00\x00\x00\x03\x00',1)]:
   self.path.write_bytes(data)
   with self.assertRaises(ValueError):Font(self.path)
 def test_empty_loop_markers_report_explicit_full_sample_repair(self):
  data=bytearray(sf2(izones=[[(53,0),(54,1)]]));off=data.index(b'shdr')+8;struct.pack_into('<II',data,off+28,0,0);self.path.write_bytes(data)
  with Font(self.path) as f:
   plan=f.plan(0);self.assertEqual((plan['zones'][0]['loop_start'],plan['zones'][0]['loop_end']),(0,64));self.assertTrue(any('Empty loop' in w for w in plan['warnings']))
 def test_excess_zones_block_before_import(self):
  with self.font(izones=[[(53,0)]]*129) as f:self.assertTrue(any('128' in b for b in f.plan(0)['blockers']))

class SoundFontWorkflowTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.library=Library(self.root,source_scan=lambda:[]);self.addCleanup(self.library.soundfonts.pool.shutdown,wait=True);self.addCleanup(self.library.sounds.pool.shutdown,wait=True);self.sf=self.library.soundfonts
 def wait(self):
  for i in range(500):
   s=self.sf.status()
   if not s['busy']:return s
   time.sleep(.005)
  self.fail('Job did not complete')
 def upload(self):
  data=sf2();self.sf.upload('Piano.sf2',io.BytesIO(data),len(data));s=self.wait();self.assertEqual(s['job']['state'],'READY');return s['job']['font']
 def test_upload_inspect_confirm_import_editable_sound_and_delete_source(self):
  identity=self.upload();self.sf.inspect(dict(font=identity,preset=0));job=self.wait()['job'];self.assertEqual(job['state'],'REVIEW');self.assertEqual(job['preview']['zone_count'],1)
  value=dict(font=identity,preset=0,name='Test Piano',folder='Keys/SF2',tags=['piano'])
  self.sf.import_sound(value);self.assertEqual(self.wait()['job']['state'],'ERROR');self.assertEqual(self.library.sounds.store.scan()['sounds'],[])
  self.sf.import_sound(dict(value,accept_warnings=True));s=self.wait();self.assertEqual(s['job']['state'],'DONE');sound=s['job']['sound'];track=self.library.sounds.store.read(sound)
  self.assertEqual(track['name'],'Test Piano');self.assertEqual(track['zones'][0]['root'],60);self.assertEqual(track.get('plugins',[]),[])
  from app.model import Application
  from app.presets import read_preset
  from app.controller_inputs import ControllerInputs
  link=self.library.sounds.store.folder/self.library.sounds.store.row(sound)['link']
  for controller in ('mikro','mk1','mk2'):
   app=Application(self.root);loaded=read_preset(link,'SOUND',self.root);app.finish_preset_load(dict(group=0,pad=0,kind='SOUND',generation=app.project_generation,revision=app.revision),loaded)
   app.keyboard_enabled=True;app.page='PAD';app.actions.clear();inputs=ControllerInputs(app);inputs.pad_on(controller,0,100);self.assertTrue(any(k=='controller_hit' for k,v in app.actions));inputs.pad_off(controller,0)
  asset=track['zones'][0]['sample'];self.sf.delete(dict(font=identity));self.assertTrue(Path(asset).is_file());self.assertEqual(self.library.sounds.store.draft(sound)['folder'],'Keys/SF2')
 def test_path_safety_failed_upload_and_concurrent_jobs(self):
  for bad in ('../bad','/tmp/a','a'*31,'A'*32):
   with self.assertRaises(ValueError):self.sf.path(bad)
  with self.assertRaises(ValueError):self.sf.upload('../a.sf2',io.BytesIO(b'x'),1)
  self.library.upload_lock.acquire()
  try:
   with self.assertRaises(BlockingIOError):self.sf.upload('a.sf2',io.BytesIO(b'x'),1)
  finally:self.library.upload_lock.release()
  self.sf.upload('a.sf2',io.BytesIO(b'bad'),3);self.assertEqual(self.wait()['job']['state'],'ERROR');self.assertEqual(list(self.sf.base.glob('*.sf2')),[])
  identity=self.upload();self.sf.path(identity).unlink()
  self.assertFalse(self.sf.status()['files'])

class SoundFontHTTPTests(unittest.TestCase):
 def setUp(self):
  import threading
  from app.web_server import Server
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.library=Library(self.tmp.name,source_scan=lambda:[])
  import shutil
  web=Path(self.tmp.name)/'web';web.mkdir();shutil.copyfile(Path(__file__).resolve().parents[1]/'web/soundfonts.js',web/'soundfonts.js')
  self.addCleanup(self.library.soundfonts.pool.shutdown,wait=True)
  self.server=Server(('127.0.0.1',0),self.library);self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)
  threading.Thread(target=self.server.serve_forever,daemon=True).start();self.base='http://127.0.0.1:'+str(self.server.server_port)
 def fetch(self,path,data=None,token=True):
  import urllib.request
  headers={'X-Machinista-Token':self.library.token} if token else {}
  with urllib.request.urlopen(urllib.request.Request(self.base+path,data=data,headers=headers),timeout=5) as r:return r.read()
 def test_script_route_token_upload_inspection_and_import(self):
  import urllib.error
  self.assertIn(b'soundfont-open',self.fetch('/soundfonts.js'))
  with self.assertRaises(urllib.error.HTTPError) as e:self.fetch('/api/soundfonts/upload?name=Test.sf2',sf2(),False)
  self.assertEqual(e.exception.code,403)
  self.fetch('/api/soundfonts/upload?name=Test.sf2',sf2())
  for i in range(200):
   status=json.loads(self.fetch('/api/soundfonts'))
   if not status['busy']:break
   time.sleep(.005)
  identity=status['job']['font'];self.assertEqual(status['files'][0]['presets'][0]['name'],'Test Piano')
  self.fetch('/api/soundfonts/inspect',json.dumps(dict(font=identity,preset=0)).encode())
  for i in range(200):
   status=json.loads(self.fetch('/api/soundfonts'))
   if not status['busy']:break
   time.sleep(.005)
  self.assertEqual(status['job']['state'],'REVIEW')
  self.fetch('/api/soundfonts/import',json.dumps(dict(font=identity,preset=0,name='HTTP Piano',folder='',tags=[],accept_warnings=True)).encode())
  for i in range(200):
   status=json.loads(self.fetch('/api/soundfonts'))
   if not status['busy']:break
   time.sleep(.005)
  self.assertEqual(status['job']['state'],'DONE');self.assertEqual(json.loads(self.fetch('/api/sounds'))['sounds'][0]['name'],'HTTP Piano')
