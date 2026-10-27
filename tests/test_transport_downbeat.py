"""Stopped restart/start must retain the audio start cursor until it is used."""
import array,copy,json,os,select,subprocess,tempfile,time,unittest
from pathlib import Path
from app.model import Application
from app.native_sequence import NativeSequence
from app.sequencer_clock import advance_clock
ROOT=Path(__file__).resolve().parents[1]

class TransportDownbeatTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=Application(self.tmp.name);self.n=NativeSequence();self.commands=[]
        self.audio=type('Audio',(),{'command':self.commands.append})()
    def update(self,now=1):self.n.update(self.a,self.audio,None,now,now+self.a.clock_interval())
    def start_after_ui_advance(self):
        a=self.a;a.button('PLAY',True);a.button('PLAY',False)
        advance_clock(a,10,10+3*a.clock_interval())
        self.update(10+3*a.clock_interval())
        return [c for c in self.commands if c.startswith('sequence_seek ')][-1].split()[1]
    def test_stopped_restart_waits_for_play_even_after_idle_updates(self):
        a=self.a;a.clock_phase=900;a.step=37;self.update()
        a.button('RESTART',True);a.button('RESTART',False);self.n.reset(0);a.actions=[]
        for now in (2,3,4):self.update(now)
        self.assertEqual(self.start_after_ui_advance(),'0.000000000')
    def test_initial_play_uses_stopped_cursor_not_advanced_ui_tick(self):
        self.update();self.assertEqual(self.start_after_ui_advance(),'0.000000000')
    def test_stopped_locate_resumes_at_selected_bar_and_does_not_jump_to_zero(self):
        a=self.a;a.clock_phase=384;a.step=16;self.n.reset(384)
        for now in (1,2,3):self.update(now)
        self.assertEqual(self.start_after_ui_advance(),'384.000000000')
    def test_external_clock_handoff_uses_current_external_position(self):
        a=self.a;self.update();a.settings['midi_sync']='IN';a.playing=True;a.clock_phase=96;a.step=4
        self.update(2);a.settings['midi_sync']='OFF';a.clock_phase=192;a.step=8
        self.update(3)
        self.assertEqual([c for c in self.commands if c.startswith('sequence_seek ')][-1].split()[1],'192.000000000')
    def test_start_after_count_in_keeps_zero_and_ignores_old_epoch(self):
        a=self.a;a.clock_phase=768;a.step=32;self.update();a.start_count_in();self.n.reset(0)
        old_epoch=self.n.epoch;self.update(2)
        for tick in range(384):a.clock_tick(4+tick*a.clock_interval())
        advance_clock(a,6,6+3*a.clock_interval());self.update(7)
        self.assertEqual([c for c in self.commands if c.startswith('sequence_seek ')][-1].split()[1],'0.000000000')
        self.n.receive(a,dict(kind='sequence_clock',epoch=old_epoch,tick=900,stamp=7))
        self.assertIsNone(self.n.clock)

@unittest.skipUnless(os.name=='posix' and Path('/usr/share/alsa/alsa.conf').exists() and (ROOT/'build/audio_engine').exists(),'Native Linux audio engine required')
class NativeTransportDownbeatTests(unittest.TestCase):
    def test_actual_engine_emits_first_sample_and_midi_on_play_after_stopped_restart(self):
        for midi in (False,True):
            with self.subTest(midi=midi),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);a=Application(root);a.active_clips[0]=True
                a.put_note(0,0,dict(velocity=100,probability=100,length=24,note=60))
                sample=root/'tone.f32';sample.write_bytes(array.array('f',[.5,.5]*256).tobytes())
                if midi:a.track().update(source='MIDI',channel=1,note=60)
                else:a.track().update(sample=str(sample),start=0,end=256,note=60)
                p=subprocess.Popen([str(ROOT/'build/audio_engine')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                def send(command):p.stdin.write(command+'\n');p.stdin.flush()
                def receive():
                    self.assertTrue(select.select([p.stdout],[],[],2)[0],'engine response timed out')
                    return json.loads(p.stdout.readline())
                try:
                    path=root/'midi';path.touch();send('midi_device '+json.dumps(str(path)))
                    if not midi:send('load 0 48000 '+json.dumps(str(sample)))
                    n=NativeSequence();n.status_due=float('inf');audio=type('Audio',(),{'command':staticmethod(send)})()
                    n.update(a,audio,None,1,1);self.assertEqual(receive()['status'],'ready')
                    send('device "-" 48000');self.assertEqual(receive()['status'],'idle')
                    a.button('RESTART',True);a.button('RESTART',False);n.reset(0);a.actions=[]
                    for now in (2,3,4):n.update(a,audio,None,now,now)
                    a.button('PLAY',True);a.button('PLAY',False)
                    advance_clock(a,10,10+3*a.clock_interval())
                    n.update(a,audio,None,10+3*a.clock_interval(),10+4*a.clock_interval())
                    deadline=time.monotonic()+.5;status={}
                    while time.monotonic()<deadline:
                        time.sleep(.01);send('sequence_status');status=receive()
                        if status['emitted']:break
                    self.assertEqual(status['emitted'],1,status);self.assertLess(status['tick'],96,status)
                    if midi:self.assertIn(bytes((0x90,60,100)),path.read_bytes())
                    send('quit');_,error=p.communicate(timeout=5);self.assertEqual(p.returncode,0,error)
                finally:
                    if p.poll() is None:p.kill();p.communicate()
