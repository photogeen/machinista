"""Slice boundaries, actual sampler hits and controller feedback agree after Apply."""
import array
import copy
import hashlib
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import wave

from app.audio import AudioBackend
from app.controller_inputs import ControllerInputs
from app.leds import led_report,OFF,DIM,FULL
from app.layout import ZONE_BASE
from app.mk2_display import leds,snapshot,Mk2Renderer,PALETTE
from app.mk2_protocol import PAD_SLOTS
from app.mk2_surface import Mk2Surface
from app.model import Application,validate_project


class SamplingApplyWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.a=Application(self.root)
        self.path=self.root/'loop.wav'
        with wave.open(str(self.path),'wb') as w:
            w.setparams((1,2,1000,0,'NONE','not compressed'))
            w.writeframes(array.array('h',[1000]*12800).tobytes())
        self.original=hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.channels={(i,'orange'):i for i in range(16)}
        self.surface=Mk2Surface(self.a,ControllerInputs(self.a))
        self.ranges(4)

    def ranges(self,count):
        self.a.track().update(sample=str(self.path),start=0,end=12800,
            slices=[[12800*i//count,12800*(i+1)//count] for i in range(count)])
        self.a.open_sampling_page('CHOP');self.a.slice_edit=False

    def lights(self):
        now=time.monotonic()+1
        return tuple(led_report(self.a,self.channels,now)[i+1] for i in range(16))

    def test_all_sound_slices_reach_the_correct_sampler_zone_despite_old_scale_and_chords(self):
        a=self.a;a.performance().update(scale='MINOR PENTA',chord_mode='CUSTOM',custom={
            'name':'Old chords','root':60,'chords':[{'input':60,'notes':[60,64,67]}]})
        self.ranges(32);a.velocities16=True;a.apply_slices(0,0,'NONE')
        self.assertFalse(a.velocities16);self.assertEqual(len(a.track()['zones']),32)
        self.assertEqual(a.performance()['scale'],'MINOR PENTA')
        self.assertEqual(a.performance()['chord_mode'],'CUSTOM')
        backend=AudioBackend.__new__(AudioBackend);commands=[];backend.command=commands.append
        for base in (0,16):
            a.keyboard_root=base
            for slot in range(16):
                a.actions=[];commands.clear();a.pad_on(slot,100)
                notes=[v[0] for kind,v in a.actions if kind=='midi_note']
                self.assertEqual(notes,[base+slot])
                backend.hit(0,0,100,a.track(),notes[0])
                hits=[c for c in commands if c.startswith('hit ')]
                self.assertEqual(len(hits),1)
                self.assertEqual(int(hits[0].split()[1]),ZONE_BASE+base+slot)
                a.release_pad(slot)
        validate_project(a.project)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(),self.original)

    def test_up_to_128_slices_survive_sound_apply_and_project_reload(self):
        a=self.a;self.ranges(128);expected=copy.deepcopy(a.slice_ranges())
        a.apply_slices(0,0,'NONE');a.save();a=Application(self.root)
        self.assertEqual(len(a.track()['zones']),128)
        self.assertEqual([[z['start'],z['end']] for z in a.track()['zones']],expected)
        a.keyboard_root=112
        self.assertEqual([a.performance_notes(i) for i in range(16)],[[i] for i in range(112,128)])

    def test_group_apply_cannot_silently_discard_slices_over_16(self):
        a=self.a;self.ranges(17);before=copy.deepcopy(a.project);a.actions=[];undo=len(a.undo)
        a.apply_slices(0,None,'CREATE')
        self.assertEqual(a.message,'OVER 16: APPLY TO SOUND')
        self.assertEqual(a.project,before);self.assertEqual(a.actions,[]);self.assertEqual(len(a.undo),undo)

    def test_group_apply_restores_pad_playing_and_exact_slice_count(self):
        a=self.a;expected=copy.deepcopy(a.slice_ranges());a.velocities16=True;a.apply_slices(1,None,'NONE')
        self.assertFalse(a.velocities16 or a.keyboard_enabled)
        self.assertEqual([(p['start'],p['end']) for p in a.project['groups'][1]['pads'][:4]],list(map(tuple,expected)))
        a.actions=[];a.pad_on(2)
        self.assertIn(('hit',(1,2,100)),a.actions)
        self.assertEqual(sum(a.sound_present(i) for i in range(16)),4)

    def test_both_controllers_show_assigned_held_and_last_slice_and_keep_empty_pads_dark(self):
        a=self.a;a.apply_slices(0,0,'NONE')
        self.assertEqual(self.lights(),(FULL,DIM,DIM,DIM)+(OFF,)*12)
        a.pad_on(2);a.release_pad(2)
        self.assertEqual(self.lights(),(DIM,DIM,FULL,DIM)+(OFF,)*12)
        a.pad_on(2);a.pad_on(1)
        self.assertEqual(self.lights(),(DIM,FULL,FULL,DIM)+(OFF,)*12)
        a.release_pad(1);a.release_pad(2);a.pad_on(15)
        self.assertEqual(self.lights(),(DIM,FULL,DIM,DIM)+(OFF,)*12)
        rgb=leds(self.surface,self.channels,time.monotonic()+1)[2]
        for slot,value in enumerate(self.lights()):
            start=1+PAD_SLOTS.index(slot)*3
            self.assertEqual(tuple(rgb[start:start+3]),tuple(round(c*value/FULL) for c in PALETTE[0]))

    def test_chop_does_not_flash_unassigned_pads(self):
        a=self.a;a.slice_mode='MANUAL';a.slice_edit=True;a.pad_on(15)
        self.assertEqual(led_report(a,self.channels,time.monotonic())[16],OFF)

    def test_fresh_manual_sample_does_not_inherit_an_automatic_preview_count(self):
        a=self.a;a.track().pop('slices');a.slice_mode='MANUAL';a.slice_count=32
        self.assertEqual(a.slice_ranges(),[[0,12800]])
        a.open_sampling_page('CHOP');self.assertEqual(a.slice_count,1)

    def test_removing_last_applied_zone_cannot_resurrect_it_from_slice_source(self):
        a=self.a;a.apply_slices(0,0,'NONE');a.open_sampling_page('ZONE')
        for _ in range(4):
            a.button('SHIFT',True);a.button('F3',True);a.button('SHIFT',False)
        self.assertEqual(a.track()['zones'],[]);self.assertIsNone(a.track()['sample'])
        a.open_sampling_page('CHOP');self.assertEqual(a.slice_ranges(),[])
        a.save();restored=Application(self.root);restored.open_sampling_page('CHOP')
        self.assertIsNone(restored.track()['sample']);self.assertEqual(restored.slice_ranges(),[])

    def test_mk2_slice_tiles_follow_slice_bank(self):
        from app import fokus_mk2
        a=self.a;self.ranges(32);a.slice_bank=1;a.slice_index=17
        state=snapshot(self.surface);renderer=Mk2Renderer();self.addCleanup(renderer.close)
        with patch.object(fokus_mk2,'tiles',wraps=fokus_mk2.tiles) as draw:
            fokus_mk2.render(state,renderer)
        items=draw.call_args.args[1]
        self.assertEqual([row[0] for row in items],[str(i) for i in range(17,33)])
        self.assertEqual([i for i,row in enumerate(items) if row[2]],[1])

    def test_slice_keyboard_controls_use_slice_banks_even_with_custom_chord_settings(self):
        a=self.a;self.ranges(32);a.performance()['chord_mode']='CUSTOM';a.apply_slices(0,0,'NONE')
        a.page='PAD CONFIG'
        self.assertEqual(a.softkeys(),('KEYBD','BANK-','BANK+'))
        a.button('F3',True);self.assertEqual(a.keyboard_root,16)
        self.assertEqual(a.performance_notes(0),[16])
        self.assertEqual(self.surface.softkeys()[4:6],('BANK-','BANK+'))
        self.assertEqual([row.label for row in self.surface.fields() if row],['FIRST SLICE'])

    def test_slice_apply_and_bank_selection_preserve_the_other_sounds_keyboard_root(self):
        a=self.a;a.performance()['root']=48;a.keyboard_root=48
        a.apply_slices(0,0,'NONE');self.assertEqual(a.keyboard_root,0)
        self.assertEqual(a.performance()['root'],48)
        a.page='PAD CONFIG';self.surface.softkey(5)
        self.assertEqual(a.performance()['root'],48)
        a.select_sound(1);self.assertEqual(a.keyboard_root,48)
        a.select_sound(0);self.assertEqual(a.keyboard_root,0)

    def test_last_slice_highlight_stays_with_the_slice_when_changing_banks(self):
        a=self.a;self.ranges(32);a.apply_slices(0,0,'NONE')
        a.pad_on(3);a.release_pad(3);a.keyboard_root=16
        self.assertEqual(self.lights(),(DIM,)*16)
        a.pad_on(4);a.release_pad(4)
        self.assertEqual(self.lights()[4],FULL)
        a.keyboard_root=0;self.assertEqual(self.lights(),(DIM,)*16)
