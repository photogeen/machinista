import threading
import time
import unittest
from app.controller_output import ControllerOutput
from app.model import Application
from app.sequencer_clock import advance_clock
import tempfile

class ControllerOutputTests(unittest.TestCase):
    def test_blocked_usb_does_not_block_clock_and_latest_frame_wins(self):
        started=threading.Event();release=threading.Event();sent=[]
        def send(fd,report):
            if not started.is_set():started.set();release.wait(2)
            sent.append(report)
        out=ControllerOutput(0,lambda p:[p],send,lambda *a:None)
        self.addCleanup(release.set);self.addCleanup(out.close)
        out.submit(b'first',b'led');self.assertTrue(started.wait(1))
        with tempfile.TemporaryDirectory() as root:
            a=Application(root);a.playing=True;a.project['groups'][0]['patterns'][0][0][0]=True
            deadline=0
            for i in range(8):
                out.submit(bytes([i]),b'led');deadline,overrun=advance_clock(a,deadline,i*a.clock_interval())
                self.assertFalse(overrun)
            self.assertIn(('hit',(0,0,100)),a.actions)
        release.set();out.close()
        self.assertEqual(sent,[b'led',b'first',bytes([7])])
    def test_only_changed_strips_are_sent_and_settings_are_serialized(self):
        sent=[];settings=[]
        out=ControllerOutput(0,lambda p:[p[:1],p[1:]],lambda fd,r:sent.append(r),lambda fd,*s:settings.append(s))
        out.submit(b'ab',b'led')
        deadline=time.monotonic()+1
        while out.frames<1 and time.monotonic()<deadline:time.sleep(.001)
        out.display_settings(60,39);out.submit(b'ac',b'led');out.close()
        self.assertEqual(sent,[b'led',b'a',b'b',b'c']);self.assertEqual(settings,[(60,39)])
    def test_output_error_reaches_main_loop(self):
        def fail(*a):raise OSError('disconnected')
        out=ControllerOutput(0,lambda p:[p],fail,lambda *a:None);out.submit(b'frame',b'led');out.close()
        with self.assertRaises(OSError):out.check()

    def test_play_rec_leds_update_when_lcd_budget_defers_all_frames(self):
        from app.leds import led_report,FULL,DIM
        from app.display_budget import DisplayBudget
        sent=[]
        def no_lcd(p):raise AssertionError('LCD must not render')
        out=ControllerOutput(0,no_lcd,lambda fd,r:sent.append(r),lambda *a:None)
        with tempfile.TemporaryDirectory() as root:
            a=Application(root);a.button_led_map={'PLAY':10,'REC':9}
            a.playing=a.recording=True
            self.assertFalse(DisplayBudget().available(1,1.001,True))
            out.submit_leds(led_report(a,{},1));out.close()
            self.assertEqual(len(sent),1);self.assertEqual(sent[0][11],FULL);self.assertEqual(sent[0][10],FULL)
        stopped=ControllerOutput(0,no_lcd,lambda fd,r:sent.append(r),lambda *a:None)
        a.playing=a.recording=False;stopped.submit_leds(led_report(a,{},2));stopped.close()
        self.assertEqual(sent[-1][11],DIM);self.assertEqual(sent[-1][10],DIM)
