import tempfile
import unittest
from app.model import Application,validate_project
class BankTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.a=Application(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def test_new_banks_and_empty_clip_are_independent(self):
        a=self.a;a.page='PATTERN';a.button('SHIFT',True);a.button('NAV RIGHT',True);a.button('SHIFT',False);a.pad_on(3)
        self.assertEqual(a.pattern,19);self.assertIn(19,a.project['groups'][0]['pattern_created'])
        a.page='SCENE';a.button('SHIFT',True);a.button('NAV RIGHT',True);a.button('SHIFT',False);a.pad_on(4)
        self.assertEqual(a.scene,20);self.assertFalse(any(a.active_clips));validate_project(a.project)
    def test_shorten_preserves_hidden_notes_and_extend_restores(self):
        a=self.a;a.set_pattern_length(128);a.put_note(0,100*24,{'velocity':100,'probability':100});a.set_pattern_length(16)
        self.assertNotIn((0,2400),a.notes());a.set_pattern_length(128);self.assertIn((0,2400),a.notes())
        validate_project(a.project);a.save();b=Application(self.temp.name);self.assertEqual(b.pattern_steps(),128)
    def test_scene_duplicate_shares_pattern_and_unique_copies(self):
        a=self.a;a.put_note(0,0,{'velocity':100,'probability':100});a.duplicate_scene()
        self.assertEqual(a.project['scenes'][0][0],a.project['scenes'][1][0]);a.unique_scene()
        self.assertNotEqual(a.project['scenes'][0][0],a.project['scenes'][1][0]);validate_project(a.project)
    def test_group_bank_has_independent_sounds_routes_and_clips(self):
        from app.layout import GROUP_BASE,MASTER
        from app.routing import build_graph
        a=self.a;a.page='GROUP';a.button('SHIFT',True);a.button('NAV RIGHT',True);a.button('SHIFT',False);a.pad_on(12)
        self.assertEqual(a.group,8);self.assertEqual(a.group_name(),'A2');self.assertEqual(len(a.project['groups']),16)
        self.assertFalse(a.active_clips[8]);a.project['groups'][8]['pads'][0]['gain']=55
        self.assertEqual(a.project['groups'][0]['pads'][0]['gain'],80)
        nodes,order=build_graph(a.project);self.assertIn(GROUP_BASE+8,order);self.assertIn(MASTER,order)
        validate_project(a.project);a.save();b=Application(a.root);self.assertEqual(len(b.project['groups']),16);self.assertEqual(b.project['groups'][8]['pads'][0]['gain'],55)

    def test_delete_pattern_removes_occupied_marker_and_undo_restores_it(self):
        from app.mk3_surface import Mk3Surface
        from app.controller_inputs import ControllerInputs
        from app.mk3_state import snapshot
        from app.mk3_display import Mk3Renderer
        from app.mk3_graphics import PANEL,ACCENT
        from PIL import ImageColor
        a=self.a;a.page='PATTERN';a.pad_on(2);a.message='';a.put_note(0,0,dict(velocity=100,probability=100))
        group=a.project['groups'][0];group['pattern_created'].append(3)
        surface=Mk3Surface(a,ControllerInputs(a));renderer=Mk3Renderer();self.addCleanup(renderer.close)
        before=snapshot(surface);self.assertEqual(before['tiles'][2],('3',True,True))
        self.assertEqual(renderer.draw(before)[1].getpixel((249,173)),ImageColor.getrgb(ACCENT))
        a.clear_pattern();after=snapshot(surface)
        self.assertEqual(after['tiles'][2],('3',False,True));self.assertIn(3,group['pattern_created'])
        self.assertFalse(a.notes());self.assertNotIn(2,group['pattern_created'])
        self.assertEqual(renderer.draw(after)[1].getpixel((249,173)),ImageColor.getrgb(PANEL))
        a.undo_action();self.assertIn(2,a.project['groups'][0]['pattern_created']);self.assertTrue(a.notes())
        a.undo_action(redo=True);self.assertNotIn(2,a.project['groups'][0]['pattern_created']);self.assertFalse(a.notes())
        a.save();reopened=Application(a.root);self.assertNotIn(2,reopened.project['groups'][0]['pattern_created'])
