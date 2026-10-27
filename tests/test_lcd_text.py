import unittest
from app.lcd_text import display_text
from app.lcd_font import FONTS
from app.mk2_font import FONTS as FULL_FONTS
from app.fokus import Canvas
from app.ni_display import label
from app.mk2_display import text

class LcdTextTests(unittest.TestCase):
    def test_every_printable_ascii_character_has_a_glyph_in_every_face(self):
        for fonts in (FONTS,FULL_FONTS):
            for name,face in fonts.items():
                for code in range(32,127):
                    with self.subTest(font=name,character=chr(code)):
                        self.assertIn(chr(code),face)
                        rows=face[chr(code)]
                        self.assertEqual(len(rows),len(face['A']))
                        self.assertTrue(all(len(row)==len(rows[0]) for row in rows))
    def test_typical_sample_and_patch_names_remain_readable(self):
        self.assertEqual(display_text('Kick (1) / JV!'), 'Kick (1) / JV!')
        self.assertEqual(display_text('Cosmic’s “Rhödes” – 80♯'), 'Cosmic\'s "Rhodes" - 80#')
        self.assertEqual(display_text('Crème Brûlée / Æther / Straße'),'Creme Brulee / AEther / Strasse')
        self.assertNotIn('?',display_text('Piano 🎹 / 日本語'))
        self.assertEqual(display_text('DELETE SAMPLE?'),'DELETE SAMPLE?')
    def test_unknown_characters_and_accents_match_width_and_pixels(self):
        for width in (128,256):
            for original,expected in [('Rhödes (1)!','Rhodes (1)!'),('A🎹B','A B')]:
                a,b=Canvas(width),Canvas(width)
                self.assertEqual(a.text_width(original),b.text_width(expected))
                a.fitted(3,25,original,width-6);b.fitted(3,25,expected,width-6)
                self.assertEqual(a.finish(),b.finish())
        for draw,size in ((label,128),(text,256)):
            a,b=bytearray(size*64),bytearray(size*64)
            draw(a,3,25,'Rhödes (1)!');draw(b,3,25,'Rhodes (1)!')
            self.assertEqual(a,b)
    def test_parentheses_and_exclamation_do_not_render_as_question_marks(self):
        for width in (128,256):
            for character in ('(',')','!',"'",','):
                a,b=Canvas(width),Canvas(width)
                a.text(3,25,character);b.text(3,25,'?')
                self.assertNotEqual(a.finish(),b.finish())
