import tempfile
import copy
from pathlib import Path
import wave
import unittest
from unittest.mock import Mock,patch
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.mk2_surface import Mk2Surface
from app.mk2_display import snapshot,Mk2Renderer,leds
from app.settings_menu import SETTING_PAGES


class Mk2SurfaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=Application(self.tmp.name);self.inputs=ControllerInputs(self.a)
        self.s=Mk2Surface(self.a,self.inputs)
    def press(self,name):self.s.button(name,True);self.s.button(name,False)

    def test_pad_pin_highlight_and_led_follow_real_pin_state(self):
        self.patch_leds=patch('app.mk2_display.led_reports',side_effect=lambda buttons,pads,groups:buttons)
        self.patch_leds.start();self.addCleanup(self.patch_leds.stop)
        a=self.a;a.page='CHANNEL';a.pinned_modes.discard('PAD MODE')
        self.s.button('PAD MODE',True)
        self.assertEqual(self.s.softkeys()[0],'PIN')
        self.assertNotIn(0,snapshot(self.s)['active_left'])
        self.assertEqual(leds(self.s,{})['DISPLAY 1'],25)
        self.s.softkey(0)
        self.assertIn('PAD MODE',a.pinned_modes)
        self.assertIn(0,snapshot(self.s)['active_left'])
        self.assertEqual(leds(self.s,{})['DISPLAY 1'],85)
        self.s.softkey(0)
        self.assertNotIn(0,snapshot(self.s)['active_left'])
        self.assertEqual(leds(self.s,{})['DISPLAY 1'],25)
        self.s.button('PAD MODE',False);a.page='PAD CONFIG'
        self.assertEqual(self.s.softkeys()[0],'PAD')
        self.assertIn(0,snapshot(self.s)['active_left'])

    def test_grid_tabs_highlight_show_only_relevant_fields_and_keep_pin(self):
        a=self.a;a.page='CHANNEL';self.s.button('GRID',True)
        with patch('app.mk2_display.led_reports',side_effect=lambda buttons,pads,groups:buttons):
            for key,tab,labels in ((2,2,['GRID','GRID ON','NUDGE','REC QUANT']),(1,1,['SWING']),(3,0,['STRENGTH','TARGET'])):
                self.s.softkey(key);self.assertEqual(a.grid_tab,tab)
                self.assertIn(key,snapshot(self.s)['active_left'])
                self.assertEqual(leds(self.s,{})['DISPLAY '+str(key+1)],85)
                self.assertEqual([f.label.upper() for f in self.s.fields() if f],labels)
                self.assertEqual(self.s.softkeys()[7],'APPLY' if tab==0 else '')
            self.s.softkey(0);self.assertIn('GRID',a.pinned_modes)
            self.s.button('GRID',False);self.assertEqual(a.page,'OPTIONS')
            self.assertEqual(self.s.softkeys()[0],'BACK');self.s.softkey(0)
            self.assertEqual(a.page,'CHANNEL')

    def test_quant_apply_moves_notes_but_tab_selection_does_not(self):
        a=self.a;a.page='OPTIONS';a.put_note(0,13,dict(velocity=90,note=36))
        a.timing().update(grid='1/16',grid_on=True,strength=100,target='GROUP')
        self.s.softkey(1);self.s.softkey(2);self.s.softkey(7)
        self.assertIn((0,13),a.notes())
        self.s.softkey(3);self.assertIn((0,13),a.notes())
        self.s.softkey(7);self.assertNotIn((0,13),a.notes());self.assertIn((0,24),a.notes())

    def test_grid_tab_encoders_change_only_visible_settings(self):
        a=self.a;a.page='OPTIONS';a.grid_tab=1
        old=a.timing()['strength'];self.s.rotate(1,5)
        self.assertEqual(a.timing()['swing'],5);self.assertEqual(a.timing()['strength'],old)
        self.s.softkey(3);self.s.rotate(1,-10);self.s.rotate(2,1)
        self.assertEqual(a.timing()['strength'],old-10);self.assertEqual(a.timing()['target'],'SOUND')
        self.s.softkey(2);self.s.rotate(2,-1);self.assertFalse(a.timing()['grid_on'])
        self.assertEqual(a.timing()['swing'],5)

    def test_repeat_eighth_triplets_and_selection_follow_actual_rate(self):
        a=self.a;a.page='NOTE REPEAT';a.project['repeat_presets']=[16,16,32,64]
        self.assertEqual(self.s.softkeys()[4:8],('1/8','1/16','1/32','1/64'))
        self.s.softkey(4)
        self.assertEqual(a.project['repeat_presets'][0],8)
        self.assertEqual(snapshot(self.s)['active_right'],(0,))
        self.assertEqual(self.s.fields()[0].value,'1/8')
        self.s.softkey(3)
        self.assertEqual(a.project['arp']['division'],'TRIPLET')
        self.assertIn(3,snapshot(self.s)['active_left'])
        self.s.softkey(6)
        self.assertEqual(snapshot(self.s)['active_right'],(2,))
        self.assertEqual(self.s.fields()[0].value,'1/32')
        a.project['arp']['rate']=8
        self.s.rotate(1,-1)
        self.assertEqual(self.s.fields()[0].value,'1/16')
        self.assertEqual(snapshot(self.s)['active_right'],(1,))
        self.s.softkey(3);self.assertEqual(a.project['arp']['division'],'DOTTED')
        self.s.softkey(3);self.assertEqual(a.project['arp']['division'],'NORMAL')
        self.assertNotIn(3,snapshot(self.s)['active_left'])

    def test_scope_channel_property_and_individual_parameter_columns(self):
        a=self.a;a.page='CHANNEL';self.s.softkey(1);self.assertEqual(a.control_level,1)
        self.s.rotate(3,-4);self.assertEqual(a.plugin_target()['gain'],96)
        self.s.rotate(4,12);self.assertEqual(a.plugin_target()['routing']['pan'],12)
        self.assertEqual(a.track()['gain'],80)
        self.s.softkey(2);self.assertEqual(a.control_level,2)
        a.track()['sample']='fixture.wav'
        self.s.softkey(5);self.assertEqual(a.page,'SAMPLER')

    def test_sampler_adsr_has_all_envelope_controls_in_right_columns(self):
        a=self.a;a.page='SAMPLER';a.sampler_page=1;a.track()['sampler']={'type':'ADSR'}
        self.assertEqual([f.label if f else None for f in self.s.fields()][4:],['ATTACK','DECAY','SUSTAIN','RELEASE'])
        self.s.rotate(7,-5);self.assertEqual(a.track()['sampler']['sustain'],95)
        self.s.rotate(8,2);self.assertEqual(a.track()['sampler']['release'],120)

    def test_plugin_slot_arrows_start_at_visible_sampler_not_stale_choice(self):
        a=self.a;a.page='SAMPLER';a.track()['sample']='fixture.wav';a.parameter_choice=3
        a.track()['plugins']=[dict(uri='urn:test:first',controls={},kind='EFFECT'),dict(uri='urn:test:second',controls={},kind='EFFECT')]
        self.s.softkey(7);self.assertEqual(a.page,'PLUGIN');self.assertEqual(a.plugin_slot,0)
        self.s.softkey(7);self.assertEqual(a.plugin_slot,1)
        self.s.softkey(6);self.assertEqual(a.plugin_slot,0)

    def test_mixer_knob_does_not_change_selection_and_shift_does_not_record(self):
        a=self.a;a.page='MIXER';a.selected_pads={0,1};a.sync_selection();a.playing=True;a.step=0;a.clock_phase=0
        self.s.button('SHIFT',True);self.s.rotate(3,5);self.s.button('SHIFT',False)
        self.assertEqual(a.selected_pads,{0,1});self.assertEqual(a.pad,0)
        self.assertEqual(a.project['groups'][0]['pads'][2]['gain'],85)
        self.assertEqual(a.project['groups'][0]['pads'][0]['gain'],80)
        self.assertFalse(a.project['groups'][0].get('automation'))

    def test_auto_lock_ends_when_leaving_mode(self):
        a=self.a;a.page='SAMPLER';self.s.button('SHIFT',True);self.press('AUTO');self.s.button('SHIFT',False)
        self.assertTrue(self.s.auto_locked);a.page='SAMPLING';self.s.fields()
        self.assertFalse(self.s.auto_locked);self.assertFalse(a.mk2_auto)

    def test_sampling_navigate_shows_zoom_and_scroll_above_their_knobs(self):
        a=self.a;a.page='SAMPLE EDIT';self.s.button('NAVIGATE',True)
        self.assertEqual(self.s.softkeys()[4:],('ZOOM-','ZOOM+','SCROLL-','SCROLL+'))
        self.assertEqual([f.label for f in self.s.fields()[:2]],['ZOOM','SCROLL'])
        self.s.button('NAVIGATE',False);self.assertFalse(a.wave_view())

    def test_page_buttons_change_pages_without_nav_modifier_and_disable_edges(self):
        a=self.a;a.page='SAMPLER';a.sampler_page=0
        mono,_,_=leds(self.s,{})
        self.assertEqual(mono[5],0);self.assertGreater(mono[6],0)
        self.press('PAGE RIGHT');self.assertEqual(a.sampler_page,1)
        for _ in range(10):self.press('PAGE RIGHT')
        self.assertEqual(a.sampler_page,5);self.assertEqual(leds(self.s,{})[0][6],0)

    def test_mode_pin_is_mode_plus_display_one(self):
        a=self.a;self.s.button('SCENE',True);self.s.softkey(0);self.s.button('SCENE',False)
        self.assertIn('SCENE',a.pinned_modes);self.assertEqual(a.page,'SCENE')
        self.press('SCENE');self.assertEqual(a.page,'PAD')

    def test_sampling_tabs_and_slice_target_group_do_not_change_source_focus(self):
        a=self.a;a.page='SAMPLING';self.s.softkey(1);self.assertEqual(a.page,'SAMPLE EDIT')
        self.s.softkey(3);self.assertEqual(a.page,'ZONE')
        a.page='SLICE TARGET';source=a.group
        self.press('GROUP G');self.assertEqual(a.slice_target_group,6);self.assertEqual(a.group,source)

    def test_mixer_eight_knobs_edit_each_channel_and_restore_focus(self):
        a=self.a;a.page='MIXER';a.pad=11;a.mixer_level=2;a.mixer_field=0
        self.s.rotate(1,2);self.s.rotate(8,7)
        self.assertEqual(a.project['groups'][0]['pads'][8]['gain'],82)
        self.assertEqual(a.project['groups'][0]['pads'][15]['gain'],87)
        self.assertEqual(a.pad,11)

    def test_tempo_master_fine_and_transport_locate(self):
        a=self.a;a.page='CHANNEL';a.channel_page=2
        self.press('TEMPO');self.s.rotate(0,3);self.assertEqual(a.project['tempo'],123)
        self.s.button('SHIFT',True);self.s.rotate(0,2);self.s.button('SHIFT',False)
        self.assertEqual(a.project['tempo'],123.02);self.assertEqual(a.channel_page,2)
        self.press('TEMPO');a.clock_phase=0;a.adjust_pattern_length(1)
        self.s.rotate(0,1);self.assertGreater(a.clock_phase,0)

    def test_volume_master_defaults_to_master_and_held_pad_selects_sound(self):
        a=self.a;a.page='CHANNEL';a.control_level=2;self.press('VOLUME');self.s.rotate(0,-3)
        self.assertEqual(a.project['gain'],97);self.assertEqual(a.track()['gain'],80)
        self.inputs.pad_on('mk2',0,100);self.s.rotate(0,-5)
        self.assertEqual(a.track()['gain'],75);self.assertEqual(a.project['gain'],97)

    def test_tempo_with_group_held_tunes_samples_and_preserves_project_tempo(self):
        a=self.a;a.page='SAMPLER'
        for track in a.project['groups'][1]['pads']:track['sample']='fixture.wav'
        self.s.button('GROUP B',True);self.press('TEMPO');self.s.rotate(0,2)
        self.assertEqual(a.project['tempo'],120)
        self.assertTrue(all(t['sampler']['tune']==2 for t in a.project['groups'][1]['pads']))
        self.assertEqual(a.group,1);self.assertEqual(a.control_level,2)
        self.s.button('GROUP B',False)

    def test_auto_records_and_shift_only_is_fine_edit_without_modulation(self):
        a=self.a;a.page='SAMPLER';a.sampler_page=1;a.track()['sampler']={'type':'ADSR'}
        a.playing=True;a.step=0;a.clock_phase=0
        self.s.button('SHIFT',True);self.s.rotate(5,2);self.s.button('SHIFT',False)
        self.assertFalse(a.project['groups'][0].get('automation'))
        self.s.button('AUTO',True);self.s.rotate(5,2);self.s.button('AUTO',False)
        self.assertTrue(a.project['groups'][0]['automation'])
        self.assertFalse(a.mk2_auto)

    def test_editor_eight_knob_edit_keeps_selected_note_identity(self):
        a=self.a;a.page='PATTERN GRID';a.put_note(0,0,{'velocity':90,'length':24,'probability':100,'note':36})
        a.grid_selected=set(a.event_notes());self.s.rotate(8,10);self.s.rotate(6,5)
        event=next(iter(a.event_notes().values()));self.assertEqual(event['velocity'],100);self.assertEqual(event['length'],29)

    def test_dispatch_uses_captured_track_and_individual_token_release(self):
        audio,midi=Mock(),Mock();a=self.a;a.track().update(source='MIDI',channel=3)
        self.inputs.pad_on('mk2',0,100);a.track()['channel']=9
        self.inputs.pad_off('mk2',0)
        for action,value in a.actions:self.inputs.dispatch(action,value,audio,midi)
        self.assertEqual(midi.hit.call_args.args,(0,100,36,3))
        self.assertEqual(midi.note_off.call_args.args[:2],(36,3))
        self.assertEqual(midi.hit.call_args.kwargs['voice_token'],midi.note_off.call_args.args[-1])

    def test_undo_legacy_release_stops_owned_attack_without_stopping_other_controller(self):
        audio,midi=Mock(),Mock();a=self.a
        self.inputs.pad_on('mk2',0,100);self.inputs.pad_on('mikro',1,90)
        self.assertTrue(self.inputs.dispatch('note_off',(0,0,36),audio,midi))
        self.assertEqual(audio.note_off.call_count,1)
        self.assertTrue(self.inputs.pads[('mikro',1)]);self.assertFalse(self.inputs.pads[('mk2',0)])

    def test_shortcuts_show_actual_values_and_exit_hardware_panel(self):
        a=self.a;a.page='BRIGHTNESS';self.press('VOLUME')
        self.assertEqual(a.page,a.control_home())

        before=a.settings['controllers']['mk2']['brightness']
        self.s.rotate(0,-4);state=snapshot(self.s)
        self.assertEqual(a.project['gain'],96)
        self.assertEqual(state['master_feedback'],('MASTER VOLUME','-0.4 DB'))
        self.assertEqual(a.settings['controllers']['mk2']['brightness'],before)
        self.press('SWING');self.s.rotate(0,3)
        self.assertEqual(self.s.master_feedback(),('MASTER SWING','3%'))
        self.press('TEMPO');self.s.rotate(0,2)
        self.assertEqual(self.s.master_feedback(),('MASTER TEMPO','122.00 BPM'))
        self.press('TEMPO');self.assertIsNone(self.s.master_feedback())

    def test_all_selects_sounds_without_moving_focus_and_edits_all(self):
        a=self.a;a.page='CHANNEL';a.control_level=2;a.select_sound(3)
        self.press('ALL');self.assertEqual(a.pad,3)
        self.assertEqual(a.selected_pads,set(range(16)))
        self.s.rotate(3,-5)
        self.assertTrue(all(p['gain']==75 for p in a.project['groups'][0]['pads']))
        a.page='PATTERN GRID';a.put_note(3,0,{'velocity':90,'length':24,'probability':100,'note':39})
        self.press('ALL');self.assertEqual(a.grid_selected,set(a.event_notes()))

    def test_pinned_auto_stops_with_plain_auto_and_held_auto_still_records(self):
        a=self.a;a.page='SAMPLER';a.sampler_page=1;a.track()['sampler']={'type':'ADSR'}
        a.playing=True;a.step=0;a.clock_phase=0
        self.s.button('SHIFT',True);self.press('AUTO');self.s.button('SHIFT',False)
        self.assertTrue(a.mk2_auto);self.s.rotate(5,1)
        self.assertTrue(a.project['groups'][0]['automation'])
        self.press('AUTO');self.assertFalse(a.mk2_auto);self.assertFalse(self.s.auto_locked)
        self.assertFalse(snapshot(self.s)['auto_write'])

    def test_master_screen_stays_until_explicit_exit_and_tracks_live_value(self):
        a=self.a;a.page='CHANNEL';self.press('TEMPO')
        with patch('time.monotonic',return_value=10**12):
            self.assertEqual(snapshot(self.s)['master_feedback'],('MASTER TEMPO','120.00 BPM'))
        self.s.rotate(0,2);self.assertEqual(self.s.master_feedback(),('MASTER TEMPO','122.00 BPM'))
        self.press('TEMPO');self.assertIsNone(self.s.master_feedback());self.assertIsNone(self.s.master_mode)
        self.press('VOLUME');self.press('CONTROL')  # Same underlying page still counts as explicit navigation.
        self.assertIsNone(snapshot(self.s)['master_feedback']);self.assertIsNone(self.s.master_mode)
        self.press('SWING');a.page='SAMPLING'  # Navigation from the other controller.
        self.assertIsNone(snapshot(self.s)['master_feedback']);self.assertIsNone(self.s.master_mode)
        self.press('TEMPO');self.press('BROWSE');self.assertIsNone(self.s.master_mode)

    def test_all_toggles_selection_and_led_in_sound_and_event_context(self):
        a=self.a;a.page='CHANNEL';a.select_sound(4)
        def all_led():
            with patch('app.mk2_display.led_reports',side_effect=lambda b,p,g:b):return leds(self.s,{})['ALL']
        self.press('ALL');self.assertEqual(all_led(),85)
        self.press('ALL');self.assertEqual(a.selected_pads,{4});self.assertEqual(all_led(),8)
        self.assertEqual(a.pad,4)
        self.press('ALL')  # Sound selection must not leak into event LED.
        a.page='PATTERN GRID';self.assertEqual(all_led(),8)
        a.put_note(4,0,{'velocity':90,'length':24,'probability':100,'note':40})
        self.press('ALL');self.assertEqual(a.grid_selected,set(a.event_notes()));self.assertEqual(all_led(),85)
        self.press('ALL');self.assertEqual(a.grid_selected,set());self.assertEqual(all_led(),8)
        a.save=Mock();self.s.button('SHIFT',True);self.press('ALL');self.s.button('SHIFT',False)
        a.save.assert_called_once();self.assertFalse(a.grid_selected)

    def test_navigate_exposes_views_without_unrelated_zoom_controls(self):
        a=self.a;a.page='CHANNEL';self.s.button('NAVIGATE',True)
        self.assertEqual(a.page,'VIEW NAV')
        self.assertEqual(self.s.softkeys()[3],'MIXER')
        before=a.view_count;self.s.rotate(5,1);self.assertEqual(a.view_count,before)
        self.assertFalse(any(self.s.fields()));self.assertEqual(self.s.softkeys()[7],'BACK')
        self.s.softkey(3);self.s.button('NAVIGATE',False)
        self.assertEqual(a.page,'MIXER')
        self.s.button('NAVIGATE',True);self.s.softkey(5);self.s.button('NAVIGATE',False)
        self.assertEqual(a.page,'PATTERN GRID')
        self.s.button('NAVIGATE',True);self.s.softkey(0);self.s.button('NAVIGATE',False)
        self.assertEqual(a.page,'VIEW NAV');self.assertIn('VIEW',a.pinned_modes)
        self.s.softkey(2);self.assertEqual(a.page,'SONG')

    def test_navigate_back_cancels_preview_without_changing_follow(self):
        a=self.a;a.page='CHANNEL';a.grid_follow=True
        self.s.button('NAVIGATE',True);self.s.softkey(3);self.s.softkey(7)
        self.assertEqual(a.page,'CHANNEL');self.assertTrue(a.grid_follow)
        self.s.button('NAVIGATE',False);self.assertEqual(a.page,'CHANNEL')

    def test_navigate_marks_destination_immediately_before_release_and_on_reentry(self):
        a=self.a;a.page='CHANNEL';self.s.button('NAVIGATE',True)
        for key,destination in ((3,'MIXER'),(4,'BROWSE'),(5,'PATTERN GRID'),(2,'SONG'),(1,'SCENE')):
            self.s.softkey(key);self.assertEqual(a.page,'VIEW NAV')
            state=snapshot(self.s)
            active=set(state['active_left'])|{i+4 for i in state['active_right']}
            self.assertIn(key,active)
            self.assertEqual(active.intersection({1,2,3,4,5}),{key})
            with patch('app.mk2_display.led_reports',side_effect=lambda b,p,g:b):buttons=leds(self.s,{})
            self.assertEqual(buttons[f'DISPLAY {key+1}'],85)
        self.s.button('NAVIGATE',False);self.assertEqual(a.page,'SCENE')
        self.s.button('NAVIGATE',True);self.assertIn(1,snapshot(self.s)['active_left'])
        self.s.softkey(0);self.assertIn(0,snapshot(self.s)['active_left'])
        self.assertIn(1,snapshot(self.s)['active_left'])

    def test_navigate_active_workspace_toggles_back_on_both_full_size_controllers(self):
        from app.mk1_session import Mk1Surface
        for cls in (Mk1Surface,Mk2Surface):
            for key,target in ((1,'SCENE'),(2,'SONG'),(3,'MIXER'),(4,'BROWSE'),(5,'PATTERN GRID')):
                with self.subTest(controller=cls.source,target=target):
                    a=self.a;a.page='CHANNEL';a.pinned_modes.discard('VIEW')
                    s=cls(a,self.inputs)
                    for expected in (target,'CHANNEL'):
                        s.button('NAVIGATE',True);s.softkey(key)
                        self.assertEqual(a.view_origin,expected)
                        active=snapshot(s)
                        selected=set(active['active_left'])|{i+4 for i in active['active_right']}
                        self.assertEqual(key in selected,expected==target)
                        s.button('NAVIGATE',False);self.assertEqual(a.page,expected)

    def test_navigate_pinned_toggle_and_direct_editor_fallback(self):
        a=self.a;a.page='CHANNEL';s=self.s
        s.button('NAVIGATE',True);s.softkey(3);s.button('NAVIGATE',False)
        s.button('NAVIGATE',True);s.softkey(0);s.button('NAVIGATE',False)
        self.assertEqual(a.page,'VIEW NAV')
        s.softkey(3);self.assertEqual(a.page,'CHANNEL')
        self.assertIn('VIEW',a.pinned_modes)
        a.pinned_modes.discard('VIEW');a.page='GRID EDIT';a.view_returns.clear()
        s.button('NAVIGATE',True);s.softkey(5);s.button('NAVIGATE',False)
        self.assertEqual(a.page,a.control_home())

    def test_navigate_repeated_preview_toggle_keeps_original_return(self):
        a=self.a;a.page='CHANNEL';s=self.s
        s.button('NAVIGATE',True);s.softkey(3);s.button('NAVIGATE',False)
        s.button('NAVIGATE',True)
        for expected in ('CHANNEL','MIXER','CHANNEL'):
            s.softkey(3);self.assertEqual(a.view_origin,expected)
        s.button('NAVIGATE',False);self.assertEqual(a.page,'CHANNEL')

    def test_sampling_direct_zoom_scroll_preserve_ranges_and_pad_audition(self):
        a=self.a;path=Path(self.tmp.name)/'samples/direct.wav'
        with wave.open(str(path),'wb') as wav:
            wav.setparams((1,2,48000,0,'NONE','not compressed'));wav.writeframes(bytes(9600))
        a.track().update(sample=str(path),start=0,end=4800,slices=[[0,2400],[2400,4800]])
        from app.sampler import default_zone
        a.track()['zones']=[default_zone(a.track())]
        for page in ('SAMPLE EDIT','CHOP','ZONE'):
            a.page=page;a.wave_zoom=a.wave_offset=0
            fields=self.s.fields();self.assertEqual([f.label for f in fields[2:4]],['ZOOM','SCROLL'])
            before=copy.deepcopy(a.track());a.actions.clear()
            self.s.rotate(3,1);self.assertEqual(a.wave_zoom,1,page)
            self.s.rotate(4,1);state=snapshot(self.s)
            self.assertTrue(state['direct_wave']);self.assertGreater(state['wave'][1],0,page)
            self.assertEqual(state['wave'][2]-state['wave'][1],2400,page)
            self.assertEqual(a.track(),before);self.assertEqual(a.actions,[])
            self.assertFalse(a.wave_view());self.assertFalse(a.wave_selected)
            if page!='ZONE':
                self.inputs.pad_on('mk2',0,100);self.assertTrue(any(k in ('controller_hit','slice_play','slice_live_play') for k,v in a.actions),(page,a.actions))
                self.inputs.pad_off('mk2',0)
            self.s.rotate(4,10000);self.assertEqual(self.s.waveform_window()[2],4800)
            self.s.rotate(4,-10000);self.assertEqual(self.s.waveform_window()[1],0)
            if page=='SAMPLE EDIT':
                self.s.rotate(1,1);self.assertEqual(a.wave_zoom,1)
                a.track()['start']=0

    def test_trim_markers_do_not_resize_viewport_or_reload_waveform(self):
        from app.sampler import default_zone
        a=self.a;path=Path(self.tmp.name)/'samples/trim.wav'
        with wave.open(str(path),'wb') as wav:
            wav.setparams((1,2,48000,0,'NONE','not compressed'));wav.writeframes(bytes(19200))
        a.track().update(sample=str(path),start=0,end=4800)
        a.track()['zones']=[default_zone(a.track())]
        for page in ('SAMPLE EDIT','CHOP','ZONE'):
            a.page=page;self.s.waveform_key=None
            original=self.s.waveform_window();self.assertEqual(original,(str(path),0,9600))
            source=self.s.waveform_source()
            with patch('app.mk2_surface.wave.open',side_effect=AssertionError('reopened on trim')):
                for end in (4000,6000,2400,8000):
                    source['end']=end;source['start']=100
                    self.assertEqual(self.s.waveform_window(),original)
                self.s.rotate_waveform(0,1);zoomed=self.s.waveform_window()
                source['end']=1200
                self.assertEqual(self.s.waveform_window(),zoomed)
                self.s.rotate_waveform(1,100);self.assertEqual(self.s.waveform_window()[2],9600)

    def test_zone_waveform_uses_selected_zone_asset_and_all_pages_keep_controls(self):
        from app.sampler import default_zone
        a=self.a;a.page='ZONE'
        a.track().update(sample='/source.wav',start=0,end=9000)
        z=default_zone(a.track());z.update(sample='/other.wav',start=100,end=3200)
        a.track()['zones']=[z]
        for page in range(5):
            a.zone_page=page;state=snapshot(self.s)
            self.assertEqual(state['wave'][0],'/other.wav')
            self.assertEqual([f.label for f in self.s.fields()[2:4]],['ZOOM','SCROLL'])
            self.assertEqual(state['markers'],((100,3200),))
        self.s.rotate(3,1);self.assertGreater(a.wave_zoom,0)
        z['sample']='/third.wav';snapshot(self.s)
        self.assertEqual((a.wave_zoom,a.wave_offset),(0,0))

    def test_sampling_left_controls_keep_all_zone_and_slice_parameters_reachable(self):
        from app.sampler import default_zone,ZONE_PAGES
        a=self.a;a.track().update(sample='/source.wav',start=0,end=4800,slices=[[0,2400],[2400,4800]])
        a.track()['zones']=[default_zone(a.track())];a.page='ZONE';seen=set()
        self.assertEqual(self.s.page_state(),(0,8))
        for page in range(8):
            fields=self.s.fields();self.assertEqual([f.label for f in fields[2:4]],['ZOOM','SCROLL'])
            self.assertFalse(any(fields[4:]))
            for f in fields[:2]:
                if f:seen.add((a.zone_page,dict(f.attributes)['zone_field']))
            self.assertEqual(self.s.page_state()[0],page);self.press('PAGE RIGHT')
        self.assertEqual(seen,{(p,i) for p,(_,keys) in enumerate(ZONE_PAGES) for i in range(len(keys))})
        a.page='CHOP';a.slice_mode='DETECT';a.slice_edit=False;self.s.slice_subpage=0;seen=set()
        for page in range(3):
            fields=self.s.fields();seen.update(f.label for f in fields[:2] if f)
            self.assertFalse(any(fields[4:]));self.press('PAGE RIGHT')
        self.assertEqual(seen,{'MODE','SENSITIVITY','BPM','ADJUST','MONO','ZERO-X'})
        a.slice_edit=True;a.slice_index=0;self.s.rotate(0,1)
        fields=self.s.fields();self.assertEqual(a.slice_index,1)
        self.assertEqual([(f.label,f.value) for f in fields[:2]],[('START','2400'),('END','4800')])
        self.assertIn('MASTER',snapshot(self.s)['headings'][0])
        self.assertEqual(a.track()['slices'],[[0,2400],[2400,4800]])

    def test_all_existing_pages_render_as_two_native_canvases_with_black_border(self):
        renderer=Mk2Renderer();self.addCleanup(renderer.close)
        pages=['PAD','CHANNEL','INPUT','GROOVE','MACRO','SAMPLER','PLUGIN','PLUGIN BROWSE','PAD CONFIG','SAMPLING','SAMPLE EDIT','CHOP','ZONE','SLICE TARGET','MIXER','STEP','PATTERN','SCENE','SELECT','MUTE','SOLO','PATTERN GRID','GRID EDIT','SETTINGS','SONG','PROJECT','NOTE REPEAT','ARP']+list(SETTING_PAGES)
        for page in pages:
            self.a.page=page;state=snapshot(self.s)
            for canvas in renderer(state):
                self.assertEqual(len(canvas),16384,page)
                self.assertFalse(any(canvas[:256])+any(canvas[-256:]),page)
                self.assertTrue(all(canvas[y*256]==canvas[y*256+255]==0 for y in range(64)),page)
                self.assertTrue(any(canvas),page)

if __name__=='__main__':unittest.main()
