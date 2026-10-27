import math
from pathlib import Path
import struct
import unittest
from app.export_audio import render_export
from app.export_formats import export_format,verify_audio_export
from app.ni_display import frame
from tests import test_export_audio as export_tests
ROOT=export_tests.ROOT


class FormatOptionsTests(unittest.TestCase):
    setUp=export_tests.ExportTests.setUp
    request=export_tests.ExportTests.request
    # Separate menu and invalid-format tests; inherited export regressions remain in their own suite.
    def test_container_depth_menu_and_midi_independence(self):
        a=self.a;a.open_export();self.assertEqual(len(a.export_fields()),9)
        a.export_field=4;a.rotate(1);self.assertEqual(a.export_value(),'AIFF')
        a.button('NAV RIGHT',True);a.rotate(2);self.assertEqual(a.export_value(),'32 FLOAT')
        self.assertEqual(len(frame(a)),8192);a.button('F3',True)
        request=a.actions[-1][1];self.assertEqual((request['format'],request['bits']),('AIFF',32))
        a.export_busy=False;a.open_export('MIDI');self.assertEqual(len(a.export_fields()),4)
        self.assertEqual((a.export_format,a.export_bits),('AIFF',32))
    def test_invalid_options_cancel_without_publication(self):
        self.assertEqual(export_format({}),('WAV',16))
        for kw in ({'format':'MP3'},{'bits':20},{'bits':True}):
            with self.assertRaisesRegex(ValueError,'FORMAT'):render_export(self.request(**kw),self.root)
        self.assertEqual(list((self.root/'exports').iterdir()),[])


@unittest.skipUnless((ROOT/'build/audio_engine').exists() and Path('/usr/share/alsa/alsa.conf').exists(),'Linux native build required')
class NativeFormatTests(unittest.TestCase):
    setUp=export_tests.NativeExportTests.setUp
    request=export_tests.ExportTests.request
    def test_all_containers_depths_and_rates_real_render_and_precision(self):
        before=Path(self.a.track()['sample']).read_bytes()
        self.a.put_event((0,0),dict(velocity=127,probability=100,length=24,note=36))
        self.a.track()['gain']=33
        for format in ('WAV','AIFF'):
            for bits in (16,24,32):
                with self.subTest(format=format,bits=bits):
                    rate=44100 if bits==24 else 48000
                    destination=render_export(self.request(format=format,bits=bits,rate=rate),self.root)
                    path=destination/('Mix.wav' if format=='WAV' else 'Mix.aiff')
                    start=verify_audio_export(path,format,bits,rate,rate*2)
                    with path.open('rb') as file:file.seek(start);data=file.read(bits//8*2)
                    if bits==32:
                        left,right=struct.unpack(('>' if format=='AIFF' else '<')+'ff',data)
                        self.assertAlmostEqual(left,.25*.33,places=6);self.assertAlmostEqual(right,.125*.33,places=6)
                    else:
                        width=bits//8;left=int.from_bytes(data[:width],'big' if format=='AIFF' else 'little',signed=True)
                        self.assertAlmostEqual(left,.25*.33*((1<<(bits-1))-1),delta=2)
                    damaged=destination/'damaged';damaged.write_bytes(path.read_bytes()[:-1])
                    with self.assertRaises(ValueError):verify_audio_export(damaged,format,bits,rate,rate*2)
                    with self.assertRaises(ValueError):verify_audio_export(path,format,bits,rate+1,rate*2)
        self.assertEqual(Path(self.a.track()['sample']).read_bytes(),before)
    def test_float_preserves_overload_and_manifest(self):
        import json
        self.a.track()['gain']=100
        self.a.project['groups'][0]['gain']=100;self.a.project['gain']=100
        for pad in range(1,8):
            self.a.project['groups'][0]['pads'][pad].update(sample=self.a.track()['sample'],start=0,end=256,gain=100)
            self.a.put_event((pad,0),dict(velocity=127,probability=100,length=24,note=36+pad))
        for format in ('WAV','AIFF'):
            destination=render_export(self.request(format=format,bits=32),self.root)
            path=destination/('Mix.wav' if format=='WAV' else 'Mix.aiff');start=verify_audio_export(path,format,32,48000,96000)
            with path.open('rb') as file:file.seek(start);left=struct.unpack('>f' if format=='AIFF' else '<f',file.read(4))[0]
            self.assertGreater(left,1);self.assertTrue(math.isfinite(left))
            manifest=json.loads((destination/'Export.json').read_text());self.assertEqual(manifest['encoding'],'float');self.assertGreater(manifest['files'][0]['peak'],1)
