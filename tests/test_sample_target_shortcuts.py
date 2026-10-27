"""Target selection stays inside the workspace; direct shortcuts survive release."""
import copy
import tempfile
import unittest
import wave
from pathlib import Path
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.mk2_surface import Mk2Surface
from app.mk2_display import snapshot

class SampleTargetShortcutTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=Application(self.tmp.name);self.inputs=ControllerInputs(self.a)
        self.mk2=Mk2Surface(self.a,self.inputs)
        self.sample=Path(self.tmp.name)/'samples/Test.wav'
        with wave.open(str(self.sample),'wb') as w:
            w.setparams((1,2,44100,0,'NONE','not compressed'));w.writeframes(b'\x00\x10'*1000)

    def button(self,source,key,pressed):
        if source=='mk2':self.mk2.button(key,pressed)
        else:self.inputs.button(source,key,pressed)

    def test_direct_shortcuts_both_devices_and_release_orders(self):
        a=self.a
        for source in ('mk2','mikro'):
            for key,page in (('SAMPLING','SAMPLE EDIT'),('SELECT','PATTERN GRID')):
                for shift_first in (False,True):
                    with self.subTest(source=source,key=key,shift_first=shift_first):
                        a.page='BROWSE';a.keyboard_enabled=False;a.velocities16=True
                        a.mode_origins[key]='BROWSE';before=copy.deepcopy(a.project)
                        self.button(source,'SHIFT',True);self.button(source,key,True)
                        for release in (('SHIFT',key) if shift_first else (key,'SHIFT')):self.button(source,release,False)
                        self.assertEqual(a.page,page);self.assertNotIn(key,a.mode_origins)
                        self.assertFalse(any(k in ('save','capture_stop') for k,v in a.actions))
                        if key=='PAD MODE':self.assertTrue(a.keyboard_enabled);self.assertFalse(a.velocities16)
                        self.assertEqual(a.project,before);self.assertEqual(a.pinned_modes,set())

    def test_shift_pad_mode_toggles_on_all_controllers_without_pin_changes(self):
        from app.mk1_session import Mk1Surface
        mk1=Mk1Surface(self.a,self.inputs)
        for source,surface in [('mikro',None),('mk1',mk1),('mk2',self.mk2)]:
            for shift_first in (False,True):
                with self.subTest(source=source,shift_first=shift_first):
                    a=self.a;a.page='CHANNEL';a.keyboard_enabled=False;a.velocities16=True
                    pinned=set(a.pinned_modes)
                    def button(key,pressed):
                        if surface:surface.button(key,pressed)
                        else:self.inputs.button(source,key,pressed)
                    for enabled in (True,False,True,False):
                        button('SHIFT',True);button('PAD MODE',True)
                        self.assertEqual(a.keyboard_enabled,enabled)
                        # Duplicate physical reports must not toggle twice.
                        button('PAD MODE',True);self.assertEqual(a.keyboard_enabled,enabled)
                        for key in (('SHIFT','PAD MODE') if shift_first else ('PAD MODE','SHIFT')):button(key,False)
                        self.assertEqual(a.keyboard_enabled,enabled);self.assertEqual(a.page,'CHANNEL')
                        self.assertFalse(a.velocities16);self.assertEqual(a.pinned_modes,pinned)

    def test_shortcut_does_not_latch_a_temporarily_held_pad_mode(self):
        a=self.a;a.page='CHANNEL';a.pinned_modes.clear()
        self.button('mk2','PAD MODE',True);self.assertEqual(a.page,'PAD CONFIG')
        self.button('mk2','SHIFT',True)
        # Release/repress while SHIFT remains down uses the shortcut.
        self.button('mk2','PAD MODE',False);self.assertEqual(a.page,'CHANNEL')
        self.button('mk2','PAD MODE',True);self.assertTrue(a.keyboard_enabled)
        self.button('mk2','PAD MODE',False);self.button('mk2','SHIFT',False)
        self.assertEqual(a.page,'CHANNEL');self.assertNotIn('PAD MODE',a.pinned_modes)

    def test_browse_target_with_and_without_prehear_loads_to_selected_slot(self):
        a=self.a;a.audio=type('Audio',(),{})()
        for prehear in (True,False):
            a.page='BROWSE';a.browser.directory=self.sample.parent;a.browser.index=0;a.browser.prehear=prehear
            for pad in (2,7):
                a.actions.clear();self.inputs.pad_on('mk2',pad,99);self.inputs.pad_off('mk2',pad)
                self.assertEqual((a.page,a.pad),('BROWSE',pad))
                self.assertEqual(a.browser.selected(),self.sample);self.assertEqual(a.browser.prehear,prehear)
                self.assertIn('preview' if prehear else 'controller_hit',[k for k,v in a.actions])
                self.assertEqual(snapshot(self.mk2)['sample_target'],f'A:{pad+1:02}')
                a.enter();self.assertEqual(a.project['groups'][0]['pads'][pad]['sample'],str(self.sample.resolve()))
                self.assertEqual(a.page,'BROWSE')
        self.assertIsNone(a.project['groups'][0]['pads'][0]['sample'])

    def test_record_selection_preserves_capture_and_does_not_record_pattern(self):
        a=self.a;a.page='SAMPLING';a.playing=True;a.recording=True;a.capture_started=12.5;a.capture_armed=True
        before=copy.deepcopy(a.project);a.actions.clear()
        self.inputs.pad_on('mk2',4,100);self.inputs.pad_on('mk2',8,100)
        self.inputs.pad_off('mk2',4);self.inputs.pad_off('mk2',8)
        self.assertEqual((a.page,a.pad,a.capture_started,a.capture_armed),('SAMPLING',8,12.5,True))
        self.assertEqual(a.project,before)
        hits=[v for k,v in a.actions if k=='controller_hit'];self.assertEqual([v[1] for v in hits],[4,8])
        self.assertNotIn('capture_stop',[k for k,v in a.actions])
        self.assertEqual(snapshot(self.mk2)['sample_target'],'A:09')

    def test_manual_slice_and_keyboard_audition_keep_their_pad_roles(self):
        a=self.a;a.track().update(sample=str(self.sample),start=0,end=1000)
        a.open_sampling_page('CHOP');a.slice_mode='MANUAL';a.actions.clear()
        self.inputs.pad_on('mk2',0,100);self.inputs.pad_off('mk2',0)
        self.assertEqual(a.pad,0);self.assertTrue(a.track().get('slices'))
        self.button('mk2','SELECT',True);self.inputs.pad_on('mk2',5,100);self.inputs.pad_off('mk2',5)
        self.button('mk2','SELECT',False)
        self.assertEqual((a.page,a.pad),('CHOP',5))
        self.assertTrue(a.project['groups'][0]['pads'][0]['slices'])

    def test_empty_target_led_visible_even_with_keyboard_enabled(self):
        from app.leds import led_report,FULL,OFF
        a=self.a;a.keyboard_enabled=True;a.pad=7
        channels={(slot,'orange'):slot for slot in range(16)}
        for page in ('BROWSE','SAMPLING'):
            a.page=page;report=led_report(a,channels,now=0)
            self.assertEqual(report[8],FULL);self.assertEqual(report[1],OFF)
