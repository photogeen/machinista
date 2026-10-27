import json,os,stat,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from app.mk1_midi import discover_mk1
from app.devices import MidiDevice
from app.midi import MidiBackend,flush_bridge_input

class DiscoveryTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.manifest=self.root/'port.json';self.proc=self.root/'proc';self.pid=self.proc/'42';self.pid.mkdir(parents=True)
  self.exe=self.root/'mk1_monitor';self.exe.touch();(self.pid/'exe').symlink_to(self.exe)
  self.manifest.write_text(json.dumps(dict(pid=42,path='/dev/pts/123')))
  original=Path.lstat
  def lstat(p,*args,**kwargs):
   if str(p)=='/dev/pts/123':return SimpleNamespace(st_mode=stat.S_IFCHR|0o600,st_uid=os.getuid())
   return original(p,*args,**kwargs)
  m=patch.object(Path,'lstat',lstat);m.start();self.addCleanup(m.stop)
 def test_live_mk1_discovery_and_stable_identity(self):
  self.assertEqual(discover_mk1(self.manifest,self.proc),[MidiDevice('mk1:din','Maschine MK1 MIDI DIN','/dev/pts/123')])
 def test_stale_foreign_invalid_and_symlink_manifests_are_not_ports(self):
  for value in (dict(pid=99,path='/dev/pts/123'),dict(pid=True,path='/dev/pts/123'),dict(pid=42,path='/dev/snd/midiC0D0'),[],dict(pid=42)):
   self.manifest.write_text(json.dumps(value));self.assertEqual(discover_mk1(self.manifest,self.proc),[])
  self.manifest.unlink();self.manifest.symlink_to(self.exe);self.assertEqual(discover_mk1(self.manifest,self.proc),[])
 def test_wrong_executable_is_rejected(self):
  (self.pid/'exe').unlink();other=self.root/'another';other.touch();(self.pid/'exe').symlink_to(other)
  self.assertEqual(discover_mk1(self.manifest,self.proc),[])
 def test_input_flush_only_targets_bridge_ttys(self):
  with patch('termios.tcflush') as f:
   flush_bridge_input(3,'/dev/snd/midiC1D0');f.assert_not_called()
   flush_bridge_input(3,'/dev/pts/5');f.assert_called_once()

@unittest.skipUnless(os.name=='posix','PTY routing requires POSIX')
class MidiRoutingTests(unittest.TestCase):
 def test_raw_input_and_output_do_not_echo_or_translate_midi(self):
  import tty,select
  master,slave=os.openpty();self.addCleanup(os.close,master);self.addCleanup(os.close,slave);tty.setraw(slave);path=os.ttyname(slave)
  backend=MidiBackend();self.addCleanup(backend.close)
  backend.configure([MidiDevice('mk1:din','MK1',path)],dict(midi_in='mk1:din',midi_out='mk1:din',midi_channel=1))
  os.write(master,bytes([0x90,60,100,0xf8,0x80,60,0]));backend.poll()
  self.assertEqual(backend.take_events(),[(0x90,(60,100)),(0xf8,()),(0x80,(60,0))])
  backend.send(bytes([0x90,64,127]));self.assertTrue(select.select([master],[],[],.1)[0]);self.assertEqual(os.read(master,64),bytes([0x90,64,127]))
  self.assertFalse(select.select([backend.port_fd(path)],[],[],0)[0])

@unittest.skipUnless(__import__('sys').platform=='linux','Linux controlling-terminal regression')
class HangupTests(unittest.TestCase):
 def test_midi_selection_never_becomes_controlling_terminal_or_kills_session_on_unplug(self):
  import subprocess,sys,select,tty
  master,slave=os.openpty();tty.setraw(slave);path=os.ttyname(slave)
  script='''import os,sys
from app.midi import MidiBackend
from app.devices import MidiDevice
os.setsid()
m=MidiBackend();m.configure([MidiDevice('mk1:din','MK1',sys.argv[1])],dict(midi_in='mk1:din',midi_out='mk1:din',midi_channel=1))
try:
 fd=os.open('/dev/tty',os.O_RDWR|os.O_NOCTTY);os.close(fd);raise AssertionError('Acquired a controlling terminal')
except OSError:pass
print('ready',flush=True)
sys.stdin.readline()
m.close_ports()
print('survived',flush=True)
'''
  p=subprocess.Popen([sys.executable,'-c',script,path],cwd=Path(__file__).resolve().parents[1],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  try:
   self.assertTrue(select.select([p.stdout],[],[],3)[0]);self.assertEqual(p.stdout.readline().strip(),'ready')
   os.close(slave);slave=-1;os.close(master);master=-1
   out,err=p.communicate('unplugged\n',timeout=3)
   self.assertEqual(p.returncode,0,err);self.assertEqual(out.strip(),'survived')
  finally:
   if master>=0:os.close(master)
   if slave>=0:os.close(slave)
   if p.poll() is None:p.kill();p.communicate()
