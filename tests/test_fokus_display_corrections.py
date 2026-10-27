"""Regression coverage for incorrect display state found in the Fokus audit."""
import copy
from unittest.mock import patch
from tests import test_fokus_v2 as fixtures
from app.mk2_display import snapshot
from app.controller_settings import DEVICE_PAGES
from app.preferences import PREFERENCES


import unittest
class FokusDisplayCorrectionsTests(unittest.TestCase):
    setUp=fixtures.FokusV2Tests.setUp
    check_pixels=fixtures.FokusV2Tests.check_pixels

    def test_preferences_show_and_edit_actual_values_instead_of_sound_fallback(self):
        a=self.a
        for page in ('MIDI SYNC','MIDI OFFSET','PERFORM GRID','ARRANGE GRID','RETRIGGER'):
            with self.subTest(page=page):
                a.page=page;key,default,bounds=PREFERENCES[page];a.settings[key]=default
                state=snapshot(self.surface)
                self.assertEqual(state['utility'][0],page)
                self.assertEqual(state['fields'][0][1],str(default)+(' MS' if page=='MIDI OFFSET' else ''))
                self.assertNotIn('GAIN',str(state['utility']))
                self.surface.rotate(1,1)
                expected=bounds[bounds.index(default)+1] if isinstance(default,str) else default+1
                self.assertEqual(a.settings[key],expected)
                self.assertEqual(snapshot(self.surface)['utility'][1][0],str(expected)+(' MS' if page=='MIDI OFFSET' else ''))

    def test_hardware_and_system_do_not_copy_legacy_pixels_and_use_device_local_values(self):
        a=self.a;values=a.settings['controllers']['mk2'];values.update(brightness=21,contrast_left=33,contrast_right=77,pad_sensitivity=125,pad_curve='SOFT')
        before=copy.deepcopy(a.settings)
        with patch.object(self.renderer,'legacy_frame',side_effect=AssertionError('legacy pixels must not enter dedicated layouts')):
            for page in DEVICE_PAGES+('SYSTEM',):
                a.page=page;state=snapshot(self.surface)
                if page!='SYSTEM':
                    self.assertEqual(state['hardware']['contrast_left'],33)
                    self.assertEqual(state['hardware']['contrast_right'],77)
                    self.assertEqual(state['fields'][0][1],'21')
                for pixels in self.renderer(state):self.check_pixels(pixels,256)
        self.assertEqual(a.settings,before)

    def test_first_and_fifth_note_rows_are_both_visible(self):
        a=self.a;a.page='PATTERN GRID';a.grid_step=3
        empty=snapshot(self.surface);blank=self.renderer(empty)[1]
        for pad in (0,4):a.pad=pad;a.edit_grid_event()
        a.pad=0;state=snapshot(self.surface);pixels=self.renderer(state)[1]
        self.assertEqual(len(state['grid']['rows']),5)
        for row in (0,4):
            self.assertTrue(state['grid']['rows'][row][2][3][1])
            x=36+3*212//state['grid']['columns'];y=20+row*5
            self.assertNotEqual(blank[(y+2)*256+x+2:(y+2)*256+x+5],pixels[(y+2)*256+x+2:(y+2)*256+x+5])
        # Bottom row must not cover encoder captions/values.
        self.assertTrue(any(pixels[50*256:63*256]))

    def test_pad_status_distinguishes_active_focus_held_and_silence(self):
        a=self.a
        for page in ('MUTE','SOLO','SELECT'):
            a.page=page;before=snapshot(self.surface);first=self.renderer(before)[1]
            if page=='SELECT':a.selected_pads={0,2,4}
            else:a.project['groups'][0]['pads'][2][page.lower()]=True
            a.held_pads.add(4);state=snapshot(self.surface)
            self.assertTrue(state['pad_status'][2][0]);self.assertFalse(state['pad_status'][2][1])
            self.assertTrue(state['pad_status'][0][1]);self.assertTrue(state['pad_status'][4][3])
            self.assertNotEqual(first,self.renderer(state)[1])
        before=copy.deepcopy(a.project);self.renderer(snapshot(self.surface));self.assertEqual(before,a.project)

    def test_move_target_survives_chain_render_and_encoder_edits_destination(self):
        a=self.a
        a.plugin_catalog=[dict(uri='urn:test:gain',name='Gain',kind='EFFECT',supported=True,ports=[])]
        a.track()['plugins']=[dict(uri='urn:test:gain',kind='EFFECT',bypass=False,controls={}) for _ in range(3)]
        a.page='PLUGIN MOVE';a.plugin_move_to=0
        first=self.renderer(snapshot(self.surface))[1]
        self.surface.rotate(1,2)
        state=snapshot(self.surface);self.assertEqual(state['move_target'],2)
        self.assertEqual(state['fields'][0],('TARGET SLOT','3'))
        self.assertNotEqual(first[24*256:46*256],self.renderer(state)[1][24*256:46*256])
        self.assertEqual(a.plugin_slot,0)
