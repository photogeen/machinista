"""MUTE gates active audio, not just future sequencer events."""
import array
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import wave
from app.audio import AudioBackend
from app.model import Application
from app.layout import GROUP_BASE,MASTER

ROOT=Path(__file__).resolve().parent.parent


def encoder():
    backend=AudioBackend.__new__(AudioBackend);commands=[];backend.command=commands.append
    backend.desired=backend.recorder=backend.capture_pending=backend.native_capture=None
    backend.input_device='-';backend.routing_signature=None
    return backend,commands


def routes(command):
    parts=command.split();count=int(parts[1]);body=parts[2+count:]
    return {int(body[i]):tuple(float(v) for v in body[i+1:i+12]) for i in range(0,len(body),12)}


class ImmediateMuteTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.a=Application(tmp.name)
        self.backend,self.commands=encoder()

    def test_pad_button_gates_main_and_both_pre_sends_without_changing_faders(self):
        a=self.a;t=a.track();t.update(gain=73)
        t['routing']={'dest':'OUT 1/2','aux1_dest':'OUT 3/4','aux1_level':65,'aux1_pre':True,'aux2_dest':'MASTER','aux2_level':37,'aux2_pre':True}
        original=copy.deepcopy(t);self.backend.routing(a.project);before=routes(self.commands[-1])[0]
        revision=a.revision;a.page='MUTE';a.pad_on(0)
        self.assertGreater(a.revision,revision)
        self.backend.routing(a.project);muted=routes(self.commands[-1])[0]
        self.assertEqual((muted[0],muted[4],muted[7]),(0,0,0))
        self.assertEqual(t['gain'],73);self.assertEqual(t['routing'],original['routing'])
        a.pad_on(0);self.backend.routing(a.project)
        self.assertEqual(routes(self.commands[-1])[0],before)

    def test_group_mute_gates_its_direct_outputs_without_muting_other_groups(self):
        a=self.a;a.track()['routing']={'dest':'OUT 3/4','aux1_dest':'MASTER','aux1_level':100,'aux1_pre':True}
        a.page='GROUP';a.mode_origins['GROUP']='MUTE';a.pad_on(12)
        self.backend.routing(a.project);r=routes(self.commands[-1])
        self.assertEqual(r[0][0],0);self.assertEqual(r[0][4],0);self.assertEqual(r[GROUP_BASE][0],0)
        self.assertGreater(r[16][0],0);self.assertGreater(r[GROUP_BASE+1][0],0);self.assertGreater(r[MASTER][0],0)

    def test_existing_cue_monitoring_exception_is_preserved(self):
        a=self.a;a.track().update(mute=True);a.project['groups'][0]['mute']=True
        for direct in (True,False):
            a.track()['routing']={'dest':'CUE' if direct else 'PARENT'}
            a.project['groups'][0]['routing']={'dest':'PARENT' if direct else 'CUE'}
            self.backend.routing(a.project);r=routes(self.commands[-1])
            self.assertGreater(r[0][0],0)
            if not direct:self.assertGreater(r[GROUP_BASE][0],0)


@unittest.skipUnless((ROOT/'build/audio_engine').exists() and Path('/usr/share/alsa/alsa.conf').exists(),'Linux native audio required')
class NativeImmediateMuteTests(unittest.TestCase):
    def test_an_already_running_sample_is_silent_from_mute_and_returns_on_unmute(self):
        for kind in ('SOUND','PREFADER','GROUP BYPASS'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);a=Application(root/'project');backend,commands=encoder()
                if kind=='PREFADER':a.track()['routing']={'aux1_dest':'MASTER','aux1_level':100,'aux1_pre':True}
                if kind=='GROUP BYPASS':a.track()['routing']={'dest':'MASTER'}
                backend.routing(a.project);initial=commands[-1]
                target=a.project['groups'][0] if kind=='GROUP BYPASS' else a.track()
                target['mute']=True;backend.routing(a.project);mute=commands[-1]
                target['mute']=False;backend.routing(a.project);unmute=commands[-1]
                left=root/'left.f32';right=root/'right.f32';out=root/'out.wav'
                left.write_bytes(array.array('f',[.25,0]*16384).tobytes())
                right.write_bytes(array.array('f',[0,.125]*16384).tobytes())
                script=initial+'\n'+f'load 0 48000 {json.dumps(str(left))}\nload 16 48000 {json.dumps(str(right))}\n'
                script+='sequence_begin\nsequence_lane 384\nsequence_event 0 1 100 0\nhit 0 1 1\nhit 16 1 1\nsequence_commit\nsequence_seek 0 1\nsequence_transport 120 1\n'
                script+=f'offline_control 2048 {json.dumps(mute)}\noffline_control 4096 {json.dumps(unmute)}\n'
                script+=f'render_start {json.dumps(str(out))} 8192 {MASTER}\nquit\n'
                result=subprocess.run([str(ROOT/'build/audio_engine'),'--offline-render'],input=script,text=True,capture_output=True,timeout=15)
                self.assertEqual(result.returncode,0,result.stderr+result.stdout)
                self.assertFalse(any(json.loads(line).get('status')=='error' for line in result.stdout.splitlines()),result.stdout)
                with wave.open(str(out),'rb') as wav:
                    self.assertEqual(wav.getnchannels(),2);data=array.array('h');data.frombytes(wav.readframes(8192))
                l=data[::2];r=data[1::2]
                self.assertGreater(min(l[512:2048]),0)
                self.assertEqual(max(abs(v) for v in l[2048:4096]),0)
                self.assertGreater(min(l[4096:7680]),0)
                self.assertGreater(min(r[512:7680]),0) # Unrelated Sound never drops.
