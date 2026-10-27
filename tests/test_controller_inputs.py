import tempfile
import unittest
from app.controller_inputs import ControllerInputs
from app.model import Application


class ControllerInputsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=Application(self.tmp.name);self.a.fixed_velocity=False
        self.inputs=ControllerInputs(self.a)

    def hits(self):return [v for k,v in self.a.actions if k=='controller_hit']
    def offs(self):return [v for k,v in self.a.actions if k=='controller_off']

    def test_shared_shift_only_releases_after_last_owner(self):
        p=self.inputs;a=self.a
        p.button('mikro','SHIFT',True);p.button('mk2','SHIFT',True)
        p.button('mikro','SHIFT',False);self.assertTrue(a.shift)
        p.button('mk2','SHIFT',False);self.assertFalse(a.shift)
        p.button('mk2','SHIFT',False);self.assertFalse(a.shift)

    def test_same_pad_two_controllers_have_independent_voice_tokens(self):
        p=self.inputs;a=self.a;a.keyboard_enabled=True
        p.pad_on('mikro',0,70);p.pad_on('mk2',0,100)
        first,second=self.hits();self.assertNotEqual(first[4],second[4])
        self.assertEqual(len(a.live_notes),2)
        p.pad_off('mikro',0)
        self.assertEqual(self.offs()[0][-1],first[4]);self.assertIn(0,a.held_pads)
        self.assertEqual(len(a.live_notes),1)
        p.pad_off('mk2',0)
        self.assertEqual(self.offs()[1][-1],second[4]);self.assertNotIn(0,a.held_pads)
        self.assertFalse(a.live_notes)
        self.assertFalse(any(k=='note_off' for k,_ in a.actions))

    def test_release_keeps_original_link_pitch_and_midi_channel(self):
        a=self.a;p=self.inputs;a.keyboard_enabled=True;a.keyboard_root=60
        a.track().update(link_group=1,note=36)
        target=a.project['groups'][0]['pads'][1];target.update(link_group=1,note=40,source='MIDI',channel=3)
        p.pad_on('mk2',0,100)
        target.update(link_group=0,note=80,channel=9);a.track()['note']=90
        a.group=1;a.pad=8;p.pad_off('mk2',0)
        self.assertEqual([v[:5] for v in self.offs()],[(0,0,60,1,False),(0,1,64,3,True)])
        self.assertEqual(self.hits()[1][5]['channel'],3)

    def test_disconnect_only_releases_its_inputs_and_preserves_other_pad(self):
        p=self.inputs;a=self.a
        p.pad_on('mk2',0,80);p.pad_on('mikro',0,90)
        p.button('mk2','SHIFT',True);p.button('mikro','SHIFT',True)
        p.disconnect('mk2')
        self.assertEqual(len(self.offs()),1);self.assertTrue(a.shift);self.assertIn(0,a.held_pads)
        self.assertEqual(set(p.pads),{('mikro',0)})
        p.disconnect('mikro');self.assertFalse(a.shift);self.assertFalse(a.held_pads)

    def test_fixed_velocity_and_duplicate_reports(self):
        a=self.a;p=self.inputs;a.fixed_velocity=True;a.velocity_value=110
        p.pad_on('mk2',0,12);p.pad_on('mk2',0,12)
        self.assertEqual(len(self.hits()),1);self.assertEqual(self.hits()[0][2],110)
        p.pad_off('mk2',0);p.pad_off('mk2',0);self.assertEqual(len(self.offs()),1)

    def test_project_generation_drops_old_physical_pad_binding(self):
        p=self.inputs;a=self.a;p.pad_on('mk2',0,100)
        a.project_generation+=1;a.live_notes.clear();a.held_pads.clear();a.actions.clear()
        p.pad_off('mk2',0);self.assertFalse(a.actions)
        p.pad_on('mk2',0,100);self.assertEqual(len(self.hits()),1)

    def test_two_controller_recordings_keep_their_own_press_durations(self):
        a=self.a;p=self.inputs;a.keyboard_enabled=True;a.keyboard_root=60
        a.recording=True;a.playing=True;a.clock_phase=0;a.step=0;a.page='KEYBOARD'
        a.input_timestamp=10;p.pad_on('mikro',0,80)
        a.input_timestamp=10.1;p.pad_on('mk2',1,90)
        self.assertEqual(len(a.live_notes),2)
        a.input_timestamp=10.25;p.pad_off('mikro',0)
        a.input_timestamp=10.6;p.pad_off('mk2',1)
        by_pitch={v['note']:v for v in a.event_notes().values()}
        self.assertEqual(by_pitch[60]['length'],round(.25/a.clock_interval()))
        self.assertEqual(by_pitch[61]['length'],round(.5/a.clock_interval()))

if __name__=='__main__':unittest.main()
