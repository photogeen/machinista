import json
from pathlib import Path
import struct
import unittest
from app.export_audio import render_export
from app.export_formats import verify_audio_export
from tests import test_export_audio as export_tests
ROOT=export_tests.ROOT


class ExportProcessingOptions(unittest.TestCase):
    setUp=export_tests.ExportTests.setUp
    request=export_tests.ExportTests.request
    def test_new_options_defaults_snapshot_and_midi_isolation(self):
        a=self.a;a.open_export();self.assertFalse(a.export_loop);self.assertFalse(a.export_normalize)
        a.export_field=6;a.rotate(1);self.assertEqual(a.export_value(),'ON')
        a.button('NAV RIGHT',True);a.rotate(1);a.button('F3',True)
        self.assertTrue(a.actions[-1][1]['normalize']);self.assertTrue(a.actions[-1][1]['loop_optimize'])
        a.export_busy=False;a.open_export('MIDI');self.assertEqual(len(a.export_fields()),4)
    def test_invalid_boolean_option_leaves_no_partial_files(self):
        for key in ('normalize','loop_optimize'):
            with self.assertRaisesRegex(ValueError,'OPTION'):render_export(self.request(**{key:1}),self.root)
        self.assertEqual(list((self.root/'exports').iterdir()),[])


@unittest.skipUnless((ROOT/'build/audio_engine').exists() and Path('/usr/share/alsa/alsa.conf').exists(),'Linux native build required')
class NativeExportProcessing(unittest.TestCase):
    setUp=export_tests.NativeExportTests.setUp
    request=export_tests.ExportTests.request
    def samples(self,path,format,frames,rate=48000):
        start=verify_audio_export(path,format,32,rate,frames)
        with path.open('rb') as stream:stream.seek(start);data=stream.read()
        return struct.unpack(('>' if format=='AIFF' else '<')+str(frames*2)+'f',data)
    def test_normalize_recovers_float_overload_and_stereo_ratio_all_formats(self):
        a=self.a;original=Path(a.track()['sample']).read_bytes()
        for pad in range(8):
            a.project['groups'][0]['pads'][pad].update(sample=a.track()['sample'],start=0,end=256,gain=100)
            a.put_event((pad,0),dict(velocity=127,probability=100,length=24,note=36+pad))
        for format in ('WAV','AIFF'):
            for bits in (16,24,32):
                with self.subTest(format=format,bits=bits):
                    destination=render_export(self.request(format=format,bits=bits,normalize=True),self.root)
                    path=destination/('Mix.wav' if format=='WAV' else 'Mix.aiff');start=verify_audio_export(path,format,bits,48000,96000)
                    with path.open('rb') as stream:stream.seek(start);data=stream.read(bits//8*2)
                    if bits==32:left,right=struct.unpack(('>' if format=='AIFF' else '<')+'ff',data);self.assertEqual(left,1);self.assertEqual(right,.5)
                    else:
                        width=bits//8;values=[int.from_bytes(data[i*width:(i+1)*width],'big' if format=='AIFF' else 'little',signed=True) for i in range(2)]
                        self.assertEqual(values[0],(1<<(bits-1))-1);self.assertAlmostEqual(values[1]/values[0],.5,places=4)
                    manifest=json.loads((destination/'Export.json').read_text());self.assertGreater(manifest['files'][0]['peak'],1);self.assertLess(manifest['files'][0]['gain'],1)
        self.assertEqual(Path(a.track()['sample']).read_bytes(),original)
    def test_tail_wrap_exact_length_metadata_and_multiple_turns(self):
        import array,wave
        a=self.a;sample=self.root/'long.wav'
        with wave.open(str(sample),'wb') as out:out.setparams((2,2,48000,0,'NONE',''));out.writeframes(array.array('h',[8192,4096]*24000).tobytes())
        a.track().update(sample=str(sample),start=0,end=24000,gain=100)
        a.put_event((0,0),None);a.put_event((0,360),dict(velocity=127,probability=100,length=24,note=36))
        for format in ('WAV','AIFF'):
            destination=render_export(self.request(format=format,bits=32,tail=1,loop_optimize=True),self.root)
            path=destination/('Mix.wav' if format=='WAV' else 'Mix.aiff');pcm=self.samples(path,format,96000)
            self.assertGreater(pcm[0],.24);self.assertGreater(pcm[90000*2],.24)
            self.assertIn(b'BPM=120.000000 BARS=1.000000',path.read_bytes())
            manifest=json.loads((destination/'Export.json').read_text());self.assertEqual((manifest['frames'],manifest['render_frames']),(96000,144000))
        # A short loop and long one-shot exercise tail spanning several loop turns.
        a.set_pattern_length(1);a.put_event((0,360),None);a.put_event((0,0),dict(velocity=127,probability=100,length=24,note=36))
        destination=render_export(self.request(bits=32,tail=1,loop_optimize=True),self.root)
        pcm=self.samples(destination/'Mix.wav','WAV',6000);self.assertGreaterEqual(max(pcm),.99)
    def test_silence_normalize_is_finite_and_cancel_processing_cleans_up(self):
        import threading
        a=self.a;a.put_event((0,0),None)
        destination=render_export(self.request(bits=32,normalize=True,loop_optimize=True,tail=0),self.root)
        self.assertTrue(all(value==0 for value in self.samples(destination/'Mix.wav','WAV',96000)))
        cancel=threading.Event()
        class Progress:
            def put(self,value):
                if value.startswith('RENDER'):cancel.set()
        with self.assertRaisesRegex(ValueError,'CANCELED'):render_export(self.request(normalize=True),self.root,cancel,Progress())
        self.assertFalse(any(path.name.startswith('.') for path in (self.root/'exports').iterdir()))
