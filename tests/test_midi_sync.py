import tempfile
import unittest
from unittest.mock import Mock
from app.midi_sync import MidiClock
from app.midi_performance import MidiPerformance
from app.model import Application

class MidiSyncTests(unittest.TestCase):
    def test_external_clock_produces_96_ppq_without_duplicates(self):
        c=MidiClock();c.configure('IN');self.assertEqual(c.receive(0xfa,(),0),('start',0))
        ticks=[]
        for pulse in range(25):
            now=pulse*.02;c.receive(0xf8,(),now);ticks.extend(p for _,p in c.ticks(now+.019))
        self.assertEqual(ticks,list(range(100)));self.assertAlmostEqual(60/c.period/24,125)
        c.receive(0xfc,(),.6);self.assertEqual(c.ticks(1),[])
        self.assertEqual(c.receive(0xf2,(2,0),1),('locate',48));c.receive(0xfb,(),1);c.receive(0xf8,(),1);self.assertEqual([p for _,p in c.ticks(1.019)],[48,49,50,51])
    def test_clock_loss_and_delayed_input(self):
        c=MidiClock();c.configure('IN');c.receive(0xfa,(),0);c.receive(0xf8,(),0,10)
        self.assertEqual(c.ticks(.005),[]);self.assertEqual(c.ticks(.011)[0][1],0)
        c.ticks(1);self.assertFalse(c.running)
    def test_output_24_clocks_per_quarter_and_transport(self):
        c=MidiClock();c.configure('OUT');messages=[]
        for i in range(500):messages.extend(c.output(i/1000,True,0,120))
        self.assertEqual(messages[0],bytes([0xfa]));self.assertEqual(messages.count(bytes([0xf8])),24)
        self.assertEqual(c.output(.5,False,96,120),[bytes([0xfc])])
        restart=c.output(.6,True,96,120);self.assertEqual(restart[:2],[bytes([0xf2,4,0]),bytes([0xfb])])
    def test_sustain_release_survives_focus_change_and_cc_reaches_plugin(self):
        with tempfile.TemporaryDirectory() as root:
            a=Application(root);a.keyboard_enabled=True;audio=Mock();midi=Mock();p=MidiPerformance(a,audio,midi)
            p.event(0x90,(60,100));p.event(0xb0,(64,127));a.group=1;a.pad=4;p.event(0x80,(60,0))
            audio.note_off.assert_not_called()
            p.event(0xb0,(1,100));self.assertTrue(any('plugin_midi 0 176 1 100' in str(call) for call in audio.command.call_args_list))
            p.event(0xb0,(64,0));self.assertEqual(audio.note_off.call_args.args[:3],(0,0,60))
    def test_preferences_persist_and_pad_curves_differ(self):
        with tempfile.TemporaryDirectory() as root:
            a=Application(root);a.page='MIDI SYNC';a.rotate(2);a.page='MIDI OFFSET';a.rotate(-12)
            b=Application(root);self.assertEqual((b.settings['midi_sync'],b.settings['midi_offset']),('OUT',-12))
            b.settings['pad_curve']='SOFT';soft=b.pad_velocity(500);b.settings['pad_curve']='HARD';self.assertGreater(soft,b.pad_velocity(500))
