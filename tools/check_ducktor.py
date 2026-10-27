"""No-device integration test for the real native Ducktor insert and bus routing."""
import array,json,math,os,subprocess,sys,wave
from pathlib import Path
engine=Path(sys.argv[1]).resolve();work=Path(sys.argv[2]);work.mkdir(parents=True,exist_ok=True)
env=dict(os.environ,LV2_PATH='/nonexistent');catalog=json.loads(subprocess.check_output([str(engine),'--plugins'],env=env,text=True));meta=next(p for p in catalog if p['uri']=='urn:machinista:effect:ducktor');assert meta['builtin'] and meta['sidechain'] and len(meta['ports'])==10
results=[]
for rate in (44100,48000):
 target=work/f'target{rate}.f32';trigger=work/f'key{rate}.f32';a=array.array('f');b=array.array('f')
 for i in range(rate*2):
  a.extend((.12,.06));v=.8 if .1<=i/rate% .5<.12 else 0;b.extend((v,v))
 target.write_bytes(a.tobytes());trigger.write_bytes(b.tobytes())
 for source,automated in ((-1,False),(15,False),(15,True)):
  path=work/f'out-{rate}-{source}-{int(automated)}.wav';state=work/f'state-{rate}-{source}-{int(automated)}'
  # Deliberately higher source Sound ID than target; graph must render it first.
  cmds=[f'offline_rate {rate}',f'load 0 {rate} '+json.dumps(str(target)),f'load 15 {rate} '+json.dumps(str(trigger)),'plugins 0 '+json.dumps(meta['uri']),f'plugin_sidechain 0 0 {source}','plugin_param 0 0 0 -18','plugin_param 0 0 1 6','plugin_param 0 0 2 1','plugin_param 0 0 3 80','plugin_save 0 0 '+json.dumps(str(state)),'plugin_restore 0 0 '+json.dumps(str(state/'state.ttl')),
  'routing 3 15 0 1088 15 1 0 1088 -1 0 0 -1 0 0 0 1 0 1 0 1088 -1 0 0 -1 0 0 0 1 1088 1 0 -1 -1 0 0 -1 0 0 0 1',
  'sequence_begin','sequence_lane 768','sequence_event 0 768 100 0','hit 0 1 1','hit 15 1 1','sequence_commit','sequence_seek 0 1','sequence_transport 120 1 0 0','render_start '+json.dumps(str(path))+f' {rate*2} 0 16 WAV 0 0','ducktor_meter 0 0','dsp_status','quit','']
  if automated:
   for frame,value in ((rate//2,0),(rate*3//2,24)):
    cmds.insert(next(i for i,v in enumerate(cmds) if v.startswith('render_start ')),'offline_control '+str(frame)+' '+json.dumps(f'plugin_param 0 0 4 {value}'))
  r=subprocess.run([str(engine),'--offline-render'],input='\n'.join(cmds),text=True,capture_output=True,env=env,timeout=30);assert r.returncode==0,r.stderr
  rows=[json.loads(line) for line in r.stdout.splitlines() if line.startswith('{')];assert not any(x.get('status')=='error' for x in rows),(rows,r.stderr)
  with wave.open(str(path)) as f:data=array.array('h');data.frombytes(f.readframes(f.getnframes()))
  def at(t):return sum(abs(x) for x in data[round(t*rate)*2:round(t*rate)*2+128:2])/64
  before=at(.08);ducked=at(.125);recovered=at(.48);meter=next(x for x in rows if x.get('kind')=='ducktor_meter')
  assert before>1000
  if source<0:assert abs(before-ducked)<2 and meter['reduction']==0
  else:assert ducked/before<.4 and recovered/before>.9 and meter['reduction']>10,(before,ducked,recovered,meter)
  if automated:assert at(.625)/before>.9 and at(1.625)/before<.4
  # The one shared envelope must preserve the stereo ratio throughout.
  assert max(abs(data[i]*.5-data[i+1]) for i in range(0,len(data),2))<2
  results.append(dict(rate=rate,source=source,automated=automated,before=before,ducked=ducked,recovered=recovered,meter=meter,dsp=next(x for x in rows if x.get('kind')=='dsp_status')))
(work/'results.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results,indent=2))
