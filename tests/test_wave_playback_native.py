"""Real engine telemetry against ALSA null, without touching physical outputs."""
import array
import json
import os
from pathlib import Path
import select
import subprocess
import tempfile
import time
import unittest
from app.audio import AudioBackend
from app.layout import PREVIEW,ZONE_BASE

ENGINE=Path(os.environ.get('MACHINISTA_TEST_ENGINE',str(Path(__file__).resolve().parent.parent/'build/audio_engine')))

@unittest.skipUnless(ENGINE.exists() and Path('/usr/share/alsa/alsa.conf').exists(),'Linux ALSA engine required')
class NativeWavePlaybackTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  path=Path(self.tmp.name)/'sample.f32';path.write_bytes(array.array('f',[.05]*16384).tobytes())
  self.p=subprocess.Popen([str(ENGINE)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
  self.addCleanup(self.close)
  self.send(f'load 0 48000 {json.dumps(str(path))}\nrange 0 1000 7000\ndevice "null" 48000')
  self.wait(lambda e:e.get('kind')=='audio' and e.get('status')=='ready')
  backend=AudioBackend.__new__(AudioBackend);backend.command=self.send
  self.backend=backend
 def close(self):
  if self.p.poll() is None:
   self.send('quit')
   try:self.p.communicate(timeout=5)
   except subprocess.TimeoutExpired:self.p.kill();self.p.communicate()
 def send(self,line):self.p.stdin.write(line+'\n');self.p.stdin.flush()
 def wait(self,predicate):
  deadline=time.monotonic()+3
  while time.monotonic()<deadline:
   ready,_,_=select.select([self.p.stdout],[],[],.1)
   if ready:
    line=self.p.stdout.readline()
    if not line:self.fail('engine exited: '+self.p.stderr.read())
    event=json.loads(line)
    if predicate(event):return event
  self.fail('engine telemetry timeout')
 def cursor(self,token,active):
  for _ in range(100):
   self.send('wave_status')
   event=self.wait(lambda e:e.get('kind')=='wave_position')
   if event['token']==token and event['active']==active:return event
   time.sleep(.002)
  self.fail(str(event))
 def loop(self,slot,reverse=False):
  self.backend._params(slot,{'sampler':{'reverse':reverse}},dict(loop=True,loop_start=1500,loop_end=6500))
 def test_real_voices_pitch_reverse_loop_and_stop(self):
  self.loop(0);self.send('wave_watch 1 0 0\nhit 0 0.1 2')
  first=self.cursor(1,True)
  frames=[]
  for _ in range(8):
   frames.append(self.cursor(1,True)['frame']);time.sleep(.003)
  self.assertTrue(all(1000<=x<7000 for x in frames));self.assertGreater(len(set(frames)),1)
  self.send('kill_bus 0');self.cursor(1,False)
  self.loop(0,True);self.send('hit 0 0.1 0.5');self.cursor(1,True)
  self.send('panic');self.cursor(1,False)
 def test_zone_preview_and_unrelated_sound_are_distinguished(self):
  self.send(f'assign {ZONE_BASE} 0\nrange {ZONE_BASE} 1000 7000');self.loop(ZONE_BASE)
  self.send(f'wave_watch 2 0 0\nhit {ZONE_BASE} 0.1');self.cursor(2,True)
  self.send('wave_watch 3 1 0');self.cursor(3,False)
  self.send(f'assign {PREVIEW} 0\nrange {PREVIEW} 1000 7000');self.loop(PREVIEW)
  self.send(f'hit {PREVIEW} 0.1');self.cursor(3,True)
  self.send('preview_stop');self.cursor(3,False)
