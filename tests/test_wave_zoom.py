import array
from pathlib import Path
import tempfile
import unittest
import wave
from app.model import Application
from app.waveform import read_envelope


class WaveZoomTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.app=Application(self.temp.name)
        self.path=Path(self.temp.name)/'samples/zoom.wav'
        with wave.open(str(self.path),'wb') as wav:
            wav.setparams((1,2,48000,0,'NONE','not compressed'))
            values=array.array('h',[0]*4800);values[600]=32767;wav.writeframes(values.tobytes())
        self.app.track().update(sample=str(self.path),start=0,end=4800)
        self.app.page='SAMPLE EDIT';self.app.actions.clear()
    def tearDown(self):self.temp.cleanup()
    def test_played_slice_focus_is_shared_and_preserves_sample_and_audio(self):
        import copy
        from app.controller_inputs import ControllerInputs
        from app.mk2_surface import Mk2Surface
        a=self.app;a.page='CHOP';a.slice_edit=True;a.slice_mode='MANUAL';a.fixed_velocity=False
        a.track()['slices']=[[i*600,(i+1)*600] for i in range(8)]
        surface=Mk2Surface(a,ControllerInputs(a));surface.waveform_window()
        a.wave_zoom=2
        original=copy.deepcopy(a.track())
        a.pad_on(3,91)
        first,last=a.wave_bounds(4800)
        self.assertEqual((first,last),(1500,2700))
        self.assertEqual(surface.waveform_window(),(str(self.path),first,last))
        action,track=a.actions[-1]
        self.assertEqual(action,'slice_play');self.assertEqual((track['start'],track['end']),(1800,2400))
        self.assertEqual(track['_preview_velocity'],91);self.assertEqual(a.track(),original)
        surface.rotate_waveform(1,1);manual=a.wave_bounds(4800)
        self.assertNotEqual(manual,(first,last));self.assertEqual(a.wave_bounds(4800),manual)
        a.pad_on(3,91)  # The same pad must also restore focus after scrolling.
        self.assertEqual(surface.waveform_window()[1:],(first,last))
        a.wave_zoom=3;a.pad_on(3,91)
        self.assertEqual(surface.waveform_window()[1:],(1500,2100))
        self.assertEqual(a.wave_zoom,3)
        a.wave_zoom=2
        for slot,expected in ((0,(0,1200)),(7,(3600,4800))):
            a.pad_on(slot)
            self.assertEqual(surface.waveform_window()[1:],expected)
            self.assertEqual(a.wave_bounds(4800),expected)

    def test_close_zoom_boundary_arrows_and_pad_replay_keep_focus(self):
        from app.controller_inputs import ControllerInputs
        from app.mk2_surface import Mk2Surface
        from app.mk2_display import snapshot
        a=self.app;a.page='CHOP';a.slice_edit=True
        a.track()['slices']=[[i*600,(i+1)*600] for i in range(8)]
        s=Mk2Surface(a,ControllerInputs(a));s.waveform_window();a.wave_zoom=4
        a.pad_on(3)
        self.assertEqual(a.wave_bounds(4800),(1650,1950))
        self.assertEqual(s.page_directions(),(True,True))
        s.change_page(1)
        self.assertEqual(a.slice_field,2)
        self.assertEqual(s.waveform_window()[1:],(2250,2550))
        self.assertEqual(snapshot(s)['focus_detail'],'END')
        a.pad_on(4)
        self.assertEqual(a.wave_bounds(4800),(2850,3150))
        a.button('NAV LEFT',True);a.button('NAV LEFT',False)
        self.assertEqual(a.slice_field,1)
        self.assertEqual(a.wave_bounds(4800),(2250,2550))
        a.pad_on(3)
        self.assertEqual(a.wave_bounds(4800),(1650,1950))
        self.assertEqual(a.wave_zoom,4)
        a.button('NAV RIGHT',True);a.button('NAV RIGHT',False)
        self.assertEqual(s.waveform_window()[1:],(2250,2550))
        s.change_page(-1)
        self.assertEqual(s.waveform_window()[1:],(1650,1950))
        a.button('F1',True);a.button('F1',False)
        a.slice_focus_end=True
        a.button('F1',True);a.button('F1',False)
        self.assertFalse(a.slice_focus_end)
        self.assertEqual(a.slice_field,1)

    def test_live_manual_chopping_does_not_auto_zoom(self):
        a=self.app;a.page='CHOP';a.slice_edit=False;a.slice_mode='MANUAL'
        a.track()['slices']=[[0,2400],[2400,4800]]
        a.pad_on(0)
        self.assertEqual(a.wave_bounds(4800),(0,4800))

    def test_slice_edit_mode_is_marked_on_both_controllers(self):
        from app.controller_inputs import ControllerInputs
        from app.mk2_surface import Mk2Surface
        from app.mk2_display import snapshot
        a=self.app;a.page='CHOP';surface=Mk2Surface(a,ControllerInputs(a))
        for enabled in (False,True,False):
            a.slice_edit=enabled
            self.assertEqual(0 in a.active_softkeys(),enabled)
            self.assertEqual(0 in snapshot(surface)['active_right'],enabled)

    def test_trim_fine_step_is_visible_and_scales_with_zoom(self):
        a=self.app
        a.button('SHIFT',True);a.rotate(1);a.button('SHIFT',False)
        self.assertEqual(a.track()['start'],40)
        a.button('ENCODER PUSH',True);a.rotate(1);a.button('ENCODER PUSH',False)
        self.assertEqual(a.track()['start'],80)
        a.rotate(1);self.assertEqual(a.track()['start'],240)
        a.wave_zoom=2;a.button('SHIFT',True);a.rotate(1);a.button('SHIFT',False)
        self.assertEqual(a.track()['start'],250)
        a.sample_field=1;a.button('ENCODER PUSH',True);a.rotate(-1);a.button('ENCODER PUSH',False)
        self.assertEqual(a.track()['end'],4790)
        a.wave_zoom=16;a.button('SHIFT',True);a.rotate(-1);a.button('SHIFT',False)
        self.assertEqual(a.track()['end'],4789)
    def test_view_wave_zoom_scroll_and_release_preserve_audio_and_ranges(self):
        a=self.app;a.button('VIEW',True);a.button('F2',True)
        self.assertEqual(a.page,'SAMPLE EDIT');self.assertTrue(a.wave_view());self.assertEqual(a.softkeys(),('-','WAVE','-'))
        original=dict(a.track());a.pad_on(5);self.assertEqual(a.wave_bounds(4800),(0,2400))
        a.pad_on(2);self.assertEqual(a.wave_bounds(4800),(600,3000))
        a.pad_on(0);self.assertEqual(a.wave_bounds(4800),(0,2400))
        a.pad_on(1);self.assertEqual(a.wave_bounds(4800),(0,4800))
        self.assertEqual(a.track(),original);self.assertEqual(a.actions,[])
        a.button('VIEW',False);self.assertFalse(a.wave_view())
        a.rotate(1);self.assertGreater(a.track()['start'],0)
    def test_pin_limits_new_sample_reset_and_mixer_outside_edit(self):
        a=self.app;a.button('VIEW',True);a.button('F2',True)
        a.button('MAIN',True);a.button('MAIN',False);a.button('VIEW',False)
        self.assertTrue(a.wave_view())
        for _ in range(30):a.pad_on(5)
        first,last=a.wave_bounds(4800);self.assertEqual(last-first,120)
        for _ in range(300):a.pad_on(2)
        self.assertEqual(a.wave_bounds(4800),(4680,4800))
        for _ in range(300):a.pad_on(0)
        self.assertEqual(a.wave_bounds(4800),(0,120))
        a.button('VIEW',True);a.button('VIEW',False);self.assertFalse(a.wave_view())
        a.wave_sample='other.wav';self.assertEqual(a.wave_bounds(4800),(0,4800))
        a.page='PAD';a.button('VIEW',True);self.assertEqual(a.page,'VIEW NAV')
        # Mikro VIEW commits on release; BACK clears all workspace choices.
        a.button('F1',True);a.button('F1',False);a.button('VIEW',False);self.assertEqual(a.page,'PAD')
    def test_window_reads_actual_audio_detail_and_maps_markers(self):
        full=read_envelope(self.path);detail=read_envelope(self.path,start=480,end=720)
        self.assertEqual((detail.frames,detail.start,detail.end),(4800,480,720))
        self.assertEqual(full.peaks[15][1],32767/32768)
        self.assertEqual(detail.peaks[60][1],32767/32768)
        from app.ni_display import frame
        self.app.track()['start']=600
        pixels=frame(self.app,detail)
        self.assertEqual(pixels[22*128+64],1)  # actual frame 600 is at window midpoint
        self.assertTrue(all(pixel==1 for pixel in pixels[63*128:]))
