import array
import copy
import json
import shutil
import tempfile
import unittest
import wave
from pathlib import Path
from app.model import Application,validate_project
from app.presets import preset_snapshot,write_preset,read_preset
from app.sampler import default_zone
from app.layout import GROUP_BASE

class PresetTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.a=Application(self.root)
        self.path=self.root/'samples'/'loop.wav'
        with wave.open(str(self.path),'wb') as w:w.setparams((1,2,44100,0,'NONE','not compressed'));w.writeframes(array.array('h',[1000]*100).tobytes())
        self.a.track().update(sample=str(self.path),start=0,end=100,name='KICK')
        self.a.track()['zones']=[default_zone(self.a.track())]
        self.a.track()['slice_source']={'sample':str(self.path),'start':0,'end':100}
        self.a.plugin_catalog=[dict(uri='urn:test',supported=True,kind='EFFECT',ports=[])]
    def bundle(self,kind,name='KIT'):
        project,chains=preset_snapshot(self.a,kind)
        for local,(bus,chain) in chains.items():
            for index,plugin in enumerate(chain):
                folder=self.root/'capture'/str(local)/str(index);folder.mkdir(parents=True,exist_ok=True)
                (folder/'state.ttl').write_text('opaque state');(folder/'resource.bin').write_bytes(b'plugin resource')
                plugin['state']=str(folder/'state.ttl')
        write_preset(dict(kind=kind,name=name,project=project),self.root)
        return self.root/'presets'/('Sounds' if kind=='SOUND' else 'Groups')/name/'Preset.json'
    def test_machinista_presets_and_legacy_presets_load(self):
        path=self.bundle('SOUND');data=json.loads(path.read_text())
        self.assertEqual(data['format'],'Machinista-preset')
        self.assertEqual(read_preset(path,'SOUND',self.root)['name'],'KICK')
        data['format']='Machinist-preset';path.write_text(json.dumps(data))
        self.assertEqual(read_preset(path,'SOUND',self.root)['name'],'KICK')
        data['format']='maschineOS-preset';path.write_text(json.dumps(data))
        self.assertEqual(read_preset(path,'SOUND',self.root)['name'],'KICK')
    def load_request(self,kind,group=0,pad=0):
        return dict(kind=kind,group=group,pad=pad,generation=self.a.project_generation,revision=self.a.revision)
    def test_sound_bundle_portable_deduplicated_with_independent_plugin_state_and_undo(self):
        a=self.a;a.track()['plugins']=[dict(uri='urn:test',kind='EFFECT',controls={'gain':.75},bypass=True)]
        source=copy.deepcopy(a.track());path=self.bundle('SOUND');self.assertEqual(a.track(),source)
        self.assertEqual(len(list((path.parent/'samples').iterdir())),1)
        moved=self.root/'moved';shutil.move(str(path.parent),moved);self.path.unlink()
        target=read_preset(moved/'Preset.json','SOUND',self.root)
        self.assertTrue(Path(target['zones'][0]['sample']).is_file());self.assertEqual(target['slice_source']['sample'],target['sample'])
        state=Path(target['plugins'][0]['state']);self.assertFalse(state.is_relative_to(moved));self.assertEqual((state.parent/'resource.bin').read_bytes(),b'plugin resource')
        before=copy.deepcopy(a.project);a.finish_preset_load(self.load_request('SOUND',1,3),target)
        loaded=a.project['groups'][1]['pads'][3];self.assertEqual(loaded['plugins'][0]['controls'],{'gain':.75});self.assertTrue(loaded['plugins'][0]['bypass'])
        self.assertEqual(a.project['groups'][0]['pads'][0],before['groups'][0]['pads'][0]);validate_project(a.project)
        a.undo_action();self.assertEqual(a.project,before)
    def test_group_remaps_internal_routes_macros_preserves_patterns_and_other_groups(self):
        a=self.a;a.group=2;a.project['groups'][2]['pads'][1]=copy.deepcopy(a.project['groups'][0]['pads'][0])
        g=a.project['groups'][2];g['name']='DRUMS';g['pads'][0]['routing']={'dest':'SOUND 33'}
        g['pads'][1]['plugins']=[dict(uri='urn:test',kind='EFFECT',controls={},bypass=False)]
        g['macros']={'0':dict(bus=33,slot=0,symbol='gain',value=50)}
        g['patterns'][0][0][0]=True
        path=self.bundle('GROUP');target=read_preset(path,'GROUP',self.root)
        self.assertFalse(any(any(l) for p in target['patterns'] for l in p))
        a.project['groups'][4]['patterns'][0][3][4]=True;before=copy.deepcopy(a.project)
        a.finish_preset_load(self.load_request('GROUP',4,0),target)
        loaded=a.project['groups'][4];self.assertEqual(loaded['patterns'],before['groups'][4]['patterns'])
        self.assertEqual(loaded['pads'][0]['routing']['dest'],'SOUND 65');self.assertEqual(loaded['macros']['0']['bus'],65)
        self.assertEqual(loaded['name'],'DRUMS');self.assertEqual(a.project['groups'][2],before['groups'][2]);validate_project(a.project)
    def test_undo_preserves_newly_captured_outgoing_plugin_state(self):
        a=self.a;path=self.bundle('SOUND');target=read_preset(path,'SOUND',self.root)
        a.track()['plugins']=[dict(uri='urn:test',kind='EFFECT',controls={'gain':1},bypass=False,state='old-state.ttl')]
        request=self.load_request('SOUND');request['previous']={0:[dict(a.track()['plugins'][0],state='captured-live-state.ttl')]}
        a.finish_preset_load(request,target);self.assertFalse(a.track().get('plugins'))
        a.undo_action();self.assertEqual(a.track()['plugins'][0]['state'],'captured-live-state.ttl')
    def test_duplicate_missing_assets_and_invalid_kind_fail_without_publication(self):
        path=self.bundle('SOUND','TEST')
        with self.assertRaises(ValueError):self.bundle('SOUND','test')
        with self.assertRaises(ValueError):read_preset(path,'GROUP',self.root)
        for sample in (path.parent/'samples').iterdir():sample.unlink()
        with self.assertRaises(ValueError):read_preset(path,'SOUND',self.root)
        project,_=preset_snapshot(self.a,'SOUND');self.path.unlink()
        with self.assertRaises(OSError):write_preset(dict(kind='SOUND',name='MISSING',project=project),self.root)
        self.assertFalse((self.root/'presets/Sounds/MISSING').exists())
        self.assertFalse(any(p.name.startswith('.') for p in (self.root/'presets/Sounds').iterdir()))
    def test_stale_missing_plugin_and_running_transport_do_not_replace(self):
        a=self.a;path=self.bundle('SOUND');target=read_preset(path,'SOUND',self.root);before=copy.deepcopy(a.project)
        request=self.load_request('SOUND');a.revision+=1;a.finish_preset_load(request,target);self.assertEqual(a.project,before)
        target['plugins']=[dict(uri='urn:missing',kind='EFFECT',controls={},bypass=False)]
        a.finish_preset_load(self.load_request('SOUND'),target);self.assertEqual(a.message,'PLUGIN NOT INSTALLED');self.assertEqual(a.project,before)
        a.playing=True;a.request_preset_load(path,'SOUND',0,0);self.assertFalse(any(k=='preset_load' for k,v in a.actions))
        a.finish_preset_load(self.load_request('SOUND'),target);self.assertEqual(a.project,before)
    def test_controller_save_name_load_confirmation_and_display(self):
        from app.project_manager import MANAGE
        from app.ni_display import frame
        a=self.a;a.button('SHIFT',True);a.button('MAIN',True);a.button('SHIFT',False);a.button('F3',True)
        a.menu=a.setting_entries().index('PROJECT SETTINGS');a.button('ENTER',True);a.menu=a.setting_entries().index('PROJECT');a.button('ENTER',True);self.assertEqual(a.page,'PROJECT')
        a.button('F3',True);self.assertEqual(a.page,'PROJECT MANAGE')
        a.manage_index=MANAGE.index('SAVE SOUND');a.button('F2',True)
        self.assertEqual(a.page,'PROJECT NAME');self.assertEqual(a.name_value,'');a.name_value='MY KICK';a.button('F3',True)
        self.assertEqual(a.page,'PROJECT MANAGE');action,request=a.actions.pop();self.assertEqual(action,'preset_save')
        write_preset(request,self.root);a.manage_index=MANAGE.index('LOAD SOUND');a.button('F2',True)
        self.assertEqual(a.page,'PRESET LOAD');self.assertEqual(a.softkeys(),('BACK','LOAD','BACK'));self.assertEqual(len(frame(a)),8192)
        a.button('F2',True);self.assertEqual(a.page,'CONFIRM');a.button('F1',True);self.assertEqual(a.page,'PRESET LOAD')
        a.button('F2',True);a.button('F2',True);self.assertEqual(a.actions[-1][0],'preset_load')
    def test_replaced_chain_automation_removed_but_notes_and_other_automation_kept(self):
        a=self.a;path=self.bundle('SOUND');target=read_preset(path,'SOUND',self.root)
        a.project['groups'][0]['patterns'][0][0][2]=True
        a.project['groups'][0]['automation']={'0:0:value:-1:gain':{'base':80,'points':{'0':20}},'0:1:value:-1:gain':{'base':80,'points':{'0':30}}}
        a.finish_preset_load(self.load_request('SOUND'),target)
        self.assertTrue(a.project['groups'][0]['patterns'][0][0][2]);self.assertNotIn('0:0:value:-1:gain',a.project['groups'][0]['automation'])
        self.assertIn('0:1:value:-1:gain',a.project['groups'][0]['automation'])

from tests import test_lv2_engine as lv2_fixture
ENGINE=lv2_fixture.ENGINE
@unittest.skipUnless(ENGINE.exists() and Path('/usr/share/alsa/alsa.conf').exists(),'Linux LV2/ALSA build required')
class NativePresetTests(unittest.TestCase):
    setup_engine=lv2_fixture.LV2RenderTests.setup_engine
    send=lv2_fixture.LV2RenderTests.send
    def test_group_preset_captures_actual_lv2_buses_and_restores_audio_on_other_group(self):
        from app.presets import prepare_preset_state
        from app.layout import GROUP_BASE
        import time
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);a=Application(root);a.group=2;a.pad=3
            uri='http://plugin.org.uk/swh-plugins/amp'
            a.plugin_catalog=[dict(uri=uri,supported=True)]
            plugin=dict(uri=uri,kind='EFFECT',controls={'gain':6.0205999},bypass=False)
            a.track()['plugins']=[copy.deepcopy(plugin)];a.project['groups'][2]['plugins']=[copy.deepcopy(plugin)]
            p,output=self.setup_engine(root)
            for bus in (35,GROUP_BASE+2):
                self.send(p,'plugins '+str(bus)+' '+json.dumps(uri));self.assertEqual(json.loads(p.stdout.readline())['status'],'ready')
                self.send(p,f'plugin_param {bus} 0 0 6.0205999')
            project,chains=preset_snapshot(a,'GROUP');request=dict(kind='GROUP',name='ROUNDTRIP',project=project,chains=chains)
            proxy=type('Proxy',(),{'command':lambda _,line:self.send(p,line)})()
            prepare_preset_state(proxy,request,root)
            statuses=[json.loads(p.stdout.readline()) for _ in range(3)]
            self.assertEqual(sum(e['kind']=='state_barrier' for e in statuses),1)
            self.assertTrue(all(e['status']=='saved' for e in statuses if e['kind']!='state_barrier'))
            write_preset(request,root);path=root/'presets/Groups/ROUNDTRIP/Preset.json'
            target=read_preset(path,'GROUP',root)
            a.finish_preset_load(dict(kind='GROUP',group=4,pad=3,generation=a.project_generation,revision=a.revision),target)
            self.assertEqual(a.message,'GROUP PRESET LOADED')
            for bus,target in ((35,None),(GROUP_BASE+2,None),(67,a.project['groups'][4]['pads'][3]),(GROUP_BASE+4,a.project['groups'][4])):
                self.send(p,'plugins '+str(bus)+(' '+json.dumps(uri) if target else ''))
                event=json.loads(p.stdout.readline())
                while event['kind']=='audio' and event['status']=='idle':event=json.loads(p.stdout.readline())
                self.assertEqual(event['status'],'ready')
                if target:
                    self.send(p,f'plugin_restore {bus} 0 '+json.dumps(target['plugins'][0]['state']));self.assertEqual(json.loads(p.stdout.readline())['status'],'saved')
                    self.send(p,f'plugin_param {bus} 0 0 '+str(target['plugins'][0]['controls']['gain']))
            sample=root/'sample.f32';sample.write_bytes(array.array('f',[.125]*96).tobytes())
            self.send(p,'load 67 48000 '+json.dumps(str(sample)));self.send(p,'device "fixture"');event=json.loads(p.stdout.readline())
            if event['status']=='idle':event=json.loads(p.stdout.readline())
            self.assertEqual(event['status'],'ready');self.send(p,'hit 67 1 1');time.sleep(.04);self.send(p,'quit');_,error=p.communicate(timeout=5)
            self.assertEqual(p.returncode,0,error);values=array.array('h');values.frombytes(output.read_bytes());sounding=[v for v in values if v]
            self.assertEqual(len(sounding),96);self.assertLessEqual(max(abs(v-16383) for v in sounding),1)
