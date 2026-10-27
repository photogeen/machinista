"""Visual feedback must follow real state without mutating the audio model."""
import copy
import unittest
from tests import test_fokus_v2 as fixtures
from app.fokus import Canvas
from app.fokus_graphics import response
from app.mk2_display import snapshot


class FokusGraphicsTests(unittest.TestCase):
    setUp=fixtures.FokusV2Tests.setUp
    check_pixels=fixtures.FokusV2Tests.check_pixels
    # Reuse the engine fixture and framebuffer checks, not its whole test suite.
    def test_envelope_filter_and_lfo_graphs_follow_their_parameters(self):
        for section,key,a,b in ((1,'attack',10,900),(2,'cutoff',80,14000),(4,'lfo_shape','SINE','RECT')):
            with self.subTest(section=section):
                first=Canvas(256);second=Canvas(256)
                values={'type':'ADSR','filter':'LP2',key:a};response(first,section,values)
                values[key]=b;response(second,section,values)
                self.assertNotEqual(first.finish(),second.finish())
                self.check_pixels(second.finish(),256)

    def test_output_route_and_plugin_graphics_follow_actual_target(self):
        a=self.a;a.page='PAD';before=copy.deepcopy(a.project)
        first=self.renderer(snapshot(self.surface))[1]
        a.track()['routing']={'dest':'MASTER'}
        second=self.renderer(snapshot(self.surface))[1]
        self.assertNotEqual(first[24*256:46*256],second[24*256:46*256])
        a.project=before
        meta={'uri':'urn:test:gain','name':'Gain','kind':'EFFECT','supported':True,'ports':[dict(index=0,symbol='gain',name='Gain',default=1,min=0,max=2)]}
        a.plugin_catalog=[meta];a.track()['plugins']=[dict(uri=meta['uri'],kind='EFFECT',bypass=False,controls={'gain':.2})];a.page='PLUGIN'
        first=self.renderer(snapshot(self.surface));a.track()['plugins'][0]['controls']['gain']=1.8
        second=self.renderer(snapshot(self.surface))
        self.assertNotEqual(first[1][24*256:46*256],second[1][24*256:46*256])
        before=copy.deepcopy(a.project);self.renderer(snapshot(self.surface));self.assertEqual(before,a.project)

    def test_song_strip_moves_selection_and_repeat_grid_changes_rate(self):
        a=self.a;a.page='SONG';a.project['song']=[0,2,1,3]
        first=self.renderer(snapshot(self.surface));a.song_index=2
        self.assertNotEqual(first,self.renderer(snapshot(self.surface)))
        a.page='NOTE REPEAT';first=self.renderer(snapshot(self.surface));a.project['repeat_presets'][a.repeat_bank*2+a.repeat_preset]=32
        self.assertNotEqual(first,self.renderer(snapshot(self.surface)))
