"""Offline integration: real native host, all factory patches, state, user tables and automation."""
import array,json,math,os,subprocess,sys,wave
from pathlib import Path
engine=Path(sys.argv[1]).resolve();root=Path(sys.argv[2]).resolve();out=Path(sys.argv[3]);out.mkdir(parents=True,exist_ok=True)
env=dict(os.environ,LV2_PATH='/nonexistent')
meta=next(p for p in json.loads(subprocess.check_output([str(engine),'--plugins'],text=True,env=env)) if p['uri']=='urn:machinista:instrument:synth');assert meta['builtin'] and meta['kind']=='INSTRUMENT' and len(meta['ports'])==588
indices={p['symbol']:p['index'] for p in meta['ports']};bank=json.loads((root/'presets/plugin-banks/machinista-synth/factory.json').read_text());results=[]
def run(name,rate,controls,notes=(48,55,60),extra=(),duration=3):
 path=out/(name+'-'+str(rate)+'.wav');cmd=[f'offline_rate {rate}','plugins 0 '+json.dumps(meta['uri'])]+[f'plugin_param 0 0 {indices[k]} {v}' for k,v in controls.items()]+list(extra)
 cmd+=['sequence_begin','sequence_lane 768','sequence_event 24 240 100 0']+[f'plugin_note 0 {note} 100' for note in notes]+['sequence_commit','sequence_seek 0 1','sequence_transport 120 1 0 0','render_start '+json.dumps(str(path))+f' {rate*duration} 0 16 WAV 0 0','dsp_status','quit','']
 p=subprocess.run([str(engine),'--offline-render'],input='\n'.join(cmd),text=True,capture_output=True,env=env,timeout=120);assert p.returncode==0,p.stderr
 rows=[json.loads(v) for v in p.stdout.splitlines() if v.startswith('{')];assert not any(r.get('status')=='error' for r in rows),(name,rows,p.stderr)
 with wave.open(str(path)) as f:data=array.array('h');data.frombytes(f.readframes(f.getnframes()))
 peak=max(abs(x) for x in data);assert peak>40,(name,peak)
 assert all(x==0 for x in data[:int(.12*rate)*2]),'Note started early'
 dsp=next(v for v in rows if v['kind']=='dsp_status');export=next(v for v in rows if v['kind']=='export');assert export['overflow']==0
 results.append(dict(name=name,rate=rate,peak=peak,dsp=dsp))
 return data
for rate in (44100,48000):
 for patch in bank['patches']:run(patch['name'].replace(' ','-'),rate,patch['controls'])
 # Four imported morph frames, project state saved and reloaded by a fresh instance.
 asset=out/'user.mwave';frames=4;size=512;a=array.array('f')
 for frame in range(frames):
  for i in range(size):a.append(.6*math.sin(math.tau*i/size)+frame*.08*math.sin(math.tau*3*i/size))
 import struct
 asset.write_bytes(b'MWAVE001'+struct.pack('<II',frames,size)+a.tobytes())
 state=out/f'state-{rate}'
 run('user-state',rate,dict(osc1_wave=32),extra=[f'synth_wave 0 0 0 '+json.dumps(str(asset)),f'plugin_save 0 0 '+json.dumps(str(state)),f'plugin_restore 0 0 '+json.dumps(str(state/'state.ttl'))])
 # Plain/automated output comparison proves host numeric automation reaches native controls.
 cmd='plugin_param 0 0 '+str(indices['output'])+' 0'
 data=run('output-automation',rate,dict(env1_sustain=1,env1_release=20),extra=['offline_control '+str(rate//2)+' '+json.dumps(cmd)])
 assert max(abs(x) for x in data[int(.7*rate)*2:])<5
(out/'results.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(dict(renders=len(results),max_block_ms=max(v['dsp']['max_ms'] for v in results),overruns=sum(v['dsp']['overruns'] for v in results))))
