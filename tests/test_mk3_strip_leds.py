import tempfile,unittest
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.mk3_surface import Mk3Surface
from app.mk3_session import Mk3Session,strip_leds

class StripPlayheadTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=Application(self.tmp.name);self.s=Mk3Surface(self.a,ControllerInputs(self.a))
    def position(self):
        leds=strip_leds(self.a,self.s)
        self.assertEqual(len(leds),25);self.assertEqual(leds.count(127),1)
        self.assertEqual(leds.count(0),24)
        return leds.index(127)
    def test_pattern_start_middle_end_and_wrap(self):
        length=self.a.pattern_ticks();self.a.playing=True
        for tick,expected in ((0,0),(length//2,12),(length-1,24),(length,0),(length*3+length//2,12)):
            self.a.clock_phase=tick;self.assertEqual(self.position(),expected)
    def test_pitch_mod_modes_do_not_hide_playhead_and_stop_holds(self):
        self.a.clock_phase=self.a.pattern_ticks()//2
        for mode in (None,'PITCH','MOD','NOTES','PERFORM'):
            self.s.strip_mode=mode
            for playing in (True,False):
                self.a.playing=playing;self.assertEqual(self.position(),12)
    def test_touch_override_and_release_restore_transport_position(self):
        self.a.clock_phase=self.a.pattern_ticks()-1
        for value,expected in ((1,0),(512,12),(1024,24)):
            self.s.strip_value=value;self.assertEqual(self.position(),expected)
        self.s.strip_value=0;self.assertEqual(self.position(),24)
    def test_selected_pattern_length_is_respected(self):
        self.a.clock_phase=96;self.a.pattern_ticks=lambda:384
        self.assertEqual(self.position(),6)
        self.a.pattern_ticks=lambda:768;self.assertEqual(self.position(),3)
    def test_encoded_report_changes_only_strip_when_playhead_moves(self):
        session=Mk3Session(self.tmp.name,self.a,ControllerInputs(self.a),{})
        session.palette=[(0,0,0),(127,64,0),(0,127,0),(127,0,0)]
        self.a.clock_phase=0;first=session.reports(1)
        self.a.clock_phase=self.a.pattern_ticks()-1;last=session.reports(1)
        self.assertEqual(first[0],last[0]);self.assertEqual(first[1][26:],last[1][26:])
        self.assertEqual(first[1][1:26],bytes([127]+[0]*24))
        self.assertEqual(last[1][1:26],bytes([0]*24+[127]))
