import tempfile
import unittest
from app.model import Application,validate_project
class PerformanceTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.a=Application(self.temp.name);self.a.performance()['root']=36;self.a.keyboard_root=36
    def tearDown(self):self.temp.cleanup()
    def test_scale_harmonizer_and_chord_set_pad_limits(self):
        a=self.a;p=a.performance();p.update(scale='MAJOR',chord_mode='HARM',chord_type='1-3-5')
        self.assertEqual(a.performance_notes(0),[36,40,43]);self.assertEqual(a.performance_notes(1),[38,41,45])
        p.update(chord_mode='SET',chord_type='MINOR 2');self.assertEqual(len(a.performance_notes(0)),4);self.assertEqual(a.performance_notes(12),[])
    def test_chord_recording_keeps_all_generated_notes(self):
        a=self.a;a.keyboard_enabled=True;a.playing=a.recording=True;a.step=a.clock_phase=0;a.performance().update(chord_mode='HARM',chord_type='MAJOR')
        a.pad_on(0);event=a.notes()[(0,0)];self.assertEqual(sorted(v['note'] for v in a.event_notes().values()),[36,40,43])
        a.actions=[];a.emit_note(0,0,event);notes=[v[3] for k,v in a.actions if k=='event_hit'];self.assertEqual(notes,[36,40,43]);a.release_pad(0)
    def test_arp_types_and_gate_generate_notes_without_transport(self):
        a=self.a;a.page='ARP';a.pad_on(0);a.pad_on(4);a.project['arp'].update(type='DOWN',octaves=2,gate=50);a.actions=[];a.repeat_tick(0)
        self.assertIn(('midi_note',(52,100,1)),a.actions);self.assertTrue(any(k=='note_gate' for k,v in a.actions));validate_project(a.project)
    def test_link_master_and_slave_have_distinct_trigger_sets(self):
        a=self.a;a.track().update(link_group=1,link_mode='MASTER');a.project['groups'][0]['pads'][3].update(link_group=1,link_mode='SLAVE')
        self.assertEqual(a.linked_sounds(0,0),[0,3]);self.assertEqual(a.linked_sounds(0,3),[3])

    def test_repeat_waits_for_transport_grid_and_does_not_restart_on_contact(self):
        a=self.a;a.page='NOTE REPEAT';a.playing=True;a.project['repeat_presets'][0]=8
        def poll(phase,pads):
            a.clock_phase=phase;a.clock_last=phase*a.clock_interval();a.repeat_pads=set(pads);a.actions=[]
            a.repeat_tick(a.clock_last)
            return [value for action,value in a.actions if action=='hit']
        self.assertEqual(poll(17,()),[])
        self.assertEqual(poll(18,(0,)),[])
        self.assertEqual(len(poll(48,(0,))),1)
        self.assertEqual(poll(49,()),[])
        self.assertEqual(poll(50,(0,1)),[])
        self.assertEqual(len(poll(96,(0,1))),2)
        self.assertEqual(poll(96,(0,1)),[])

    def test_repeat_triplet_and_dotted_share_transport_origin(self):
        a=self.a;a.page='NOTE REPEAT';a.playing=True;a.repeat_pads={0};a.project['repeat_presets'][0]=8
        for division,spacing in [('NORMAL',48),('TRIPLET',32),('DOTTED',72)]:
            with self.subTest(division=division):
                a.project['arp']['division']=division;a.repeat_grid_state=None
                for phase,expected in [(13,0),(spacing,1),(spacing+2,0),(spacing*2,1)]:
                    a.clock_phase=phase;a.clock_last=phase*a.clock_interval();a.actions=[];a.repeat_tick(a.clock_last)
                    self.assertEqual(sum(k=='hit' for k,v in a.actions),expected)

    def test_repeat_grid_skips_late_hits_and_resets_on_transport_seek(self):
        a=self.a;a.page='NOTE REPEAT';a.playing=True;a.repeat_pads={0};a.project['repeat_presets'][0]=8
        for phase,expected in [(0,1),(145,1),(220,0),(240,1),(0,1)]:
            a.clock_phase=phase;a.clock_last=phase*a.clock_interval();a.actions=[];a.repeat_tick(a.clock_last)
            self.assertEqual(sum(k=='hit' for k,v in a.actions),expected)

    def test_stopped_repeat_still_auditions_without_play(self):
        a=self.a;a.page='NOTE REPEAT';a.repeat_pads={0};a.actions=[];a.repeat_tick(0)
        self.assertTrue(any(k=='hit' for k,v in a.actions))
        a.actions=[];a.repeat_tick(.01);self.assertEqual(a.actions,[])
