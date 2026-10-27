import copy
import tempfile
import unittest
from app.model import Application,validate_project
from app.audio import AudioBackend
from app.layout import ZONE_BASE


class StepKeyboardNoteTests(unittest.TestCase):
    def setUp(self):
        self.root=tempfile.TemporaryDirectory();self.addCleanup(self.root.cleanup)
        self.a=Application(self.root.name);self.a.keyboard_enabled=True;self.a.keyboard_root=0
        self.a.track().update(note=0,sample='sliced.wav',start=0,end=400)
        self.a.track()['zones']=[dict(sample='sliced.wav',start=i*100,end=(i+1)*100,
            loop_start=i*100,loop_end=(i+1)*100,
            root=i,key_lo=i,key_hi=i,vel_lo=1,vel_hi=127,gain=100) for i in range(4)]
        self.a.page='PAD'
    def play(self,slot):
        self.a.pad_on(slot);self.a.release_pad(slot)
    def step_mode(self):
        a=self.a;a.button('SHIFT',True);a.button('NOTE REPEAT',True);a.button('NOTE REPEAT',False);a.button('SHIFT',False)
        self.assertEqual(a.page,'STEP')
    def test_last_played_slice_is_stored_and_routes_to_same_zone_on_playback(self):
        a=self.a;self.play(1);self.play(3);self.play(2);self.step_mode();a.pad_on(0);a.release_pad(0)
        event=next(iter(a.event_notes().values()));self.assertEqual(event['note'],2)
        commands=[];audio=AudioBackend.__new__(AudioBackend);audio.command=commands.append
        audio.hit(0,0,100,a.track(),event['note']-a.track()['note'])
        hits=[c for c in commands if c.startswith('hit ')]
        self.assertEqual(len(hits),1);self.assertTrue(hits[0].startswith(f'hit {ZONE_BASE+2} '))
        a.save();b=Application(self.root.name);self.assertEqual(next(iter(b.event_notes().values()))['note'],2)
        validate_project(b.project)
    def test_step_edits_keep_selected_pitch_and_undo_redo(self):
        a=self.a;self.play(3);self.step_mode();a.pad_on(0);a.pad_on(1)
        self.assertEqual([e['note'] for e in a.event_notes().values()],[3,3])
        a.pad_on(0);self.assertEqual(len(a.event_notes()),1)
        a.undo_action(step=True);self.assertEqual(len(a.event_notes()),2)
        a.undo_action(redo=True,step=True);self.assertEqual(len(a.event_notes()),1)
        a.page='PAD';self.play(1);self.step_mode();a.pad_on(2)
        self.assertEqual({e['note'] for e in a.event_notes().values()},{1,3})
    def test_sounds_have_independent_selection_and_drum_hit_restores_base_note(self):
        a=self.a;self.play(2);a.pad=1;a.keyboard_root=36;self.play(5)
        self.step_mode();a.pad_on(0);self.assertEqual(next(iter(a.event_notes().values()))['note'],41)
        a.pad=0;a.pad_on(1)
        self.assertEqual(next(e['note'] for k,e in a.event_notes().items() if k[0]==0),2)
        a.keyboard_enabled=False;a.page='PAD';self.play(0);self.step_mode();a.pad_on(2)
        event=next(e for k,e in a.event_notes().items() if k[:2]==(0,48));self.assertNotIn('note',event)
    def test_new_project_or_replaced_sound_cannot_inherit_stale_keyboard_pitch(self):
        a=self.a;self.play(3);a.project_generation+=1;self.assertIsNone(a.step_input_note())
        self.play(2);a.project['groups'][0]['pads'][0]=copy.deepcopy(a.track());self.assertIsNone(a.step_input_note())
    def test_scale_chord_uses_played_root_not_last_harmony_voice(self):
        a=self.a;a.keyboard_root=36;a.performance().update(scale='MINOR',chord_mode='HARM',chord_type='1-3-5')
        self.play(2);self.assertEqual(a.step_input_note(),39)
        self.step_mode();a.pad_on(0);self.assertEqual(next(iter(a.event_notes().values()))['note'],39)
