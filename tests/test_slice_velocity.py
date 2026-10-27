import array
import tempfile
from pathlib import Path
import unittest
import wave
from app.model import Application
from app.audio import AudioBackend
from app.layout import PREVIEW

class SliceVelocityTests(unittest.TestCase):
    def setUp(self):
        self.root=tempfile.TemporaryDirectory();self.addCleanup(self.root.cleanup)
        self.a=Application(self.root.name);path=Path(self.root.name)/'sample.wav'
        with wave.open(str(path),'wb') as w:
            w.setparams((1,2,1000,0,'NONE','not compressed'));w.writeframes(array.array('h',[1000]*1000).tobytes())
        self.a.track().update(sample=str(path),start=0,end=1000,slices=[[0,500],[500,1000]])
        self.a.open_sampling_page('CHOP')
        self.backend=AudioBackend.__new__(AudioBackend);self.sent=[];self.backend.command=self.sent.append
        self.loaded=[];self.backend.load=lambda *v:self.loaded.append(v)
    def play(self,manual,edit,fixed,level,strength):
        a=self.a;a.slice_mode='MANUAL' if manual else 'SPLIT';a.slice_edit=edit
        a.fixed_velocity=fixed;a.velocity_value=level;a.actions=[];a.pad_on(0,strength)
        action,value=a.actions[-1]
        if action=='slice_live_play':track,token=value
        else:self.assertEqual(action,'slice_play');track=value;token=None
        self.backend.slice_preview(track,token)
        return track,float(self.sent[-1].split()[-1])
    def test_fixed_level_reaches_manual_chop_and_edited_and_split_previews(self):
        for manual,edit in ((True,False),(True,True),(False,False)):
            for level in (64,127):
                track,gain=self.play(manual,edit,True,level,12)
                self.assertEqual(track['_preview_velocity'],level);self.assertAlmostEqual(gain,level/127,places=6)
        self.assertEqual(self.loaded[-1][2]['sampler'],{})
        self.assertEqual(self.loaded[-1][2]['choke_group'],0)
        self.assertNotIn('_preview_velocity',self.a.track())
    def test_fixed_off_uses_physical_strength_in_both_preview_commands(self):
        for strength in (20,100,127):
            for manual in (True,False):
                track,gain=self.play(manual,False,False,127,strength)
                self.assertAlmostEqual(gain,strength/127,places=6)
    def test_existing_zone_audition_defaults_to_full_preview_level(self):
        self.backend.slice_preview({'sample':'sample.wav','start':0,'end':10})
        self.assertEqual(self.sent[-1],f'hit {PREVIEW} 1.000000')
