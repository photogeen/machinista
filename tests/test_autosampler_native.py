"""Actual Linux capture of MIDI-driven LV2 audio, no hardware input needed."""
import array
import json
import os
from pathlib import Path
import select
import subprocess
import tempfile
import time
import threading
import unittest
from unittest.mock import Mock
from app.model import Application
from app.audio import AudioBackend
from app.devices import AudioDevice
from app.autosampler import AutoSampler
from app.sound_library import SoundLibrary
from app.note_tokens import NoteTokens
from tests.test_autosampler import Pool
from tests.test_lv2_transport import LV2TransportTests
ROOT=Path(__file__).resolve().parents[1]

@unittest.skipUnless((ROOT/'build/audio_engine').exists() and Path('/usr/share/alsa/alsa.conf').exists(),'Linux native audio required')
class NativeAutosamplerTests(unittest.TestCase):
    def test_two_notes_recorded_by_native_engine_map_to_correct_root_and_range(self):
        LV2TransportTests.setUpClass();self.addCleanup(LV2TransportTests.tearDownClass)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);a=Application(root);a.audio=AudioDevice('fixture','Fixture','fixture',None);a.track().update(note=60,plugins=[dict(uri='urn:maschineos:test-time',kind='INSTRUMENT',controls={},bypass=False)])
            fifo=root/'paced.raw';os.mkfifo(fifo);stop=threading.Event()
            def drain():
                fd=os.open(fifo,os.O_RDWR|os.O_NONBLOCK)
                try:
                    while not stop.is_set():
                        try:data=os.read(fd,1024)
                        except BlockingIOError:data=b''
                        time.sleep(len(data)/4/48000 if data else .001)
                finally:os.close(fd)
            drain_thread=threading.Thread(target=drain,daemon=True);drain_thread.start()
            config=root/'alsa.conf';config.write_text('</usr/share/alsa/alsa.conf>\n'+f'pcm.fixture {{ type file slave.pcm "null" file "{fifo}" format "raw" }}\n')
            # A paced sink prevents null-device processing from consuming a
            # whole recording before the asynchronous MIDI note can arrive.
            env=dict(LV2TransportTests.env,ALSA_CONFIG_PATH=str(config))
            p=subprocess.Popen([str(ROOT/'build/audio_engine')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
            backend=AudioBackend.__new__(AudioBackend);backend.native_capture=None;backend.recorder=None;backend.capture_pending=None;backend.sample_rate=48000;backend.instrument_tokens=NoteTokens();backend.loaded={}
            backend.command=lambda cmd:(p.stdin.write(cmd+'\n'),p.stdin.flush())
            backend.command('plugins 0 "urn:maschineos:test-time"');backend.command('device "fixture" 48000')
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                event=json.loads(p.stdout.readline())
                if event.get('kind')=='audio' and event.get('status')=='ready':break
            auto=AutoSampler(root,a,backend,Mock(),Pool(),SoundLibrary(root));now=time.monotonic()
            auto.start(dict(name='Native Notes',source='LV2',low=48,high=60,step=12,velocities=[100],hold=.06,tail=.04,gap=.05,trim=False),now)
            try:
                deadline=now+10
                while time.monotonic()<deadline and (auto.active or auto.future):
                    now=time.monotonic();auto.tick(now)
                    if select.select([p.stdout],[],[],.002)[0]:
                        line=p.stdout.readline()
                        if line:auto.event(json.loads(line),time.monotonic())
                self.assertEqual(auto.state['state'],'DONE',auto.state)
                track=auto.library.read(auto.state['sound']);self.assertEqual([z['root'] for z in track['zones']],[48,60]);self.assertEqual([(z['key_lo'],z['key_hi']) for z in track['zones']],[(0,54),(55,127)])
                for zone in track['zones']:
                    with __import__('wave').open(zone['sample'],'rb') as wav:
                        raw=array.array('h');raw.frombytes(wav.readframes(wav.getnframes()))
                    self.assertGreater(max(raw[1::2]),int(zone['root']/1000*32767)-3)
            finally:
                p.stdin.write('quit\n');p.stdin.flush()
                try:p.communicate(timeout=3)
                except subprocess.TimeoutExpired:p.kill();p.communicate()
                stop.set();drain_thread.join(2)
