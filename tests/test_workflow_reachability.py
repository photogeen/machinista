"""Physical routes, not just renderable page names, for beta regressions."""
import tempfile
import unittest
from unittest.mock import patch
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.devices import AudioDevice, MidiDevice
from app.mk1_session import Mk1Surface
from app.mk2_surface import Mk2Surface
from app.mk2_encoders import choice_binding


class WorkflowReachabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=Application(self.tmp.name);self.inputs=ControllerInputs(self.a)

    @staticmethod
    def press(s,key):
        s.button(key,True);s.button(key,False)

    def test_mk1_and_mk2_device_selection_uses_visible_first_encoder(self):
        for cls in (Mk1Surface,Mk2Surface):
            a=self.a;s=cls(a,self.inputs)
            a.audio_devices=[AudioDevice('usb-a','USB A','plughw:1,0',None)]
            a.midi_devices=[MidiDevice('midi-a','USB MIDI','/tmp/midi')]
            for page,key,initial,wanted in (('AUDIO','audio','AUTO','usb-a'),('MIDI IN','midi_in','OFF','midi-a'),('MIDI OUT','midi_out','OFF','midi-a')):
                with self.subTest(controller=cls.source,page=page):
                    a.page=page;a.settings[key]=initial
                    self.assertEqual(s.fields()[0].label,'DEVICE')
                    self.assertTrue(choice_binding(s,s.fields()[0]))
                    s.rotate(1,1);self.assertEqual(a.settings[key],wanted)
                    self.assertIn('USB',s.fields()[0].value)

    def test_settings_routing_cue_delay_and_scene_length_have_real_bindings(self):
        for cls in (Mk1Surface,Mk2Surface):
            a=self.a;s=cls(a,self.inputs)
            for page in ('MAIN OUTPUT','CUE OUTPUT','CUE LEVEL','PLUGIN DELAY','SCENE'):
                with self.subTest(controller=cls.source,page=page):
                    a.page=page;self.assertIsNotNone(s.fields()[0])
            a.page='CUE LEVEL';a.settings['cue_level']=50;s.rotate(1,3)
            self.assertEqual(a.settings['cue_level'],53)
            a.page='PLUGIN DELAY';a.settings['plugin_delay']=False;s.rotate(1,1)
            self.assertTrue(a.settings['plugin_delay'])
            a.page='SCENE';before=a.scene_steps();s.rotate(1,1)
            self.assertEqual(a.scene_steps(),before+16)

    def test_midi_learn_keys_match_their_actual_actions_and_list_scrolls(self):
        for cls in (Mk1Surface,Mk2Surface):
            a=self.a;s=cls(a,self.inputs);a.page='MIDI LEARN'
            a.project['midi_mappings']={'a':{},'b':{}};a.midi_map_index=0
            self.assertEqual(s.softkeys()[:3],('BACK','LEARN','REMOVE'))
            s.rotate(1,1);self.assertEqual(a.midi_map_index,1)
            a.page='SONG AUTO';a.project['master_automation']={'a':{},'b':{}};a.midi_map_index=0
            self.assertEqual(s.softkeys()[:3],('BACK','ON/OFF','REMOVE'))
            s.rotate(1,1);self.assertEqual(a.midi_map_index,1)

    def test_shift_browse_find_is_visible_and_calls_existing_quickbrowse(self):
        for cls in (Mk1Surface,Mk2Surface):
            a=self.a;s=cls(a,self.inputs);a.page='BROWSE'
            s.button('SHIFT',True)
            with patch.object(a,'quick_browse_sample') as find:
                self.assertEqual(s.softkeys()[1],'FIND');self.press(s,'DISPLAY 2');find.assert_called_once()
            s.button('SHIFT',False)

    def test_held_mode_pin_does_not_steal_displaced_action_or_song_insert(self):
        for cls in (Mk1Surface,Mk2Surface):
            a=self.a;a.page='PAD';a.pinned_modes.clear();s=cls(a,self.inputs)
            s.button('DUPLICATE',True)
            self.assertEqual(s.softkeys()[0],'PIN');self.assertEqual(s.softkeys()[3],'+ EVNT')
            before=a.duplicate_events;self.press(s,'DISPLAY 4');self.assertNotEqual(a.duplicate_events,before)
            s.button('DUPLICATE',False)
            s.button('SCENE',True);self.press(s,'DISPLAY 1')
            self.assertIn('SCENE',a.pinned_modes)
            s.button('SHIFT',True);self.press(s,'DISPLAY 2');s.button('SHIFT',False)
            self.assertEqual(a.page,'SONG');self.assertEqual(s.softkeys()[0],'INSERT')
            before=len(a.project['song']);self.press(s,'DISPLAY 1')
            self.assertEqual(len(a.project['song']),before+1)
            s.button('SCENE',False)

    def test_full_size_quantize_can_apply_without_an_encoder_push(self):
        a=self.a;s=Mk1Surface(a,self.inputs);s.button('GRID',True)
        self.assertEqual(s.softkeys()[0],'PIN');self.assertEqual(s.softkeys()[3],'QUANT')
        self.press(s,'DISPLAY 4');self.assertEqual(a.grid_tab,0)
        self.assertEqual(s.softkeys()[7],'APPLY')
        with patch.object(a,'quantize_pattern') as quantize:
            self.press(s,'DISPLAY 8');quantize.assert_called_once()
        s.button('GRID',False)

    def test_full_size_scene_and_pattern_bank_page_buttons(self):
        for cls in (Mk1Surface,Mk2Surface):
            a=self.a;s=cls(a,self.inputs)
            for mode in ('SCENE','PATTERN'):
                a.page='PAD';a.pinned_modes.clear();s.button(mode,True);s.button('SHIFT',True)
                self.press(s,'PAGE RIGHT');self.assertEqual(getattr(a,mode.lower()+'_bank'),1)
                self.assertTrue(s.page_directions()[0]);self.press(s,'PAGE LEFT')
                self.assertEqual(getattr(a,mode.lower()+'_bank'),0)
                s.button('SHIFT',False);s.button(mode,False)

    def test_scene_tools_reachable_on_mikro_and_fullsize_with_delete_confirmation(self):
        a=self.a;a.button('SCENE',True);a.button('SHIFT',True);a.button('F1',True);a.button('F1',False);a.button('SHIFT',False)
        self.assertEqual(a.page,'SCENE OPTIONS');self.assertEqual(a.softkeys()[:2],('BACK','SELECT'))
        a.project['scene_lengths']['0']=64
        a.button('F2',True);a.button('F2',False)
        self.assertEqual(a.page,'SCENE');self.assertNotIn('0',a.project['scene_lengths'])
        for cls in (Mk1Surface,Mk2Surface):
            a.page='PAD';a.pinned_modes.clear();s=cls(a,self.inputs)
            s.button('SCENE',True);s.button('SHIFT',True)
            self.assertEqual(s.softkeys()[3],'OPTIONS');self.press(s,'DISPLAY 4');s.button('SHIFT',False)
            self.assertEqual(a.page,'SCENE OPTIONS')
            with patch.object(a,'unique_scene') as unique:
                s.rotate(1,1);self.press(s,'DISPLAY 2')
                self.assertEqual(a.page,'CONFIRM');self.press(s,'DISPLAY 2');unique.assert_called_once()
            a.page='SCENE OPTIONS'
            with patch.object(a,'delete_scene') as delete:
                s.rotate(1,1);self.press(s,'DISPLAY 2');self.assertEqual(a.page,'CONFIRM')
                self.press(s,'DISPLAY 2');delete.assert_called_once()
            s.button('SCENE',False)

    def test_song_cursor_uses_e1_on_mk1_without_changing_sound(self):
        a=self.a;s=Mk1Surface(a,self.inputs);a.page='SONG';a.project['song']=[0,1,2];a.song_index=0
        gain=a.track()['gain'];s.rotate(1,1)
        self.assertEqual(a.song_index,1);self.assertEqual(a.track()['gain'],gain)

    def test_live_fx_exits_via_navigation_with_off_recorded_and_held_pad_safe(self):
        a=self.a
        for cls in (Mk1Surface,Mk2Surface):
            for key,page in (('BROWSE','BROWSE'),('SAMPLING','SAMPLING'),('CONTROL',a.control_home()),('STEP','STEP')):
                with self.subTest(controller=cls.source,key=key):
                    s=cls(a,self.inputs);a.page='PAD';a.open_live_fx();a.live_fx_mode=1
                    a.live_fx_pad_on(2,100,owner=cls.source);self.assertNotEqual(a.live_fx_current,0)
                    self.press(s,key);self.assertEqual(a.page,page);self.assertEqual(a.live_fx_current,0)
                    self.assertFalse(a.live_fx_held);self.assertFalse(a.live_fx_pad_off(2,owner=cls.source))

    def test_device_reset_has_visible_action_and_only_changes_its_controller(self):
        for cls in (Mk1Surface,Mk2Surface):
            a=self.a;s=cls(a,self.inputs);a.page='PAD SENS'
            a.settings['pad_sensitivity']=75
            a.settings['controllers'][cls.source]['pad_sensitivity']=150
            self.assertEqual(s.softkeys()[1],'RESET');self.press(s,'DISPLAY 2')
            self.assertEqual(a.settings['controllers'][cls.source]['pad_sensitivity'],100)
            self.assertEqual(a.settings['pad_sensitivity'],75)
            a.page='BRIGHTNESS';a.settings['controllers'][cls.source]['brightness']=17
            self.press(s,'DISPLAY 2')
            self.assertEqual(a.settings['controllers'][cls.source]['brightness'],72 if cls.source=='mk1' else 100)

    def test_scene_loop_and_mute_all_actions_are_available_while_holding_mode(self):
        for cls in (Mk1Surface,Mk2Surface):
            a=self.a;s=cls(a,self.inputs);a.pinned_modes.clear();a.page='PAD'
            s.button('SCENE',True);self.assertEqual(s.softkeys()[3],'ALL')
            self.press(s,'DISPLAY 4');self.assertIsNotNone(a.loop_range)
            s.button('SCENE',False);s.button('MUTE',True)
            self.assertEqual(s.softkeys()[3],'ALL ON')
            self.press(s,'DISPLAY 2')
            self.assertTrue(all(p['mute'] for p in a.project['groups'][a.group]['pads']))
            self.press(s,'DISPLAY 4')
            self.assertFalse(any(p['mute'] for p in a.project['groups'][a.group]['pads']))
            s.button('MUTE',False)

    def test_project_load_and_new_do_not_keep_an_invisible_latched_effect(self):
        a=self.a;a.save_as();a.name_value='BEFORE';a.finish_project_name();path=a.active_project_file()
        for operation in ('LOAD','NEW'):
            a.open_live_fx();a.live_fx_mode=1;a.live_fx_pad_on(4,100,owner='mk1');a.actions.clear()
            if operation=='LOAD':a.load_project(path)
            else:a.start_new();a.name_value='AFTER';a.finish_project_name()
            self.assertEqual(a.live_fx_current,0);self.assertFalse(a.live_fx_held)
            self.assertTrue(any(action=='live_fx' and value[1:4]==(0,0,0) for action,value in a.actions))

    def test_mikro_live_fx_does_not_keep_pixels_from_the_previous_workspace(self):
        from app.fokus import utility
        a=self.a;a.open_live_fx();a.message=''
        clean=utility(a,bytes(128*64));dirty=utility(a,bytes([1])*(128*64))
        self.assertEqual(clean,dirty)
        a.live_fx_pad=1;self.assertNotEqual(clean,utility(a,bytes(128*64)))
