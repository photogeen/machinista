import io
import struct
import unittest
import wave
from app.wav_validation import validate_pcm


def sample(metadata=True):
    s=io.BytesIO()
    with wave.open(s,'wb') as w:w.setparams((1,2,44100,0,'NONE','NONE'));w.writeframes(b'\x24\x18'*256)
    b=s.getvalue()
    if metadata:b=b[:36]+b'smpl'+struct.pack('<I',56)+bytes(56)+b[36:];b=b[:4]+struct.pack('<I',len(b)-8)+b[8:]
    return b


class WavValidationTests(unittest.TestCase):
    def test_unsupported_encoding_exposes_parser_reason(self):
        b=bytearray(sample(False));struct.pack_into('<H',b,20,6)
        with self.assertRaisesRegex(ValueError,'unknown format: 6'):
            validate_pcm(io.BytesIO(b))
    def floating(self,values):
        data=struct.pack('<'+'f'*len(values),*values)
        chunks=b'fmt '+struct.pack('<IHHIIHH',16,3,1,48000,192000,4,32)+b'fact'+struct.pack('<II',4,len(values))+b'data'+struct.pack('<I',len(data))+data+b'smpl'+struct.pack('<I',36)+bytes(36)
        return b'RIFF'+struct.pack('<I',len(chunks)+4)+b'WAVE'+chunks
    def test_float32_converts_for_sampler_without_dropping_metadata(self):
        b=self.floating([-1,-.5,0,.5,1]);s=io.BytesIO(b)
        self.assertTrue(validate_pcm(s));converted=s.getvalue()
        self.assertEqual(len(converted),len(b));self.assertEqual(converted[-44:],b[-44:])
        with wave.open(io.BytesIO(converted)) as w:
            self.assertEqual((w.getsampwidth(),w.getframerate(),w.getnframes()),(4,48000,5))
            self.assertEqual(struct.unpack('<5i',w.readframes(5)),(-2147483648,-1073741824,0,1073741824,2147483647))
    def test_overrange_float_scales_whole_sample_without_clipping(self):
        s=io.BytesIO(self.floating([-4,-2,0,1,2,4]));details={}
        self.assertTrue(validate_pcm(s,details))
        self.assertAlmostEqual(details['gain_db'],-12.041199826559248)
        with wave.open(io.BytesIO(s.getvalue())) as w:
            self.assertEqual(struct.unpack('<6i',w.readframes(6)),(-2147483648,-1073741824,0,536870912,1073741824,2147483647))
    def test_nonfinite_float_is_rejected(self):
        for value in (float('inf'),float('-inf'),float('nan')):
            with self.assertRaisesRegex(ValueError,'non-finite'):validate_pcm(io.BytesIO(self.floating([value])))
    def test_complete_legacy_riff_256_bytes_short_repairs_only_length(self):
        correct=sample();bad=bytearray(correct);struct.pack_into('<I',bad,4,len(correct)-8-256)
        s=io.BytesIO(bad);self.assertTrue(validate_pcm(s));self.assertEqual(s.getvalue(),correct)

    def test_valid_wav_and_metadata_are_byte_exact(self):
        for metadata in (True,False):
            b=sample(metadata);s=io.BytesIO(b);self.assertFalse(validate_pcm(s));self.assertEqual(s.getvalue(),b)

    def test_readable_wav_with_trailing_nonriff_tag_is_preserved(self):
        b=sample()+b'TAG'+bytes(125);s=io.BytesIO(b)
        self.assertFalse(validate_pcm(s));self.assertEqual(s.getvalue(),b)

    def test_missing_audio_and_damaged_chunks_never_repaired(self):
        b=bytearray(sample());struct.pack_into('<I',b,4,len(b)-8-256)
        for invalid in (b[:-1],b[:-100],b+b'garbage',b[:50]):
            s=io.BytesIO(invalid)
            with self.assertRaises(ValueError):validate_pcm(s)
            self.assertEqual(s.getvalue(),invalid)

    def test_fmt_and_single_data_are_required_before_repair(self):
        b=bytearray(sample());struct.pack_into('<I',b,4,4)
        duplicate=b+b'data'+struct.pack('<I',2)+b'xx'
        for invalid in (duplicate, b[:12]+b'data'+struct.pack('<I',2)+b'xx'):
            with self.assertRaises(ValueError):validate_pcm(io.BytesIO(invalid))

    def test_broken_declared_chunk_yields_readable_error_not_runtimeerror(self):
        b=bytearray(sample(False));b[36:40]=b'JUNK'
        with self.assertRaisesRegex(ValueError,'PCM WAV'):validate_pcm(io.BytesIO(b))
