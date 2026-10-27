"""Verify rendered audio through an ALSA file sink, without physical hardware."""
import array
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

ENGINE = Path(__file__).resolve().parent.parent/'build/audio_engine'


@unittest.skipUnless(ENGINE.exists() and Path('/usr/share/alsa/alsa.conf').exists(), 'Linux ALSA build required')
class RenderTests(unittest.TestCase):
    def render_pitch(self,pitch,trim=None,output_rate=48000):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sample = root/'sample.f32'
            sample.write_bytes(array.array('f', [0.5]*96).tobytes())
            output = root/'render.raw'
            config = root/'alsa.conf'
            config.write_text('include "/usr/share/alsa/alsa.conf"\n'  # ALSA uses angle-bracket includes below.
                              .replace('include "/usr/share/alsa/alsa.conf"', '</usr/share/alsa/alsa.conf>')+
                              f'pcm.fixture {{ type file slave.pcm "null" file "{output}" format "raw" }}\n')
            process = subprocess.Popen([str(ENGINE)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True,
                                       env=dict(os.environ, ALSA_CONFIG_PATH=str(config)))
            try:
                process.stdin.write(f'load 0 48000 {json.dumps(str(sample))}\ndevice "fixture" {output_rate}\n')
                process.stdin.flush()
                status = json.loads(process.stdout.readline())
                self.assertEqual(status['status'], 'ready')
                if trim:
                    process.stdin.write(f'load 0 48000 {json.dumps(str(sample))}\nrange 0 {trim[0]} {trim[1]}\n')
                process.stdin.write(f'hit 0 0.5 {pitch}\n')
                process.stdin.flush()
                time.sleep(0.03)
                process.stdin.write('quit\n')
                process.stdin.flush()
                stdout, stderr = process.communicate(timeout=3)
                self.assertNotIn('ready',stdout)
                self.assertEqual(process.returncode, 0, stderr)
                values = array.array('h')
                values.frombytes(output.read_bytes())
                sounding = [value for value in values if value]
                self.assertEqual(len(sounding), __import__("math").ceil(((trim[1]-trim[0]) if trim else 48)/pitch*output_rate/48000)*2)
                self.assertEqual(set(sounding), {8191})
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()

    def test_native_sampler_renders_expected_gain_and_one_shot_length(self):
        for pitch in (1,2):
            with self.subTest(pitch=pitch):
                self.render_pitch(pitch)

    def test_44100_output_resamples_48000_sample_without_pitch_or_duration_shift(self):
        self.render_pitch(1,output_rate=44100)

    def test_live_load_and_trim_preserve_output_device_and_exact_range(self):
        self.render_pitch(1,trim=(8,24))

    def test_generated_metronome_clicks_match_accent_and_level(self):
        import math
        for accent in (0,1):
            with self.subTest(accent=accent), tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);output=root/'click.raw';config=root/'alsa.conf'
                config.write_text('</usr/share/alsa/alsa.conf>\n'+f'pcm.fixture {{ type file slave.pcm "null" file "{output}" format "raw" }}\n')
                process=subprocess.Popen([str(ENGINE)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
                                         env=dict(os.environ,ALSA_CONFIG_PATH=str(config)))
                try:
                    process.stdin.write('device "fixture"\n');process.stdin.flush()
                    self.assertEqual(json.loads(process.stdout.readline())['status'],'ready')
                    process.stdin.write(f'click {accent} 0.5\n');process.stdin.flush()
                    # Wait for recorded audio, not a scheduler-dependent 30ms sleep.
                    deadline=time.monotonic()+2
                    while time.monotonic()<deadline:
                        captured=array.array('h')
                        if output.exists():
                            raw=output.read_bytes();captured.frombytes(raw[:len(raw)//2*2])
                        first=next((i for i,v in enumerate(captured) if v),None)
                        if first is not None and len(captured)>=first-2+960:break
                        time.sleep(.005)
                    else:self.fail('metronome did not finish within2s')
                    process.stdin.write('quit\n');process.stdin.flush();_,stderr=process.communicate(timeout=3)
                    self.assertEqual(process.returncode,0,stderr)
                    values=array.array('h');values.frombytes(output.read_bytes())
                    first=next(i for i,v in enumerate(values) if v)-2
                    actual=values[first:first+960]
                    frequency=1800 if accent else 1100
                    expected=[int(math.sin(2*math.pi*frequency*i/48000)*math.exp(-i/100)*0.8*0.5*32767) for i in range(480) for _ in range(2)]
                    self.assertEqual(len(actual),960)
                    self.assertLessEqual(max(abs(a-b) for a,b in zip(actual,expected)),1)
                finally:
                    if process.poll() is None:process.kill();process.communicate()

    def test_same_pitch_voice_token_off_keeps_neighbor_audible(self):
        from app.audio import AudioBackend
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);sample=root/'sample.f32';sample.write_bytes(array.array('f',[.25]*64).tobytes())
            output=root/'tokens.raw';config=root/'alsa.conf'
            config.write_text('</usr/share/alsa/alsa.conf>\n'+f'pcm.fixture {{ type file slave.pcm "null" file "{output}" format "raw" }}\n')
            p=subprocess.Popen([str(ENGINE)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=dict(os.environ,ALSA_CONFIG_PATH=str(config)))
            try:
                p.stdin.write('device "fixture" 48000\n');p.stdin.flush()
                self.assertEqual(json.loads(p.stdout.readline())['status'],'ready')
                commands=[];backend=AudioBackend.__new__(AudioBackend);backend.command=commands.append
                backend._params(0,dict(sampler=dict(type='ADSR',attack=0,decay=0,sustain=100,release=1)),dict(loop=True,loop_start=0,loop_end=32))
                p.stdin.write(f'load 0 48000 {json.dumps(str(sample))}\n'+commands[0]+'\nhit 0 .5 1 60 101\nhit 0 .25 1 60 102\n');p.stdin.flush();time.sleep(.04)
                p.stdin.write('off 0 60 101\n');p.stdin.flush();time.sleep(.04)
                p.stdin.write('off 0 60 102\n');p.stdin.flush();time.sleep(.04)
                p.stdin.write('quit\n');p.stdin.flush();_,stderr=p.communicate(timeout=3)
                self.assertEqual(p.returncode,0,stderr)
                values=array.array('h');values.frombytes(output.read_bytes())
                self.assertGreater(sum(abs(v-6143)<=1 for v in values),64)
                self.assertGreater(sum(abs(v-2047)<=1 for v in values),64)
                self.assertTrue(all(v==0 for v in values[-512:]))
            finally:
                if p.poll() is None:p.kill();p.communicate()


if __name__ == '__main__':
    unittest.main()
