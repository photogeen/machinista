"""Real LV2 chains, routing dependencies and serial fallback through ALSA file PCM."""
import array,json,os,shutil,subprocess,tempfile,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ENGINE=ROOT/'build/audio_engine'
@unittest.skipUnless(ENGINE.exists() and Path('/usr/share/alsa/alsa.conf').exists(),'Linux native audio required')
class ParallelRenderTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  bundle=self.root/'lv2/gain.lv2';bundle.mkdir(parents=True)
  prefix='@prefix lv2: <http://lv2plug.in/ns/lv2core#>. @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>. @prefix doap: <http://usefulinc.com/ns/doap#>. '
  uris=['urn:test:parallel-gain','urn:test:parallel-sc','urn:test:parallel-synth']
  (bundle/'manifest.ttl').write_text(prefix+'\n'.join(f'<{u}> a lv2:Plugin; lv2:binary <gain.so>; rdfs:seeAlso <gain.ttl>.' for u in uris))
  ports='[a lv2:InputPort,lv2:AudioPort;lv2:index 0;lv2:symbol "in";lv2:name "In"],[a lv2:OutputPort,lv2:AudioPort;lv2:index 1;lv2:symbol "out";lv2:name "Out"],[a lv2:InputPort,lv2:ControlPort;lv2:index 2;lv2:symbol "gain";lv2:name "Gain";lv2:default 1;lv2:minimum 0;lv2:maximum 8]'
  sc=',[a lv2:InputPort,lv2:AudioPort;lv2:index 3;lv2:symbol "sc";lv2:name "SC";lv2:portProperty lv2:isSideChain]'
  synth=ports.replace('a lv2:InputPort,lv2:AudioPort;lv2:index 0','a lv2:OutputPort,lv2:AudioPort;lv2:index 0')
  (bundle/'gain.ttl').write_text(prefix+'\n'.join(f'<{u}> a lv2:Plugin;doap:name "Parallel fixture";lv2:port {synth if i==2 else ports+(sc if i==1 else "")}.' for i,u in enumerate(uris)))
  source=self.root/'gain.c';source.write_text('''#include <lv2/core/lv2.h>
#include <stdlib.h>
#include <string.h>
typedef struct {float*p[4];int synth;} S;
static LV2_Handle init(const LV2_Descriptor*d,double r,const char*b,const LV2_Feature*const*f){S*s=calloc(1,sizeof(S));s->synth=strstr(d->URI,"synth")!=0;return s;}
static void connect(LV2_Handle h,uint32_t p,void*v){((S*)h)->p[p]=v;}
static void run(LV2_Handle h,uint32_t n){S*s=h;if(s->synth){for(unsigned i=0;i<n;++i)s->p[0][i]=s->p[1][i]=.03125f*(*s->p[2]);return;}for(unsigned i=0;i<n;++i)s->p[1][i]=(s->p[0][i]+(s->p[3]?s->p[3][i]:0))*(*s->p[2]);}
static void cleanup(LV2_Handle h){free(h);}
static const LV2_Descriptor d[]={{"urn:test:parallel-gain",init,connect,0,run,0,cleanup,0},{"urn:test:parallel-sc",init,connect,0,run,0,cleanup,0},{"urn:test:parallel-synth",init,connect,0,run,0,cleanup,0}};
const LV2_Descriptor*lv2_descriptor(uint32_t i){return i<3?d+i:0;}
''')
  flags=subprocess.check_output(['pkg-config','--cflags','lv2'],text=True).split()
  subprocess.run(['cc','-shared','-fPIC',str(source),'-o',str(bundle/'gain.so'),*flags],check=True,capture_output=True)
  config=self.root/'alsa.conf';self.output=self.root/'audio.raw'
  config.write_text('</usr/share/alsa/alsa.conf>\n'+f'pcm.fixture {{type file slave.pcm "null" file "{self.output}" format "raw"}}\n')
  self.env=dict(os.environ,LV2_PATH=str(self.root/'lv2'),ALSA_CONFIG_PATH=str(config))
 def render(self,rows,chains,pdc=False,sc=None,gains=(),replace=False,constant=False):
  order=[r[0] for r in rows];graph='routing '+str(len(rows))+' '+' '.join(map(str,order))+' '+' '.join(f'{b} 1 0 {dest} -1 0 0 -1 0 0 0 1' for b,dest in rows)
  p=subprocess.Popen([str(ENGINE)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=self.env)
  try:
   def send(command):p.stdin.write(command+'\n');p.stdin.flush()
   def response():return json.loads(p.stdout.readline())
   send(graph);self.assertEqual(response()['status'],'ready')
   for bus,uris in chains.items():send('plugins '+str(bus)+' '+' '.join(json.dumps(u) for u in uris));self.assertEqual(response()['status'],'ready')
   for bus,index,gain in gains:send(f'plugin_param {bus} {index} 2 {gain}')
   if sc is not None:send('plugin_sidechain 1 0 '+str(sc))
   send('pdc '+str(int(pdc)));response()
   for bus,level in [(0,.125),(1,.0625),(2,.03125)]:
    f=self.root/f's{bus}.f32';f.write_bytes(array.array('f',[level]*512).tobytes());send(f'load {bus} 48000 '+json.dumps(str(f)))
   send('device "fixture" 48000');self.assertEqual(response()['status'],'ready')
   send('sequence_begin\nsequence_lane 10000\nsequence_event 0 1 100 0\nhit 0 1 1\nhit 1 1 1\nhit 2 1 1\nsequence_commit\nsequence_seek 0 1\nsequence_transport 120 1')
   time.sleep(.05)
   if replace:
    for i in range(40):
     send('plugins 2 '+('' if i%2 else json.dumps('urn:test:parallel-gain')))
     reply=response()
     while reply.get('kind')!='plugin':reply=response()
     self.assertEqual(reply.get('status'),'ready')
    send('plugins 2 '+json.dumps('urn:test:parallel-gain'))
    reply=response()
    while reply.get('kind')!='plugin':reply=response()
    time.sleep(.02)
   send('dsp_status');stats=response()
   while stats.get('kind')!='dsp_status':stats=response()
   send('quit');_,stderr=p.communicate(timeout=5);self.assertEqual(p.returncode,0,stderr)
   values=array.array('h');values.frombytes(self.output.read_bytes());nonzero=[v for v in values if v]
   if not constant:self.assertEqual(len(nonzero),512)
   return stats,nonzero
  finally:
   if p.poll() is None:p.kill();p.communicate()
 def test_independent_chains_mix_in_order_without_extra_block_or_double_processing(self):
  uri='urn:test:parallel-gain';stats,values=self.render([(0,1088),(1,1088),(2,1088),(1088,-1)],{0:[uri,uri],1:[uri],2:[uri]},gains=[(0,0,2),(0,1,3)])
  self.assertGreater(stats['workers'],0);self.assertEqual(stats['parallel_chains'],3);self.assertTrue(all(abs(v-int(.84375*32767))<=1 for v in values))
 def test_routed_sound_waits_for_its_upstream_chain(self):
  uri='urn:test:parallel-gain';stats,values=self.render([(0,1),(1,1088),(2,1088),(1088,-1)],{0:[uri],1:[uri],2:[uri]},gains=[(1,0,2)])
  self.assertEqual(stats['parallel_chains'],2);self.assertTrue(all(abs(v-int(.40625*32767))<=1 for v in values))
 def test_pdc_stays_serial_and_preserves_samples(self):
  uri='urn:test:parallel-gain';stats,values=self.render([(0,1088),(1,1088),(2,1088),(1088,-1)],{0:[uri],1:[uri]},pdc=True)
  self.assertEqual(stats['parallel_chains'],0);self.assertTrue(all(abs(v-int(.21875*32767))<=1 for v in values))
 def test_sidechain_capable_chain_stays_serial_even_when_switched_off(self):
  uri='urn:test:parallel-gain';stats,values=self.render([(0,1088),(1,1088),(2,1088),(1088,-1)],{0:[uri],1:['urn:test:parallel-sc'],2:[uri]},sc=-1)
  self.assertEqual(stats['parallel_chains'],2);self.assertTrue(all(abs(v-int(.21875*32767))<=1 for v in values))
 def test_sidechain_reads_completed_source_in_same_block(self):
  uri='urn:test:parallel-gain';stats,values=self.render([(0,1088),(1,1088),(2,1088),(1088,-1)],{0:[uri],1:['urn:test:parallel-sc'],2:[uri]},sc=0)
  self.assertEqual(stats['parallel_chains'],2);self.assertTrue(all(abs(v-int(.34375*32767))<=1 for v in values))

 def test_chains_can_be_replaced_and_removed_while_workers_run(self):
  uri='urn:test:parallel-gain';stats,values=self.render([(0,1088),(1,1088),(2,1088),(1088,-1)],{0:[uri],1:[uri],2:[uri]},replace=True)
  self.assertEqual(stats['parallel_chains'],3);self.assertTrue(all(abs(v-int(.21875*32767))<=1 for v in values))

 def test_live_instruments_overlap_sampler_work_on_other_sounds(self):
  uri='urn:test:parallel-synth';stats,values=self.render([(0,1088),(1,1088),(2,1088),(16,1088),(17,1088),(1088,-1)],{16:[uri],17:[uri]},constant=True)
  self.assertEqual(stats['early_chains'],2);self.assertEqual(stats['parallel_chains'],2)
  self.assertTrue(all(abs(v-int(.0625*32767))<=1 for v in values[-512:]))
 def test_instrument_with_sequenced_sample_input_is_not_run_early(self):
  uri='urn:test:parallel-synth';stats,values=self.render([(0,1088),(1,1088),(2,1088),(17,1088),(1088,-1)],{0:[uri],17:[uri]},constant=True)
  self.assertEqual(stats['early_chains'],1)
 def test_pdc_disables_early_instruments(self):
  uri='urn:test:parallel-synth';stats,values=self.render([(0,1088),(1,1088),(2,1088),(16,1088),(17,1088),(1088,-1)],{16:[uri],17:[uri]},pdc=True,constant=True)
  self.assertEqual(stats['early_chains'],0)

 @unittest.skipUnless((Path('/tmp/machinista-midi-fixture')/'midi-channels.lv2/fixture.so').exists(),'MIDI channel fixture required')
 def test_sequenced_instrument_keeps_sample_accurate_gate_with_early_live_synth(self):
  stats,values=self.midi_fixture_case(False)
  self.assertEqual(stats['early_chains'],1)
  # One tick at120BPM/48kHz is exactly250 frames; both channels.
  self.assertEqual(sum(abs(v-int(.04125*32767))<=1 for v in values),500)

 @unittest.skipUnless((Path('/tmp/machinista-midi-fixture')/'midi-channels.lv2/fixture.so').exists(),'MIDI channel fixture required')
 def test_old_plan_release_gate_prevents_early_render_until_seek_flushes_it(self):
  stats,_=self.midi_fixture_case(True)
  self.assertEqual(stats['before']['early_chains'],1)
  self.assertEqual(stats['replaced']['early_chains'],1)
  self.assertEqual(stats['seeked']['early_chains'],2)

 def midi_fixture_case(self,replace):
  env=dict(self.env,LV2_PATH=self.env['LV2_PATH']+':/tmp/machinista-midi-fixture')
  p=subprocess.Popen([str(ENGINE)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
  try:
   def send(c):p.stdin.write(c+'\n');p.stdin.flush()
   def read(kind):
    while True:
     line=p.stdout.readline();self.assertTrue(line,'Engine terminated');obj=json.loads(line)
     if obj.get('kind')==kind:return obj
   def stats():send('dsp_status');return read('dsp_status')
   send('routing 3 0 17 1088 0 1 0 1088 -1 0 0 -1 0 0 0 1 17 1 0 1088 -1 0 0 -1 0 0 0 1 1088 1 0 -1 -1 0 0 -1 0 0 0 1');read('routing')
   send('plugins 0 "urn:machinista:test:midi-channels"');self.assertEqual(read('plugin')['status'],'ready')
   send('plugins 17 "urn:test:parallel-synth"');self.assertEqual(read('plugin')['status'],'ready')
   send('device "fixture" 48000');read('audio')
   send('sequence_begin\nsequence_lane 98304\nsequence_event '+('0 98304' if replace else '3 1')+' 100 0\nplugin_note 0 60 100\nsequence_commit\nsequence_seek 0 1\nsequence_transport 120 1')
   time.sleep(.04);report=stats()
   if replace:
    before=report;send('sequence_begin\nsequence_lane 98304\nsequence_commit');read('sequence');time.sleep(.02);replaced=stats()
    send('sequence_seek 0 2');time.sleep(.02);report=dict(before=before,replaced=replaced,seeked=stats())
   send('quit');_,stderr=p.communicate(timeout=5);self.assertEqual(p.returncode,0,stderr)
   values=array.array('h');values.frombytes(self.output.read_bytes());return report,values
  finally:
   if p.poll() is None:p.kill();p.communicate()
