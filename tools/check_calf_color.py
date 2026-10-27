"""Isolated native Calf Color smoke/preset/automation/noise-generator test; never opens ALSA."""
import array,json,math,os,subprocess,sys,time,wave
from pathlib import Path

root=Path(sys.argv[1]);engine=Path(sys.argv[2]);work=Path(sys.argv[3]);work.mkdir(parents=True,exist_ok=True)
source=work/'probe.f32';samples=array.array('f')
for i in range(144000):
 v=.06*(math.sin(2*math.pi*220*i/48000)+.5*math.sin(2*math.pi*3300*i/48000)) if i<96000 else 0
 samples.extend((v,v))
source.write_bytes(samples.tobytes());env=dict(os.environ,LV2_PATH=str(root));env.pop('LD_LIBRARY_PATH',None)
r=subprocess.run([str(engine),'--plugins'],env=env,text=True,capture_output=True,check=True);catalog=[p for p in json.loads(r.stdout) if not p.get('builtin')];assert len(catalog)==3 and all(p['supported'] for p in catalog),r.stdout
profiles=Path(__file__).resolve().parents[1]/'app/plugin_profiles_data';banks=Path(__file__).resolve().parents[1]/'presets/plugin-banks';results=[];baseline={}
def render(label,rate,chain,patches=None,bypass=False):
 path=work/(label+'-'+str(rate)+'.wav');commands=[f'offline_rate {rate}','load 0 48000 '+json.dumps(str(source))]
 if chain:commands+=['plugins 0 '+' '.join(json.dumps(p['uri']) for p in chain)]
 for slot,p in enumerate(chain):
  patch=(patches or [{}]*len(chain))[slot]
  commands += [f'plugin_param 0 {slot} {v["index"]} {patch.get(v["symbol"],v["default"])}' for v in p['ports']]
  if bypass:commands.append(f'plugin_bypass 0 {slot} 1')
  # Exercise atomic parameter changes while rendering, without recreating DSP.
  change=next((v for v in p['ports'] if v['symbol'] in ('freq','mix','amount','threshold','bits','ls_freq')),None)
  if change and not bypass:
   for at,value in ((rate//2,change['default']),(rate,patch.get(change['symbol'],change['default']))):commands.append(f'offline_control {at} '+json.dumps(f'plugin_param 0 {slot} {change["index"]} {value}'))
 commands+=['sequence_begin','sequence_lane 768','sequence_event 0 768 100 0','hit 0 1 1','sequence_commit','sequence_seek 0 1','sequence_transport 120 1 0 0','render_start '+json.dumps(str(path))+f' {rate*3} 1088 16 WAV 0 0','dsp_status','quit','']
 start=time.monotonic();r=subprocess.run([str(engine),'--offline-render'],env=env,input='\n'.join(commands),text=True,capture_output=True,timeout=30);assert r.returncode==0,(label,r.stderr)
 assert 'error' not in r.stderr.lower() and 'failed' not in r.stderr.lower(),(label,r.stderr)
 rows=[json.loads(line) for line in r.stdout.splitlines() if line.startswith('{')];assert not any(v.get('status')=='error' for v in rows),(label,rows,r.stderr)
 exported=next(v for v in rows if v.get('kind')=='export');assert exported['frames']==rate*3 and not exported['overflow'],(label,exported)
 with wave.open(str(path)) as f:data=array.array('h');data.frombytes(f.readframes(f.getnframes()))
 assert max(map(abs,data))>0,label
 if not chain:baseline[rate]=data
 if bypass:assert max(abs(a-b) for a,b in zip(data,baseline[rate]))<=1,(label,'bypass differs from dry')
 results.append(dict(label=label,rate=rate,peak=max(map(abs,data)),clipped=sum(abs(x)>=32767 for x in data),dsp=next((v for v in rows if v.get('kind')=='dsp_status'),{}),seconds=round(time.monotonic()-start,4),stderr=r.stderr))
 return data
if '--recheck' in sys.argv:
 rate=48000;render('dry',rate,[])
 vinyl=next(p for p in catalog if p['uri'].endswith('/Vinyl'))
 profile=json.loads((profiles/'calf-vinyl.json').read_text());bank=json.loads(next((banks/profile['id']).glob('*.json')).read_text())
 for trial in range(3):render('Vinyl-recheck'+str(trial),rate,[vinyl],[bank['patches'][0]['controls']])
 render('three-effect-chain-recheck',rate,catalog)
else:
 for rate in (44100,48000):
  render('dry',rate,[])
  for p in catalog:
   name=p['uri'].rsplit('/',1)[-1];profile=json.loads((profiles/('calf-'+name.lower()+'.json')).read_text());bank=json.loads(next((banks/profile['id']).glob('*.json')).read_text())
   render(name+'-bypass',rate,[p],bypass=True)
   for i,patch in enumerate(bank['patches']):render(name+'-preset'+str(i),rate,[p],[patch['controls']])
  render('three-effect-chain',rate,catalog)
  tape=next(p for p in catalog if p['uri'].endswith('/TapeSimulator'))
  clean=render('Tape-immediate',rate,[tape],[dict(noise=0,mechanical=0,magnetical=0,mix=1,lowpass=18000)])
  first=lambda a:next(i//2 for i,x in enumerate(a) if abs(x)>50)
  assert abs(first(clean)-first(baseline[rate]))<rate*.01,'Unexpected tape onset latency'
  vinyl=next(p for p in catalog if p['uri'].endswith('/Vinyl'))
  original=source;source=work/'silence.f32';source.write_bytes(bytes(144000*8))
  for gen in range(7):
   controls={f'active{i}':0 for i in range(7)};controls.update({f'active{gen}':1,f'gain{gen}':.2,'drone':0,'aging':0})
   render('Vinyl-generator'+str(gen),rate,[vinyl],[controls])
  source=original
(work/'results.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(dict(renders=len(results),errors=0,max_dsp_ms=max(x['dsp'].get('max_ms',0) for x in results),overruns=sum(x['dsp'].get('overruns',0) for x in results),clipped=sum(x['clipped'] for x in results)),indent=2))
