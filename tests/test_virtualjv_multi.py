import copy,json,tempfile,unittest,wave
from pathlib import Path
from app.model import Application,validate_project
from app.layout import GROUP_BASE
from app.virtualjv_multi import URI,SPECS_MULTI,BY_SYMBOL,internal_destination,link_empty_pads
from app.routing import build_graph
from app.audio import AudioBackend
from app.native_sequence import sequence_commands

class VirtualJVMultiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.a=Application(self.root)
        self.meta=dict(uri=URI,name='VirtualJV Multi',kind='INSTRUMENT',supported=True,ports=[dict(index=p['index'],symbol=p['symbol'],name=p['name'],min=min(p['min'],p['default']),max=p['max'],default=p['default'],integer=True) for p in SPECS_MULTI])
        self.a.plugin_catalog=[self.meta]
    def add_rack(self,group=0):
        a=self.a;a.group=group;a.control_level=1;a.page='PLUGIN BROWSE';a.plugin_filter='INSTRUMENT';a.plugin_browser_index=0
        a.plugins_button('ENTER',True);self.assertEqual(a.page,'PLUGIN');return a.project['groups'][group]['plugins'][0]
    def backend(self):
        b=AudioBackend.__new__(AudioBackend);b.command=self.commands.append;b.sample_rate=44100;b.plugin_chains={};b.plugin_metadata=[self.meta]
        b.desired=b.recorder=b.capture_pending=b.native_capture=None;b.input_device='-';b.routing_signature=None;return b
    def test_group_rack_links_only_empty_pads_and_uses_one_plugin(self):
        a=self.a;a.track()['sample']='existing.wav';a.track()['end']=20
        plugin=self.add_rack();group=a.project['groups'][0]
        self.assertEqual(group['pads'][0]['sample'],'existing.wav')
        linked=[p for p in group['pads'] if internal_destination(p)]
        self.assertEqual([p['channel'] for p in linked],[1,2,3,4,5,6,7,10])
        self.assertTrue(all(not p.get('plugins') for p in linked));self.assertEqual(len(group['plugins']),1)
        validate_project(a.project)
    def test_instrument_scope_is_explicit_and_links_reject_duplicate_channels(self):
        self.add_rack();validate_project(self.a.project)
        self.a.project['groups'][0]['pads'][1]['channel']=1
        with self.assertRaisesRegex(ValueError,'already assigned'):build_graph(self.a.project)
        self.a.project['groups'][0]['pads'][1]['channel']=2
        self.a.track()['plugins']=[dict(uri=URI,kind='INSTRUMENT',controls={})]
        with self.assertRaises(ValueError):validate_project(self.a.project)
    def test_sequencer_compiles_channels_and_source_pad_identity(self):
        self.add_rack();a=self.a;a.active_clips[0]=True
        for pad in (0,1):a.put_event((pad,0,'fixture'+str(pad)),dict(_id='fixture'+str(pad),note=60,velocity=100,probability=100,length=48))
        commands=sequence_commands(a)
        self.assertIn(f'plugin_note_ch {GROUP_BASE} 0 60 100 0',commands)
        self.assertIn(f'plugin_note_ch {GROUP_BASE} 1 60 100 1',commands)
        self.assertFalse(any(c.startswith(('hit ','plugin_note ')) for c in commands))
    def test_live_release_uses_attack_routing_and_defers_same_pitch_noteoff(self):
        self.commands=[];b=self.backend();track=dict(self.a.track(),routing={'midi_target':'GROUP 0'},channel=2,note=60)
        b.hit(0,0,100,track,voice_token=11);b.hit(0,1,100,track,voice_token=12)
        b.note_off(0,0,60,11);self.assertFalse(any(c.endswith('60 0 0') for c in self.commands))
        b.note_off(0,1,60,12);self.assertEqual(self.commands[-2],f'plugin_note_ch {GROUP_BASE} 1 60 0 0');self.assertEqual(self.commands[-1],f'plugin_note_ch {GROUP_BASE} 1 60 0 1')
        b.hit(0,0,100,track,voice_token=13);track['channel']=6
        self.assertEqual(b.internal_control_targets(0,0,internal_destination(track)),[(GROUP_BASE,1),(GROUP_BASE,5)])
        b.note_off(0,0,60,13);self.assertEqual(self.commands[-1],f'plugin_note_ch {GROUP_BASE} 1 60 0 0')
    def test_part_mixer_is_separate_from_group_output_and_parameter_updates_are_sparse(self):
        plugin=self.add_rack();self.commands=[];b=self.backend();b.plugins(GROUP_BASE,[plugin]);count=len(self.commands)
        b.plugins(GROUP_BASE,[plugin]);self.assertFalse(any(c.startswith('plugin_param ') for c in self.commands[count:]))
        a=self.a;a.track()['gain']=37;a.track()['mute']=True;b.routing(a.project)
        self.assertIn(f'plugin_param {GROUP_BASE} 0 {BY_SYMBOL["p1_mixer_gain"]["index"]} 37',self.commands)
        self.assertIn(f'plugin_param {GROUP_BASE} 0 {BY_SYMBOL["p1_mixer_mute"]["index"]} 1',self.commands)
        self.assertIn(f'plugin_param {GROUP_BASE} 0 {BY_SYMBOL["p2_mixer_mute"]["index"]} 0',self.commands)
        self.assertEqual(sum(c.startswith('plugins ') for c in self.commands),1)
    def test_selected_part_has_25_pages_and_rhythm_has_three(self):
        plugin=self.add_rack();ports=self.a.plugin_controls();self.assertEqual(len(ports),198)
        self.assertEqual([p['symbol'] for p in ports[:4]],['editor_part','expansion','p1_bank','p1_program'])
        self.assertEqual(ports[32]['symbol'],'p1_t1_on')
        self.assertEqual(ports[192]['symbol'],'p1_velocity_switch')
        self.assertIn('PATCH ADVANCED',ports[192]['section'])
        plugin['controls']['editor_part']=1;self.assertEqual(self.a.plugin_controls()[32]['symbol'],'p2_t1_on')
        plugin['controls']['editor_part']=7;ports=self.a.plugin_controls();self.assertEqual(len(ports),24)
        self.assertFalse(any('_t1_' in p['symbol'] for p in ports))
    def test_older_multi_plugin_keeps_existing_pages_without_fake_advanced_controls(self):
        self.meta['ports']=[p for p in self.meta['ports'] if p['index']<1310]
        self.add_rack();ports=self.a.plugin_controls()
        self.assertEqual(len(ports),192);self.assertEqual(ports[32]['symbol'],'p1_t1_on')
        self.assertFalse(any(p['symbol']=='p1_velocity_switch' for p in ports))

    def test_encoder_changes_only_selected_part_and_reset_preserves_other_parts(self):
        plugin=self.add_rack();a=self.a;a.plugin_param=38;a.plugins_rotate(5)
        self.assertEqual(plugin['controls']['p1_t1_cutoff'],5);self.assertEqual(plugin['controls']['p2_t1_cutoff'],-1000)
        a.virtualjv_reset(True);self.assertEqual(plugin['controls']['p1_t1_cutoff'],-1000)
        a.plugin_param=0;a.plugins_rotate(1);self.assertEqual(plugin['controls']['editor_part'],1);self.assertEqual(a.plugin_param,0)
    def test_group_preset_and_group_delete_remap_shared_links(self):
        self.add_rack(2)
        from app.presets import preset_snapshot
        project,chains=preset_snapshot(self.a,'GROUP')
        self.assertEqual(project['groups'][0]['pads'][0]['routing']['midi_target'],'GROUP 0');validate_project(project)
        from app.group_delete import compact_group
        compacted,_=compact_group(self.a.project,1)
        self.assertEqual(compacted['groups'][1]['pads'][0]['routing']['midi_target'],'GROUP 1');validate_project(compacted)
    def test_removing_rack_unlinks_pads_and_new_sample_replaces_internal_source(self):
        self.add_rack();a=self.a;a.control_level=2
        sample=self.root/'new.wav'
        with wave.open(str(sample),'wb') as w:w.setparams((1,2,44100,0,'NONE','not compressed'));w.writeframes(b'\0\0'*20)
        a.assign_browser_sample(sample);self.assertIsNone(internal_destination(a.track()))
        a.control_level=1;a.plugin_slot=0;a.remove_plugin()
        self.assertTrue(all(internal_destination(p) is None for p in a.project['groups'][0]['pads']));validate_project(a.project)
    def test_multi_descriptors_match_native_source(self):
        root=Path(__file__).resolve().parents[1]
        path=root/'tests/data/plugin-specs/jv880-multi.json'
        if path.exists():self.assertEqual(list(SPECS_MULTI),json.loads(path.read_text()))
