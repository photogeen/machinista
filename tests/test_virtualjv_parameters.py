"""Native-editor behavior using a tiny non-ROM fixture with known packed values."""
import json, unittest
from tests.test_virtualjv_controls import VirtualJVControlsTests
from app.virtualjv_controls import SPECS, PRESET, _cache, _ports_cache
from app.ni_display import plugin_value
from app.control_display import control_state
from app.mk2_display import snapshot

class VirtualJVParameterTests(VirtualJVControlsTests):
    def setUp(self):
        super().setUp()
        folder=self.root/'presets/virtualjv/prepared';(folder/'assets').mkdir()
        image=bytearray(362*3)
        # Independently chosen packed Tone1 cutoff/resonance/level values.
        image[362+26+49]=91
        # Look up offsets solely for fixture fields not asserted independently below.
        for symbol,value in [('t1_cutoff',91),('t1_level',103),('t4_on',128),('t2_coarse',244),('patch_pan',64)]:
            spec=next(p for p in SPECS if p['symbol']==symbol)
            image[362+spec['compact']]=value
        (folder/'assets/test.bin').write_bytes(image)
        (folder/'catalog.tsv').write_text('VJV1\nbank\t6\tTest\tassets/test.bin\t0\t3\t0\t0\tassets/test.bin\n')
        ports=self.a.plugin_catalog[0]['ports']
        for s in SPECS:
            ports.append(dict(index=s['index'],symbol=s['symbol'],name=s['name'],min=PRESET if not s['kind'] else s['min'],max=s['max'],default=s['default'],integer=True))
        _cache.clear();_ports_cache.clear()
    def test_all_pages_have_eight_encoders_and_four_complete_tones(self):
        ports=self.a.plugin_controls();self.assertEqual(len(ports),184)
        for start in range(8,184,8):
            group=ports[start:start+8]
            self.assertEqual(len({p['section'] for p in group}),1)
        for tone in range(1,5):
            self.assertEqual(sum(p['symbol'].startswith(f't{tone}_') for p in ports),40)
            for sym in ['attack','decay1','decay2','sustain','release','cutoff','resonance']:
                self.assertIn(f't{tone}_{sym}',[p['symbol'] for p in ports])
    def test_factory_values_and_first_turn_do_not_jump_from_sentinel(self):
        ports=self.a.plugin_controls();index=next(i for i,p in enumerate(ports) if p['symbol']=='t1_cutoff')
        port=ports[index];self.assertEqual(port['preset_value'],91)
        self.assertEqual(plugin_value(port,PRESET),'91')
        self.a.plugin_param=index;self.a.plugins_rotate(1)
        self.assertEqual(self.a.plugin_selected()['controls']['t1_cutoff'],92)
        self.assertEqual(plugin_value(next(p for p in ports if p['symbol']=='t2_coarse'),PRESET),'-12')
    def test_reset_page_preserves_other_tones_and_bank_change_inherits_new_patch(self):
        a=self.a;ports=a.plugin_controls();c=a.plugin_selected()['controls']
        c.update(t1_cutoff=30,t2_cutoff=40)
        a.plugin_param=next(i for i,p in enumerate(ports) if p['symbol']=='t1_cutoff')
        self.assertTrue(a.virtualjv_reset(True));self.assertEqual(c['t1_cutoff'],PRESET);self.assertEqual(c['t2_cutoff'],40)
        self.assertEqual(c['program'],1)
        a.plugin_param=1;a.plugins_rotate(1)
        self.assertEqual(c['program'],2);self.assertEqual(c['t2_cutoff'],PRESET)
    def test_mikro_and_mk2_show_envelope_section_and_effective_values(self):
        a=self.a;ports=a.plugin_controls();a.plugin_param=next(i for i,p in enumerate(ports) if p['symbol']=='t1_attack')
        small=control_state(a);large=snapshot(self.session.surface)
        self.assertIn('AMP',str(small));self.assertIn('AMP',str(large));self.assertFalse(large.get('plugin_names'))
        self.assertNotIn('-1000',str(large))
    def test_rhythm_hides_patch_tone_edits_but_keeps_performance(self):
        self.a.plugin_selected()['controls']['rhythm']=1
        self.assertEqual(len(self.a.plugin_controls()),8)
    def test_metadata_and_native_spec_remain_identical(self):
        from pathlib import Path
        root=Path(__file__).resolve().parents[1]
        self.assertEqual(list(SPECS),json.loads((root/'tests/data/plugin-specs/jv880.json').read_text()))
