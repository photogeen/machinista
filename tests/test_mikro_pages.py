import copy
import unittest
from tests import test_fokus_v2 as fixtures
from app.mikro_pages import position,marker
from app.control_display import control_state,control_frame
from app.ni_display import frame

class MikroPageTests(unittest.TestCase):
    setUp=fixtures.FokusV2Tests.setUp
    check_pixels=fixtures.FokusV2Tests.check_pixels

    def test_real_nav_pages_and_arrow_boundaries(self):
        a=self.a;a.page='SAMPLER'
        self.assertEqual(control_state(a)['pages'],(0,6))
        a.button('NAV',True);a.button('NAV RIGHT',True);a.button('NAV',False)
        self.assertEqual(a.page,'SAMPLER');self.assertEqual(control_state(a)['pages'],(1,6))
        self.assertEqual(marker(0,6),' 1/6>');self.assertEqual(marker(5,6),'<6/6 ')
        self.assertEqual(marker(0,1),' 1/1 ')
        self.check_pixels(control_frame(control_state(a)),128)

    def test_scope_and_sampling_modes_have_their_real_counts(self):
        a=self.a;a.page='PAD';a.control_level=2;self.assertEqual(position(a),(0,4))
        a.control_level=1;self.assertEqual(position(a),(0,3))
        a.page='ZONE';a.zone_page=4;self.assertEqual(position(a),(4,5));self.check_pixels(frame(a),128)
        a.page='CHOP';a.slice_mode='SPLIT';self.assertEqual(position(a),(0,1))
        a.slice_mode='DETECT';a.slice_section=1;self.assertEqual(position(a),(1,2))

    def test_rendering_nav_indicator_does_not_select_a_different_plugin(self):
        a=self.a;a.page='PARAM NAV';a.parameter_kind='PLUG-IN';a.plugin_slot=1
        before=copy.deepcopy(a.__dict__['project']);slot=a.plugin_slot
        position(a);frame(a)
        self.assertEqual(a.plugin_slot,slot);self.assertEqual(a.project,before)
