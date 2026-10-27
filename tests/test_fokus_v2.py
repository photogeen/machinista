import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,Mock
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.mk2_surface import Mk2Surface
from app.mk2_display import Mk2Renderer,snapshot
from app.ni_display import frame
from app.fokus import Canvas
from app.ui_inventory import PAGES
from app.sampler import SAMPLER_PAGES,ZONE_PAGES,default_zone
from app.waveform import Envelope


def fixture(root):
    a=Application(root);a.confirmation=('DELETE?',lambda:None,'PROJECT');a.name_action='NEW PROJECT'
    a.preset_kind='SOUND';a.export_result='export.wav';a.export_result_device='SD CARD'
    a.track().update(sample=str(Path(root)/'samples/example.wav'),start=0,end=44100)
    a.track()['zones']=[default_zone(a.track())]
    a.track()['slices']=[[0,11025],[11025,22050],[22050,33075],[33075,44100]]
    a.track()['slice_source']={'sample':a.track()['sample'],'start':0,'end':44100}
    a.slice_count=4;a.slice_mode='SPLIT';a.message=''
    a.capture_options();a.sample_delete_index=0
    from app.browser import Browser
    a.relink_browser=Browser(Path(root)/'samples')
    a.system_stats={'cpu':23,'ram':{'percent':31},'storage':[dict(name='SD CARD',percent=42,used=13.4e9,total=32e9)]}
    return a


class FokusV2Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=fixture(self.tmp.name);self.surface=Mk2Surface(self.a,ControllerInputs(self.a))
        self.renderer=Mk2Renderer();self.addCleanup(self.renderer.close)
        self.renderer.waveforms.envelope=Mock(return_value=Envelope(44100,((-.5,.5),)*120,0,44100))
        env=patch.dict(os.environ,{'MACHINISTA_UI':'v2'});env.start();self.addCleanup(env.stop)

    def check_pixels(self,pixels,width):
        self.assertEqual(len(pixels),width*64);self.assertLessEqual(set(pixels),{0,1})
        black=1 if width==128 else 0
        self.assertTrue(all(v==black for v in pixels[:width]+pixels[-width:]))
        self.assertTrue(all(pixels[y*width]==pixels[y*width+width-1]==black for y in range(64)))
        self.assertIn(1-black,pixels)

    def test_every_registered_workflow_renders_both_controllers_and_retains_project(self):
        a=self.a;before=copy.deepcopy(a.project)
        for page in PAGES:
            with self.subTest(page=page):
                a.page=page
                self.check_pixels(frame(a),128)
                for p in self.renderer(snapshot(self.surface)):self.check_pixels(p,256)
        self.assertEqual(a.project,before)

    def test_all_sampler_fields_are_visible_in_mikro_and_bound_on_mk2(self):
        a=self.a;a.page='SAMPLER';a.track()['sampler']={'type':'ADSR','polyphony':'LEGATO','filter':'EQ'}
        for page,(_,fields) in enumerate(SAMPLER_PAGES):
            a.sampler_page=page;seen=set()
            for i,field in enumerate(a.sampler_fields()):
                a.sampler_field=i;before=frame(a)
                from app.control_display import control_state
                self.assertIn(field[1],control_state(a)['caption'])
                self.check_pixels(before,128)
            for subpage in range(2 if page==2 else 1):
                self.surface.sampler_subpage=subpage
                for bound in self.surface.fields():
                    if bound:seen.update(dict(bound.attributes).values())
            for i,field in enumerate(a.sampler_fields()):self.assertIn(i,seen,field[0])

    def test_all_zone_fields_bound_without_covering_zoom_scroll(self):
        a=self.a;a.page='ZONE'
        for page,(_,keys) in enumerate(ZONE_PAGES):
            a.zone_page=page;seen=set()
            for subpage in range((len(keys)+1)//2):
                self.surface.zone_subpage=subpage
                fields=self.surface.fields()
                self.assertEqual([f.label for f in fields[2:4]],['ZOOM','SCROLL'])
                for field in fields[:2]:
                    if field:seen.add(dict(field.attributes)['zone_field'])
            self.assertEqual(seen,set(range(len(keys))))

    def test_new_direct_probability_and_base_key_bindings_edit_the_shown_value(self):
        a=self.a;a.page='PATTERN GRID';a.edit_grid_event()
        self.assertEqual(self.surface.fields()[2].label,'PROBABILITY')
        self.surface.rotate(3,-17)
        self.assertEqual(next(iter(a.event_notes().values()))['probability'],83)
        a.page='PAD CONFIG';a.keyboard_enabled=False;self.surface.pad_page=1
        note=a.track()['note'];self.surface.rotate(2,2)
        self.assertEqual(a.track()['note'],note+2)

    def test_utility_encoder_one_scrolls_the_actual_settings_selection(self):
        a=self.a;a.open_settings('AUDIO');before=a.menu
        self.assertEqual(self.surface.fields()[0].label,'SELECT');self.surface.rotate(1,1)
        self.assertEqual(a.menu,before+1)

    def test_project_export_and_relink_content_uses_real_workflow_not_generic_sound_fallback(self):
        a=self.a;a.page='PROJECT MANAGE';a.manage_index=5
        data=snapshot(self.surface)['utility']
        self.assertEqual(data[0],'PROJECT / MANAGE');self.assertIn('>SAVE SOUND',data[1])
        a.page='MISSING SAMPLES';self.assertIn('NO MISSING SAMPLES',snapshot(self.surface)['utility'][1])
        a.page='EXPORT';self.surface.utility_bank=0;seen=set()
        for _ in range(self.surface.page_state()[1]):
            seen.update(f.label for f in self.surface.fields() if f)
            self.surface.change_page(1)
        self.assertEqual(seen,set(a.export_fields()))

    def test_target_group_and_sound_are_directly_selectable_and_displayed(self):
        a=self.a;a.page='SLICE TARGET';self.surface.rotate(3,2)
        self.assertEqual(a.slice_target_group,2)
        self.surface.rotate(4,4);self.assertEqual(a.slice_target_sound,3)
        self.assertEqual(self.surface.fields()[2].value,'C')
        self.assertEqual(self.surface.fields()[3].value,'4')

    def test_replacing_titles_clears_previous_pixels(self):
        c=Canvas(256);c.title('LONG PREVIOUS TITLE');c.title('NEW')
        fresh=Canvas(256);fresh.title('NEW')
        self.assertEqual(c.finish(),fresh.finish())

    def test_parameters_survive_messages_and_waveform_panel_keeps_all_eight_bindings(self):
        a=self.a;a.page='SAMPLER';a.sampler_page=1
        first=self.renderer(snapshot(self.surface));a.message='STATUS';second=self.renderer(snapshot(self.surface))
        self.assertEqual(first[1][46*256:],second[1][46*256:])
        a.message='';a.page='SAMPLE EDIT'
        state=snapshot(self.surface)
        self.assertEqual([f[0] for f in state['fields'][:4]],['START','END','ZOOM','SCROLL'])
        pixels=self.renderer(state)[0]
        self.assertTrue(any(pixels[26*256:46*256]));self.check_pixels(pixels,256)

    def test_v1_renderer_switch_still_works_without_data_migration(self):
        self.a.page='SAMPLER';original=copy.deepcopy(self.a.project)
        modern=frame(self.a);modern_mk2=self.renderer(snapshot(self.surface))
        with patch.dict(os.environ,{'MACHINISTA_UI':'v1'}):
            old=frame(self.a);old_mk2=self.renderer(snapshot(self.surface))
        self.assertNotEqual(old,modern);self.assertNotEqual(old_mk2,modern_mk2)
        self.assertEqual(original,self.a.project)

    def test_long_parameter_values_get_a_separate_line_instead_of_collision(self):
        c=Canvas();c.field('DESTINATION','GROUP 64 / SOUND 16')
        self.assertTrue(any(v==0 for v in c.p[46*128:51*128]))
        self.assertTrue(any(v==0 for v in c.p[55*128:60*128]))


if __name__=='__main__':unittest.main()
