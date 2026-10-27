"""Release the original attack and routing, not the currently focused sound."""
import array
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import Mock
from app.audio import AudioBackend
from app.midi import MidiBackend
from app.midi_performance import MidiPerformance
from app.model import Application
from app.note_tokens import NoteTokens

ROOT=Path(__file__).resolve().parents[1]

class LiveBindingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.app=Application(self.tmp.name);self.app.keyboard_enabled=True
        self.audio=Mock();self.midi=Mock();self.live=MidiPerformance(self.app,self.audio,self.midi)

    def test_overlapping_same_pitch_releases_individual_attacks_fifo(self):
        p=self.live;p.event(0x90,(60,40));p.event(0x90,(60,100))
        first,second=[c.args[-1] for c in self.audio.hit.call_args_list]
        self.assertNotEqual(first,second);self.assertLess(second,1<<63)
        self.assertFalse(any(a=='note_off' for a,_ in self.app.actions))
        self.audio.note_off.assert_not_called()
        p.event(0x80,(60,0));self.audio.note_off.assert_called_once_with(0,0,60,first)
        p.event(0x90,(60,0));self.assertEqual(self.audio.note_off.call_args.args,(0,0,60,second))
        self.assertEqual(p.held,0);p.event(0x80,(60,0));self.assertEqual(self.audio.note_off.call_count,2)

    def test_focus_link_key_channel_changes_cannot_redirect_release(self):
        a=self.app;source=a.track();source.update(link_group=1,note=36)
        linked=a.project['groups'][0]['pads'][1];linked.update(link_group=1,note=40,source='MIDI',channel=3)
        self.live.event(0x90,(60,100));token=self.audio.hit.call_args.args[-1]
        source.update(link_group=0,note=80);linked.update(link_group=0,note=90,channel=9,source='SAMPLER')
        a.group=1;a.pad=4;self.live.event(0x80,(60,0))
        self.assertEqual([c.args for c in self.audio.note_off.call_args_list],[(0,0,60,token),(0,1,64,token)])
        self.midi.note_off.assert_called_once_with(64,3,token)

    def test_channels_have_independent_queues_and_sustain(self):
        p=self.live;p.event(0x90,(60,100));first=self.audio.hit.call_args.args[-1]
        p.event(0x91,(60,90));second=self.audio.hit.call_args.args[-1]
        p.event(0xb0,(64,127));p.event(0x80,(60,0));self.audio.note_off.assert_not_called()
        p.event(0x81,(60,0));self.audio.note_off.assert_called_once_with(0,0,60,second)
        p.event(0xb1,(64,0));self.assertEqual(p.held,1)
        p.event(0xb0,(64,0));self.assertEqual(self.audio.note_off.call_args.args,(0,0,60,first));self.assertEqual(p.held,0)

    def test_sustained_retrigger_preserves_both_tokens_until_pedal_up(self):
        p=self.live;p.event(0xb0,(64,127));p.event(0x90,(60,70));p.event(0x80,(60,0))
        p.event(0x90,(60,110));p.event(0x80,(60,0));self.assertEqual(p.held,2)
        self.audio.note_off.assert_not_called();p.event(0xb0,(64,0))
        self.assertEqual(self.audio.note_off.call_count,2);self.assertEqual(p.held,0)

    def test_actual_midi_tokens_defer_last_pitch_release(self):
        midi=MidiBackend();sent=[];midi.send=sent.append
        self.app.track().update(source='MIDI',channel=2);p=MidiPerformance(self.app,self.audio,midi)
        p.event(0x90,(60,50));p.event(0x90,(60,100));p.event(0x80,(60,0))
        self.assertEqual(sent,[bytes([0x91,60,50]),bytes([0x91,60,100])])
        p.event(0x80,(60,0));self.assertEqual(sent[-1],bytes([0x81,60,0]));self.assertFalse(midi.tokens.active)

    def test_controls_follow_saved_outputs_without_duplicate_bus_messages(self):
        a=self.app;a.track().update(source='MIDI',channel=2)
        self.live.event(0x90,(60,100));a.track()['channel']=3
        self.audio.command.reset_mock();self.midi.send.reset_mock();self.live.event(0xb0,(1,50))
        self.assertEqual([c.args[0] for c in self.audio.command.call_args_list],['plugin_midi 0 176 1 50','wheel 0 0.3937007874015748'])
        self.assertEqual({c.args[0] for c in self.midi.send.call_args_list},{bytes([0xb1,1,50]),bytes([0xb2,1,50])})

    def test_panic_project_change_and_limit_release_without_reusing_tokens(self):
        p=self.live;p.event(0x90,(60,100));old=self.audio.hit.call_args.args[-1]
        p.event(0xb0,(64,127));p.event(0x80,(60,0));p.panic();self.assertEqual(p.held,0)
        p.event(0x90,(60,100));self.assertGreater(self.audio.hit.call_args.args[-1],old)
        self.app.project_generation+=1;p.event(0x80,(60,0));self.assertEqual(p.held,0)
        p.MAX_HELD=2;p.event(0x90,(60,100));p.event(0x90,(60,100));p.event(0x90,(60,100))
        self.assertEqual(p.held,0);self.assertEqual(self.app.message,'MIDI LIVE LIMIT')
        self.assertFalse(p.bindings);self.assertFalse(p.sustained)

@unittest.skipUnless((ROOT/'build/audio_engine').exists() and Path('/usr/share/alsa/alsa.conf').exists(),'Linux native audio required')
class NativeLiveBindingsTests(unittest.TestCase):
    def test_actual_sampler_overlap_and_independent_release_at_original_bus(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);out=root/'audio.raw';conf=root/'alsa.conf';sample=root/'tone.f32'
            conf.write_text('</usr/share/alsa/alsa.conf>\n'+f'pcm.fixture {{ type file slave.pcm "null" file "{out}" format "raw" }}\n')
            sample.write_bytes(array.array('f',[.25,.25]*48000).tobytes())
            a=Application(root/'project');a.keyboard_enabled=True;a.track().update(note=60,gain=100,sampler={'type':'ADSR','attack':0,'decay':0,'sustain':100,'release':0,'vel_volume':100})
            proc=subprocess.Popen([str(ROOT/'build/audio_engine')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=dict(os.environ,ALSA_CONFIG_PATH=str(conf)))
            backend=AudioBackend.__new__(AudioBackend);backend.loaded={};backend.instrument_tokens=NoteTokens()
            backend.command=lambda c:(proc.stdin.write(c+'\n'),proc.stdin.flush())
            midi=MidiBackend();p=MidiPerformance(a,backend,midi)
            def meter():
                deadline=time.monotonic()+2
                while time.monotonic()<deadline:
                    backend.command('meter_status');event=json.loads(proc.stdout.readline())
                    if event['peak']>0:return event['peak']
                    time.sleep(.005)
                self.fail('No rendered audio')
            try:
                backend.command(f'load 0 48000 {json.dumps(str(sample))}\ndevice "fixture" 48000');self.assertEqual(json.loads(proc.stdout.readline())['status'],'ready')
                backend._params(0,a.track());backend.command('meter_source 0');p.event(0x90,(60,64));p.event(0x90,(60,127))
                self.assertGreater(meter(),.37)
                a.group=1;a.pad=5;p.event(0x80,(60,0))
                # The second sample voice must remain audible at its original bus.
                deadline=time.monotonic()+2;peak=None
                while time.monotonic()<deadline:
                    backend.command('meter_status');peak=json.loads(proc.stdout.readline())['peak']
                    if abs(peak-.25)<.001:break
                    time.sleep(.005)
                self.assertAlmostEqual(peak,.25,places=3)
                p.event(0x80,(60,0));time.sleep(.025);backend.command('meter_status');proc.stdout.readline()
                time.sleep(.025);backend.command('meter_status');self.assertEqual(json.loads(proc.stdout.readline())['peak'],0)
                backend.command('quit');_,err=proc.communicate(timeout=5);self.assertEqual(proc.returncode,0,err)
            finally:
                if proc.poll() is None:proc.kill();proc.communicate()
