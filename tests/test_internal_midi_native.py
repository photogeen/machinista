"""Channel ownership and Group-instrument summing through the real offline engine."""
import array,json,os,subprocess,tempfile,unittest,wave
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];ENGINE=ROOT/'build/audio_engine'
FIXTURE=Path(os.environ.get('MACHINISTA_MIDI_CHANNEL_FIXTURE','/tmp/machinista-midi-fixture'))
@unittest.skipUnless(ENGINE.exists() and (FIXTURE/'midi-channels.lv2/fixture.so').exists(),'Linux native build and MIDI channel fixture required')
class InternalMidiNativeTests(unittest.TestCase):
    def render(self,commands):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'render.wav';script='\n'.join(['offline_rate 48000','plugins 1024 "urn:machinista:test:midi-channels"',*commands,'sequence_seek 0 1','sequence_transport 120 1 0 0','render_start '+json.dumps(str(path))+' 96000 1088 16 WAV 0 0','quit',''])
            result=subprocess.run([str(ENGINE),'--offline-render'],input=script,text=True,capture_output=True,env=dict(os.environ,LV2_PATH=str(FIXTURE)),timeout=20)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertNotIn('"status":"error"',result.stdout)
            with wave.open(str(path)) as w:data=array.array('h');data.frombytes(w.readframes(w.getnframes()))
            return [v/32768 for v in data[::2]]
    def at(self,a,time):return sum(a[round(time*48000):round(time*48000)+128])/128
    def test_same_pitch_distinct_channels_keep_independent_gates(self):
        data=self.render(['sequence_begin','sequence_lane 768','sequence_event 0 96 100 0','plugin_note_ch 1024 0 60 100 0','sequence_event 48 144 100 0','plugin_note_ch 1024 1 60 100 1','sequence_commit'])
        for time,expected in [(.1,.01),(.3,.03),(.6,.02),(1.1,0)]:self.assertAlmostEqual(self.at(data,time),expected,delta=4e-5)
    def test_channel_sustain_does_not_hold_the_other_part(self):
        control=lambda frame,cmd:f'offline_control {frame} '+json.dumps(cmd)
        data=self.render([control(0,'plugin_midi 1024 176 64 127 0'),control(35072,'plugin_midi 1024 176 64 0 0'),'sequence_begin','sequence_lane 768','sequence_event 0 48 100 0','plugin_note_ch 1024 0 60 100 0','plugin_note_ch 1024 1 60 100 1','sequence_commit'])
        self.assertAlmostEqual(self.at(data,.1),.03,delta=4e-5);self.assertAlmostEqual(self.at(data,.4),.01,delta=4e-5);self.assertAlmostEqual(self.at(data,.9),0,delta=4e-5)
    def test_group_instrument_keeps_sample_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            sample=Path(tmp)/'constant.f32';sample.write_bytes(array.array('f',[.1]*192000).tobytes())
            data=self.render(['load 0 48000 '+json.dumps(str(sample)),'sequence_begin','sequence_lane 768','sequence_event 0 384 100 0','hit 0 1 1','plugin_note_ch 1024 0 60 100 1','sequence_commit'])
        self.assertAlmostEqual(self.at(data,.1),.11,delta=4e-5)
