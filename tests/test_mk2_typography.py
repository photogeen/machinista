import tempfile
import unittest
from unittest.mock import Mock
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.mk2_surface import Mk2Surface
from app.mk2_display import Mk2Renderer,snapshot,parameter,mixer_strip
from app.mk2_font import FONTS
from app.lcd_font import FONTS as MIKRO_FONTS

class Mk2TypographyTests(unittest.TestCase):
    def test_trim_inverts_only_outside_playable_waveform_including_signal(self):
        from app.waveform import Envelope
        with tempfile.TemporaryDirectory() as tmp:
            a=Application(tmp);a.page='SAMPLE EDIT'
            a.track().update(sample=tmp+'/example.wav',start=0,end=100)
            surface=Mk2Surface(a,ControllerInputs(a));renderer=Mk2Renderer()
            renderer.waveforms.envelope=Mock(return_value=Envelope(100,((-0.5,0.5),)*120,0,100))
            try:
                state=snapshot(surface);full=renderer(state)[0]
                state['markers']=((25,75),);trimmed=renderer(state)[0]
                for y in range(26,46):
                    for x in (20,220):self.assertEqual(trimmed[y*256+x],full[y*256+x]^1)
                    self.assertEqual(trimmed[y*256+100],full[y*256+100])
                # The waveform outline and outer black margin stay untouched.
                self.assertEqual(full[:26*256],trimmed[:26*256])
                self.assertEqual(full[46*256:],trimmed[46*256:])
            finally:renderer.close()

    def test_tall_face_and_stable_digit_width_preserve_mikro_font(self):
        for char,rows in FONTS['bold7'].items():
            self.assertEqual(len(rows),7,char)
            self.assertEqual(len({len(row) for row in rows}),1,char)
        self.assertEqual({len(FONTS['bold7'][c][0]) for c in '0123456789'},{6})
        self.assertNotIn('bold7',MIKRO_FONTS)

    def test_parameter_captions_and_values_center_above_their_knob(self):
        for column in range(4):
            canvas=bytearray(16384);parameter(canvas,column,'A','1')
            for y in (46,54):
                xs=[i%256 for i,v in enumerate(canvas) if v and y<=i//256<y+(5 if y==46 else 7)]
                self.assertLessEqual(abs((min(xs)+max(xs))/2-(33+63*column)),1)

    def test_status_message_never_hides_control_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=Application(tmp);a.page='SAMPLER';a.sampler_page=1
            surface=Mk2Surface(a,ControllerInputs(a));renderer=Mk2Renderer()
            try:
                a.message='';before=renderer(snapshot(surface))
                a.message='ALL SAMPLES FOUND';after=renderer(snapshot(surface))
                self.assertEqual(before[0],after[0])
                self.assertNotEqual(before[1],after[1])
                self.assertEqual(before[1][38*256:],after[1][38*256:])
            finally:renderer.close()

    def test_vertical_mixer_stereo_meter_growth_peak_hold_and_selection(self):
        silent=bytearray(16384);mixer_strip(silent,0,'01 KICK','80',(0,0),(0,0))
        active=bytearray(16384);mixer_strip(active,0,'01 KICK','80',(.1,0),(1,0),True)
        # Left signal grows from bottom; right remains empty. Held peak is at top.
        self.assertEqual(active[48*256+24],1)
        self.assertEqual(active[30*256+24],0)
        self.assertEqual(active[27*256+24],1)
        self.assertEqual(active[48*256+34],0)
        self.assertEqual(silent[48*256+24],0)
        self.assertEqual(active[24*256+10],1)
        self.assertEqual(silent[24*256+10],0)
        # Meter changes never overwrite caption or value rows.
        self.assertEqual(silent[18*256:23*256],active[18*256:23*256])
        self.assertEqual(silent[54*256:61*256],active[54*256:61*256])

    def test_sampling_polarity_matches_edit_and_slice_references(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=Application(tmp);a.track()['sample']=str(tmp+'/example.wav');a.track()['end']=100
            surface=Mk2Surface(a,ControllerInputs(a));renderer=Mk2Renderer()
            try:
                a.page='SAMPLE EDIT';light=renderer(snapshot(surface))[0]
                a.page='CHOP';dark=renderer(snapshot(surface))[0]
                self.assertTrue(light[30*256+100]);self.assertFalse(dark[30*256+100])
            finally:renderer.close()

if __name__=='__main__':unittest.main()
