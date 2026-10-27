import errno
import threading
import unittest
from app.mk2_output import Mk2Output
from app.mk2_protocol import led_reports


class Mk2OutputTests(unittest.TestCase):
    def test_render_and_usb_run_outside_caller_and_identical_frames_are_skipped(self):
        rendered=threading.Event();done=threading.Event();writes=[];threads=[]
        def render(snapshot):
            threads.append(threading.get_ident());rendered.set();return snapshot,snapshot
        def write(fd,report):
            writes.append(report)
            if len(writes)==16:done.set()
        worker=Mk2Output(3,render,write);self.addCleanup(worker.close)
        pixels=bytes(256*64);worker.submit(pixels)
        self.assertTrue(done.wait(2));self.assertEqual(len(writes),16)
        self.assertNotEqual(threads[0],threading.get_ident())
        rendered.clear();worker.submit(pixels)
        worker.close();self.assertEqual(len(writes),16);self.assertEqual(len(threads),1)

    def test_pending_frames_coalesce_and_leds_can_arrive_during_screen_writes(self):
        entered=threading.Event();release=threading.Event();latest=threading.Event();writes=[];seen=[]
        def write(fd,report):
            writes.append(report)
            if len(writes)==1:entered.set();release.wait(2)
            if report[0]==0xe1 and report[3]==56:latest.set()
        def render(snapshot):seen.append(snapshot);return bytes([snapshot])*16384,bytes(16384)
        worker=Mk2Output(3,render,write);self.addCleanup(worker.close)
        worker.submit(0);self.assertTrue(entered.wait(2))
        for value in range(1,11):worker.submit(value)
        worker.submit_leds(led_reports({'PLAY':80}));release.set()
        self.assertTrue(latest.wait(2));worker.close()
        self.assertEqual(seen,[0,10]);self.assertEqual(writes[1][0],0x82)
        self.assertIsNone(worker.error)

    def test_updates_during_render_do_not_starve_current_frame(self):
        entered=threading.Event();release=threading.Event();done=threading.Event();writes=[]
        def render(state):
            if state==0:entered.set();release.wait(2)
            return bytes([state])*16384,bytes([state])*16384
        def write(fd,report):
            writes.append(report)
            if len(writes)==16:done.set()
        worker=Mk2Output(3,render,write);self.addCleanup(worker.close)
        worker.submit(0);self.assertTrue(entered.wait(2));worker.submit(1);release.set()
        self.assertTrue(done.wait(2));worker.close()
        self.assertEqual([r[0] for r in writes[:16]],[0xe0]*8+[0xe1]*8)
        self.assertTrue(all(not any(r[9:]) for r in writes[:16]))

    def test_background_waveform_can_refresh_an_identical_snapshot(self):
        done=threading.Event();calls=[]
        class Renderer:
            needs_refresh=False
            def __call__(self,state):
                calls.append(state);self.needs_refresh=len(calls)==1
                return bytes([len(calls)>1])*16384,bytes(16384)
        def write(fd,report):
            if report[0]==0xe0 and report[3]==56 and any(report[9:]):done.set()
        worker=Mk2Output(3,Renderer(),write);self.addCleanup(worker.close)
        worker.submit(42);self.assertTrue(done.wait(2));worker.close()
        self.assertEqual(calls,[42,42])

    def test_unplug_is_contained_and_rejects_new_work(self):
        attempted=threading.Event()
        def write(fd,report):attempted.set();raise OSError(errno.ENODEV,'unplugged')
        worker=Mk2Output(3,lambda s:(s,s),write);self.addCleanup(worker.close)
        worker.submit_leds(led_reports());self.assertTrue(attempted.wait(2));worker.close()
        self.assertIsInstance(worker.error,OSError);self.assertFalse(worker.submit(bytes(16384)))

    def test_transient_nonblocking_backpressure_retries_worker_only(self):
        completed=threading.Event();calls=[]
        def write(fd,report):
            calls.append(report)
            if len(calls)==1:raise BlockingIOError(errno.EAGAIN,'busy')
            if len(calls)==4:completed.set()
        worker=Mk2Output(3,lambda s:(s,s),write);self.addCleanup(worker.close)
        worker.submit_leds(led_reports());self.assertTrue(completed.wait(2));worker.close()
        self.assertEqual(calls[0],calls[1]);self.assertIsNone(worker.error)
