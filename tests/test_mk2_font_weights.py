"""MK2 semantic typography stays bold even for full-width values/softkeys."""
import unittest
from unittest.mock import patch
from app.fokus_mk2_style import Canvas,parameters,bold_font
from app.mk2_font import FONTS
from app.lcd_font import FONTS as MIKRO_FONTS
from app.mk2_surface import Mk2Surface
from app.controller_inputs import ControllerInputs
from tools.audit.fokus_fein_cases import cases,apply
from tests import test_fokus_v2 as fixtures
from app.mk2_display import snapshot

class Mk2FontWeightTests(unittest.TestCase):
    setUp=fixtures.FokusV2Tests.setUp

    def test_record_source_full_text_is_bold_seven_rows(self):
        a=self.a;a.page='SAMPLING';a.capture_options()['source']='EXT STEREO'
        fields=snapshot(self.surface)['fields'][:4];self.assertEqual(fields[0],('source','EXT STEREO'))
        c=Canvas()
        with patch.object(c,'text',wraps=c.text) as text:parameters(c,fields)
        value=next(call for call in text.call_args_list if call.args[2]=='EXT STEREO')
        self.assertEqual(value.args[1],54);self.assertEqual(value.kwargs['font'],'bold7_compact')
        self.assertLessEqual(c.text_width('EXT STEREO','bold7_compact'),58)
        self.assertGreater(c.text_width('EXT STEREO','bold7'),58)
        self.assertNotIn('bold7_compact',MIKRO_FONTS)

    def test_all_registered_fields_and_softkeys_preserve_weight_and_height(self):
        checked=0
        for label,page,values in cases():
            with self.subTest(label=label):
                a=fixtures.fixture(self.tmp.name);a.track()['sampler']={'type':'ADSR','filter':'EQ'}
                s=Mk2Surface(a,ControllerInputs(a));apply(a,s,page,values);state=snapshot(s)
                for side in range(2):
                    c=Canvas()
                    with patch.object(c,'fitted',wraps=c.fitted) as text:
                        parameters(c,state['fields'][side*4:side*4+4])
                        for call in text.call_args_list:
                            y=call.args[1];font=call.args[4] if len(call.args)>4 else call.kwargs.get('font','regular5')
                            self.assertEqual(font,'regular5' if y==48 else bold_font(c,call.args[2],58))
                            if y==54:self.assertTrue(font.startswith('bold7'));checked+=1
                    with patch.object(c,'fitted',wraps=c.fitted) as text:
                        c.header(state['keys'][side*4:side*4+4])
                        for call in text.call_args_list:self.assertTrue(call.args[4].startswith('bold7'))
        self.assertGreater(checked,400)

    def test_compact_face_is_seven_rows_with_monospaced_digits(self):
        for char,rows in FONTS['bold7_compact'].items():
            self.assertEqual(len(rows),7,char);self.assertEqual(len({len(row) for row in rows}),1,char)
        self.assertEqual({len(FONTS['bold7_compact'][d][0]) for d in '0123456789'},{5})
        c=Canvas()
        with patch.object(c,'text',wraps=c.text) as text:parameters(c,(('START','123456789'),None,None,None))
        value=next(call for call in text.call_args_list if call.args[2]=='123456789')
        self.assertEqual(value.kwargs['font'],'bold7_compact')
