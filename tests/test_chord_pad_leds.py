"""Chord assignments, contact and last selection drive both controller reports."""
import copy
import tempfile
import unittest
from app.model import Application
from app.leds import led_report,DIM,FULL,OFF
from app.controller_inputs import ControllerInputs
from app.mk2_surface import Mk2Surface
from app.mk2_display import leds,PALETTE
from app.mk2_protocol import PAD_SLOTS

PRESET={'name':'LED fixture','root':60,'chords':[{'input':60,'name':'C','notes':[60,64,67]},{'input':61,'name':'Am','notes':[57,60,64]},{'input':62,'name':'F','notes':[53,57,60]}]}

class ChordPadLEDTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=Application(self.tmp.name);self.a.page='PAD CONFIG';self.a.keyboard_enabled=True;self.a.fixed_velocity=False;self.a.keyboard_root=60
        self.a.performance().update(chord_mode='CUSTOM',custom=copy.deepcopy(PRESET),root=60)
        self.channels={(slot,'orange'):slot for slot in range(16)}
        self.inputs=ControllerInputs(self.a);self.surface=Mk2Surface(self.a,self.inputs)
    def micro(self):return tuple(led_report(self.a,self.channels,now=1)[slot+1] for slot in range(16))
    def mk2(self):
        pad=leds(self.surface,self.channels,now=1)[2]
        return tuple(tuple(pad[1+PAD_SLOTS.index(slot)*3:4+PAD_SLOTS.index(slot)*3]) for slot in range(16))
    def test_empty_sound_still_shows_assigned_chords_and_unassigned_stay_dark(self):
        self.assertFalse(self.a.sound_present(0))
        self.assertEqual(self.micro(),(FULL,DIM,DIM)+(OFF,)*13)
        self.assertEqual(self.mk2()[:3],(PALETTE[0],tuple(round(c*DIM/FULL) for c in PALETTE[0]),tuple(round(c*DIM/FULL) for c in PALETTE[0])))
        self.assertEqual(self.mk2()[3:],((0,0,0),)*13)
    def test_shared_chord_tones_do_not_light_other_chords_brightly(self):
        self.inputs.pad_on('mk2',1,100)
        self.assertEqual(self.micro()[:3],(DIM,FULL,DIM))
        self.inputs.pad_off('mk2',1)
        self.assertEqual(self.micro()[:3],(DIM,FULL,DIM))
        self.assertEqual(self.mk2()[1],PALETTE[0])
    def test_all_held_pads_bright_then_only_the_last_selected(self):
        self.inputs.pad_on('mk2',0,100);self.inputs.pad_on('mikro',2,100)
        self.assertEqual(self.micro()[:3],(FULL,DIM,FULL))
        self.inputs.pad_off('mikro',2);self.assertEqual(self.micro()[:3],(FULL,DIM,FULL))
        self.inputs.pad_off('mk2',0);self.assertEqual(self.micro()[:3],(DIM,DIM,FULL))
    def test_unassigned_pad_does_not_steal_selection_or_flash(self):
        self.inputs.pad_on('mk2',1,100);self.inputs.pad_off('mk2',1)
        self.inputs.pad_on('mk2',15,100);self.assertEqual(self.a.chord_focus,1)
        self.assertEqual(self.micro()[15],OFF);self.inputs.pad_off('mk2',15)
        self.assertEqual(self.micro()[:3],(DIM,FULL,DIM))
    def test_chord_sets_and_harmonizer_use_same_selection_rule(self):
        for mode,kind,lit in [('SET','MAJOR 1',12),('HARM','MAJOR',16)]:
            with self.subTest(mode=mode):
                self.a.performance().update(chord_mode=mode,chord_type=kind)
                self.inputs.pad_on('mk2',5,100);self.inputs.pad_off('mk2',5)
                values=self.micro();self.assertEqual(values[5],FULL)
                self.assertTrue(all(value==DIM for slot,value in enumerate(values[:lit]) if slot!=5))
                self.assertTrue(all(value==OFF for value in values[lit:]))
    def test_mapping_not_filtered_by_sampler_zone_ranges(self):
        self.a.track()['zones']=[{'sample':'fixture.wav','start':0,'end':100,'key_lo':0,'key_hi':1}]
        self.assertEqual(self.micro()[:3],(FULL,DIM,DIM))
    def test_bank_only_shows_chords_present_on_that_bank(self):
        self.a.performance()['custom_bank']=1
        self.assertEqual(self.micro(),(OFF,)*16);self.assertEqual(self.mk2(),((0,0,0),)*16)
    def test_normal_keyboard_keeps_existing_unloaded_sound_behavior(self):
        self.a.performance()['chord_mode']='OFF';self.assertEqual(self.micro(),(OFF,)*16)

if __name__=='__main__':unittest.main()
