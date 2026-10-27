"""Raw MK2 travel edits real categorical bindings without accelerating levels."""
import tempfile,unittest
from unittest.mock import patch
from app.model import Application
from app.mk2_session import Mk2Session
from app.controller_inputs import ControllerInputs
from app.mk2_encoders import quantum

class Mk2EncoderChoicesTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=Application(self.tmp.name);self.s=Mk2Session(self.tmp.name,self.a,ControllerInputs(self.a),{})
        self.addCleanup(self.s.close)

    def test_filter_ignores_small_turns_and_moves_with_32_counts(self):
        a=self.a;a.page='SAMPLER';a.sampler_page=2
        self.s.rotate_raw(5,31);self.assertNotIn('filter',a.track().get('sampler',{}))
        self.s.rotate_raw(5,1);self.assertEqual(a.track()['sampler']['filter'],'LP2')
        for _ in range(7):self.s.rotate_raw(2,1)
        self.assertNotIn('drive',a.track()['sampler'])
        self.s.rotate_raw(2,1);self.assertEqual(a.track()['sampler']['drive'],1)
        self.s.rotate_raw(5,-32);self.assertEqual(a.track()['sampler']['filter'],'OFF')

    def test_boolean_and_continuous_envelope_controls_are_distinct(self):
        a=self.a;a.page='SAMPLER';a.sampler_page=1;a.track()['sampler']={'type':'ADSR'}
        self.s.rotate_raw(3,32);self.assertTrue(a.track()['sampler']['reverse'])
        self.s.rotate_raw(5,2);self.assertNotIn('attack',a.track()['sampler'])
        self.s.rotate_raw(5,6);self.assertGreater(a.track()['sampler']['attack'],0)

    def test_dynamic_adjust_mode_discards_travel_before_numeric_tempo(self):
        a=self.a;a.page='CHOP';self.s.surface.slice_subpage=1
        fields=self.s.surface.fields();self.assertEqual(quantum(self.s.surface,fields[1]),32)
        self.s.rotate_raw(2,31)  # Incomplete AUTO half/double selection.
        cfg=dict(a.slice_options());cfg['bpm_mode']='MANUAL';a.track()['slice_options']=cfg
        self.assertEqual(quantum(self.s.surface,self.s.surface.fields()[1]),8)
        before=a.slice_bpm();self.s.rotate_raw(2,7);self.assertEqual(a.slice_bpm(),before)
        self.s.rotate_raw(2,1);self.assertEqual(a.slice_bpm(),before+1)

    def test_page_binding_and_direction_changes_discard_old_travel(self):
        a=self.a;a.page='SAMPLER';a.sampler_page=2
        self.s.rotate_raw(5,31);self.s.rotate_raw(5,-31)
        self.assertNotIn('filter',a.track().get('sampler',{}))
        self.s.rotate_raw(5,-1);self.assertEqual(a.track()['sampler']['filter'],'OFF')
        self.s.rotate_raw(5,31);a.sampler_page=1;a.track()['sampler']['type']='ADSR'
        self.s.rotate_raw(5,7);self.assertNotIn('attack',a.track()['sampler'])
        self.s.rotate_raw(5,1);self.assertGreater(a.track()['sampler']['attack'],0)

    def test_routing_and_keyboard_selectors_use_choice_travel(self):
        a=self.a;a.page='INPUT';self.s.rotate_raw(1,32)
        self.assertEqual(a.track()['routing']['input'],'EXT STEREO')
        a.page='PAD CONFIG';a.keyboard_enabled=True
        self.s.rotate_raw(2,32);self.assertEqual(a.performance()['scale'],'MAJOR')
        a.page='MIXER';a.mixer_field=2
        self.assertTrue(all(quantum(self.s.surface,f)==32 for f in self.s.surface.fields() if f))
        a.mixer_field=0;self.assertTrue(all(quantum(self.s.surface,f)==8 for f in self.s.surface.fields() if f))

    def test_small_lv2_integer_range_is_not_assumed_to_be_an_enum(self):
        from app.mk2_surface import Field
        ports=[dict(toggle=True),dict(integer=True,min=0,max=12),dict(min=0,max=1)]
        with patch.object(self.a,'plugin_controls',return_value=ports):
            self.assertEqual([quantum(self.s.surface,Field('TEST','0',(('plugin_param',i),))) for i in range(3)],[32,8,8])
