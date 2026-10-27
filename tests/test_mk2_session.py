import tempfile
import json
import threading
import time
import unittest
from unittest.mock import Mock,patch
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.mk2_session import Mk2Session


class Mk2SessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=Application(self.tmp.name);self.inputs=ControllerInputs(self.a)
        self.session=Mk2Session(self.tmp.name,self.a,self.inputs,{})
        self.addCleanup(self.session.close)

    def test_missing_controller_never_blocks_engine_and_retries_at_interval(self):
        self.session.connect=Mock();self.session.next_scan=20
        self.session.poll(10);self.session.connect.assert_not_called()
        self.session.poll(20);self.session.connect.assert_called_once_with(20)

    def test_unplug_releases_only_its_inputs_and_cleans_up_outside_dispatch(self):
        p=self.inputs;s=self.session
        p.pad_on('mikro',0,100);p.pad_on('mk2',1,100)
        p.button('mk2','SHIFT',True);p.button('mikro','SHIFT',True)
        entered=threading.Event();release=threading.Event()
        renderer=Mock()
        def close():entered.set();release.wait(2)
        renderer.close.side_effect=close;s.renderer=renderer
        try:
            started=time.monotonic();s.disconnect();self.assertLess(time.monotonic()-started,.1)
            self.assertTrue(entered.wait(1));self.assertTrue(self.a.shift)
            self.assertEqual(set(p.pads),{('mikro',0)})
        finally:release.set()

    def test_snapshot_failure_is_optional_controller_error(self):
        s=self.session;s.output=Mock();s.output.error=None
        with patch('app.mk2_session.snapshot',side_effect=RuntimeError('bad screen')):
            s.update(10)
        self.assertIsNone(s.output);self.assertGreater(s.next_scan,10)

    def test_malformed_input_disconnects_optional_session(self):
        s=self.session;s.process=Mock();s.process.poll.return_value=None
        s.output=Mock();s.output.error=None
        s.buffer=b'{bad json}\n'
        with patch('app.mk2_session.os.read',side_effect=BlockingIOError):s.poll(10)
        self.assertIsNone(s.process);self.assertGreater(s.next_scan,10)

    def test_encoder_backlog_combines_turn_without_crossing_input_boundaries(self):
        s=self.session;s.process=Mock();s.process.poll.return_value=None
        s.output=Mock();s.output.error=None;s.output.hardware_values=None
        events=[dict(kind='encoder',raw_control=2,value=1) for _ in range(200)]
        events += [dict(kind='encoder',raw_control=2,value=-8),
                   dict(kind='button',name='SHIFT',value=1),
                   dict(kind='encoder',raw_control=2,value=8),
                   dict(kind='pad_on',name='PAD_1',value=100),
                   dict(kind='encoder',raw_control=2,value=8),
                   dict(kind='encoder',raw_control=3,value=8)]
        s.buffer=b''.join(json.dumps(e).encode()+b'\n' for e in events)
        calls=[]
        s.rotate_raw=lambda i,d:calls.append(('encoder',i,d))
        s.surface.button=lambda k,v:calls.append(('button',k,v))
        s.inputs.pad_on=lambda *v:calls.append(('pad',*v))
        with patch('app.mk2_session.os.read',side_effect=BlockingIOError),patch('app.mk2_session.time.monotonic',return_value=10):
            s.poll(10)
        self.assertFalse(s.buffer)
        self.assertEqual(calls[:4],[('encoder',2,200),('encoder',2,-8),('button','SHIFT',True),('encoder',2,8)])
        self.assertEqual(calls[4][0],'pad')
        self.assertEqual(calls[5:],[('encoder',2,8),('encoder',3,8)])

if __name__=='__main__':unittest.main()

class Mk2EncoderResolutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=Application(self.tmp.name)
        self.s=Mk2Session(self.tmp.name,self.a,ControllerInputs(self.a),{})
        self.addCleanup(self.s.close)
        self.s.surface.rotate=Mock()

    def test_smooth_knobs_accumulate_but_master_keeps_detents(self):
        s=self.s
        for _ in range(7):s.rotate_raw(3,1)
        s.surface.rotate.assert_not_called()
        s.rotate_raw(3,1);s.surface.rotate.assert_called_once_with(3,1)
        s.rotate_raw(4,24);s.surface.rotate.assert_called_with(4,3)
        s.rotate_raw(0,-2);s.surface.rotate.assert_called_with(0,-2)

    def test_reversal_and_page_change_do_not_carry_stale_travel(self):
        s=self.s
        s.rotate_raw(3,7);s.rotate_raw(3,-8)
        s.surface.rotate.assert_called_once_with(3,-1)
        s.surface.rotate.reset_mock()
        s.rotate_raw(3,7);self.a.page='CHANNEL';s.rotate_raw(3,1)
        s.surface.rotate.assert_not_called()
        s.rotate_raw(3,7);s.surface.rotate.assert_called_once_with(3,1)
