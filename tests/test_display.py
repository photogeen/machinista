from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent/'tools'))
from machinista import display_pixels
from mikro_feedback import GLYPHS
from app.model import Application


class DisplayTests(unittest.TestCase):
    def test_selection_is_visible_and_moves_to_the_next_menu_row(self):
        self.assertIn('>', GLYPHS)
        with tempfile.TemporaryDirectory() as root:
            app = Application(root)
            app.button('SHIFT', True);app.button('MAIN', True);app.button('SHIFT', False)
            before = display_pixels(app)
            row = lambda pixels, index: sum(pixels[(24+index*8)*128:(31+index*8)*128])
            self.assertLess(row(before, 0), 350)
            self.assertGreater(row(before, 1), 700)
            app.rotate(1)
            after = display_pixels(app)
            self.assertGreater(row(after, 0), 700)
            self.assertLess(row(after, 1), 350)

    def test_sampling_parameter_changes_below_the_waveform(self):
        with tempfile.TemporaryDirectory() as root:
            app = Application(root)
            app.button('SAMPLING', True)
            app.page = 'SAMPLE EDIT'
            pixels = display_pixels(app)
            self.assertEqual(app.sample_field, 0)
            self.assertGreater(sum(pixels[12*128:21*128]), 700)
            app.button('NAV RIGHT', True)
            after = display_pixels(app)
            self.assertEqual(app.sample_field, 1)
            self.assertEqual(pixels[:48*128], after[:48*128])
            self.assertNotEqual(pixels[48*128:], after[48*128:])

    def test_controller_page_reports_preserve_strip_and_row_order(self):
        from mikro_feedback import frame_reports
        pixels=[0]*8192
        for y,x in ((0,0),(7,31),(8,32),(63,127)):pixels[y*128+x]=1
        reports=frame_reports(pixels)
        self.assertEqual([r[1] for r in reports],[0,32,64,96])
        self.assertEqual(reports[0][9],1);self.assertEqual(reports[0][9+31],128)
        self.assertEqual(reports[1][9+32],1);self.assertEqual(reports[3][-1],128)
        self.assertTrue(all(r[9:]==bytes([255])*256 for r in frame_reports([1]*8192)))


if __name__ == '__main__':
    unittest.main()
