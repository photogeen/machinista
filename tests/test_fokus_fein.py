"""Whole-surface layout regressions: borders, footers, overlays and dense grids."""
import copy
import unittest
from unittest.mock import patch
from tests import test_fokus_v2 as fixtures
from tools.audit.fokus_fein_cases import cases,apply
from app.mk2_display import snapshot
from app.fokus_mk2_style import Canvas,parameters,GRID_TOP
from app.ni_display import frame

class FokusFeinTests(unittest.TestCase):
    setUp=fixtures.FokusV2Tests.setUp

    def test_browser_renders_sources_folders_samples_and_empty_directory(self):
        from pathlib import Path
        import wave
        a=self.a;a.page='BROWSE'
        root=Path(self.tmp.name)/'samples';root.mkdir(exist_ok=True)
        directory=root/'Kicks';directory.mkdir()
        with wave.open(str(directory/'Kick.wav'),'wb') as sample:
            sample.setparams((1,2,44100,0,'NONE','not compressed'))
            sample.writeframes(b'\x00\x00'*256)
        empty=root/'Empty';empty.mkdir()
        for location in (None,root,directory,empty):
            with self.subTest(location=location):
                a.browser.directory=location;a.browser.index=0
                state=snapshot(self.surface)
                self.assertIn('browser',state)
                for pixels in self.renderer(state):
                    self.assertEqual(len(pixels),256*64)
                    self.assertTrue(any(pixels))

    def test_all_workspaces_subpages_and_overlays_keep_bottom_padding_and_fields(self):
        # Fresh application per case: transitions cannot hide errors by leaving
        # fields or flags from a previous fixture behind.
        from app.mk2_surface import Mk2Surface
        from app.controller_inputs import ControllerInputs
        count=0
        for label,page,values in cases():
            with self.subTest(label=label):
                a=fixtures.fixture(self.tmp.name);a.track()['sampler']={'type':'ADSR','filter':'EQ'}
                surface=Mk2Surface(a,ControllerInputs(a));apply(a,surface,page,values)
                state=snapshot(surface);before=copy.deepcopy(a.project)
                base=self.renderer.draw(state);pixels=self.renderer(state)
                for side,p in enumerate(pixels):
                    self.assertEqual(len(p),16384);self.assertLessEqual(set(p),{0,1})
                    self.assertFalse(any(p[61*256:]),'three empty bottom rows required')
                    self.assertFalse(any(p[:256]));self.assertFalse(any(p[y*256] or p[y*256+255] for y in range(64)))
                    fields=state['fields'][side*4:side*4+4]
                    if any(fields) and page not in ('MIXER','SYSTEM'):
                        expected=Canvas();parameters(expected,fields)
                        self.assertEqual(base[side][46*256:],expected.finish()[46*256:],'body/status must not overwrite encoder fields')
                        # The final name-marquee pass intentionally replaces
                        # SCALE/PRESET glyphs, but may touch only its own cell.
                        for pixel in range(46*256,64*256):
                            if p[pixel]==base[side][pixel]:continue
                            x,y=pixel%256,pixel//256
                            self.assertTrue(any(field and field[0].upper() in ('SCALE','PRESET') and
                                4+i*63<=x<62+i*63 and 54<=y<61 for i,field in enumerate(fields)))
                self.assertEqual(a.project,before);count+=1
        self.assertGreater(count,200)

    def test_status_and_automation_never_cover_parameters(self):
        a=self.a;a.page='SAMPLER';a.sampler_page=2;a.track()['sampler']={'type':'ADSR','filter':'EQ'}
        plain=self.renderer(snapshot(self.surface))
        for notice,auto in (('SAVED',False),('',True),('SAVED',True)):
            a.message=notice;self.surface.auto_locked=auto;self.surface.auto_page=a.page
            rendered=self.renderer(snapshot(self.surface))
            self.assertEqual(plain[1][46*256:],rendered[1][46*256:])
            self.assertTrue(plain[1][:46*256]!=rendered[1][:46*256])

    def test_all_five_note_rows_fit_above_footer_and_change_independently(self):
        a=self.a;a.page='PATTERN GRID';a.grid_step=3
        blank=self.renderer(snapshot(self.surface))[1]
        for row in range(5):a.put_note(row,72,dict(velocity=100,probability=100))
        state=snapshot(self.surface);filled=self.renderer(state)[1]
        for row in range(5):
            y=GRID_TOP+row*5
            self.assertNotEqual(blank[y*256:(y+5)*256],filled[y*256:(y+5)*256])
        expected=Canvas();parameters(expected,state['fields'][4:])
        self.assertEqual(filled[46*256:],expected.finish()[46*256:])

    def test_long_numeric_values_fall_back_to_complete_font_and_titles_elide(self):
        c=Canvas();calls=[]
        with patch.object(c,'text',wraps=c.text) as text:
            parameters(c,(('VERY LONG PARAMETER NAME','123456789'),None,None,None))
            calls=[call.args[2] for call in text.call_args_list]
        self.assertIn('123456789',calls)
        self.assertIn('...',next(value for value in calls if '...' in value))
        c.title('LONG PREVIOUS TITLE','123:4:1');c.title('NEW')
        fresh=Canvas();fresh.title('NEW')
        self.assertEqual(c.finish()[14*256:23*256],fresh.finish()[14*256:23*256])

    def test_mikro_pixels_and_project_do_not_depend_on_mk2_style(self):
        a=self.a;a.page='SAMPLER';before=frame(a)
        self.renderer(snapshot(self.surface))
        self.assertEqual(frame(a),before)
