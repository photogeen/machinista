import copy
import array
import json
import math
import subprocess
from pathlib import Path
import tempfile
import unittest
import wave

from app.audio import AudioBackend
from app.controller_inputs import ControllerInputs
from app.mk1_session import Mk1Surface
from app.mk2_surface import Mk2Surface
from app.model import Application,validate_project
from app.native_sequence import sequence_commands


class AudioLoopWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=Application(self.tmp.name)
        self.path=Path(self.tmp.name)/'samples/loop.wav'
        with wave.open(str(self.path),'wb') as f:f.setparams((2,2,48000,0,'NONE',''));f.writeframes(bytes(48000*4*2))

    def test_sound_source_selection_bus_identity_and_round_trip(self):
        a=self.a;a.capture_options().update(source='INTERNAL',input='SOUND 3 15',mode='LOOP')
        self.assertIn('SOUND 3 15',a.capture_inputs());self.assertEqual(AudioBackend.capture_source(a.capture_options()),63)
        self.assertEqual(a.capture_source_label(),'SOUND D:16');self.assertEqual(a.capture_fields()[-1],'bars')
        validate_project(a.project)
        a.project['sampling']['input']='SOUND 99 0'
        with self.assertRaises(ValueError):validate_project(a.project)

    def test_audio_mode_controls_persist_and_emit_transport_plan_without_notes(self):
        a=self.a;a.assign_browser_sample(self.path);a.audio_loop_setup();a.audio_tool_rotate(1)
        self.assertEqual(a.track()['playback_mode'],'AUDIO')
        commands=sequence_commands(a);self.assertTrue(any(c.startswith('sequence_audio 0 384 ') for c in commands))
        self.assertFalse(any(c.startswith('hit ') for c in commands));validate_project(a.project)
        a.put_note(0,0,dict(velocity=100,probability=100,length=24,note=36))
        commands=sequence_commands(a);self.assertFalse(any(c.startswith('hit ') for c in commands))
        a.track()['mute']=True;self.assertFalse(any(c.startswith('sequence_audio ') for c in sequence_commands(a)))
        a.track()['mute']=False;a.active_clips[0]=False;self.assertFalse(any(c.startswith('sequence_audio ') for c in sequence_commands(a)))

    def test_loop_record_result_is_target_owned_and_preserves_source(self):
        a=self.a;a.track()['plugins']=[dict(uri='urn:test:synth',kind='INSTRUMENT',controls={})]
        a.put_note(0,0,dict(velocity=100,probability=100,length=24,note=36));source=copy.deepcopy(a.track());notes=copy.deepcopy(a.event_notes())
        a.bounce_setup();self.assertEqual(a.bounce_config['target_pad'],1);a.start_bounce()
        job=next(v for k,v in a.actions if k=='capture_to');job['tempo']=120;a.capture_job=job
        a.group=1;a.pad=5
        self.assertTrue(a.finish_sample_recording((0,1),self.path,a.project_generation))
        target=a.project['groups'][0]['pads'][1]
        self.assertEqual(target['playback_mode'],'AUDIO');self.assertEqual(target['audio_loop']['bars'],1)
        self.assertEqual(a.project['groups'][0]['pads'][0],source);self.assertEqual(a.event_notes(0,0),notes)
        self.assertFalse(a.recording);validate_project(a.project)

    def test_bounce_rejects_occupied_target_and_midi_recording(self):
        a=self.a;a.bounce_setup();a.bounce_config['target_pad']=a.pad;a.start_bounce()
        self.assertEqual(a.message,'CHOOSE AN EMPTY TARGET');self.assertFalse(a.capture_armed)
        a.bounce_config['target_pad']=1;a.recording=True;a.start_bounce()
        self.assertEqual(a.message,'STOP MIDI REC FIRST');self.assertFalse(a.capture_armed)

    def test_loading_synth_or_midi_source_overrides_previous_audio_loop(self):
        a=self.a;a.assign_browser_sample(self.path);a.track()['playback_mode']='AUDIO'
        a.put_note(0,0,dict(velocity=100,probability=100,length=24,note=36))
        a.track()['plugins']=[dict(uri='urn:test:synth',kind='INSTRUMENT',controls={})]
        commands=sequence_commands(a)
        self.assertFalse(any(c.startswith('sequence_audio ') for c in commands));self.assertTrue(any(c.startswith('plugin_note 0 ') for c in commands))
        a.track()['plugins']=[];a.track()['source']='MIDI';commands=sequence_commands(a)
        self.assertFalse(any(c.startswith('sequence_audio ') for c in commands));self.assertTrue(any(c.startswith('external_note ') for c in commands))

    def test_bounce_external_input_and_optional_mute(self):
        a=self.a;a.bounce_setup();a.bounce_config.update(input='EXT 1/2',mute_source=True,result='SAMPLER');a.start_bounce()
        job=next(v for k,v in a.actions if k=='capture_to');self.assertEqual(job['options']['source'],'EXT STEREO')
        a.capture_job=job;a.finish_sample_recording((0,1),self.path,a.project_generation)
        self.assertTrue(a.project['groups'][0]['pads'][0]['mute']);self.assertEqual(a.project['groups'][0]['pads'][1]['playback_mode'],'SAMPLER')

    def test_audio_transport_with_external_clock_does_not_duplicate_midi_notes(self):
        from app.native_sequence import NativeSequence
        from unittest.mock import Mock
        a=self.a;a.assign_browser_sample(self.path);a.track()['playback_mode']='AUDIO'
        a.put_note(0,0,dict(velocity=100,probability=100,length=24,note=36))
        a.settings['midi_sync']='IN';a.playing=True
        audio=Mock();commands=[];audio.command=commands.append
        NativeSequence().update(a,audio,None,1,1)
        self.assertFalse(a.native_sequence);self.assertTrue(audio.loop_transport_running)
        self.assertTrue(any('sequence_audio 0 ' in c for c in commands));self.assertFalse(any('hit 0 ' in c for c in commands))
        b=AudioBackend.__new__(AudioBackend);b.command=commands.append;b.loop_transport_running=True
        before=list(commands);b.hit(0,0,100,a.track());self.assertEqual(commands,before)

    def test_external_clock_capture_bridge_triggers_once_and_leaves_autosampler_alone(self):
        a=self.a;commands=[];b=AudioBackend.__new__(AudioBackend);b.command=commands.append
        b.native_capture=dict(mode='SYNC',triggered=False);a.playing=True;a.clock_phase=384
        b.external_capture_tick(a);self.assertFalse(commands)
        a.settings['midi_sync']='IN';b.external_capture_tick(a);b.external_capture_tick(a)
        self.assertEqual(commands,['record_trigger'])
        b.native_capture=dict(autosampler=True);b.external_capture_tick(a)
        self.assertEqual(commands,['record_trigger'])

    def test_changed_target_and_project_do_not_get_overwritten(self):
        a=self.a;a.bounce_setup();a.start_bounce();job=next(v for k,v in a.actions if k=='capture_to')
        a.capture_job=job;t=a.project['groups'][0]['pads'][1];t['gain']=50
        self.assertFalse(a.finish_sample_recording((0,1),self.path,a.project_generation));self.assertIsNone(t['sample']);self.assertTrue(self.path.exists())
        a.capture_job=job;self.assertFalse(a.finish_sample_recording((0,1),self.path,a.project_generation-1))

    def test_loop_take_activates_empty_target_group_clip_and_has_cancel_action(self):
        a=self.a;a.active_clips[0]=False;a.project['scenes'][a.scene][0]=None
        a.capture_job=dict(result='AUDIO',tempo=120,options=dict(bars=1))
        self.assertTrue(a.finish_sample_recording((0,0),self.path,a.project_generation))
        self.assertTrue(a.active_clips[0]);self.assertIsNotNone(a.project['scenes'][a.scene][0])
        a.page='SAMPLING';a.bounce_setup();a.capture_armed=True
        a.audio_tool_button('F2',True);self.assertIn(('capture_cancel',None),a.actions)

    def test_inactive_target_group_never_starts_its_old_midi_pattern(self):
        a=self.a;a.group=1;a.pad=0
        with wave.open(str(self.path),'wb') as f:f.setparams((2,2,48000,0,'NONE',''));f.writeframes(bytes(48000*4*8))
        a.put_note(0,0,dict(velocity=100,probability=100,length=24,note=36))
        previous=copy.deepcopy(a.event_notes(1,0));a.active_clips[1]=False;a.project['scenes'][a.scene][1]=None
        a.capture_job=dict(result='AUDIO',tempo=120,options=dict(bars=4))
        a.finish_sample_recording((1,1),self.path,a.project_generation)
        self.assertNotEqual(a.active_patterns[1],0);self.assertEqual(a.event_notes(1,0),previous)
        self.assertEqual(a.pattern_steps(1,a.active_patterns[1]),64)
        self.assertFalse(a.event_notes(1,a.active_patterns[1]));validate_project(a.project)

    def test_stopping_a_long_take_early_does_not_stretch_one_bar_to_four(self):
        a=self.a;a.capture_job=dict(result='AUDIO',tempo=120,options=dict(bars=4))
        a.finish_sample_recording((0,0),self.path,a.project_generation)
        self.assertEqual(a.track()['audio_loop']['bars'],1)

    def test_tools_reachable_and_encoder_bindings_on_all_surfaces(self):
        for cls in (Mk1Surface,Mk2Surface):
            a=self.a;a.page='SAMPLING';s=cls(a,ControllerInputs(a));s.button('SHIFT',True)
            self.assertEqual(s.softkeys()[4:6],('BOUNCE','AUDIO'));s.softkey(4);s.button('SHIFT',False)
            self.assertEqual(a.page,'BOUNCE TO PAD');s.rotate(6,1);self.assertEqual(a.bounce_config['bars'],2)
            s.softkey(0);self.assertEqual(a.page,'SAMPLING')
            s.button('SHIFT',True);s.softkey(5);s.button('SHIFT',False);self.assertEqual(a.page,'AUDIO LOOP')
            s.softkey(0)
        a.page='SAMPLING';a.button('SHIFT',True);a.button('F1',True);a.button('F1',False);a.button('SHIFT',False)
        self.assertEqual(a.page,'BOUNCE TO PAD');a.button('F1',True);a.button('F1',False)
        self.assertEqual(a.page,'SAMPLING')


ENGINE=Path(__file__).resolve().parents[1]/'build/audio_engine'

@unittest.skipUnless(ENGINE.exists() and Path('/usr/share/alsa/alsa.conf').exists(),'ARM/Linux engine required')
class AudioLoopRenderTests(unittest.TestCase):
    def test_actual_engine_loops_without_midi_and_seek_is_sample_exact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'loop.f32';output=root/'loop.wav'
            pcm=array.array('f')
            for i in range(4800):pcm.extend((i/12000,-.125))
            source.write_bytes(pcm.tobytes())
            commands=[f'load 0 48000 {json.dumps(str(source))}','sequence_begin','sequence_lane 48','sequence_audio 0 24 0 1','sequence_commit','sequence_seek 12 1','sequence_transport 120 1',f'render_start {json.dumps(str(output))} 12000 0','quit']
            result=subprocess.run([str(ENGINE),'--offline-render'],input='\n'.join(commands)+'\n',capture_output=True,text=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('"status":"finished"',result.stdout)
            with wave.open(str(output),'rb') as f:
                self.assertEqual(f.getnframes(),12000);values=array.array('h');values.frombytes(f.readframes(12000))
            for i in (0,1,100,2998,3000,5999,6000,9001,11999):
                position=math.fmod(2400+i*.8,4800)
                expected=int(position/12000*32767)
                self.assertLessEqual(abs(values[2*i]-expected),2,(i,values[2*i],expected))
                self.assertLessEqual(abs(values[2*i+1]-int(-.125*32767)),1)
            # Stopped transport is silent; a new shorter Pattern restarts its
            # audio phase even if it cuts through a longer recording.
            for playing,lane in ((False,48),(True,12)):
                commands=[f'load 0 48000 {json.dumps(str(source))}','sequence_begin',f'sequence_lane {lane}','sequence_audio 0 24 0 1','sequence_commit','sequence_seek 0 2',f'sequence_transport 120 {int(playing)}',f'render_start {json.dumps(str(output))} 6500 0','quit']
                result=subprocess.run([str(ENGINE),'--offline-render'],input='\n'.join(commands)+'\n',capture_output=True,text=True,timeout=15)
                self.assertEqual(result.returncode,0,result.stderr)
                with wave.open(str(output),'rb') as f:values=array.array('h');values.frombytes(f.readframes(6500))
                if not playing:self.assertTrue(all(v==0 for v in values))
                else:
                    for offset in (0,3000,6000):self.assertLessEqual(abs(values[2*offset]),1)
