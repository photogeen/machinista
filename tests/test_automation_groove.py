import tempfile
import unittest
from app.model import Application,validate_project

class AutomationGrooveTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.a=Application(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def test_shift_encoder_records_interpolated_modulation_and_save_keeps_base(self):
        a=self.a;a.page='SAMPLER';a.sampler_page=1;a.sampler_field=0;a.playing=True;a.shift=True;a.clock_phase=0;a.rotate(4)
        a.clock_phase=96;a.rotate(8);self.assertEqual(a.track()['sampler']['tune'],12)
        a.shift=False;a.clock_phase=48;a.automation_tick();self.assertEqual(a.track()['sampler']['tune'],8)
        a.save();b=Application(a.root);self.assertEqual(b.track()['sampler']['tune'],0)
        self.assertEqual(len(b.project['groups'][0]['automation']),1);validate_project(b.project)
        a.automation_restore();self.assertEqual(a.track()['sampler']['tune'],0)
    def test_duplicate_double_and_clear_preserve_or_remove_modulation(self):
        a=self.a;a.page='PAD';a.control_level=2;a.playing=True;a.shift=True;a.clock_phase=0;a.rotate(1);a.shift=False
        a.double_pattern();lane=next(iter(a.project['groups'][0]['automation'].values()));self.assertIn('384',lane['points'])
        a.duplicate_pattern();self.assertTrue(any(key.startswith('1:') for key in a.project['groups'][0]['automation']))
        a.clear_automation();self.assertFalse(any(key.startswith('1:') for key in a.project['groups'][0]['automation']));validate_project(a.project)
    def test_groove_is_scoped_and_can_advance_notes(self):
        a=self.a;a.page='GROOVE';a.control_level=2;a.rotate(100)
        self.assertGreater(a.groove_position(0,0,48,384),48);self.assertEqual(a.groove_position(0,1,48,384),48)
        a.button('NAV RIGHT',True);a.button('NAV RIGHT',True);a.rotate(1)
        self.assertLess(a.groove_position(0,0,48,384),48);validate_project(a.project)
    def test_scene_perform_grid_and_retrigger(self):
        a=self.a;a.settings['perform_grid']='1/4';a.settings['scene_retrigger']='ON';a.playing=True;a.step=2;a.clock_phase=94;a.select_scene(1)
        a.clock_tick(0);self.assertEqual(a.scene,0);a.clock_tick(.1);self.assertEqual((a.scene,a.step,a.clock_phase),(1,0,0))
    def test_transport_uses_step_and_arrange_grid_without_discarding_substep(self):
        a=self.a;a.double_pattern();a.clock_phase=5;a.step=0;a.settings['arrange_grid']='1/4';a.seek_transport('TRANSPORT RIGHT');self.assertEqual(a.clock_phase,101)
        a.shift=True;a.timing()['grid']='1/32';a.seek_transport('TRANSPORT RIGHT');self.assertEqual(a.clock_phase,113)
