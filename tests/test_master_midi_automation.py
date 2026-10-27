import copy
import tempfile
import unittest
from unittest.mock import patch
from app.model import Application,validate_project
from app.layout import MASTER,GROUP_BASE
from app.automation import lane_key

class MasterMidiAutomationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.a=Application(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def master(self):
        a=self.a;a.project['song']=[0,0];a.song_playing=a.playing=True;a.page='MIXER';a.mixer_level=0;a.mixer_field=0;a.shift=True;a.clock_phase=0
        return a
    def learn(self,descriptor,cc=20,channel=0):
        a=self.a;a.midi_last_touched=(a.project_generation,descriptor);a.page='MIDI LEARN';a.button('F2',True);self.assertIsNotNone(a.midi_learning)
        before=a.automation_value(descriptor);self.assertTrue(a.midi_remote_event(0xb0|channel,[cc,1]));self.assertEqual(a.automation_value(descriptor),before)
    def test_master_song_interpolation_save_restore_and_repeated_scene_independence(self):
        a=self.master();base=a.project.get('gain',100);a.rotate(-20);a.clock_phase=96;a.rotate(-40)
        a.shift=False;a.clock_phase=48;a.automation_tick();self.assertEqual(a.project['gain'],60)
        saved=a.project_for_save();self.assertEqual(saved.get('gain',100),base);validate_project(saved)
        a.save();b=Application(a.root);self.assertEqual(b.project.get('gain',100),base);self.assertEqual(len(b.project['master_automation']),1)
        a.automation_written.clear();a.song_bar=1;a.clock_phase=0;a.automation_tick();self.assertEqual(a.project['gain'],base)
        a.automation_restore();self.assertEqual(a.project['gain'],base)
    def test_master_not_recorded_outside_song_and_mixer_sound_modulation(self):
        a=self.master();a.song_playing=False;a.rotate(-10);self.assertNotIn('master_automation',a.project)
        a.mixer_level=2;a.clock_phase=0;a.rotate(-10);self.assertTrue(a.project['groups'][0]['automation']);validate_project(a.project_for_save())
    def test_song_insert_delete_remaps_lanes_and_undo(self):
        a=self.master();a.rotate(-10);key=next(iter(a.project['master_automation']));a.shift=False;a.page='SONG';a.song_index=0;a.button('F1',True)
        self.assertIn('1:'+key.split(':',1)[1],a.project['master_automation']);a.delete_song_entry();self.assertIn(key,a.project['master_automation'])
        a.song_index=0;a.delete_song_entry();self.assertFalse(a.project['master_automation']);validate_project(a.project)
    def test_master_take_and_step_undo(self):
        a=self.master();a.rotate(-10);a.clock_phase=96;a.rotate(-10);self.assertEqual(len(a.undo),1)
        a.shift=False;a.undo_action(step=True);lane=next(iter(a.project['master_automation'].values()));self.assertEqual(set(lane['points']),{'0'})
        a.undo_action(redo=True,step=True);self.assertEqual(set(lane['points']),{'0','96'})
    def test_master_auto_overview_disable_remove(self):
        a=self.master();a.rotate(-10);a.page='SONG';a.button('F3',True);self.assertEqual(a.page,'SONG AUTO');self.assertEqual(a.softkeys(),('BACK','ON/OFF','REMOVE'))
        a.shift=False;a.button('F2',True);self.assertFalse(next(iter(a.project['master_automation'].values()))['enabled'])
        a.clock_phase=0;a.automation_tick();self.assertEqual(a.project.get('gain',100),100)
        a.button('F3',True);self.assertEqual(a.page,'CONFIRM');a.button('F2',True);self.assertFalse(a.project['master_automation'])
    def test_cc_learn_channel_range_enum_reserved_passthrough(self):
        a=self.a;d=(0,'sampler',-1,'tune');self.learn(d,20,2)
        self.assertFalse(a.midi_remote_event(0xb0,[20,127]));a.midi_remote_event(0xb2,[20,127]);self.assertEqual(a.track()['sampler']['tune'],48)
        a.midi_remote_event(0xb2,[20,0]);self.assertEqual(a.track()['sampler']['tune'],-48)
        for cc in (64,120,121,123,127):self.assertFalse(a.midi_remote_event(0xb2,[cc,127]))
        self.learn((0,'sampler',-1,'filter'),21);a.midi_remote_event(0xb0,[21,127]);self.assertEqual(a.track()['sampler']['filter'],'EQ');validate_project(a.project)
        a.save();b=Application(a.root);self.assertIn('2:20',b.project['midi_mappings'])
    def test_cc_permanent_gesture_has_one_history_snapshot(self):
        a=self.a;self.learn((0,'value',-1,'gain'));before=len(a.undo)
        for value in (5,20,60,127):a.midi_remote_event(0xb0,[20,value])
        self.assertEqual(len(a.undo),before+1);self.assertEqual(a.track()['gain'],100);self.assertTrue(any(k=='routing_refresh' for k,v in a.actions))
    def test_cc_record_target_owner_while_focus_elsewhere_and_master_song(self):
        a=self.a;self.learn((16,'value',-1,'gain'));a.playing=a.recording=True;a.group=0;a.clock_phase=24;a.midi_remote_event(0xb0,[20,64])
        self.assertFalse(a.project['groups'][0].get('automation'));self.assertIn(lane_key(0,(16,'value',-1,'gain')),a.project['groups'][1]['automation']);self.assertEqual(a.group,0)
        self.learn((MASTER,'value',-1,'gain'),22);a.project['song']=[0];a.song_playing=True;a.midi_remote_event(0xb0,[22,50]);self.assertTrue(a.project['master_automation']);validate_project(a.project_for_save())
    def test_plugin_reindex_and_group_delete_preserve_remote_identities(self):
        a=self.a;a.project['plugins']=[{'uri':'urn:test','kind':'EFFECT','controls':{'gain':1}}]
        a.project['master_automation']={'0:'+str(MASTER)+':plugin:0:gain':{'base':1,'uri':'urn:test','points':{'0':.5}}};a.project['song']=[0]
        a.project['midi_mappings']={'0:20':dict(descriptor=[MASTER,'plugin',0,'gain'],uri='urn:test',name='GAIN',min=0,max=1)}
        a.plugin_reindex(MASTER,{0:1});self.assertIn(':plugin:1:',next(iter(a.project['master_automation'])));self.assertEqual(a.project['midi_mappings']['0:20']['descriptor'][2],1)
        a.plugin_reindex(MASTER,{});self.assertFalse(a.project['master_automation']);self.assertFalse(a.project['midi_mappings'])
    def test_learn_is_canceled_after_leaving_its_view(self):
        a=self.a;a.midi_last_touched=(a.project_generation,(0,'value',-1,'gain'));a.page='MIDI LEARN';a.button('F2',True);a.page='PAD'
        self.assertFalse(a.midi_remote_event(0xb0,[20,127]));self.assertIsNone(a.midi_learning);self.assertFalse(a.project.get('midi_mappings'))

    def test_invalid_project_lanes_and_mappings_rejected(self):
        a=self.a;a.project['song']=[0];a.project['master_automation']={'0:0:value:-1:gain':{'base':100,'points':{'0':20}}}
        with self.assertRaises(ValueError):validate_project(a.project)
        a.project.pop('master_automation');a.project['midi_mappings']={'0:64':dict(descriptor=[0,'value',-1,'gain'],name='GAIN',min=0,max=100)}
        with self.assertRaises(ValueError):validate_project(a.project)

    def test_song_export_controls_have_independent_entry_gain_and_no_pattern_leak(self):
        from app.export_audio import compile_export
        a=self.a;a.project['song']=[0,0];d=(MASTER,'value',-1,'gain')
        a.project['master_automation']={lane_key(0,d):{'base':100,'points':{'0':50}},lane_key(1,d):{'base':100,'points':{'0':25,'96':75}}}
        request=dict(mode='SONG',rate=48000,tail=0,group=0,pattern=0,scene=0,metadata=[],scene_retrigger='OFF')
        commands,_,_=compile_export(a,request)
        self.assertTrue(any('1088 0.5 ' in c for c in commands));self.assertTrue(any('1088 0.25 ' in c for c in commands));self.assertTrue(any('1088 0.75 ' in c for c in commands));self.assertEqual(a.project.get('gain',100),100)
        request['mode']='PATTERN';commands,_,_=compile_export(a,request);self.assertFalse(any('1088 0.25 ' in c for c in commands))

    def test_plugin_cc_log_scale_and_uri_guard(self):
        a=self.a;uri='urn:test';a.track()['plugins']=[dict(uri=uri,kind='EFFECT',controls={'freq':100})]
        a.plugin_catalog=[dict(uri=uri,ports=[dict(symbol='freq',min=10,max=1000,log=True,integer=False)])]
        self.learn((0,'plugin',0,'freq'));a.midi_remote_event(0xb0,[20,64]);self.assertAlmostEqual(a.track()['plugins'][0]['controls']['freq'],10*100**(64/127))
        self.assertEqual(a.actions[-1][0],'plugin_controls');a.track()['plugins'][0]['uri']='urn:other';a.midi_remote_event(0xb0,[20,127]);self.assertEqual(a.message,'MIDI TARGET MISSING')

    def test_scene_deletion_removes_only_matching_song_entry_automation(self):
        a=self.a;a.project['song']=[0,1,0];d=(MASTER,'value',-1,'gain')
        a.project['master_automation']={lane_key(i,d):{'base':100,'points':{'0':20+i}} for i in range(3)}
        a.scene=0;a.delete_scene();self.assertEqual(a.project['song'],[0]);self.assertEqual(a.project['master_automation'][lane_key(0,d)]['points']['0'],21);validate_project(a.project)

    def test_group_delete_remaps_midi_binding(self):
        from app.group_delete import compact_group
        a=self.a;self.learn((16,'value',-1,'gain'));self.learn((0,'value',-1,'gain'),21)
        result,_=compact_group(a.project,0);self.assertEqual(result['midi_mappings']['0:20']['descriptor'][0],0);self.assertNotIn('0:21',result['midi_mappings']);validate_project(result)

from pathlib import Path
import array
import wave
import json
import subprocess
from app.export_audio import render_export
ROOT=Path(__file__).resolve().parent.parent

@unittest.skipUnless((ROOT/'build/audio_engine').exists() and Path('/usr/share/alsa/alsa.conf').exists(),'Linux native build required')
class NativeMasterAutomationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        (self.root/'build').mkdir();(self.root/'build/audio_engine').symlink_to(ROOT/'build/audio_engine')
        self.a=Application(self.root);sample=self.root/'tone.wav'
        with wave.open(str(sample),'wb') as wav:
            wav.setparams((2,2,48000,0,'NONE','not compressed'));wav.writeframes(array.array('h',[8192,4096]*256).tobytes())
        self.a.track().update(sample=str(sample),start=0,end=256,gain=100)
        self.a.put_event((0,0),dict(velocity=127,probability=100,length=24,note=36));self.a.project['song']=[0,0]
    def render(self,metadata=[]):
        a=self.a;request=dict(project=a.project_for_save(),mode='SONG',source='MIX',rate=48000,tail=0,group=0,pad=0,pattern=0,scene=0,metadata=metadata,scene_retrigger='ON')
        destination=render_export(request,self.root)
        with wave.open(str(destination/'Mix.wav')) as wav:
            pcm=array.array('h');pcm.frombytes(wav.readframes(wav.getnframes()));return pcm
    def test_actual_song_master_gain_and_pan_are_audible_and_save_keeps_base(self):
        a=self.a;gain=(MASTER,'value',-1,'gain');pan=(MASTER,'routing',-1,'pan')
        a.project['master_automation']={lane_key(0,gain):dict(base=100,points={'0':50}),lane_key(1,gain):dict(base=100,points={'0':25}),lane_key(1,pan):dict(base=0,points={'0':100})}
        before=copy.deepcopy(a.project);pcm=self.render();self.assertAlmostEqual(pcm[0],4095,delta=2);self.assertAlmostEqual(pcm[1],2047,delta=2)
        self.assertEqual(pcm[192000],0);self.assertAlmostEqual(pcm[192001],1023,delta=2);self.assertEqual(a.project,before)
    def test_actual_master_lv2_automation_changes_effect_without_chain_replacement(self):
        a=self.a;uri='http://plugin.org.uk/swh-plugins/amp';state=self.root/'state'
        script='plugins '+str(MASTER)+' '+json.dumps(uri)+'\nplugin_save '+str(MASTER)+' 0 '+json.dumps(str(state))+'\nquit\n'
        result=subprocess.run([str(ROOT/'build/audio_engine')],input=script,text=True,capture_output=True,timeout=10);self.assertEqual(result.returncode,0);self.assertTrue((state/'state.ttl').exists())
        a.project['plugins']=[dict(uri=uri,kind='EFFECT',controls={'gain':0},state=str(state/'state.ttl'))]
        d=(MASTER,'plugin',0,'gain');a.project['master_automation']={lane_key(0,d):dict(base=0,uri=uri,points={'0':0}),lane_key(1,d):dict(base=0,uri=uri,points={'0':-6.0205999})}
        metadata=json.loads(subprocess.check_output([str(ROOT/'build/audio_engine'),'--plugins'],text=True));pcm=self.render(metadata)
        self.assertAlmostEqual(pcm[0],8191,delta=2);self.assertAlmostEqual(pcm[192000],4095,delta=3);self.assertEqual(a.project['plugins'][0]['controls']['gain'],0)
