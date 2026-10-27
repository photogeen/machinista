import array
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
import wave
from app.model import Application
from app.export_audio import compile_export,export_spans,export_targets,render_export
from app.ni_display import frame
from app.layout import MASTER,GROUP_BASE
ROOT=Path(__file__).resolve().parent.parent

class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.a=Application(self.root)
        self.a.put_event((0,0),dict(velocity=127,probability=100,length=24,note=36))
    def request(self,**values):
        request=dict(project=self.a.project_for_save(),mode='PATTERN',source='MIX',rate=48000,tail=0,group=0,pad=0,pattern=0,scene=0,metadata=[],scene_retrigger='ON')
        request.update(values);return request
    def test_controller_menu_fields_stopped_guard_and_cancel(self):
        a=self.a;a.page='PROJECT MANAGE'
        from app.project_manager import MANAGE
        a.manage_index=MANAGE.index('EXPORT AUDIO');a.button('ENTER',True);a.button('ENTER',False)
        self.assertEqual(a.page,'EXPORT');self.assertEqual(a.softkeys(),('BACK','-','EXPORT'));self.assertEqual(len(frame(a)),8192)
        a.button('NAV RIGHT',True);a.rotate(2);self.assertEqual(a.export_source,2)
        a.playing=True;a.button('F3',True);self.assertFalse(a.export_busy)
        a.playing=False;a.button('F3',True);self.assertTrue(a.export_busy)
        action,request=a.actions[-1];self.assertEqual(action,'audio_export');self.assertEqual(request['source'],'GROUP')
        before=copy.deepcopy(request['project']);a.project['name']='NEW';self.assertEqual(request['project'],before)
        a.button('PLAY',True);self.assertFalse(a.playing)
        a.button('F1',True);self.assertEqual(a.actions[-1],('export_cancel',None))
    def test_pattern_scene_song_lengths_loops_and_tail(self):
        a=self.a;a.set_pattern_length(32);a.project['scenes'][0]=[0]+[None]*7;a.project['scene_lengths']['0']=16
        a.project['scenes'][1]=[0]+[None]*7;a.project['scene_lengths']['1']=48;a.project['song']=[0,1]
        request=self.request(mode='SONG',tail=2)
        before=copy.deepcopy(a.project)
        controls,plan,frames=compile_export(a,request)
        onsets=[int(line.split()[1]) for line in plan if line.startswith('sequence_event')]
        self.assertEqual(onsets,[0,384,1152]);self.assertEqual(frames,48000*10)
        self.assertEqual(a.project,before)
        a.settings['scene_retrigger']='OFF';request['scene_retrigger']='OFF'
        _,plan,_=compile_export(a,request)
        self.assertEqual([int(line.split()[1]) for line in plan if line.startswith('sequence_event')],[0,768])
    def test_sources_export_named_bus_stems_without_muting_other_routes(self):
        a=self.a;a.project['scenes'][0]=[0]+[None]*7
        self.assertEqual(export_targets(a,self.request(source='SOUND')),[(0,'A-Sound01')])
        self.assertEqual(export_targets(a,self.request(source='GROUP')),[(GROUP_BASE,'Group-A')])
        self.assertEqual(export_targets(a,self.request(source='ALL SOUNDS')),[(0,'A-Sound01')])
        self.assertEqual(export_targets(a,self.request(source='ALL GROUPS')),[(GROUP_BASE,'Group-A')])
        self.assertEqual(export_targets(a,self.request()),[(MASTER,'Mix')])
    def test_modulation_is_scheduled_and_original_saved_base_restored(self):
        a=self.a;a.project['groups'][0]['automation']={'0:0:value:-1:gain':{'base':80,'points':{'0':40,'96':80}}}
        controls,plan,frames=compile_export(a,self.request())
        self.assertTrue(any(line.startswith('offline_control 0 ') and 'routing ' in line for line in controls))
        self.assertGreater(len(controls),2);self.assertEqual(a.track()['gain'],80)
    def test_cancel_and_empty_song_fail_before_publication(self):
        cancel=threading.Event();cancel.set()
        with self.assertRaisesRegex(ValueError,'CANCELED'):compile_export(self.a,self.request(),cancel)
        with self.assertRaisesRegex(ValueError,'EMPTY'):export_spans(self.a,self.request(mode='SONG'))


@unittest.skipUnless((ROOT/'build/audio_engine').exists() and Path('/usr/share/alsa/alsa.conf').exists(),'Linux native build required')
class NativeExportTests(unittest.TestCase):
    request=ExportTests.request
    def setUp(self):
        ExportTests.setUp(self);(self.root/'build').mkdir();(self.root/'build/audio_engine').symlink_to(ROOT/'build/audio_engine')
        sample=self.root/'tone.wav'
        with wave.open(str(sample),'wb') as wav:
            wav.setparams((2,2,48000,0,'NONE','not compressed'));wav.writeframes(array.array('h',[8192,4096]*256).tobytes())
        self.a.track().update(sample=str(sample),start=0,end=256,gain=100)
    def read(self,path):
        with wave.open(str(path)) as wav:
            result=(wav.getframerate(),wav.getnframes());pcm=array.array('h');pcm.frombytes(wav.readframes(wav.getnframes()))
        return result,pcm
    def test_real_render_stereo_length_no_loop_tail_and_unique_names(self):
        before=copy.deepcopy(self.a.project);original=Path(self.a.track()['sample']).read_bytes();request=self.request(tail=1)
        destination=render_export(request,self.root);(rate,frames),pcm=self.read(destination/'Mix.wav')
        self.assertEqual((rate,frames),(48000,144000));self.assertGreater(pcm[0],8000)
        self.assertEqual(pcm[1],4095);self.assertTrue(all(v==0 for v in pcm[512:]));self.assertEqual(self.a.project,before);self.assertEqual(Path(self.a.track()['sample']).read_bytes(),original)
        second=render_export(request,self.root);self.assertNotEqual(destination,second)
        self.assertTrue((destination/'Export.json').is_file());self.assertFalse(any(p.name.startswith('.') for p in (self.root/'exports').iterdir()))
    def test_44100_stems_group_gain_and_scheduled_gain_modulation(self):
        a=self.a;a.project['groups'][0]['gain']=50
        a.put_event((0,96),dict(velocity=127,probability=100,length=24,note=36))
        a.project['groups'][0]['automation']={'0:0:value:-1:gain':{'base':100,'points':{'0':100,'95':100,'96':50}}}
        destination=render_export(self.request(source='SOUND',rate=44100),self.root)
        (rate,frames),pcm=self.read(destination/'A-Sound01.wav');self.assertEqual((rate,frames),(44100,88200))
        self.assertGreater(max(pcm[:600]),8000);self.assertLess(max(pcm[44100:44700]),4200)
        destination=render_export(self.request(source='GROUP',rate=44100),self.root)
        _,group=self.read(destination/'Group-A.wav');self.assertLess(max(group[:600]),4200)
    def test_failure_cancel_and_live_input_leave_no_export_files(self):
        cancel=threading.Event();cancel.set()
        with self.assertRaisesRegex(ValueError,'CANCELED'):render_export(self.request(),self.root,cancel)
        self.assertFalse((self.root/'exports').exists() and any((self.root/'exports').iterdir()))
        self.a.track().setdefault('routing',{})['input']='EXT STEREO'
        with self.assertRaisesRegex(ValueError,'LIVE INPUT'):render_export(self.request(),self.root)
        self.assertEqual(list((self.root/'exports').iterdir()),[])
    def test_lv2_effect_state_controls_and_modulation_survive_export(self):
        state=self.root/'state'
        uri='http://plugin.org.uk/swh-plugins/amp'
        commands='plugins 0 '+json.dumps(uri)+'\nplugin_param 0 0 0 6.0205999\nplugin_save 0 0 '+json.dumps(str(state))+'\nquit\n'
        saved=subprocess.run([str(ROOT/'build/audio_engine')],input=commands,capture_output=True,text=True,timeout=10)
        self.assertEqual(saved.returncode,0);self.assertTrue((state/'state.ttl').is_file())
        self.a.track()['plugins']=[dict(uri=uri,kind='EFFECT',controls={'gain':6.0205999},state=str(state/'state.ttl'))]
        metadata=json.loads(subprocess.check_output([str(ROOT/'build/audio_engine'),'--plugins'],text=True))
        destination=render_export(self.request(metadata=metadata),self.root)
        _,pcm=self.read(destination/'Mix.wav');self.assertAlmostEqual(max(pcm),16383,delta=2)

    def test_all_sound_stems_have_identical_timing_and_include_routed_returns(self):
        a=self.a;sample=a.track()['sample']
        a.project['groups'][0]['pads'][1].update(sample=sample,start=0,end=256,gain=50)
        a.put_event((1,96),dict(velocity=127,probability=100,length=24,note=37))
        a.track().setdefault('routing',{})['dest']='SOUND 2'
        a.project['groups'][0]['pads'][2]['gain']=100
        request=self.request(source='ALL SOUNDS')
        destination=render_export(request,self.root)
        self.assertEqual({p.name for p in destination.glob('*.wav')},{'A-Sound01.wav','A-Sound02.wav','A-Sound03.wav'})
        _,one=self.read(destination/'A-Sound01.wav');_,two=self.read(destination/'A-Sound02.wav');_,returned=self.read(destination/'A-Sound03.wav')
        self.assertTrue(any(one[:512]));self.assertFalse(any(two[:48000]));self.assertTrue(any(two[48000:48512]))
        self.assertEqual(one,returned)

    def test_live_instance_cannot_enable_offline_output(self):
        path=self.root/'forbidden.wav'
        script='render_start '+json.dumps(str(path))+' 100 1088 32 WAV 50 1 120 1\nquit\n'
        result=subprocess.run([str(ROOT/'build/audio_engine')],input=script,capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0);self.assertFalse(path.exists())
