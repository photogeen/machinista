import tempfile
import threading
import unittest
from unittest.mock import Mock,patch
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.mikro_session import MikroSession


class MikroSessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=Application(self.tmp.name);self.inputs=ControllerInputs(self.a)
        self.identity=patch('app.mikro_session.model_for_path',return_value='mikro')
        self.identity.start();self.addCleanup(self.identity.stop)
        self.s=MikroSession(self.tmp.name,self.a,self.inputs,Mock(),Mock(),Mock(),Mock(),'/dev/hidraw0')
        self.streams={};self.addCleanup(self.s.close,self.streams)

    def test_absent_mikro_retries_and_retains_last_render_for_reconnect(self):
        s=self.s;s.open_device.side_effect=OSError('absent')
        s.submit(b'frame',b'leds');s.submit_leds(b'new leds');s.poll(10,self.streams)
        self.assertFalse(self.streams);self.assertEqual(s.last_frame,(b'frame',b'leds'))
        self.assertEqual(s.last_leds,b'new leds');self.assertEqual(s.next_scan,12)
        s.poll(11,self.streams);self.assertEqual(s.open_device.call_count,1)

    def test_disconnect_only_releases_mikro_and_removes_pipe(self):
        p=self.inputs;s=self.s;p.pad_on('mikro',0,100);p.pad_on('mk2',1,100)
        process=Mock();process.poll.return_value=0;s.process=process;s.output=Mock(frames=0,max_ms=0.,total_ms=0.);s.output.error=None
        self.streams[process.stdout]=b'';s.poll(10,self.streams)
        self.assertFalse(self.streams);self.assertEqual(set(p.pads),{('mk2',1)})

    def test_output_error_race_cannot_escape_into_engine_loop(self):
        s=self.s;s.output=Mock(frames=0,max_ms=0.,total_ms=0.);s.output.error=None
        s.output.submit.side_effect=OSError('USB gone');s.output.submit_leds.side_effect=OSError('USB gone')
        s.output.display_settings.side_effect=OSError('USB gone')
        s.submit(b'frame',b'led');s.submit_leds(b'led');s.display_settings(100,40)

    def test_connect_restores_cached_static_display(self):
        s=self.s;s.open_device.return_value=123
        s.submit(b'frame',b'led');s.submit_leds(b'new led')
        output=Mock(frames=0,max_ms=0.,total_ms=0.);output.error=None;process=Mock();process.poll.return_value=None
        with patch('app.mikro_session.ControllerOutput',return_value=output),patch('app.mikro_session.subprocess.Popen',return_value=process),patch('app.mikro_session.os.set_blocking'),patch('app.mikro_session.os.close'):
            s.poll(10,self.streams)
            from app.branding import boot_frame
            output.submit.assert_called_once_with(boot_frame(128),b'new led')
            output.submit_leds.assert_called_once_with(b'new led')
            s.poll(12,self.streams)
            output.submit.assert_called_with(b'frame',b'led')
            s.close(self.streams)

if __name__=='__main__':unittest.main()
