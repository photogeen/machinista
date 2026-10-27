import copy,io,json,struct,tempfile,unittest
from pathlib import Path
from app.plugin_profiles import profile,banks,_cache,names
from app.plugin_bank_import import import_bank
from app.dexed_banks import decode_sysex,unpack_voice,voice_patch
from app.model import Application,validate_project
from app.mk2_session import Mk2Session
from app.controller_inputs import ControllerInputs
from app.mk2_display import snapshot
from app.control_display import control_state
from app.audio import AudioBackend

URI='https://github.com/dcoredump/dexed.lv2'

def message(payload,kind=0,channel=0):
    return bytes((0xf0,0x43,channel,kind,len(payload)>>7,len(payload)&127))+payload+bytes(((-sum(payload))&127,0xf7))

def single(name='EP TEST',level=80):
    voice=bytearray(155)
    for n in range(6):voice[n*21+16]=level;voice[n*21+18]=1;voice[n*21+20]=7
    voice[134]=31;voice[144]=24;voice[145:155]=name.encode().ljust(10)[:10]
    return bytes(voice)

def bank():
    packed=bytearray(128)
    # OP6: left/right curve 2/3, rate-scale 5, detune 11,
    # amplitude sensitivity 2, velocity 6, fixed mode, coarse 19.
    packed[11]=2|(3<<2);packed[12]=5|(11<<3);packed[13]=2|(6<<2);packed[14]=85;packed[15]=1|(19<<1);packed[16]=57
    packed[110]=31;packed[111]=7|(1<<3);packed[116]=1|(5<<1)|(6<<4);packed[117]=24
    result=[]
    for i in range(32):
        v=bytearray(packed);v[118:128]=f'VOICE {i+1:02}'.encode().ljust(10);result.append(v)
    return message(b''.join(result),9)

class DexedBankTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);_cache.clear();self.p=profile(URI)
        self.a=a=Application(self.root);a.page='PLUGIN';a.control_level=2
        self.meta=dict(uri=URI,name='Dexed',kind='INSTRUMENT',supported=True,ports=copy.deepcopy(self.p['parameters']))
        a.plugin_catalog=[self.meta];a.track()['plugins']=[dict(uri=URI,kind='INSTRUMENT',controls={s['symbol']:s['default'] for s in self.p['parameters']})]
    def test_single_voice_algorithm_and_detune_representation(self):
        b=decode_sysex(message(single()),self.p,'Bank');c=b['patches'][0]['controls']
        self.assertEqual(c['algorithm_num'],32);self.assertEqual(c['op6_osc_detune'],0);self.assertEqual(c['op1_operator_output_level'],80)
        self.assertEqual(c['transpose'],24);self.assertEqual(b['patches'][0]['name'],'EP TEST')
    def test_packed_operator_order_bitfields_and_all_patch_names(self):
        b=decode_sysex(bank(),self.p,'Cartridge');self.assertEqual(len(b['patches']),32);self.assertEqual(b['patches'][-1]['name'],'VOICE 32');c=b['patches'][0]['controls']
        expected=dict(kbd_lev_scl_lft_curve=2,kbd_lev_scl_rht_curve=3,kbd_rate_scaling=5,osc_detune=4,amp_mod_sensitivity=2,key_vel_sensitivity=6,operator_output_level=85,osc_mode=1,osc_freq_coarse=19,osc_freq_fine=57)
        for key,value in expected.items():self.assertEqual(c['op6_'+key],value,key)
        self.assertEqual(c['op1_operator_output_level'],0);self.assertEqual(c['feedback'],7);self.assertEqual(c['oscillator_sync'],1);self.assertEqual(c['lfo_waveform'],5);self.assertEqual(c['pitch_mod_sensitivity'],6)
    def test_multiple_complete_messages_and_invalid_files(self):
        data=message(single());self.assertEqual(len(decode_sysex(data+data,self.p,'Two')['patches']),2)
        invalid=[data[:-1],data+b'\0',data.replace(b'\x43',b'\x44',1),data[:-2]+bytes((data[-2]^1,0xf7)),message(single(),1),message(single(),0,16),message(single()[:154]),message(single())*257]
        bad=bytearray(single());bad[16]=100;invalid.append(message(bad))
        for value in invalid:
            with self.subTest(size=len(value)),self.assertRaises(ValueError):decode_sysex(value,self.p,'Bad')
    def test_all_parameters_reachable_and_each_page_has_eight_encoders(self):
        c=self.a.plugin_controls();self.assertEqual(len(c),len(self.p['pages'])*8);self.assertEqual({v['symbol'] for v in c},{v['symbol'] for v in self.meta['ports']}|{'@bank','@patch'})
        self.assertTrue(all(len(page['controls'])==8 for page in self.p['pages']))
    def test_bank_patch_selection_names_travel_and_project_roundtrip(self):
        result=import_bank(self.root,'dexed','Cartridge.syx',bank());a=self.a;s=Mk2Session(self.root,a,ControllerInputs(a),{});self.addCleanup(s.close)
        s.rotate_raw(1,-31);self.assertNotIn('profile_preset',a.plugin_selected());s.rotate_raw(1,-1);s.rotate_raw(2,32)
        self.assertEqual(snapshot(s.surface)['plugin_names'],('Cartridge','VOICE 02'));a.plugin_param=1;self.assertEqual(control_state(a)['value'],'VOICE 02')
        validate_project(a.project);a.save();Path(result['path']).unlink();_cache.clear();b=Application(self.root)
        self.assertEqual(b.track()['plugins'][0]['controls']['op6_osc_detune'],4);self.assertEqual(names(self.root,b.track()['plugins'][0]),('MISSING BANK','VOICE 02'))
    def test_bank_selection_never_recreates_synth_or_sends_virtual_ports(self):
        import_bank(self.root,'dexed','Patch.syx',message(single()));a=self.a
        backend=AudioBackend.__new__(AudioBackend);backend.sample_rate=44100;backend.plugin_chains={};backend.plugin_metadata=[self.meta];commands=[];backend.command=commands.append
        backend.plugins(0,a.track()['plugins']);a.plugins_rotate(1);backend.plugins(0,a.track()['plugins'])
        self.assertEqual(sum(c.startswith('plugins ') for c in commands),1);self.assertFalse(any('@bank' in c for c in commands))
    def test_raw_ranges_and_integer_checks_preserve_obxd_normalized_validation(self):
        b=decode_sysex(message(single()),self.p,'One');b['patches'][0]['controls']['op1_osc_detune']=-7
        import_bank(self.root,'dexed','One.json',json.dumps(b).encode())
        for key,value in [('op1_osc_detune',-8),('algorithm_num',0),('algorithm_num',1.5),('output',float('nan'))]:
            bad=copy.deepcopy(b);bad['patches'][0]['controls'][key]=value
            with self.assertRaises(ValueError):import_bank(self.root,'dexed','Bad.json',json.dumps(bad).encode())
    def test_web_upload_format_matches_selected_instrument(self):
        from app.web_plugin_banks import upload,listing
        data=message(single());r=upload(self.root,'Test.syx','dexed',io.BytesIO(data),len(data));self.assertEqual(r['patches'],1)
        self.assertEqual(next(p for p in listing(self.root) if p['id']=='dexed')['banks'][0]['name'],'Test')
        for identifier,name in [('obxd','Test.syx'),('dexed','Test.fxb')]:
            with self.assertRaises(ValueError):upload(self.root,name,identifier,io.BytesIO(data),len(data))


class DexedHttpTests(unittest.TestCase):
    from tests.test_web_server import WebHttpTests as _base
    setUp=_base.setUp
    stop=_base.stop
    request=_base.request
    def test_live_api_accepts_sysex_for_dexed_and_rejects_wrong_profile(self):
        from urllib.parse import urlencode
        data=bank();h={'X-Machinista-Token':self.library.token};q=urlencode(dict(profile='dexed',name='Keys.syx'))
        self.assertEqual(self.request('POST','/api/plugin-banks/upload?'+q,data)[0],403)
        status,_,body=self.request('POST','/api/plugin-banks/upload?'+q,data,h);self.assertEqual(status,200);self.assertEqual(json.loads(body)['patches'],32)
        q=urlencode(dict(profile='obxd',name='Keys.syx'));self.assertEqual(self.request('POST','/api/plugin-banks/upload?'+q,data,h)[0],400)

if __name__=='__main__':unittest.main()
