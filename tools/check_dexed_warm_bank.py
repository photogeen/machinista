#!/usr/bin/env python3
"""Real Dexed offline renders only; no ALSA device or running project is opened."""
import array,hashlib,json,math,os,subprocess,sys,time,wave
from pathlib import Path
engine=Path(sys.argv[1]);folder=Path(sys.argv[2]);out=Path(sys.argv[3]);out.mkdir(parents=True,exist_ok=True)
env=dict(os.environ,LV2_PATH='/var/lib/machinista/lv2/plugins')
meta=next(p for p in json.loads(subprocess.check_output([str(engine),'--plugins'],text=True,env=env)) if p['uri']=='https://github.com/dcoredump/dexed.lv2')
indices={p['symbol']:p['index'] for p in meta['ports']};bank=json.loads((folder/'Machinista-Warm-Circuits.json').read_text());manifest=json.loads((folder/'patch-list.json').read_text());results=[]
for rate in (44100,48000):
 for patch,entry in zip(bank['patches'],manifest):
  name=patch['name'];base=36 if entry['category']=='Bass' else 60
  path=out/(f'{entry["slot"]:02}-'+name.replace(' ','-')+f'-{rate}.wav')
  commands=[f'offline_rate {rate}','plugins 0 '+json.dumps(bank['uri'])]+[f'plugin_param 0 0 {indices[k]} {v}' for k,v in patch['controls'].items()]
  commands+=['sequence_begin','sequence_lane 4000']
  for tick,length,velocity,notes in [(48,288,40,[base]),(624,288,85,[base]),(1200,288,127,[base]),(1776,576,127,[base-12,base-5,base,base+4,base+7,base+12])]:
   commands+=[f'sequence_event {tick} {length} 100 0']+[f'plugin_note 0 {n} {velocity}' for n in notes]
  commands+=['sequence_commit','sequence_seek 0 1','sequence_transport 120 1 0 0','render_start '+json.dumps(str(path))+f' {rate*18} 0 16 WAV 0 0','dsp_status','quit','']
  began=time.monotonic();p=subprocess.run(['nice','-n','19',str(engine),'--offline-render'],env=env,input='\n'.join(commands),text=True,capture_output=True,timeout=90)
  assert p.returncode==0,(name,p.stderr)
  process_seconds=round(time.monotonic()-began,3)
  rows=[json.loads(line) for line in p.stdout.splitlines() if line.startswith('{')];assert not any(v.get('status')=='error' for v in rows),(name,rows)
  exported=next(v for v in rows if v.get('kind')=='export');assert exported['frames']==rate*18 and not exported['overflow'],(name,exported)
  with wave.open(str(path)) as f:
   assert f.getframerate()==rate and f.getnchannels()==2
   pcm=array.array('h');pcm.frombytes(f.readframes(f.getnframes()))
  sampled=pcm[::8];peak=min(1,exported['peak']);rms=math.sqrt(sum(v*v for v in sampled)/len(sampled))/32768
  def energy(lo,hi):
   values=pcm[round(rate*lo)*2:round(rate*hi)*2:8]
   return math.sqrt(sum(v*v for v in values)/len(values))/32768
  levels=[energy(.3,1.6),energy(3.3,4.6),energy(6.3,7.6)]
  release=energy(17,18)
  row=dict(slot=entry['slot'],name=name,category=entry['category'],rate=rate,peak=peak,raw_peak=exported['peak'],rms=rms,velocity_rms=levels,tail_rms=release,clipped=pcm.count(32767)+pcm.count(-32768),sha256=hashlib.sha256(pcm.tobytes()).hexdigest(),render_seconds=round(time.monotonic()-began,3),process_seconds=process_seconds)
  assert all(math.isfinite(v) for v in [peak,rms,*levels,release]),row
  assert min(levels)>.00003 and rms>.0001,row
  results.append(row);(out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
  print(json.dumps(row),flush=True)
print(json.dumps(dict(renders=len(results),max_peak=max(v['raw_peak'] for v in results),clipped=sum(v['clipped'] for v in results),unique=len(set(v['sha256'] for v in results)))))
