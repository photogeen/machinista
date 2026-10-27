import array
import json
import math
from pathlib import Path
import subprocess
import tempfile
import unittest
import wave

from app.model import Application, validate_project
from app.controller_inputs import ControllerInputs
from app.mk1_session import Mk1Surface
from app.mk2_surface import Mk2Surface
from app.mk2_display import snapshot, Mk2Renderer


class LiveFxWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=Application(self.tmp.name);self.inputs=ControllerInputs(self.a)

    def test_both_full_size_navigate_buttons_open_fx_and_release_keeps_it_open(self):
        for cls in (Mk1Surface,Mk2Surface):
            with self.subTest(controller=cls.source):
                a=Application(Path(self.tmp.name)/cls.source);a.page='PAD';s=cls(a,ControllerInputs(a))
                s.button('NAVIGATE',True)
                self.assertEqual(a.page,'VIEW NAV');self.assertEqual(s.softkeys()[6],'LIVE FX')
                s.button('DISPLAY 7',True);s.button('DISPLAY 7',False)
                self.assertEqual(a.page,'VIEW NAV');self.assertIn(2,snapshot(s)['active_right'])
                self.assertFalse(any(action=='live_fx' for action,_ in a.actions))
                s.button('NAVIGATE',False)
                self.assertEqual(a.page,'LIVE FX')
                depth=a.live_fx_depth;s.rotate(1,-5);self.assertEqual(a.live_fx_depth,depth-5)
                s.softkey(7);self.assertEqual(a.page,'PAD');self.assertEqual(a.live_fx_current,0)

    def test_navigate_fx_preview_can_cancel_toggle_and_use_pin(self):
        for cls in (Mk1Surface,Mk2Surface):
            with self.subTest(controller=cls.source):
                a=Application(Path(self.tmp.name)/cls.source);a.page='PAD';s=cls(a,ControllerInputs(a))
                s.button('NAVIGATE',True);s.softkey(6)
                self.assertEqual(s.softkeys()[7],'BACK');s.softkey(7)
                self.assertEqual(a.page,'PAD');s.button('NAVIGATE',False)
                s.button('NAVIGATE',True);s.softkey(6);s.softkey(6)
                self.assertNotIn(2,snapshot(s)['active_right']);s.button('NAVIGATE',False)
                self.assertEqual(a.page,'PAD')
                a.pinned_modes.add('VIEW')
                s.button('NAVIGATE',True);s.softkey(6);s.button('NAVIGATE',False)
                self.assertEqual(a.page,'VIEW NAV')
                s.softkey(6);self.assertEqual(a.page,'PAD')
                s.button('NAVIGATE',True);s.button('NAVIGATE',False)
                self.assertEqual(a.page,'VIEW NAV');s.softkey(6)
                self.assertEqual(a.page,'LIVE FX');s.softkey(7)
                self.assertEqual(a.page,'PAD')

    def test_navigate_reentry_keeps_fx_selected_and_running_until_deselected(self):
        for cls in (Mk1Surface,Mk2Surface):
            for mode in (0,1,2):
                with self.subTest(controller=cls.source,mode=mode):
                    a=Application(Path(self.tmp.name)/(cls.source+str(mode)));a.page='SAMPLER';s=cls(a,ControllerInputs(a))
                    s.button('NAVIGATE',True);s.softkey(6);s.button('NAVIGATE',False)
                    a.live_fx_mode=mode;a.live_fx_depth=65;a.live_fx_pad_on(2,99,cls.source);a.actions.clear()
                    before=(a.live_fx_mode,a.live_fx_current,a.live_fx_depth,dict(a.live_fx_held))
                    for _ in range(2):
                        s.button('NAVIGATE',True)
                        self.assertEqual(a.page,'VIEW NAV');self.assertEqual(a.view_entry,'LIVE FX');self.assertIn(2,snapshot(s)['active_right'])
                        self.assertEqual((a.live_fx_mode,a.live_fx_current,a.live_fx_depth,a.live_fx_held),before)
                        s.button('NAVIGATE',False);self.assertEqual(a.page,'LIVE FX')
                        self.assertFalse(any(k=='live_fx' for k,v in a.actions))
                    s.button('NAVIGATE',True);s.softkey(6)
                    self.assertNotIn(2,snapshot(s)['active_right']);self.assertEqual(a.page,'VIEW NAV')
                    self.assertEqual(a.live_fx_current,3)
                    s.button('NAVIGATE',False);self.assertEqual(a.page,'SAMPLER');self.assertEqual(a.live_fx_current,0);self.assertFalse(a.live_fx_held)

    def test_navigate_switch_from_fx_to_other_view_stops_effect_on_commit(self):
        a=self.a;a.page='PAD';s=Mk2Surface(a,self.inputs);a.open_live_fx('PAD');a.live_fx_mode=2;a.live_fx_pad_on(0,100,'mk2');a.actions.clear()
        s.button('NAVIGATE',True);s.softkey(3)
        self.assertEqual(a.page,'VIEW NAV');self.assertEqual(a.live_fx_current,1)
        s.button('NAVIGATE',False);self.assertEqual(a.page,'MIXER');self.assertEqual(a.live_fx_current,0)

    def test_latched_fx_retains_manual_priority_during_navigate_preview(self):
        from app.layout import GROUP_BASE
        from app.automation import lane_key
        a=self.a;a.open_live_fx('PAD');a.playing=True;a.step=0;a.clock_phase=24
        descriptor=(GROUP_BASE,'fx',-1,'state')
        a.project['groups'][0]['automation']={lane_key(0,descriptor):{'base':0,'points':{'0':0}}}
        s=Mk2Surface(a,self.inputs)
        for mode in (1,2):
            a.page='LIVE FX';a.live_fx_mode=mode;a.live_fx_pad_on(3,100,'mk2');a.live_fx_pad_off(3,'mk2');a.actions.clear()
            s.button('NAVIGATE',True);a.automation_tick()
            self.assertTrue(a.live_fx_manual_override());self.assertEqual(a.live_fx_current,4)
            self.assertFalse(any(k=='live_fx' for k,v in a.actions))
            s.button('NAVIGATE',False);self.assertEqual(a.live_fx_mode,mode)
            a.live_fx_off()

    def test_mikro_view_reentry_keeps_mode_and_can_release_punch_while_navigating(self):
        a=self.a;a.page='PAD';a.open_live_fx('PAD');a.live_fx_pad_on(1,100,'mikro');a.actions.clear()
        a.button('VIEW',True);self.assertEqual(a.page,'VIEW NAV');self.assertEqual(a.view_origin,'LIVE FX')
        a.release_pad(1,owner='mikro');self.assertEqual(a.live_fx_current,0)
        a.actions.clear();a.button('VIEW',False);self.assertEqual(a.page,'LIVE FX');self.assertFalse(a.live_fx_held)
        self.assertFalse(any(k=='live_fx' for k,v in a.actions))

    def test_default_fokus_renderer_has_fx_body_and_pad_focus(self):
        a=self.a;s=Mk1Surface(a,self.inputs);renderer=Mk2Renderer();self.addCleanup(renderer.close)
        a.page='LIVE FX';state=snapshot(s)
        self.assertIn('live_fx',state);self.assertNotIn('utility',state)
        before=renderer(state)
        self.inputs.pad_on('mk1',2,100);after=renderer(snapshot(s))
        self.assertNotEqual(before,after)
        self.assertGreater(sum(after[1][25*256:62*256]),100)
        self.assertEqual(state['fields'][0][0],'DEPTH')

    def test_sampling_wave_navigate_has_fx_access_too(self):
        a=self.a;s=Mk1Surface(a,self.inputs);a.page='CHOP'
        s.button('NAVIGATE',True);self.assertTrue(a.wave_view())
        self.assertEqual(s.softkeys()[2],'LIVE FX')
        s.softkey(2);s.button('NAVIGATE',False)
        self.assertEqual(a.page,'LIVE FX');self.assertFalse(a.wave_view())
        s.softkey(7);self.assertEqual(a.page,'CHOP')

    def test_raw_velocity_and_fx_automation_require_rec_and_do_not_record_notes(self):
        a=self.a;a.page='LIVE FX';a.fixed_velocity=True;a.velocity_value=127
        a.playing=True;a.step=0;a.clock_phase=24
        notes=dict(a.notes());self.inputs.pad_on('mk1',8,41)
        self.assertEqual(a.live_fx_velocity,41);self.inputs.pad_off('mk1',8)
        self.assertFalse(a.project['groups'][0].get('automation'))
        a.recording=True;self.inputs.pad_on('mk1',8,41)
        a.clock_phase=48;self.inputs.pad_off('mk1',8)
        lane=next(iter(a.project['groups'][0]['automation'].values()))
        self.assertEqual(set(lane['points']),{'24','48'})
        self.assertEqual(a.live_fx_current,0);self.assertEqual(a.notes(),notes)
        validate_project(a.project)

    def test_first_punch_is_not_erased_by_recorded_off_automation(self):
        from app.layout import GROUP_BASE
        from app.automation import lane_key
        a=self.a;a.open_live_fx();a.playing=True;a.step=0;a.clock_phase=24
        descriptor=(GROUP_BASE,'fx',-1,'state')
        a.project['groups'][0]['automation']={lane_key(0,descriptor):{'base':0,'points':{'0':0}}}
        self.inputs.pad_on('mk2',4,100);a.actions.clear();a.automation_tick()
        self.assertEqual(a.live_fx_current,5)
        self.assertFalse(any(action=='live_fx' for action,value in a.actions))
        self.inputs.pad_off('mk2',4);a.automation_tick();self.assertEqual(a.live_fx_current,0)

    def test_pressure_updates_first_punch_and_is_owned_by_its_controller(self):
        a=self.a;a.open_live_fx();a.fixed_velocity=True
        self.inputs.pad_on('mk2',1,30);a.actions.clear()
        self.inputs.pad_pressure('mikro',1,127)
        self.assertEqual(a.live_fx_velocity,30)
        self.inputs.pad_pressure('mk2',1,110)
        self.assertEqual(a.live_fx_velocity,110)
        self.assertEqual(a.actions[-1],('live_fx',(0,2,110,1,120)))
        self.inputs.pad_off('mk2',1)
        self.assertEqual(a.actions[-1][1][1:4],(0,0,0))
        self.inputs.pad_on('mk2',1,40);self.assertEqual(a.live_fx_current,2)

    def test_off_cannot_be_reenabled_by_pressure_from_a_still_held_pad(self):
        a=self.a;a.open_live_fx();a.playing=True;a.recording=True;a.step=0;a.clock_phase=24
        surface=Mk2Surface(a,self.inputs)
        self.inputs.pad_on('mk2',1,90);a.clock_phase=48
        surface.softkey(6);self.inputs.pad_pressure('mk2',1,120)
        self.assertEqual(a.live_fx_current,0);self.assertFalse(a.live_fx_held)
        lane=next(iter(a.project['groups'][0]['automation'].values()))
        self.assertEqual(lane['points']['48'],0)
        self.inputs.pad_off('mk2',1);self.inputs.pad_on('mk2',1,100)
        self.assertEqual(a.live_fx_current,2)

    def test_releasing_newest_pad_restores_older_held_pressure(self):
        a=self.a;a.open_live_fx()
        self.inputs.pad_on('mk1',1,30);self.inputs.pad_on('mk2',2,70)
        self.inputs.pad_pressure('mk1',1,100)
        self.assertEqual(a.live_fx_current,3)
        self.inputs.pad_off('mk2',2)
        self.assertEqual((a.live_fx_current,a.live_fx_velocity),(2,100))



ENGINE=Path(__file__).resolve().parent.parent/'build/audio_engine'

@unittest.skipUnless(ENGINE.exists() and __import__('sys').platform=='linux' and __import__('platform').machine() in ('aarch64','armv7l'),'Native ARM/Linux engine build required')
class LiveFxNativeTests(unittest.TestCase):
    def test_native_main_export_processes_fx_and_dry_prefix_is_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);sample=root/'sample.f32'
            values=array.array('f',(0.17*math.sin(i*.11) for i in range(8192)))
            sample.write_bytes(values.tobytes());renders=[]
            for effect in (0,9):
                output=root/f'{effect}.wav'
                commands=[f'load 0 48000 {json.dumps(str(sample))}','sequence_begin','sequence_lane 384','sequence_event 0 384 100 0','hit 0 1','sequence_commit','sequence_transport 120 1',f'offline_control 512 "live_fx 0 {effect} 127 1 120"',f'render_start {json.dumps(str(output))} 4096 1088 16 WAV','quit']
                result=subprocess.run([str(ENGINE),'--offline-render'],input='\n'.join(commands)+'\n',capture_output=True,text=True,timeout=20)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertIn('"status":"finished"',result.stdout)
                with wave.open(str(output)) as wav:renders.append(wav.readframes(wav.getnframes()))
            self.assertEqual(renders[0][:512*4],renders[1][:512*4])
            self.assertNotEqual(renders[0][1024*4:],renders[1][1024*4:])
