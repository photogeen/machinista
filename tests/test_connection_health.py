import threading
import time
import unittest
from app.connection_health import RetryGate,output_stalled,LoopWatch
from app.controller_output import ControllerOutput

class ConnectionHealthTests(unittest.TestCase):
    def test_missing_midi_device_cannot_spin_and_retries_are_bounded(self):
        gate=RetryGate();attempts=[]
        for tick in range(20000):
            now=tick/1000
            if gate.ready('missing',now):attempts.append(now);gate.failed(now)
        self.assertEqual(attempts,[0,1,3,7,15])
    def test_changed_selection_and_explicit_reset_retry_immediately(self):
        gate=RetryGate();self.assertTrue(gate.ready('a',0));gate.failed(0)
        self.assertFalse(gate.ready('a',.1));self.assertTrue(gate.ready('b',.1))
        gate.failed(.1);gate.reset();self.assertTrue(gate.ready('b',.2))
    def test_idle_output_is_not_a_stalled_operation(self):
        class Output:busy_since=None
        self.assertFalse(output_stalled(Output(),100))
        Output.busy_since=99;self.assertFalse(output_stalled(Output(),100))
        self.assertTrue(output_stalled(Output(),105))
    def test_worker_marks_inflight_usb_and_clears_after_completion(self):
        entered=threading.Event();release=threading.Event()
        def send(*args):entered.set();release.wait(2)
        worker=ControllerOutput(0,lambda p:[p],send,lambda *a:None)
        try:
            worker.submit(b'frame',b'led');self.assertTrue(entered.wait(1))
            self.assertTrue(output_stalled(worker,time.monotonic()+6))
        finally:release.set();worker.close()
        self.assertIsNone(worker.busy_since)
    def test_loop_watch_can_close_without_leaking_thread(self):
        watch=LoopWatch();watch.tick();watch.close();self.assertFalse(watch.thread.is_alive())

class ReconnectOwnershipTests(unittest.TestCase):
    def test_mikro_does_not_reopen_while_old_fd_is_owned(self):
        from unittest.mock import Mock
        import tempfile
        from app.model import Application
        from app.controller_inputs import ControllerInputs
        from app.mikro_session import MikroSession
        with tempfile.TemporaryDirectory() as root:
            app=Application(root);opener=Mock()
            session=MikroSession(root,app,ControllerInputs(app),opener,Mock(),Mock(),Mock(),'/dev/hidraw0')
            thread=Mock();thread.is_alive.return_value=True;session.cleanup=[thread]
            session.poll(10,{})
            opener.assert_not_called()
            session.close({})
    def test_mk2_does_not_reopen_while_old_fd_is_owned(self):
        from unittest.mock import Mock,patch
        import tempfile
        from app.model import Application
        from app.controller_inputs import ControllerInputs
        from app.mk2_session import Mk2Session
        with tempfile.TemporaryDirectory() as root:
            app=Application(root);session=Mk2Session(root,app,ControllerInputs(app),{})
            thread=Mock();thread.is_alive.return_value=True;session.cleanup=[thread]
            with patch('app.mk2_session.open_device') as opener:
                session.connect(10);opener.assert_not_called()
            session.close()
