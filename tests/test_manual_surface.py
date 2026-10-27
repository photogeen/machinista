import copy
from pathlib import Path
import sys
import tempfile
import unittest
import wave
import array
from app.model import Application
from app.leds import led_report,OFF,DIM,FULL
from app.sample_edit import process_sample
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'tools'))
from mikro_leds import load_pad_channels
from machinista import display_pixels
ROOT=Path(__file__).resolve().parent.parent

class ManualSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.app=Application(self.temp.name)
        self.channels=load_pad_channels(ROOT/'captures/mikro-mk1-pad-led-map.json')
        import json
        self.app.button_led_map=json.loads((ROOT/'captures/mikro-mk1-button-led-map.json').read_text())['buttons']
    def tearDown(self):self.temp.cleanup()
    def pad_led(self,r,slot,color='orange'):return r[self.channels[(slot,color)]+1]
    def test_shift_mute_chokes_globally_on_both_controllers(self):
        from app.ui_inventory import PAGES
        from app.controller_inputs import ControllerInputs
        from app.mk2_surface import Mk2Surface
        a=self.app;surface=Mk2Surface(a,ControllerInputs(a))
        before=copy.deepcopy(a.project)
        for controller in ('mikro','mk2'):
            button=surface.button if controller=='mk2' else a.button
            for page in PAGES:
                with self.subTest(controller=controller,page=page):
                    a.page=page;a.actions=[];a.playing=a.recording=True
                    a.live_chop_started=100;a.live_chop_key=('sample',0,100)
                    a.repeat_pads.add(0);a.arp_notes.add(60);a.arp_played.append(60)
                    button('SHIFT',True);button('MUTE',True)
                    self.assertEqual(a.page,page)
                    self.assertEqual(a.actions,[('preview_stop',None),('panic',None)])
                    self.assertEqual(a.message,'CHOKE ALL NOTES')
                    self.assertIsNone(a.live_chop_started)
                    self.assertIsNone(a.live_chop_key)
                    self.assertFalse(a.repeat_pads or a.arp_notes or a.arp_played)
                    button('MUTE',False);button('SHIFT',False)
                    self.assertTrue(a.playing and a.recording)
                    self.assertEqual(a.project,before)
    def test_applied_slice_keyboard_lights_only_mapped_notes(self):
        a=self.app;path=Path(self.temp.name)/'slices.wav'
        with wave.open(str(path),'wb') as w:
            w.setparams((1,2,1000,0,'NONE','not compressed'));w.writeframes(array.array('h',[0]*1000).tobytes())
        a.track().update(sample=str(path),start=0,end=1000,slices=[[0,250],[250,500],[500,750],[750,1000]])
        a.apply_slices(0,0,'NONE')
        self.assertTrue(a.keyboard_enabled)
        r=led_report(a,self.channels,100)
        self.assertEqual([self.pad_led(r,i) for i in range(16)],[FULL,DIM,DIM,DIM]+[OFF]*12)
        a.held_pads.add(1);a.held_pads.add(7);a.flash_until[7]=200
        r=led_report(a,self.channels,100)
        self.assertEqual(self.pad_led(r,1),FULL);self.assertEqual(self.pad_led(r,7),OFF)
        a.keyboard_root=4
        self.assertTrue(all(self.pad_led(led_report(a,self.channels,100),i)==OFF for i in range(16)))
        a.keyboard_root=0;a.track()['source']='MIDI'
        self.assertTrue(all(self.pad_led(led_report(a,self.channels,100),i)>OFF for i in range(16)))
        a.track()['source']='SAMPLE';a.apply_slices(0,None,'NONE')
        self.assertFalse(a.keyboard_enabled)

    def test_temporary_modes_return_and_pin_persists(self):
        a=self.app;a.page='BROWSE';a.button('MUTE',True);self.assertEqual(a.page,'MUTE')
        a.button('MUTE',False);self.assertEqual(a.page,'BROWSE')
        a.button('PATTERN',True);a.button('MAIN',True);a.button('MAIN',False);a.button('PATTERN',False)
        self.assertEqual(a.page,'PATTERN');self.assertIn('PATTERN',Application(self.temp.name).pinned_modes)
        a.button('SHIFT',True);a.button('MAIN',True);a.button('SHIFT',False);self.assertEqual(a.page,'SETTINGS')
    def test_mute_solo_leds_match_audibility_and_empty_is_off(self):
        a=self.app;a.project['groups'][0]['pads'][0]['source']='MIDI';a.project['groups'][0]['pads'][1]['source']='MIDI'
        a.page='MUTE';r=led_report(a,self.channels,now=100)
        self.assertEqual([self.pad_led(r,i) for i in range(3)],[FULL,FULL,OFF])
        a.pad_on(1);r=led_report(a,self.channels,now=100)
        self.assertEqual(self.pad_led(r,1),DIM)
        a.button('F1',True);self.assertFalse(any(t['mute'] for t in a.project['groups'][0]['pads']))
        a.page='SOLO';a.pad_on(0);r=led_report(a,self.channels,now=100)
        self.assertEqual([self.pad_led(r,i) for i in range(2)],[FULL,DIM])
        a.button('F2',True);self.assertTrue(all(t['mute'] for t in a.project['groups'][0]['pads']))
    def test_unknown_led_channels_off_and_transport_states(self):
        a=self.app;r=led_report(a,self.channels,100)
        self.assertTrue(all(r[i+1]==0 for i in range(52,60)))
        self.assertEqual(r[11],DIM) # PLAY payload 10.
        a.button('PLAY',True);a.button('REC',True);r=led_report(a,self.channels,100)
        self.assertEqual((r[11],r[10]),(FULL,FULL))
    def test_original_step_bindings_double_follow_fixed_velocity(self):
        a=self.app;a.page='STEP';a.pad_on(0);a.button('F2',True)
        self.assertEqual(len(a.lane()),32);self.assertTrue(a.lane()[16]);self.assertTrue(a.lane()[0])
        a.playing=True;a.step=15;a.tick();self.assertEqual(a.bank,1)
        a.button('NAV LEFT',True);self.assertEqual(a.bank,0);self.assertFalse(a.follow)
        a.button('F3',True);self.assertFalse(a.fixed_velocity)
        self.assertEqual(a.softkeys(),('FOLLOW','DOUBLE','FIX VEL'))
    def test_undo_redo_and_browser_select_quiet_overlay(self):
        a=self.app;a.page='STEP';a.pad_on(0);a.button('SHIFT',True);a.pad_on(0)
        self.assertFalse(a.lane()[0]);a.pad_on(1);self.assertTrue(a.lane()[0]);a.button('SHIFT',False)
        a.page='BROWSE';a.button('SELECT',True);a.actions=[];a.pad_on(3)
        self.assertEqual(a.pad,3);self.assertEqual(a.actions,[]);a.button('SELECT',False);self.assertEqual(a.page,'BROWSE')
    def test_repeat_runs_without_transport_and_stops_on_release(self):
        a=self.app;a.button('NOTE REPEAT',True);a.pad_on(2);a.repeat_tick(0)
        self.assertIn(('hit',(0,2,100)),a.actions);self.assertFalse(a.playing)
        a.actions=[];a.release_pad(2);a.repeat_tick(1);self.assertFalse(any(kind=='hit' for kind,value in a.actions))
        self.assertNotIn(2,a.repeat_pads)
    def test_selection_process_preserves_outside_and_original(self):
        path=Path(self.temp.name)/'tone.wav'
        with wave.open(str(path),'wb') as w:
            w.setnchannels(1);w.setsampwidth(2);w.setframerate(48000);w.writeframes(array.array('h',[100,200,300,400,500]).tobytes())
        original=path.read_bytes();track={'sample':str(path),'start':0,'end':5,'selection_start':1,'selection_end':4}
        result,count=process_sample(track,'REVERSE',Path(self.temp.name)/'edited')
        with wave.open(str(result),'rb') as w:values=array.array('h',w.readframes(5))
        self.assertEqual(list(values),[100,400,300,200,500]);self.assertEqual(count,5);self.assertEqual(path.read_bytes(),original)
    def test_control_scope_changes_real_gain(self):
        a=self.app;a.button('F1',True);a.rotate(-10);self.assertEqual(a.project['gain'],90)
        a.button('F2',True);a.rotate(-20);self.assertEqual(a.project['groups'][0]['gain'],80)
        a.button('F3',True);a.rotate(-5);self.assertEqual(a.track()['gain'],75)
        self.assertEqual(len(display_pixels(a)),8192)

    def test_scene_loop_and_duplicate_to_selected_target(self):
        a=self.app;a.page='SCENE';a.pad_on(1);a.pad_on(3)
        self.assertEqual(a.loop_range,(1,3));a.release_pad(1);a.release_pad(3)
        a.scene=3;a.playing=True;a.step=15;a.tick();self.assertEqual(a.scene,1)
        a.page='PAD';a.track()['gain']=45;a.button('DUPLICATE',True);a.pad_on(0);a.pad_on(4)
        self.assertEqual(a.page,'CONFIRM');a.button('DUPLICATE',False);self.assertEqual(a.page,'CONFIRM')
        a.button('F2',True);self.assertEqual(a.project['groups'][0]['pads'][4]['gain'],45)

        a.project['scenes'][15][0]=2
        before=copy.deepcopy(a.project['scenes']);a.duplicate_scene()
        self.assertEqual(len(a.project['scenes']),32)
        self.assertEqual(a.project['scenes'][16],before[-1])
        a.save();self.assertEqual(a.undo,[]);self.assertEqual(a.redo,[])

    def test_navigation_selects_parameters_without_changing_values(self):
        a=self.app
        for page,field,count in [('PAD CONFIG','pad_field',6),('SAMPLE EDIT','sample_field',2),
                                 ('CHOP','slice_field',5),('EVENT','event_field',3),
                                 ('OPTIONS','grid_field',4),('MIDI TRACK','track_field',3)]:
            a.page=page;setattr(a,field,0);before=copy.deepcopy(a.project)
            for _ in range(count+1):a.button('NAV RIGHT',True)
            self.assertEqual(getattr(a,field),count-1)
            for _ in range(count+1):a.button('NAV LEFT',True)
            self.assertEqual(getattr(a,field),0);self.assertEqual(a.project,before)
        a.page='PAD';before=copy.deepcopy(a.project);a.button('NAV RIGHT',True)
        self.assertEqual(a.project,before)
        a.page='OPTIONS';a.button('NAV RIGHT',True);a.rotate(1)
        self.assertEqual(a.project,before)
        a.page='SAMPLE EDIT';a.button('NAV',True);a.button('NAV RIGHT',True)
        self.assertEqual(a.range_page,1);self.assertEqual(a.page,'SAMPLING NAV')
        a.button('NAV',False);self.assertEqual(a.page,'SAMPLE EDIT')

    def test_transport_arrows_seek_bars_and_shift_steps_without_editing(self):
        a=self.app;a.double_pattern();before=copy.deepcopy(a.project)
        a.step=0;a.button('TRANSPORT RIGHT',True);self.assertEqual(a.step,16)
        a.button('TRANSPORT LEFT',True);self.assertEqual(a.step,0)
        a.button('SHIFT',True);a.button('TRANSPORT LEFT',True);self.assertEqual(a.step,31)
        a.button('TRANSPORT RIGHT',True);self.assertEqual(a.step,0);a.button('SHIFT',False)
        a.page='STEP';a.button('TRANSPORT RIGHT',True)
        self.assertEqual(a.step,16);self.assertEqual(a.bank,1);self.assertTrue(a.follow)
        for page in ('PAD','MIXER','OPTIONS','MIDI TRACK','SAMPLE EDIT','SETTINGS'):
            a.page=page;a.button('TRANSPORT RIGHT',True);a.button('TRANSPORT LEFT',True)
        self.assertEqual(a.project,before)

    def test_transport_short_manual_scene_does_not_truncate_long_pattern_navigation(self):
        a=self.app;a.set_pattern_length(64);a.project['scene_lengths'][str(a.scene)]=16
        before=copy.deepcopy(a.project);a.clock_phase=0;a.step=0
        a.button('TRANSPORT RIGHT',True);a.button('TRANSPORT RIGHT',False)
        self.assertEqual((a.clock_phase,a.pattern_position()),(384,'2:1:1'))
        a.clock_phase=864;a.step=36 # 3:2:1
        a.button('TRANSPORT LEFT',True);a.button('TRANSPORT LEFT',False)
        self.assertEqual((a.clock_phase,a.pattern_position()),(480,'2:2:1'))
        a.button('TRANSPORT LEFT',True);a.button('TRANSPORT LEFT',False)
        self.assertEqual((a.clock_phase,a.pattern_position()),(96,'1:2:1'))
        a.button('SHIFT',True);a.button('TRANSPORT RIGHT',True);a.button('TRANSPORT RIGHT',False);a.button('SHIFT',False)
        self.assertEqual(a.clock_phase,120);self.assertEqual(a.project,before)
        a.clock_phase=864;a.step=36;a.transport_repeat={'TRANSPORT LEFT':10}
        a.transport_repeat_tick(10);self.assertEqual(a.clock_phase,480)
        a.transport_repeat_tick(10.25);self.assertEqual(a.clock_phase,96)

    def test_transport_hold_repeats_every_quarter_second_and_release_stops(self):
        from unittest.mock import patch
        a=self.app;a.double_pattern();a.double_pattern();a.step=0
        with patch('app.surface.time.monotonic',return_value=10):
            a.button('TRANSPORT RIGHT',True)
        self.assertEqual(a.step,16)
        a.transport_repeat_tick(10.24);self.assertEqual(a.step,16)
        a.transport_repeat_tick(10.25);self.assertEqual(a.step,32)
        a.transport_repeat_tick(10.49);self.assertEqual(a.step,32)
        a.button('SHIFT',True);a.transport_repeat_tick(10.5);self.assertEqual(a.step,33)
        a.button('TRANSPORT RIGHT',False);a.transport_repeat_tick(12);self.assertEqual(a.step,33)
        with patch('app.surface.time.monotonic',return_value=12):
            a.button('TRANSPORT LEFT',True)
        self.assertEqual(a.step,32);a.transport_repeat_tick(12.25);self.assertEqual(a.step,31)
        a.transport_repeat_tick(20);self.assertEqual(a.step,30)
        a.button('TRANSPORT LEFT',False);a.transport_repeat_tick(21);self.assertEqual(a.step,30)

    def test_main_pins_modes_and_shift_padmode_switches_keyboard(self):
        a=self.app
        for button,page in [('SCENE','SCENE'),('PAD MODE','PAD CONFIG'),('PATTERN','PATTERN')]:
            a.page='PAD';a.button(button,True);a.button('MAIN',True);a.button('MAIN',False);a.button(button,False)
            self.assertEqual(a.page,page);self.assertIn(button,a.pinned_modes)
            a.button(button,True);a.button(button,False);self.assertEqual(a.page,'PAD')
        a.button('SHIFT',True);a.button('PAD MODE',True);a.button('SHIFT',False)
        self.assertTrue(a.keyboard_enabled)
