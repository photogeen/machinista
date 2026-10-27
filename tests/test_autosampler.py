import copy
from concurrent.futures import Future
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock,patch
import wave
from app.model import Application
from app.devices import AudioDevice,MidiDevice
from app.autosampler import configuration,AutoSampler,finish_bundle
from app.sound_library import SoundLibrary
from app.sound_runtime import SoundRuntime,request

class Pool:
    def submit(self,fn,*args):
        f=Future()
        try:f.set_result(fn(*args))
        except Exception as e:f.set_exception(e)
        return f

class AutoSamplerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name).resolve();self.a=Application(self.root);self.a.audio=AudioDevice('test','Test','play','capture',2,4)
        self.a.track()['plugins']=[dict(uri='urn:test',kind='INSTRUMENT',controls={},bypass=False)]
        self.audio=Mock();self.audio.native_capture=None;self.audio.recorder=None;self.audio.capture_pending=None;self.audio.sample_rate=44100;self.audio.record_generation=0
        self.midi=Mock();self.midi.ports={};self.lib=SoundLibrary(self.root);self.auto=AutoSampler(self.root,self.a,self.audio,self.midi,Pool(),self.lib)
        self.config=dict(name='Auto EP',folder='Keys',tags=['sampled'],source='LV2',low=48,high=60,step=12,velocities=[64,127],hold=.1,tail=.1,gap=.05)
    def test_plan_covers_ranges_without_gaps_for_notes_and_layers(self):
        cfg,tasks=configuration(self.config);self.assertEqual(len(tasks),4);self.assertEqual(tasks[0],dict(root=48,velocity=64,vel_lo=1,vel_hi=95,key_lo=0,key_hi=54));self.assertEqual(tasks[-1]['key_hi'],127);self.assertEqual(tasks[-1]['vel_lo'],96)
        for changes in [dict(step=0),dict(low=80,high=20),dict(velocities=[0]),dict(hold=float('nan')),dict(low=0,high=127,step=1,velocities=[64,127])]:
            with self.subTest(changes=changes),self.assertRaises(ValueError):configuration(dict(self.config,**changes))
    def test_waits_for_native_recorder_then_note_on_off_tail_and_publication(self):
        self.auto.start(self.config,10);self.assertTrue(self.a.autosampling);self.auto.tick(10.3);self.assertEqual(self.auto.stage,'ARMING');self.audio.hit.assert_not_called()
        clock=10.3
        for i in range(4):
            self.auto.event(dict(kind='native_record',status='waiting',frames=0),clock);self.assertEqual(self.auto.stage,'HELD')
            self.assertEqual(self.audio.hit.call_count,i+1);self.auto.tick(clock+.11);self.assertEqual(self.auto.stage,'TAIL')
            with wave.open(str(self.auto.path),'wb') as w:w.setparams((2,2,44100,0,'NONE','none'));w.writeframes(b'\x10\x10\x10\x10'*8820)
            self.auto.event(dict(kind='native_record',status='finished',frames=8820,peak=.1),clock+.2)
            clock+=.3
            if i<3:self.auto.tick(clock)
        self.assertFalse(self.auto.active);self.assertFalse(self.a.autosampling);self.assertIsNone(self.audio.native_capture);self.auto.tick(clock)
        self.assertEqual(self.auto.state['state'],'DONE');rows=self.lib.scan()['sounds'];self.assertEqual(len(rows),1);self.assertEqual(rows[0]['zones'],4);self.assertFalse(self.auto.work.exists())
    def test_cancel_releases_note_and_never_publishes_partial_sound(self):
        self.auto.start(self.config,1);self.auto.tick(1.3);self.auto.event(dict(kind='native_record',status='waiting'),1.3);self.assertTrue(self.auto.note_on)
        self.auto.cancel();self.audio.note_off.assert_called_once();self.auto.event(dict(kind='native_record',status='finished',frames=100),1.5)
        self.assertEqual(self.auto.state['state'],'CANCELLED');self.assertEqual(self.lib.scan()['sounds'],[]);self.assertFalse(self.a.autosampling)
    def test_project_or_device_changes_cancel_and_preserve_original_track(self):
        before=copy.deepcopy(self.a.track());self.auto.start(self.config,1);self.a.revision+=1;self.auto.tick(2);self.assertEqual(self.auto.stage,'CANCELLING');self.assertEqual(self.a.track(),before)
    def test_external_midi_uses_selected_channel_and_available_physical_input(self):
        read,write=os.pipe();self.addCleanup(os.close,read);self.addCleanup(os.close,write);self.a.midi_devices=[MidiDevice('m','MIDI','fixture')];self.midi.ports={'fixture':write}
        self.auto.start(dict(self.config,source='EXTERNAL',midi_out='m',input='IN 3',channel=4),1);self.assertEqual(self.auto.source,-2002)
        self.auto.tick(1.3);self.auto.event(dict(kind='native_record',status='waiting'),1.3);self.assertEqual(os.read(read,3),bytes([0x93,48,64]));self.auto.cancel();self.assertEqual(os.read(read,3),bytes([0x83,48,0]))
        self.auto.event(dict(kind='native_record',status='finished',frames=0),1.4)
    def test_all_silent_recordings_are_not_published(self):
        work=self.root/'samples/take';work.mkdir();p=work/'silent.wav'
        with wave.open(str(p),'wb') as w:w.setparams((2,2,44100,0,'NONE','none'));w.writeframes(bytes(400))
        cfg,tasks=configuration(dict(self.config,low=60,high=60,velocities=[100]))
        with self.assertRaises(ValueError):finish_bundle(self.lib,cfg,tasks,[p])
        self.assertEqual(self.lib.scan()['sounds'],[])

class RuntimeTests(unittest.TestCase):
    def test_same_user_socket_context_and_stale_request_cannot_change_sound(self):
        with tempfile.TemporaryDirectory(dir='/tmp',prefix='as-') as tmp:
            a=Application(tmp);audio=Mock();audio.native_capture=None;runtime=SoundRuntime(tmp,a,audio,Mock())
            try:
                runtime.poll(time.monotonic());context=request(tmp,'status');self.assertEqual(context['pad'],0);self.assertTrue(context['available'])
                import threading
                result=[]
                def send():
                    try:result.append(request(tmp,'load',id='a'*32,group=1,pad=0,generation=0,revision=0))
                    except ValueError as e:result.append(str(e))
                t=threading.Thread(target=send);t.start()
                for _ in range(100):
                    runtime.poll(time.monotonic())
                    if not t.is_alive():break
                    time.sleep(.005)
                t.join(2);self.assertEqual(a.pad,0);self.assertIn('Selected Sound changed',result[0])
            finally:runtime.close()

if __name__=='__main__':unittest.main()

class PatchRuntimeTests(unittest.TestCase):
    def test_capture_current_patch_barrier_saves_strip_without_mutating_source(self):
        import queue,shlex
        with tempfile.TemporaryDirectory(dir='/tmp',prefix='as-') as tmp:
            a=Application(tmp);a.track()['plugins']=[dict(uri='urn:own-synth',kind='INSTRUMENT',controls={'tone':.75},bypass=False)];before=copy.deepcopy(a.track())
            audio=Mock();audio.native_capture=None
            def command(text):
                parts=shlex.split(text)
                if parts[0]=='plugin_save':
                    folder=Path(parts[-1]);folder.mkdir(parents=True);(folder/'state.ttl').write_text('test state')
            audio.command=command;runtime=SoundRuntime(tmp,a,audio,Mock())
            try:
                done=queue.Queue(1);runtime.requests.put((dict(operation='save_current',group=a.group,pad=a.pad,generation=a.project_generation,revision=a.revision,name='Live patch',folder='Synths',tags=['soft']),done,time.monotonic()+4))
                runtime.poll(time.monotonic());self.assertTrue(done.get()['ok']);self.assertIsNotNone(runtime.barrier)
                runtime.event(dict(kind='state_barrier',status='ready'),time.monotonic())
                for _ in range(200):
                    runtime.poll(time.monotonic())
                    if runtime.job['state'] in ('DONE','ERROR'):break
                    time.sleep(.005)
                self.assertEqual(runtime.job['state'],'DONE',runtime.job);draft=runtime.library.draft(runtime.job['id']);self.assertEqual(draft['kind'],'LV2');self.assertEqual(a.track(),before)
            finally:runtime.close()


class RuntimeLoadTests(unittest.TestCase):
    def test_web_load_completes_with_target_and_feedback(self):
        import queue
        from app.presets import read_preset
        with tempfile.TemporaryDirectory(dir='/tmp',prefix='as-') as tmp:
            a=Application(tmp);sample=Path(tmp)/'samples/tone.wav'
            with wave.open(str(sample),'wb') as w:w.setparams((1,2,44100,0,'NONE','none'));w.writeframes(bytes(200))
            audio=Mock();audio.native_capture=None;runtime=SoundRuntime(tmp,a,audio,Mock())
            try:
                sound=runtime.library.save(dict(name='Loaded sound',zones=[dict(asset={},root=60)]),lambda ref:sample.open('rb'))
                done=queue.Queue(1);now=time.monotonic();runtime.requests.put((dict(operation='load',id=sound['id'],group=a.group,pad=a.pad,generation=a.project_generation,revision=a.revision),done,now+4));runtime.poll(now);self.assertTrue(done.get()['ok'])
                for _ in range(200):
                    runtime.poll(time.monotonic())
                    if a.actions:break
                    time.sleep(.005)
                request=next(v for k,v in a.actions if k=='preset_load');self.assertTrue(runtime.busy)
                a.finish_preset_load(request,read_preset(request['path'],'SOUND',tmp));runtime.poll(time.monotonic()+.3)
                self.assertEqual(runtime.job['state'],'LOADED');self.assertEqual(a.track()['name'],'Loaded sound');self.assertFalse(runtime.busy)
            finally:runtime.close()
