"""Real sampler overlap for two physical controller sources, no hardware needed."""
import array
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.audio import AudioBackend
from app.midi import MidiBackend
from app.note_tokens import NoteTokens

ROOT=Path(__file__).resolve().parents[1]

@unittest.skipUnless((ROOT/'build/audio_engine').exists() and Path('/usr/share/alsa/alsa.conf').exists(),'Linux native audio required')
class NativeControllerTests(unittest.TestCase):
    def test_same_pad_owners_release_independent_real_sampler_voices(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);conf=root/'alsa.conf';sample=root/'tone.f32'
            conf.write_text('</usr/share/alsa/alsa.conf>\n'+f'pcm.fixture {{ type file slave.pcm "null" file "{root/"out.raw"}" format "raw" }}\n')
            sample.write_bytes(array.array('f',[.25,.25]*48000).tobytes())
            app=Application(root/'project');app.fixed_velocity=False;app.keyboard_enabled=True;app.keyboard_root=60
            app.track().update(note=60,gain=100,sampler={'type':'ADSR','attack':0,'decay':0,'sustain':100,'release':0,'vel_volume':100})
            proc=subprocess.Popen([str(ROOT/'build/audio_engine')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=dict(os.environ,ALSA_CONFIG_PATH=str(conf)))
            audio=AudioBackend.__new__(AudioBackend);audio.loaded={};audio.instrument_tokens=NoteTokens()
            audio.command=lambda c:(proc.stdin.write(c+'\n'),proc.stdin.flush())
            inputs=ControllerInputs(app);midi=MidiBackend()
            def dispatch():
                actions,app.actions=app.actions,[]
                for action,value in actions:inputs.dispatch(action,value,audio,midi)
            def peak(expected):
                deadline=time.monotonic()+2;value=None
                while time.monotonic()<deadline:
                    audio.command('meter_status');value=json.loads(proc.stdout.readline())['peak']
                    if abs(value-expected)<.001:return
                    time.sleep(.005)
                self.assertAlmostEqual(value,expected,places=3)
            try:
                audio.command(f'load 0 48000 {json.dumps(str(sample))}\ndevice "fixture" 48000')
                self.assertEqual(json.loads(proc.stdout.readline())['status'],'ready')
                audio._params(0,app.track());audio.command('meter_source 0')
                inputs.pad_on('mikro',0,64);inputs.pad_on('mk2',0,127);dispatch();peak(.25*(1+64/127))
                app.group=1;app.pad=5;inputs.pad_off('mikro',0);dispatch();peak(.25)
                inputs.disconnect('mk2');dispatch();peak(0)
                audio.command('quit');_,error=proc.communicate(timeout=5);self.assertEqual(proc.returncode,0,error)
            finally:
                if proc.poll() is None:proc.kill();proc.communicate()
