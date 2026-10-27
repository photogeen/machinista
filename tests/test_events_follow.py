import copy
import tempfile
import unittest
from unittest.mock import patch
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.mk2_surface import Mk2Surface
from app.mk1_session import Mk1Surface
from app.mk2_display import snapshot,leds,Mk2Renderer
from app.live_display import live_state,live_frame

class EventsFollowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=Application(self.tmp.name);self.inputs=ControllerInputs(self.a)
        self.a.double_pattern();self.a.page='PATTERN GRID';self.a.playing=True;self.a.clock_phase=400
        self.a.put_event((0,24),dict(velocity=100,probability=100))
        self.a.grid_selected={(0,24)};self.a.grid_follow=False;self.a.view_first=0

    def test_fullsize_follow_has_visible_button_highlight_led_and_immediate_catchup(self):
        a=self.a
        for surface_class in (Mk2Surface,Mk1Surface):
            s=surface_class(a,self.inputs)
            for page in ('PATTERN GRID','GRID EDIT'):
                a.page=page;a.grid_follow=False;a.view_first=0;before=copy.deepcopy(a.project);selected=set(a.grid_selected)
                self.assertEqual(s.softkeys()[2],'FOLLOW');self.assertNotIn(2,snapshot(s)['active_left'])
                with patch('app.mk2_display.led_reports',side_effect=lambda buttons,pads,groups:buttons):
                    self.assertEqual(leds(s,{})['DISPLAY 3'],25)
                    s.softkey(2)
                    self.assertTrue(a.grid_follow);self.assertEqual(a.view_first,16);self.assertIn(2,snapshot(s)['active_left'])
                    self.assertEqual(leds(s,{})['DISPLAY 3'],85)
                    s.softkey(2);self.assertFalse(a.grid_follow);self.assertEqual(a.view_first,16)
                self.assertEqual(a.project,before);self.assertEqual(a.grid_selected,selected)

    def test_edit_position_pauses_follow_and_same_button_resumes_without_losing_notes(self):
        a=self.a;s=Mk2Surface(a,self.inputs);a.grid_follow=True;a.page='GRID EDIT'
        s.rotate(5,1);self.assertFalse(a.grid_follow)
        before=copy.deepcopy(a.project);selected=set(a.grid_selected)
        s.softkey(2);self.assertTrue(a.grid_follow);self.assertEqual(a.view_first,16)
        self.assertEqual(a.project,before);self.assertEqual(a.grid_selected,selected)
        a.clock_phase=0;a.follow_pattern_grid();self.assertEqual(a.view_first,0)

    def test_mikro_grid_tool_follow_button_and_shift_shortcut_in_both_editor_pages(self):
        a=self.a;before=copy.deepcopy(a.project)
        a.button('VIEW',True);a.button('F2',True);a.button('F2',False)
        self.assertEqual(a.view_tool,'GRID');self.assertEqual(a.softkeys()[2],'FOLLOW')
        self.assertNotIn(2,a.active_softkeys())
        a.button('F3',True);a.button('F3',False)
        self.assertTrue(a.grid_follow);self.assertEqual(a.view_first,16);self.assertIn(2,a.active_softkeys())
        state=live_state(a);self.assertTrue(state['follow']);self.assertEqual(len(live_frame(state)),8192)
        a.button('VIEW',False);self.assertEqual(a.page,'PATTERN GRID')
        for page in ('PATTERN GRID','GRID EDIT'):
            a.page=page;a.grid_follow=False;a.view_first=0
            a.button('SHIFT',True);self.assertEqual(a.softkeys()[0],'FOLLOW')
            a.button('F1',True);a.button('F1',False);a.button('SHIFT',False)
            self.assertTrue(a.grid_follow);self.assertEqual(a.view_first,16)
        self.assertEqual(a.project,before)

    def test_fullsize_follow_changes_are_visible_in_rendered_frames(self):
        a=self.a;s=Mk2Surface(a,self.inputs);renderer=Mk2Renderer();self.addCleanup(renderer.close)
        a.grid_follow=False;off=renderer(snapshot(s));s.softkey(2);on=renderer(snapshot(s))
        self.assertNotEqual(off[0],on[0]);self.assertEqual(tuple(map(len,on)),(16384,16384))

    def test_follow_does_not_jump_to_an_inactive_pattern(self):
        a=self.a;a.pattern=1;a.view_first=0;s=Mk2Surface(a,self.inputs);s.softkey(2)
        self.assertTrue(a.grid_follow);self.assertEqual(a.view_first,0)

if __name__=='__main__':unittest.main()
