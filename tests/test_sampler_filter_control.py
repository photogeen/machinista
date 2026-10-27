"""Filter frequency control has a fixed octave scale on every controller."""
import tempfile
import unittest
from pathlib import Path
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.mk1_session import Mk1Surface
from app.mk2_surface import Mk2Surface
from app.sampler import adjust_cutoff,cutoff_position

class SamplerFilterControlTests(unittest.TestCase):
    def test_equal_travel_per_octave_and_reversible_adjustment(self):
        for start in (20,40,100,440,1000,5000):
            self.assertAlmostEqual(adjust_cutoff(start,32),start*2,delta=.002)
            self.assertAlmostEqual(adjust_cutoff(adjust_cutoff(start,1),-1),start,delta=.002)
            self.assertLess(adjust_cutoff(start,1,True)-start,adjust_cutoff(start,1)-start)
        self.assertEqual(adjust_cutoff(20,-100000),20)
        self.assertEqual(adjust_cutoff(20000,100000),20000)

    def test_one_normal_step_moves_graph_less_than_one_pixel_at_any_frequency(self):
        positions=[]
        for start in (20,25,40,80,100,440,1000,4000,10000,18000):
            distance=(cutoff_position(adjust_cutoff(start,1))-cutoff_position(start))*246
            self.assertGreater(distance,0);self.assertLess(distance,1)
            positions.append(distance)
        self.assertLess(max(positions)-min(positions),.002)

    def test_mikro_and_full_size_cutoff_and_shift_fine_keep_other_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            for cls in (None,Mk1Surface,Mk2Surface):
                with self.subTest(controller=cls):
                    root=Path(tmp)/(cls.source if cls else 'mikro');a=Application(root)
                    a.page='SAMPLER';a.sampler_page=2
                    a.sampler_field=next(i for i,f in enumerate(a.sampler_fields()) if f[0]=='cutoff')
                    a.track()['sampler']={'filter':'LP2','cutoff':100,'resonance':40}
                    surface=cls(a,ControllerInputs(a)) if cls else None
                    if surface:surface.rotate(6,1)
                    else:a.rotate(1)
                    normal=a.track()['sampler']['cutoff'];self.assertAlmostEqual(normal,adjust_cutoff(100,1))
                    a.track()['sampler']['cutoff']=100;a.shift=True
                    if surface:surface.rotate(6,1)
                    else:a.rotate(1)
                    fine=a.track()['sampler']['cutoff'];self.assertGreater(fine,100);self.assertLess(fine,normal)
                    self.assertEqual(a.track()['sampler']['resonance'],40)
                    self.assertEqual(a.track()['sampler']['filter'],'LP2')
