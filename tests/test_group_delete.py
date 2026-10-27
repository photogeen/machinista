import copy
from pathlib import Path
import tempfile
import unittest
from app.model import Application,validate_project
from app.group_delete import compact_group
from app.layout import GROUP_BASE,MASTER
from app.routing import build_graph

class GroupDeleteTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.a=Application(self.temp.name)
    def request(self,index):return dict(index=index,generation=self.a.project_generation,revision=self.a.revision)
    def test_hardware_chord_uses_group_pad_mapping_without_resetting_sound(self):
        a=self.a;a.button('SHIFT',True);a.button('ERASE',True);a.button('GROUP',True)
        self.assertEqual(a.page,'GROUP');before=copy.deepcopy(a.project);a.pad_on(13)
        self.assertEqual(a.actions[-1][0],'group_delete');self.assertEqual(a.actions[-1][1]['index'],1)
        self.assertEqual(a.project,before)
        a.actions=[];a.pad_on(0);self.assertFalse(a.actions)
    def test_compaction_preserves_sounds_patterns_and_scene_references(self):
        a=self.a
        for i,g in enumerate(a.project['groups']):g['name']=str(i)
        a.put_note(2,1,dict(note=40,velocity=99,probability=100),group=2,pattern=3)
        a.project['scenes'][0][2]=3;before=copy.deepcopy(a.project)
        result,mapping=compact_group(a.project,1)
        self.assertEqual(result['groups'][1],before['groups'][2]);self.assertEqual(result['scenes'][0][1],3)
        self.assertIsNone(result['scenes'][0][-1]);self.assertEqual(mapping(2),1);self.assertIsNone(mapping(1))
        self.assertEqual(a.project,before);validate_project(result)
    def test_routes_macros_automation_and_sampling_sources_move_or_disconnect(self):
        a=self.a;groups=a.project['groups']
        groups[0]['routing']={'dest':'GROUP 2','aux1_dest':'GROUP 1','aux2_dest':'SOUND 35'}
        a.project['macros']={'0':{'bus':35,'slot':0,'symbol':'gain'},'1':{'bus':GROUP_BASE+1,'slot':0,'symbol':'gain'}}
        groups[2]['pads'][3]['plugins']=[{'uri':'urn:fx','kind':'EFFECT','controls':{}}]
        groups[0]['automation']={'0:35:plugin:0:gain':{'base':0,'points':{'0':1}},f'0:{GROUP_BASE+1}:value:-1:gain':{'base':80,'points':{'0':60}}}
        a.project['sampling']={'source':'INTERNAL','input':'GROUP 2','mode':'MANUAL'}
        result,_=compact_group(a.project,1)
        self.assertEqual(result['groups'][0]['routing'],{'dest':'GROUP 1','aux1_dest':'NONE','aux2_dest':'SOUND 19'})
        self.assertEqual(result['macros']['0']['bus'],19);self.assertNotIn('1',result['macros'])
        self.assertEqual(set(result['groups'][0]['automation']),{'0:19:plugin:0:gain'})
        self.assertEqual(result['sampling']['input'],'GROUP 1');build_graph(result)
    def test_finishing_delete_and_undo_redo_preserve_saved_plugin_state(self):
        a=self.a;a.project['groups'][2]['name']='KEEP';a.group=2
        chain=[{'uri':'urn:fx','kind':'EFFECT','controls':{},'state':'cache/saved.ttl'}]
        a.project['groups'][2]['pads'][3]['plugins']=copy.deepcopy(chain)
        request=self.request(1);request['chains']={35:chain};a.finish_group_delete(request)
        self.assertEqual(a.group,1);self.assertEqual(a.project['groups'][1]['pads'][3]['plugins'],chain)
        self.assertIn(('reload',None),a.actions);self.assertEqual(a.project_generation,1)
        a.undo_action();self.assertEqual(a.project['groups'][2]['pads'][3]['plugins'],chain)
        self.assertEqual(a.group,2)
        a.undo_action(redo=True);self.assertEqual(a.project['groups'][1]['name'],'KEEP')
        self.assertEqual(a.group,1)
    def test_last_populated_group_resets_to_empty_default_without_deleting_files(self):
        a=self.a;sample=Path(self.temp.name)/'sample.wav';sample.touch();a.track().update(sample=str(sample),end=10)
        a.finish_group_delete(self.request(0))
        self.assertEqual(a.group,0);self.assertFalse(any(t.get('sample') for g in a.project['groups'] for t in g['pads']))
        self.assertTrue(sample.exists());validate_project(a.project)
    def test_empty_trailing_bank_is_removed_but_referenced_bus_is_kept(self):
        a=self.a;a.ensure_group_bank(1);a.project['groups'][8]['name']='DELETE'
        result,_=compact_group(a.project,8);self.assertEqual(len(result['groups']),8)
        a.project['groups'][0]['routing']={'aux1_dest':'GROUP 15'}
        result,_=compact_group(a.project,8);self.assertEqual(len(result['groups']),16)
        self.assertEqual(result['groups'][0]['routing']['aux1_dest'],'GROUP 14')
    def test_pending_delete_cancels_if_project_changes(self):
        a=self.a;request=self.request(1);a.remember();before=copy.deepcopy(a.project);a.finish_group_delete(request)
        self.assertEqual(a.project,before);self.assertEqual(a.message,'GROUP CHANGED: CANCELED')
    def test_deleted_internal_recording_source_falls_back_to_master(self):
        a=self.a;a.project['sampling']={'source':'INTERNAL','input':'GROUP 1'}
        result,_=compact_group(a.project,1);self.assertEqual(result['sampling']['input'],'MASTER')
    def test_sampling_take_history_moves_with_groups_and_follows_undo_redo(self):
        a=self.a;a.project['groups'][2]['name']='KEEP';a.record_history={(2,3):[{'sample':'take.wav'}],(1,0):[{'sample':'deleted.wav'}]};a.record_cursor={(2,3):0,(1,0):0}
        before=copy.deepcopy((a.record_history,a.record_cursor));a.finish_group_delete(self.request(1))
        self.assertEqual(a.record_history,{(1,3):[{'sample':'take.wav'}]})
        a.undo_action();self.assertEqual((a.record_history,a.record_cursor),before)
        a.undo_action(redo=True);self.assertEqual(a.record_cursor,{(1,3):0})
    def test_automated_route_to_empty_bus_keeps_bank_and_remaps_points(self):
        a=self.a;a.ensure_group_bank(1)
        a.project['groups'][0]['automation']={'0:0:routing:-1:aux1_dest':{'base':'NONE','points':{'0':'GROUP 15'}}}
        result,_=compact_group(a.project,8)
        self.assertEqual(len(result['groups']),16)
        self.assertEqual(result['groups'][0]['automation']['0:0:routing:-1:aux1_dest']['points']['0'],'GROUP 14')
