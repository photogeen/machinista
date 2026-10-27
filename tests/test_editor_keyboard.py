"""Keyboard audition in Events must keep the selected instrument and edit target."""
import copy
import tempfile
import unittest
from app.controller_inputs import ControllerInputs
from app.model import Application
from app.pattern_display import pattern_state
from app.ni_display import note_name
from app.polyphony import note_id, event_key


class EditorKeyboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=Application(self.tmp.name);self.inputs=ControllerInputs(self.a)
        a=self.a;a.pad=1;a.keyboard_enabled=True;a.keyboard_root=60
        a.track().update(name='My Synth',source='SAMPLE',plugins=[{'uri':'urn:test:synth','kind':'INSTRUMENT','name':'My Synth','controls':{}}])
        a.project['groups'][0]['pads'][4]['name']='JV Part 5'
        a.open_pattern_grid()

    def play(self,slot,source='mk2'):
        self.a.actions=[];self.inputs.pad_on(source,slot,90)
        hits=[v for k,v in self.a.actions if k=='controller_hit']
        self.inputs.pad_off(source,slot)
        offs=[v for k,v in self.a.actions if k=='controller_off']
        return hits,offs

    def test_all_controllers_audition_same_synth_and_release_correct_pitch(self):
        a=self.a;before=copy.deepcopy(a.project)
        for source in ('mk1','mk2','mikro','mikro_mk2'):
            for slot in (0,4,15):
                with self.subTest(source=source,slot=slot):
                    hits,offs=self.play(slot,source)
                    self.assertEqual((a.group,a.pad,a.track()['name']),(0,1,'My Synth'))
                    self.assertEqual(a.page,'PATTERN GRID');self.assertTrue(a.grid_notes)
                    self.assertEqual(hits[0][:2],(0,1));self.assertEqual(hits[0][6],60+slot)
                    self.assertEqual(offs[0][:3],(0,1,60+slot));self.assertEqual(offs[0][-1],hits[0][4])
                    self.assertEqual(next(row[0] for row in pattern_state(a)['rows'] if row[1]),note_name(60+slot))
        self.assertEqual(a.project,before);self.assertFalse(a.event_notes());self.assertFalse(a.live_notes)

    def test_open_empty_keyboard_grid_uses_last_note_or_keyboard_root(self):
        a=self.a;self.assertTrue(a.grid_notes);self.assertEqual(a.grid_note,60)
        self.play(7);a.grid_notes=False;a.open_pattern_grid()
        self.assertTrue(a.grid_notes);self.assertEqual(a.grid_note,67)

    def test_navigate_events_opens_pitch_view_and_keeps_resume_position(self):
        a=self.a;a.page='VIEW NAV';a.view_entry='PLUGIN';a.view_origin='PATTERN GRID'
        a.grid_notes=False;a.activate_view()
        self.assertEqual(a.page,'PATTERN GRID');self.assertTrue(a.grid_notes);self.assertEqual(a.grid_note,60)
        a.grid_step=9;a.grid_note=71;a.view_entry='PATTERN GRID';a.activate_view()
        self.assertEqual((a.grid_step,a.grid_note),(9,71))

    def test_playing_does_not_modify_marked_event_or_leave_event_edit(self):
        a=self.a;event=dict(note=64,velocity=80,probability=100,_id=note_id())
        key=event_key(a.pad,0,event);a.put_event(key,event)
        a.grid_selected={key};a.grid_note=64;a.grid_voice=key
        before=copy.deepcopy(a.project)
        for page in ('PATTERN GRID','GRID EDIT'):
            a.page=page;self.play(15)
            self.assertEqual(a.page,page);self.assertEqual(a.grid_selected,{key})
            self.assertEqual(a.grid_note,64);self.assertEqual(a.grid_voice,key);self.assertEqual(a.pad,1)
        self.assertEqual(a.project,before)
        a.grid_selected.clear();a.open_pattern_grid();self.assertEqual(a.grid_note,64)

    def test_recording_writes_only_selected_sound_and_all_chord_notes(self):
        a=self.a;a.performance().update(scale='MAJOR',chord_mode='HARM',chord_type='1-3-5')
        a.playing=True;a.clock_phase=a.step=0
        before=copy.deepcopy(a.project);hits,_=self.play(1)
        self.assertEqual([v[6] for v in hits],[62,65,69]);self.assertEqual(a.project,before)
        a.recording=True;self.play(1)
        self.assertEqual({k[0] for k in a.event_notes()},{1})
        self.assertEqual({v['note'] for v in a.event_notes().values()},{62,65,69})

    def test_drum_row_selection_and_explicit_sound_selection_still_work(self):
        a=self.a;a.keyboard_enabled=False;self.play(4)
        self.assertEqual(a.pad,4)
        a.keyboard_enabled=True;a.page='PAD';a.button('SELECT',True);self.play(2)
        self.assertEqual(a.pad,2);a.button('SELECT',False)

    def test_legacy_event_page_can_audition_without_changing_sound_or_position(self):
        a=self.a;a.page='EVENT';a.event_step=7
        hits,_=self.play(4)
        self.assertEqual(a.pad,1);self.assertEqual(a.event_step,7);self.assertEqual(hits[0][6],64)

if __name__=='__main__':unittest.main()
