import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,Mock
from app.connection_health import ReaderWatch,LoopWatch
from app.input_streams import ready_streams,bounded_lines


def heartbeat(seconds,reports=0):
    return dict(kind='reader_health',reports=reports,rejected=0,monotonic_ns=int(seconds*1e9),last_report_ns=0,pad_reports=0,last_pad_report_ns=0)


class ReaderHealthTests(unittest.TestCase):
    def test_idle_hardware_is_healthy_as_long_as_reader_runs(self):
        watch=ReaderWatch();watch.start(10)
        for now in range(10,100):
            self.assertTrue(watch.receive(heartbeat(now),now))
            self.assertFalse(watch.expired(now+.9))
        self.assertIsNone(watch.summary(100)['report_age'])

    def test_idle_scan_stopping_is_detected_even_with_fresh_process_heartbeats(self):
        watch=ReaderWatch(report_limit=5);watch.start(10)
        for now in range(10,100):
            event=heartbeat(now);event.update(pad_reports=now*750,last_pad_report_ns=int(now*1e9))
            watch.receive(event,now);self.assertFalse(watch.expired(now+.9))
        watch.receive(heartbeat(105),105)
        self.assertTrue(watch.expired(105))

    def test_live_but_stuck_reader_and_stale_pipe_backlog_are_detected(self):
        watch=ReaderWatch();watch.start(10)
        self.assertFalse(watch.expired(15));self.assertTrue(watch.expired(15.01))
        watch.receive(heartbeat(20),20);self.assertTrue(watch.expired(26))
        watch.receive(heartbeat(20),40);self.assertTrue(watch.expired(40))
        watch.stop();self.assertFalse(watch.expired(100))

    def test_events_are_not_mistaken_for_progress_and_bad_health_is_rejected(self):
        watch=ReaderWatch();self.assertFalse(watch.receive(dict(kind='pad_on'),10))
        with self.assertRaises(ValueError):watch.receive(dict(kind='reader_health'),10)

    def test_diagnostic_snapshot_is_atomic_private_and_contains_loop_age(self):
        watch=LoopWatch()
        try:
            with tempfile.TemporaryDirectory() as directory:
                watch.path=Path(directory)/'status.json';watch.publish(dict(page='SOUND'))
                watch.write_status();result=json.loads(watch.path.read_text())
                self.assertEqual(result['page'],'SOUND');self.assertGreaterEqual(result['loop_age'],0)
                self.assertEqual(watch.path.stat().st_mode&0o777,0o600)
                self.assertEqual(len(list(Path(directory).iterdir())),1)
        finally:watch.close()

    def test_deferred_pipe_events_remain_readable_without_more_input(self):
        streams={'audio':b'a\nb\nc\npartial','mikro':b'pad\n'}
        self.assertEqual(list(bounded_lines(streams,'audio',limit=1)),[b'a'])
        with patch('app.input_streams.select.select',return_value=([],[],[])) as select:
            chosen,readable=ready_streams(streams,1)
            self.assertEqual(chosen,['audio','mikro']);self.assertFalse(readable)
            self.assertEqual(select.call_args.args[-1],0)
        self.assertEqual(list(bounded_lines(streams,'mikro')),[b'pad'])
        self.assertEqual(list(bounded_lines(streams,'audio')),[b'b',b'c'])
        self.assertEqual(streams['audio'],b'partial')

    def test_expensive_event_does_not_starve_the_other_surface(self):
        streams={'audio':b'a\nb\n','mikro':b'pad\n'};clock=iter([0,.003]).__next__
        self.assertEqual(list(bounded_lines(streams,'audio',clock=clock)),[b'a'])
        self.assertEqual(streams['audio'],b'b\n')
        self.assertEqual(list(bounded_lines(streams,'mikro')),[b'pad'])

    def test_silent_mikro_process_recovers_without_releasing_mk2(self):
        from app.model import Application
        from app.controller_inputs import ControllerInputs
        from app.mikro_session import MikroSession
        with tempfile.TemporaryDirectory() as root:
            app=Application(root);inputs=ControllerInputs(app)
            session=MikroSession(root,app,inputs,Mock(),Mock(),Mock(),Mock())
            inputs.pad_on('mikro',0,100);inputs.pad_on('mk2',1,100)
            process=Mock();process.poll.return_value=None
            session.process=process;session.output=Mock(frames=0,max_ms=0.,total_ms=0.,busy_since=None,error=None)
            session.reader_watch.start(10);streams={process.stdout:b''}
            try:
                session.poll(16,streams)
                self.assertIsNone(session.process);self.assertFalse(streams)
                self.assertEqual(set(inputs.pads),{('mk2',1)})
            finally:session.close(streams)

    def test_silent_mk2_process_recovers_without_releasing_mikro(self):
        from app.model import Application
        from app.controller_inputs import ControllerInputs
        from app.mk2_session import Mk2Session
        with tempfile.TemporaryDirectory() as root:
            app=Application(root);inputs=ControllerInputs(app);session=Mk2Session(root,app,inputs,{})
            inputs.pad_on('mikro',0,100);inputs.pad_on('mk2',1,100)
            session.process=Mock();session.process.poll.return_value=None
            session.output=Mock(busy_since=None,error=None,hardware_values=None)
            session.reader_watch.start(10)
            try:
                with patch('app.mk2_session.os.read',side_effect=BlockingIOError):session.poll(16)
                self.assertIsNone(session.process);self.assertEqual(set(inputs.pads),{('mikro',0)})
            finally:session.close()
