import copy,tempfile,unittest
from app.model import Application,validate_project
from app.mk3_surface import Mk3Surface
from app.controller_inputs import ControllerInputs
from app.mk2_display import snapshot

class ChordInversions(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=Application(self.tmp.name);self.s=Mk3Surface(self.a,ControllerInputs(self.a))
        self.a.performance()['custom']={'name':'My Chords','root':60,'chords':[{'input':60,'name':'C Major','notes':[60,64,67]}]}
    def press(self,key):
        self.s.button(key,True);self.s.button(key,False)
    def test_chords_opens_preset_selection_not_learn_editor(self):
        self.s.pad_page=2;self.press('CHORDS')
        self.assertEqual(self.s.pad_page,0);self.assertIsNone(self.a.chord_learning)
        self.assertEqual(self.a.keyboard_chord_mode(),'CUSTOM')
        fields=snapshot(self.s)['fields']
        self.assertTrue(any(f and f[0]=='PRESET' for f in fields),fields)
    def test_inversions_keep_three_voices_and_update_played_notes(self):
        a=self.a;a.keyboard_enabled=True;a.performance()['chord_mode']='CUSTOM'
        self.s.pad_page=2;a.page='PAD CONFIG'
        self.press('DISPLAY 7');self.assertEqual(a.custom_notes(slot=0),[64,67,72])
        self.press('DISPLAY 6');self.assertEqual(a.custom_notes(slot=0),[60,64,67])
        self.assertEqual(len(a.chord_row()['notes']),3);validate_project(a.project)
    def test_limits_do_not_drop_or_duplicate_notes(self):
        for notes,operation in (([120,124,127],'INVERT UP'),([0,4,7],'INVERT DOWN')):
            with self.subTest(notes=notes):
                self.a.chord_row()['notes']=copy.copy(notes)
                self.a.chord_edit(operation);self.assertEqual(self.a.chord_row()['notes'],notes)

    def test_open_doubled_chords_return_exactly_after_every_up_step(self):
        for original in ([40,52,55,59,62,66],[48,57,62,64,67,71,74,79],[60,64,72],[48,64,67]):
            with self.subTest(notes=original):
                row=self.a.chord_row();row.clear();row.update(input=60,name='Open chord',notes=list(original))
                states=[list(original)]
                for _ in range(12):
                    self.a.chord_edit('INVERT UP')
                    if row['notes']==states[-1]:break
                    self.assertEqual(len(set(row['notes'])),len(original))
                    states.append(list(row['notes']))
                self.assertGreater(len(states),2)
                for expected in reversed(states[:-1]):
                    self.a.chord_edit('INVERT DOWN');self.assertEqual(row['notes'],expected)
                self.assertNotIn('inversion_base',row)
    def test_down_then_up_and_saved_map_keep_original_voicing(self):
        from app.chords import normalize
        row=self.a.chord_row();row['notes']=[36,48,52,55,59,62]
        original=copy.deepcopy(row)
        for _ in range(3):self.a.chord_edit('INVERT DOWN')
        preset=normalize(self.a.performance()['custom'])
        self.a.performance()['custom']=preset
        for _ in range(3):self.a.chord_edit('INVERT UP')
        self.assertEqual(self.a.chord_row(),original)
        validate_project(self.a.project)
    def test_voice_edit_does_not_resurrect_previous_voicing(self):
        self.a.chord_edit('INVERT UP');row=self.a.chord_row()
        row['notes']=[50,54,57]
        self.a.chord_edit('INVERT UP');self.assertEqual(row['notes'],[54,57,62])
        self.a.chord_edit('INVERT DOWN');self.assertEqual(row['notes'],[50,54,57])
