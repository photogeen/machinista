"""Compact plugin overview: all eight actual encoder values, without rebinding."""
import copy,pickle,tempfile,unittest
from unittest.mock import patch
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.mk1_session import Mk1Surface
from app.mk2_surface import Mk2Surface
from app.mk3_surface import Mk3Surface
from app.mk2_display import snapshot,Mk2Renderer
from app.mk3_state import snapshot as color_snapshot
from app.mk3_display import Mk3Renderer

class PluginReadoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=a=Application(self.tmp.name);a.control_level=2;a.page='PLUGIN'
        names=('CUTOFF','RESONANCE','ENV AMOUNT','ATTACK','DECAY','SUSTAIN','RELEASE','VOLUME')
        self.ports=[dict(index=i,symbol=f'p{i}',name=names[i%8],min=0,max=1,default=i/20) for i in range(18)]
        a.plugin_catalog=[dict(uri='urn:readouts',name='Readout Filter',kind='EFFECT',supported=True,ports=self.ports)]
        a.track()['plugins']=[dict(uri='urn:readouts',kind='EFFECT',controls={})]
    def surfaces(self):
        for cls in (Mk1Surface,Mk2Surface,Mk3Surface):yield cls(self.a,ControllerInputs(self.a))
    def test_every_surface_lists_current_eight_not_three_and_uses_page_boundary(self):
        a=self.a
        for s in self.surfaces():
            for parameter,count in ((0,8),(3,8),(8,8),(17,2)):
                with self.subTest(surface=s.source,parameter=parameter):
                    a.plugin_param=parameter;before=copy.deepcopy(a.project);a.actions.clear()
                    state=color_snapshot(s) if s.source=='mk3' else snapshot(s)
                    rows=state['plugin_values'];self.assertEqual(len(rows),count)
                    self.assertEqual([v[0] for v in rows],list(range(1,count+1)))
                    self.assertEqual([v[1:3] for v in rows],[v for v in state['fields'] if v])
                    first=parameter//8*8
                    self.assertEqual([v[2] for v in rows],[f'{round(i/20*100)}%' for i in range(first,first+count)])
                    self.assertEqual(a.project,before);self.assertFalse(a.actions)
                    self.assertLess(len(pickle.dumps(rows)),1024)
    def test_encoder_eight_updates_its_readout_without_changing_any_binding(self):
        for s in self.surfaces():
            self.a.plugin_param=8;state=snapshot(s);before=copy.deepcopy(self.a.plugin_selected()['controls'])
            s.rotate(8,1);after=snapshot(s)
            self.assertEqual(after['plugin_values'][7][2],'76%')
            self.assertEqual(after['plugin_values'][7][3],.76)
            self.assertEqual(self.a.plugin_selected()['controls'],dict(before,p15=.76))
            self.a.plugin_selected()['controls'].clear()
    def test_mono_eight_rows_are_clipped_above_footer_and_keep_left_screen(self):
        r=Mk2Renderer();self.addCleanup(r.close)
        for s in (Mk1Surface(self.a,ControllerInputs(self.a)),Mk2Surface(self.a,ControllerInputs(self.a))):
            state=snapshot(s);before=r.draw(state)
            for row in range(8):
                changed=copy.deepcopy(state);values=list(changed['plugin_values']);n,label,_,fraction=values[row]
                values[row]=(n,label,'100%',1);changed['plugin_values']=tuple(values)
                after=r.draw(changed);self.assertEqual(before[0],after[0])
                expected_x=4+(row//4)*126;expected_y=23+(row%4)*6
                differences=[i for i,(x,y) in enumerate(zip(before[1],after[1])) if x!=y]
                self.assertTrue(differences)
                self.assertTrue(all(expected_x<=i%256<expected_x+124 and expected_y<=i//256<expected_y+5 for i in differences))
                self.assertEqual(before[1][46*256:],after[1][46*256:])
    def test_mono_bar_fill_is_visual_and_does_not_repeat_numeric_strings(self):
        from app.fokus_mk2 import plugin_values
        from app.fokus_mk2_style import Canvas
        for fraction in (0,.5,1):
            c=Canvas();plugin_values(c,((1,'CUTOFF','DO NOT DRAW THIS PERCENTAGE',fraction),))
            fill=sum(c.p[y*256+x] for y in range(24,27) for x in range(74,125))
            self.assertEqual(fill,round(51*fraction)*3)
            other=Canvas();plugin_values(other,((1,'CUTOFF','100%',fraction),))
            self.assertEqual(c.finish(),other.finish())
    def test_color_all_eight_changes_are_in_body_and_leave_footer_and_artwork_fixed(self):
        s=Mk3Surface(self.a,ControllerInputs(self.a));state=color_snapshot(s);r=Mk3Renderer();self.addCleanup(r.close)
        before=r.draw(state)
        for row in range(8):
            changed=copy.deepcopy(state);values=list(changed['plugin_values']);n,label,_,_=values[row]
            values[row]=(n,label,'100%',1);changed['plugin_values']=tuple(values)
            after=r.draw(changed);self.assertEqual(before[0].tobytes(),after[0].tobytes())
            from PIL import ImageChops
            box=ImageChops.difference(before[1],after[1]).getbbox();self.assertIsNotNone(box)
            self.assertGreaterEqual(box[1],62);self.assertLessEqual(box[3],208)
            self.assertEqual(before[1].crop((0,216,480,272)).tobytes(),after[1].crop((0,216,480,272)).tobytes())
    def test_bank_patch_names_and_graphs_have_priority(self):
        a=self.a
        from app.plugin_profiles import profile
        uri='urn:machinista:instrument:synth';a.track()['plugins']=[dict(uri=uri,kind='INSTRUMENT',controls={})]
        a.plugin_catalog=[dict(uri=uri,name='Synth',kind='INSTRUMENT',supported=True,ports=profile(uri)['parameters'])]
        for s in self.surfaces():
            state=snapshot(s);self.assertIn('plugin_names',state)
            if s.source=='mk3':
                r=Mk3Renderer();self.addCleanup(r.close)
                with patch.object(r,'plugin_values',wraps=r.plugin_values) as values:r.draw(color_snapshot(s));values.assert_not_called()
            else:
                r=Mk2Renderer();self.addCleanup(r.close)
                with patch('app.fokus_mk2.plugin_values') as values:r.draw(state);values.assert_not_called()
        a.plugin_param=8;s=Mk3Surface(a,ControllerInputs(a));state=color_snapshot(s);self.assertIn('synth_graph',state)
        r=Mk3Renderer();self.addCleanup(r.close)
        with patch.object(r,'synth_plot',wraps=r.synth_plot) as graph,patch.object(r,'plugin_values',wraps=r.plugin_values) as values:
            r.draw(state);graph.assert_called_once();values.assert_called_once()
