"""Threshold is a visible, live marker on the same dBFS scale as input peaks."""
import unittest
from app.fokus_mk2 import capture_meter
from app.fokus_mk2_style import Canvas
from app.mk2_display import snapshot
from app.ni_display import frame
from tests import test_fokus_v2 as fixtures

class CaptureThresholdMeterTests(unittest.TestCase):
    setUp=fixtures.FokusV2Tests.setUp

    def test_snapshot_follows_threshold_and_hides_marker_outside_detect(self):
        a=self.a;a.page='SAMPLING';options=a.capture_options()
        for threshold in (-60,-24,-12,0):
            options.update(mode='DETECT',threshold=threshold)
            self.assertEqual(snapshot(self.surface)['capture_threshold'],threshold)
        for mode in ('SYNC',):
            options['mode']=mode;self.assertIsNone(snapshot(self.surface)['capture_threshold'])

    def test_marker_matches_level_scale_and_is_visible_below_and_above_peak(self):
        for db in (-60,-24,-12,0):
            x=20+round((db+60)/60*224)
            for peak in (0,10**(db/20),1):
                marked=Canvas();plain=Canvas()
                capture_meter(marked,(peak,peak),db);capture_meter(plain,(peak,peak))
                for y in (28,46):
                    for yy in range(y-1,y+13):
                        self.assertNotEqual(marked.p[yy*256+x],plain.p[yy*256+x])
                self.assertEqual(marked.p[60*256:],plain.p[60*256:])
        c=Canvas();capture_meter(c,(.1,.1)) # -20 dB fills two thirds, not one tenth.
        self.assertEqual(sum(c.p[30*256+20:30*256+245]),150)

    def test_mikro_marker_crosses_both_meters_and_moves_with_encoder_value(self):
        a=self.a;a.page='SAMPLING';a.message='';a.capture_field=0
        a.capture_stereo_peak=(1,1);o=a.capture_options();o.update(mode='DETECT',threshold=-24)
        first=frame(a);o['threshold']=-12;second=frame(a)
        x=5+round(36*114/60)
        for y in (30,38):self.assertNotEqual(first[y*128+x],second[y*128+x])
