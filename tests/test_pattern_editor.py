import copy
import tempfile
import unittest
from app.model import Application,validate_project
from app.ni_display import frame


class PatternEditorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.a=Application(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def open(self):
        self.a.page='PATTERN';self.a.button('ENTER',True)
        self.assertEqual(self.a.page,'PATTERN GRID')
    def test_create_select_scroll_edit_and_return(self):
        a=self.a;self.open();a.pad_on(15);a.rotate(3);a.button('ENTER',True)
        self.assertTrue(a.grid_present(15,3));self.assertEqual(a.page,'GRID EDIT')
        a.button('NAV RIGHT',True);a.rotate(2);self.assertEqual(a.grid_pitch(15,3),53)
        a.button('NAV RIGHT',True);a.rotate(-20);self.assertEqual(a.grid_event(15,3)['velocity'],80)
        a.button('F3',True);a.button('F2',True);self.assertEqual({k[:2] for k in a.grid_selected},{(15,72)})
        p=frame(a);self.assertEqual(len(p),8192);self.assertTrue(all(p[63*128:]))
        a.button('PATTERN',True);a.button('PATTERN',False);self.assertEqual(a.page,'PATTERN')
    def test_multiselect_move_preserves_metadata_refuses_collision_and_undo(self):
        a=self.a;self.open();pattern=a.project['groups'][0]['patterns'][0]
        pattern[0][1]=pattern[1][4]=pattern[1][5]=True
        a.grid_events()['0:0:1']={'velocity':73,'probability':42,'note':60}
        a.revision+=1
        a.grid_selected={(0,24),(1,96)};a.grid_step=1;a.page='GRID EDIT'
        before=copy.deepcopy(a.project);a.rotate(1);self.assertEqual(a.project,before)
        self.assertEqual(a.message,'TARGET OCCUPIED')
        a.rotate(2);self.assertTrue(pattern[0][3]);self.assertTrue(pattern[1][6])
        self.assertEqual(a.grid_event(0,3),{'velocity':73,'probability':42,'note':60})
        a.button('SHIFT',True);a.pad_on(0);a.button('SHIFT',False)
        self.assertEqual(a.project,before)
    def test_pitch_is_persisted_validated_and_used_for_sequencer(self):
        a=self.a;self.open();a.button('ENTER',True);a.grid_field=1;a.rotate(12)
        a.save();b=Application(self.temp.name);self.assertEqual(b.grid_pitch(0,0),48)
        validate_project(b.project);b.playing=True;b.actions=[];b.tick()
        self.assertIn(('event_hit',(0,0,100,48)),b.actions)
        b.grid_events()['0:0:0']['note']=128
        with self.assertRaises(ValueError):validate_project(b.project)
    def test_note_view_adds_other_pitch_and_deletes_only_confirmed_selection(self):
        a=self.a;self.open();a.button('ENTER',True);a.button('F3',True)
        a.button('F1',True);a.button('SHIFT',True);a.rotate(1);a.button('SHIFT',False)
        a.button('ENTER',True);self.assertEqual({v['note'] for v in a.event_notes().values() if 'note' in v},{37})
        self.assertEqual(len(a.event_notes()),2);a.button('F3',True);a.grid_note-=1
        a.button('F2',True);a.button('ERASE',True);self.assertEqual(a.page,'CONFIRM')
        a.button('F2',True);self.assertTrue(a.grid_present(0,0))
        self.assertEqual([v['note'] for v in a.event_notes().values()],[37])

    def test_shift_pattern_preserves_normal_exit_and_editor_back_navigation(self):
        a=self.a;a.pinned_modes.add('PATTERN')
        a.page='PATTERN';a.mode_origins['PATTERN']='BROWSE'
        a.button('SHIFT',True);a.button('PATTERN',True)
        a.button('PATTERN',False);a.button('SHIFT',False)
        self.assertEqual(a.page,'BROWSE');self.assertIn('PATTERN',a.pinned_modes)
        for page in ('PATTERN GRID','GRID EDIT'):
            a.page=page
            a.button('SHIFT',True);a.button('PATTERN',True)
            a.button('PATTERN',False);a.button('SHIFT',False)
            self.assertEqual(a.page,'PATTERN');self.assertIn('PATTERN',a.pinned_modes)

    def test_follow_scrolls_second_bar_and_wraps_without_changing_selection(self):
        a=self.a;a.double_pattern();self.open();a.grid_selected={(0,24)}
        a.playing=True;a.clock_phase=383;a.step=15;a.clock_tick()
        self.assertEqual(a.view_first,16);self.assertEqual(a.grid_selected,{(0,24)})
        a.clock_phase=767;a.step=31;a.clock_tick();self.assertEqual(a.view_first,0)
        a.view_count=8;a.clock_phase=191;a.step=7;a.clock_tick();self.assertEqual(a.view_first,8)
        a.pattern=1;a.view_first=0;a.clock_phase=383;a.step=15;a.clock_tick();self.assertEqual(a.view_first,0)

    def test_manual_navigation_pauses_follow_and_shift_f1_resumes(self):
        a=self.a;a.double_pattern();self.open();a.playing=True;a.clock_phase=400
        a.follow_pattern_grid();self.assertEqual(a.view_first,16)
        a.rotate(1);self.assertFalse(a.grid_follow);self.assertEqual(a.grid_step,17)
        a.clock_phase=767;a.step=31;a.clock_tick();self.assertEqual(a.view_first,16)
        a.button('SHIFT',True);self.assertEqual(a.softkeys()[0],'FOLLOW')
        a.button('F1',True);a.button('SHIFT',False)
        self.assertTrue(a.grid_follow);self.assertEqual(a.view_first,0)
        a.grid_selected.clear();a.button('F2',True);self.assertFalse(a.grid_follow)
        a.page='GRID EDIT';a.grid_follow=True;a.view_first=16;a.clock_tick();self.assertEqual(a.view_first,0)

    def test_playhead_uses_tick_position_with_no_grid_or_zoom_offset(self):
        a=self.a;a.double_pattern();self.open();a.playing=True
        a.clock_phase=0;self.assertEqual(a.pattern_playhead_x(),29)
        a.clock_phase=12;self.assertEqual(a.pattern_playhead_x(),32)
        a.clock_phase=24;self.assertEqual(a.pattern_playhead_x(),35)
        a.clock_phase=384;a.follow_pattern_grid();self.assertEqual(a.pattern_playhead_x(),29)
        a.clock_phase=396;self.assertEqual(a.pattern_playhead_x(),32)
        a.view_count=8;a.follow_pattern_grid();self.assertEqual(a.pattern_playhead_x(),35)
        a.button('PLAY',True);self.assertFalse(a.playing);self.assertEqual(a.pattern_playhead_x(),35)
        self.assertEqual(a.clock_phase,396)
        a.clock_tick();self.assertEqual(a.pattern_playhead_x(),35)
        a.button('PLAY',True);a.clock_tick();self.assertGreaterEqual(a.pattern_playhead_x(),35)
        a.active_clips[a.group]=False;self.assertIsNone(a.pattern_playhead_x())
