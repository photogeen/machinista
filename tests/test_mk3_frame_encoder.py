import os,random,struct,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
from app.mk3_frame_encoder import FrameEncoder,DisplayFrame
from app.mk3_display import Mk3Renderer
from app.mk3_graphics import rgb565
from app.mk3_output import Mk3Output
from PIL import Image

class FrameEncoderTests(unittest.TestCase):
    def decoder(self,frame):
        packet=frame.packet;pos=16;pixels=bytearray()
        self.assertEqual(struct.unpack('>4H',packet[8:16]),(0,0,480,272))
        while True:
            op=packet[pos];count=int.from_bytes(packet[pos+1:pos+4],'big');pos+=4
            if op==3:break
            self.assertIn(op,(0,1));self.assertGreater(count,0)
            if op==0:pixels+=packet[pos:pos+4*count];pos+=4*count
            else:pixels+=packet[pos:pos+4]*count;pos+=4
            self.assertLessEqual(len(pixels),261120)
        self.assertEqual(packet[pos:],bytes.fromhex('40000000'))
        self.assertEqual(len(pixels),261120);return bytes(pixels)
    @unittest.skipUnless((Path(__file__).resolve().parents[1]/'build/mk3_frame_encoder').exists(),'Build mk3_frame_encoder for native display tests')
    def test_separate_process_exact_color_full_frame_and_inversion(self):
        encoder=FrameEncoder();self.addCleanup(encoder.close);rng=random.Random(428)
        samples=[bytes((255,128,0))*(480*272),bytes(rng.randrange(256) for _ in range(480*272*3))]
        for rgb in samples:
            for display in (0,1):
                for invert in (False,True):
                    encoded=encoder.encode(rgb,display,invert)
                    self.assertEqual(self.decoder(encoded),rgb565(Image.frombytes('RGB',(480,272),rgb),invert))
                    self.assertEqual(encoded.packet[2],display)
        self.assertNotEqual(encoder.process.pid,os.getpid())
    @unittest.skipUnless((Path(__file__).resolve().parents[1]/'build/mk3_frame_encoder').exists(),'Build mk3_frame_encoder for native display tests')
    def test_repeated_frames_have_bounded_size_and_process_exit_is_detected(self):
        encoder=FrameEncoder();self.addCleanup(encoder.close);rgb=bytes(480*272*3)
        for _ in range(64):self.assertEqual(len(encoder.encode(rgb,0).packet),32)
        encoder.process.kill();encoder.process.wait()
        with self.assertRaises(OSError):encoder.encode(rgb,0)
    def test_native_failure_falls_back_to_complete_frames(self):
        r=Mk3Renderer();self.addCleanup(r.close);r.encoder_tried=True;r.encoder=Mock()
        broken=r.encoder;broken.encode.side_effect=OSError('test failure')
        state=dict(page='PAD',keys=('',)*8,fields=(),title='Fallback')
        raw=r(state);frames=r.wire_frames(state)
        self.assertTrue(all(isinstance(f,DisplayFrame) for f in frames));broken.close.assert_called_once()
        self.assertEqual(tuple(self.decoder(f) for f in frames),raw)
        self.assertEqual(r.wire_frames(state),(None,None))
        state['title']='New view';frames=r.wire_frames(state)
        self.assertIsNotNone(frames[0]);self.decoder(frames[0])
    @unittest.skipUnless((Path(__file__).resolve().parents[1]/'build/mk3_frame_encoder').exists(),'Build mk3_frame_encoder for native display tests')
    def test_output_sends_complete_encoded_frames_and_skips_unchanged(self):
        output=Mk3Output.__new__(Mk3Output);output.usb=Mock();output.closing=False;output.usb_bytes=output.usb_packets=0
        packet=FrameEncoder();self.addCleanup(packet.close);frame=packet.encode(bytes(480*272*3),1)
        output.changed_frame(1,frame);output.changed_frame(1,None)
        output.usb.send.assert_called_once_with(frame.packet)
        self.assertEqual(output.usb_bytes,32)
