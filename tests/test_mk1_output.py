import tempfile,unittest,time
from unittest.mock import Mock
from app.mk1_session import Mk1Output
from app.mk2_protocol import led_reports

class Mk1OutputTests(unittest.TestCase):
 def test_complete_frames_are_deduplicated_and_hardware_stays_local(self):
  with tempfile.TemporaryFile() as stream:
   process=Mock();process.stdin=stream;process.poll.return_value=None
   render=Mock(return_value=(bytearray(16384),bytearray(16384)));render.needs_refresh=False
   output=Mk1Output(process,render,dict(brightness=72,contrast_left=29,contrast_right=32))
   try:
    output.submit({'page':'PAD'});output.submit_leds(led_reports({'PLAY':85},{0:(100,0,0)}))
    deadline=time.monotonic()+4
    while output.frames<1 and output.error is None and time.monotonic()<deadline:time.sleep(.01)
    self.assertIsNone(output.error);self.assertEqual(output.frames,1)
    output.submit({'page':'PAD'});time.sleep(.1);self.assertEqual(output.frames,1)
   finally:output.close()
   stream.seek(0);lines=stream.read().decode().splitlines();packets=[(int(x[0]),bytes.fromhex(x[2:])) for x in lines]
   for display in (0,1):
    frame=[p for ep,p in packets if ep==8 and len(p)>100 and p[0]//2==display]
    self.assertEqual(len(frame),22)
    self.assertEqual(sum(len(p)-(4 if i==0 else 3) for i,p in enumerate(frame)),10880)
   self.assertIn((8,bytes((0,0,3,129,37,2))),packets)
   self.assertIn((8,bytes((2,0,3,129,41,2))),packets)
   led=[p for ep,p in packets if ep==1 and p[:2]==bytes((12,30))][-1]
   self.assertEqual(led[29],91)
if __name__=='__main__':unittest.main()
