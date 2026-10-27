"""NI focus/selection contract and shared editing, including undo/modulation."""
import tempfile
import unittest
from app.model import Application,validate_project
from app.layout import GROUP_BASE
from app.leds import led_report,FULL,DIM

class MultiSelectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=Application(self.tmp.name)
    def sounds(self,*slots):
        for slot in slots:self.a.select_sound(slot,True)
    def test_multi_focus_selected_focus_and_quiet_toggle(self):
        a=self.a;a.page='SELECT';a.button('F3',True);a.pad_on(2);a.release_pad(2)
        self.assertEqual((a.pad,a.selected_pads),(0,{0,2}))
        a.button('F1',True);self.assertTrue(a.select_multi)
        a.pad_on(2);a.release_pad(2);self.assertEqual(a.selected_pads,{0})
        a.pad_on(0);a.release_pad(0);self.assertEqual(a.selected_pads,{0})
        a.select_sound(2,True);a.button('F3',True);a.pad_on(2);a.release_pad(2)
        self.assertEqual((a.pad,a.selected_pads),(2,{0,2}))
        a.pad_on(4);a.release_pad(4);self.assertEqual((a.pad,a.selected_pads),(4,{4}))
    def test_group_memory_and_multi_selection_are_separate(self):
        a=self.a;self.sounds(2);a.select_sound(2);a.select_group(1);a.select_sound(4)
        a.select_group(0);self.assertEqual((a.pad,a.selected_pads),(2,{0,2}))
        a.select_group(1);self.assertEqual((a.pad,a.selected_pads),(4,{4}))
        a.select_group(2,True);self.assertEqual((a.group,a.selected_groups),(1,{1,2}))
        a.select_group(2);self.assertEqual(a.selected_groups,{1,2})
        a.select_sound(3);self.assertEqual((a.selection_level,a.selected_groups),(2,{2}))
    def test_group_chord_bank_and_no_audition(self):
        a=self.a;a.ensure_group_bank(1);a.group_bank=0;a.page='SELECT';a.select_multi=True;a.actions.clear()
        a.button('NAV RIGHT',True);a.button('GROUP',True);a.pad_on(12);a.release_pad(12);a.button('GROUP',False)
        self.assertEqual((a.group,a.selected_groups),(0,{0,8}));self.assertEqual(a.page,'SELECT')
        self.assertFalse(any(k in ('hit','midi_note') for k,v in a.actions))
    def test_relative_channel_clamp_and_single_undo(self):
        a=self.a;self.sounds(2);a.track()['gain']=95;a.project['groups'][0]['pads'][2]['gain']=40
        a.page='CHANNEL';a.channel_page=0;a.channel_field=0;count=len(a.undo)
        a.rotate(10);self.assertEqual([a.project['groups'][0]['pads'][i]['gain'] for i in (0,2)],[100,45])
        self.assertEqual(len(a.undo),count+1);a.undo_action();self.assertEqual([a.project['groups'][0]['pads'][i]['gain'] for i in (0,2)],[95,40])
    def test_group_mixer_relative_pan_and_gain(self):
        a=self.a;a.select_group(2,True);a.page='MIXER';a.mixer_level=1
        a.project['groups'][0]['gain']=60;a.project['groups'][2]['gain']=20;a.rotate(5)
        self.assertEqual([a.project['groups'][i]['gain'] for i in (0,2)],[65,25])
        a.mixer_field=1;a.rotate(-10);self.assertEqual([a.project['groups'][i]['routing']['pan'] for i in (0,2)],[-10,-10])
    def test_sampler_relative_discrete_and_instrument_guard(self):
        a=self.a;self.sounds(1,2);a.project['groups'][0]['pads'][2]['plugins']=[dict(uri='urn:instrument',kind='INSTRUMENT',controls={})]
        a.page='SAMPLER';a.sampler_page=2;a.sampler_field=5;a.track()['sampler']={'cutoff':19000};a.project['groups'][0]['pads'][1]['sampler']={'cutoff':1000}
        a.rotate(20);self.assertEqual(a.track()['sampler']['cutoff'],20000);self.assertEqual(a.project['groups'][0]['pads'][1]['sampler']['cutoff'],2000)
        self.assertNotIn('cutoff',a.project['groups'][0]['pads'][2].get('sampler',{}))
        a.sampler_page=1;a.sampler_field=2;a.rotate(1);self.assertEqual(a.project['groups'][0]['pads'][1]['sampler']['type'],'AHD')
    def test_pad_properties_are_discrete(self):
        a=self.a;self.sounds(2);a.page='PAD CONFIG';a.pad_field=4;a.rotate(1)
        self.assertEqual(a.track()['note'],a.project['groups'][0]['pads'][2]['note'])
        a.pad_field=0;a.rotate(3);self.assertEqual([a.project['groups'][0]['pads'][i]['choke_group'] for i in (0,2)],[3,3])
    def test_groove_relative_and_enum(self):
        a=self.a;self.sounds(2);a.page='GROOVE';a.groove_field=0;a.rotate(10)
        self.assertEqual(a.project['groups'][0]['pads'][2]['groove']['amount'],10)
        a.groove_field=1;a.rotate(1);self.assertEqual(a.project['groups'][0]['pads'][2]['groove']['cycle'],'1/8')
    def test_reset_selected_one_undo_and_events_preserved(self):
        a=self.a;self.sounds(2)
        for i in (0,2):a.project['groups'][0]['pads'][i]['name']='keep?'
        a.put_event((2,0),{'velocity':100});count=len(a.undo);a.reset_sound_slot(2)
        self.assertEqual(a.pad,0);self.assertEqual(len(a.undo),count+1);self.assertTrue(a.event_notes());self.assertNotEqual(a.track().get('name'),'keep?')
        a.undo_action();self.assertEqual(a.project['groups'][0]['pads'][2]['name'],'keep?')
    def test_group_batch_delete_and_undo(self):
        a=self.a
        for i in range(4):a.project['groups'][i]['name']=str(i)
        a.select_group(2,True);request=dict(index=0,indices=[0,2],generation=a.project_generation,revision=a.revision)
        a.finish_group_delete(request);self.assertEqual([g.get('name') for g in a.project['groups'][:2]],['1','3']);validate_project(a.project)
        a.undo_action();self.assertEqual([g.get('name') for g in a.project['groups'][:4]],['0','1','2','3'])
    def test_all_event_selection_edit_and_clear(self):
        a=self.a;a.put_event((0,0),{'velocity':50});a.put_event((2,24),{'velocity':70});a.page='PATTERN GRID';a.grid_follow=False
        a.shift=True;a.button('F2',True);self.assertEqual(len(a.grid_selected),2);a.shift=False;a.edit_grid_event();a.grid_field=2;a.rotate(5)
        self.assertEqual(sorted(e['velocity'] for e in a.event_notes().values()),[55,75])
        a.delete_grid_events();self.assertFalse(a.event_notes())
    def test_project_replace_clears_stale_selection(self):
        import copy
        a=self.a;self.sounds(3);a.project=copy.deepcopy(a.project);a.sync_selection();self.assertEqual(a.selected_pads,{a.pad})

    def test_same_plugin_same_slot_only_and_log_relative_amount(self):
        a=self.a;self.sounds(1,2,3)
        port=dict(symbol='x',default=10,min=1,max=1000,log=True)
        a.plugin_catalog=[dict(uri='urn:fx',ports=[port])]
        for i,uri in enumerate(('urn:fx','urn:fx','urn:other','urn:fx')):
            a.project['groups'][0]['pads'][i]['plugins']=[dict(uri=uri,kind='EFFECT',controls={'x':10 if i==0 else 100})]
        a.project['groups'][0]['pads'][3]['plugins'].insert(0,dict(uri='urn:other',kind='EFFECT',controls={}))
        a.page='PLUGIN';a.rotate(10);diff=a.track()['plugins'][0]['controls']['x']-10
        self.assertAlmostEqual(a.project['groups'][0]['pads'][1]['plugins'][0]['controls']['x'],100+diff,places=5)
        self.assertEqual(a.project['groups'][0]['pads'][2]['plugins'][0]['controls']['x'],100)
        self.assertEqual(a.project['groups'][0]['pads'][3]['plugins'][1]['controls']['x'],100)
    def test_macro_values_use_each_mapping_without_copying_assignments(self):
        a=self.a;self.sounds(2)
        for i in (0,2):
            t=a.project['groups'][0]['pads'][i];t['plugins']=[dict(uri='urn:fx',kind='EFFECT',controls={'x':0})]
            t['macros']={'0':dict(bus=i,slot=0,symbol='x',min=0,max=10 if i==0 else 20,value=0)}
        a.page='MACRO';a.rotate(10)
        self.assertEqual(a.track()['plugins'][0]['controls']['x'],1)
        self.assertEqual(a.project['groups'][0]['pads'][2]['plugins'][0]['controls']['x'],2)
        self.assertEqual(a.project['groups'][0]['pads'][2]['macros']['0']['max'],20)
    def test_shared_modulation_take_and_restore(self):
        a=self.a;self.sounds(2);a.page='CHANNEL';a.channel_page=0;a.channel_field=0
        before=[a.project['groups'][0]['pads'][i]['gain'] for i in (0,2)]
        a.playing=True;a.shift=True;a.clock_phase=12;a.rotate(-5)
        lanes=a.project['groups'][0]['automation'];self.assertEqual(len(lanes),2)
        a.automation_restore();self.assertEqual([a.project['groups'][0]['pads'][i]['gain'] for i in (0,2)],before)
        a.undo_action();self.assertFalse(a.project['groups'][0].get('automation',{}))

    def test_group_modulation_uses_each_groups_pattern(self):
        a=self.a;a.select_group(2,True);a.active_patterns[2]=1;a.page='MIXER';a.mixer_level=1
        a.playing=True;a.shift=True;a.clock_phase=12;a.rotate(-5)
        first=a.project['groups'][0]['automation'];other=a.project['groups'][2]['automation']
        self.assertTrue(next(iter(first)).startswith('0:'))
        self.assertTrue(next(iter(other)).startswith('1:'))
        a.automation_restore();a.undo_action();self.assertFalse(a.project['groups'][2].get('automation',{}))
    def test_direct_focus_change_replaces_unselected_but_preserves_selected(self):
        a=self.a;self.sounds(2);a.pad=2;a.sync_selection();self.assertEqual(a.selected_pads,{0,2})
        a.pad=3;a.sync_selection();self.assertEqual(a.selected_pads,{3})
    def test_shared_route_cycle_keeps_offending_peer_valid(self):
        from app.routing import build_graph
        a=self.a;self.sounds(2);a.page='CHANNEL';a.channel_page=0;a.channel_field=2
        fields=a.channel_fields()
        self.assertIn('dest',fields)
        a.channel_field=fields.index('dest')
        # Select a destination through normal navigation, guarding each resulting graph.
        for _ in range(8):a.rotate(1);build_graph(a.project)
        validate_project(a.project)

    def test_non_recordable_input_controls_do_not_write_peer_only_lanes(self):
        a=self.a;self.sounds(2);a.page='INPUT';a.input_field=1;a.playing=True;a.shift=True;a.rotate(5)
        self.assertEqual(a.project['groups'][0]['pads'][2]['routing']['input_gain'],105)
        self.assertFalse(a.project['groups'][0].get('automation',{}))
