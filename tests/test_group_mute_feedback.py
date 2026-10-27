"""Whole-group mute remains visible independently of focused Sound flags."""
import copy
import unittest
from unittest.mock import patch
from tests import test_fokus_v2 as fixtures
from app.mk2_display import snapshot,leds
from app.ni_display import frame

class GroupMuteFeedbackTests(unittest.TestCase):
    setUp=fixtures.FokusV2Tests.setUp
    check_pixels=fixtures.FokusV2Tests.check_pixels

    def test_unfocused_group_toggle_changes_display_and_group_led(self):
        a=self.a;a.page='MUTE';a.group=0
        before=snapshot(self.surface);pixels=self.renderer(before)[0];micro=frame(a)
        self.surface.button('GROUP B',True);self.surface.button('GROUP B',False)
        state=snapshot(self.surface)
        self.assertEqual(a.group,0);self.assertEqual(state['group_status'][1],('B',True,False,False,False))
        self.assertEqual(sum(item[0] for item in state['pad_status']),0)
        self.assertNotEqual(pixels,self.renderer(state)[0]);self.assertNotEqual(micro,frame(a))
        group_led=leds(self.surface,{})[1]
        self.assertEqual(group_led[7:13],bytes(6));self.assertTrue(any(group_led[1:7]))
        self.surface.button('GROUP B',True);self.surface.button('GROUP B',False)
        self.assertEqual(snapshot(self.surface)['group_status'],before['group_status'])
        self.assertTrue(any(leds(self.surface,{})[1][7:13]))

    def test_selected_muted_group_is_dark_and_sounds_show_silence(self):
        a=self.a;a.project['groups'][0]['mute']=True
        for page in ('MUTE','SOLO','OUTPUT'):
            a.page=page;state=snapshot(self.surface)
            self.assertTrue(state['group_muted'])
            if page in ('MUTE','SOLO'):self.assertTrue(all(not item[2] for item in state['pad_status']))
            self.assertEqual(leds(self.surface,{})[1][1:7],bytes(6))
            for p in self.renderer(state):self.check_pixels(p,256)
        a.page='SLICE TARGET';a.slice_target_group=0
        self.assertTrue(any(leds(self.surface,{})[1][1:7]))

    def test_solo_feedback_and_other_banks_are_detached(self):
        a=self.a;a.ensure_group_bank(1);a.group_bank=1;a.group=9;a.page='SOLO'
        a.project['groups'][8]['solo']=True;a.project['groups'][9]['mute']=True
        state=snapshot(self.surface)
        self.assertEqual(state['group_status'][0],('A2',False,True,False,True))
        self.assertEqual(state['group_status'][1],('B2',True,False,True,False))
        before=copy.deepcopy(a.project)
        with patch.object(a,'group_name',side_effect=AssertionError('renderer must use snapshot')):
            for p in self.renderer(state):self.check_pixels(p,256)
        self.assertEqual(a.project,before)
        # Rendering never retains mutable group dictionaries.
        a.project['groups'][9]['mute']=False
        self.assertTrue(state['group_status'][1][1])
        self.check_pixels(frame(a),128)
