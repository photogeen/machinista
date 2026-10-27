"""ARM offline renders, maximum-velocity headroom and gain calibration for classic banks."""
import array,hashlib,json,math,os,subprocess,sys,wave
from pathlib import Path
engine=Path(sys.argv[1]).resolve();root=Path(sys.argv[2]).resolve();out=Path(sys.argv[3]);out.mkdir(parents=True,exist_ok=True)
manifest=json.loads((root/'output/native-synth/classic-banks/manifest.json').read_text())
env=dict(os.environ,LV2_PATH='/nonexistent');indices={p['symbol']:p['index'] for p in next(p for p in json.loads(subprocess.check_output([str(engine),'--plugins'],env=env,text=True)) if p['uri']=='urn:machinista:instrument:synth')['ports']}
results=[];calibration={}
def render(name,controls,rate,notes,vel,duration):
 path=out/(name.replace(' ','-')+f'-{rate}-{vel}.wav');commands=[f'offline_rate {rate}','plugins 0 "urn:machinista:instrument:synth"']+[f'plugin_param 0 0 {indices[k]} {v}' for k,v in controls.items()]
 commands+=['sequence_begin','sequence_lane 1536','sequence_event 24 480 100 0']+[f'plugin_note 0 {n} {vel}' for n in notes]+['sequence_commit','sequence_seek 0 1','sequence_transport 120 1 0 0',f'render_start '+json.dumps(str(path))+f' {round(rate*duration)} 0 16 WAV 0 0','dsp_status','quit','']
 p=subprocess.run([str(engine),'--offline-render'],input='\n'.join(commands),capture_output=True,text=True,env=env,timeout=120)
 assert p.returncode==0,(name,p.stderr)
 rows=[json.loads(row) for row in p.stdout.splitlines() if row.startswith('{')];assert not any(r.get('status')=='error' for r in rows),(name,rows)
 export=next(r for r in rows if r['kind']=='export');dsp=next(r for r in rows if r['kind']=='dsp_status')
 with wave.open(str(path)) as f:pcm=array.array('h');pcm.frombytes(f.readframes(f.getnframes()))
 assert max(map(abs,pcm))>40,(name,'silent')
 assert not any(pcm[:int(rate*.1)*2]),(name,'starts before event')
 rms=math.sqrt(sum((x/32768)**2 for x in pcm)/len(pcm));return dict(name=name,rate=rate,velocity=vel,peak=export['peak'],rms=rms,clipped=sum(abs(x)>=32767 for x in pcm),export_overflow=export['overflow'],dsp=dsp,path=str(path))
for bank in manifest:
 data=json.loads((root/bank['file']).read_text())
 for patch in data['patches']:
  name=patch['name'];controls=patch['controls'].copy();mono=bool(controls['mono']);notes=(36,43,48) if mono else (48,55,60,64,67,72)
  for attempt in range(5):
   stress=render(name,controls,48000,notes,127,5)
   if stress['peak']<=.78:break
   controls['output']=round(controls['output']*min(.7,.72/stress['peak']),6)
  assert stress['peak']<=.78 and not stress['clipped'],(name,stress)
  calibration[name]=controls['output'];results.append(stress)
  standard=render(name,controls,44100,notes if mono else (48,55,60,64),100,5);results.append(standard)
  assert standard['peak']<=.95 and not standard['clipped'],(name,standard)
  assert all(v['export_overflow']==0 for v in (stress,standard)),name
  print(json.dumps(dict(patch=name,output=controls['output'],peak=round(stress['peak'],4),rms=round(standard['rms'],4),max_ms=stress['dsp']['max_ms'],overruns=stress['dsp']['overruns'])),flush=True)
 (out/'calibration.json').write_text(json.dumps(calibration,indent=2)+'\n')
 (out/'audio-results.json').write_text(json.dumps(results,indent=2)+'\n')
summary=dict(patches=len(calibration),renders=len(results),max_peak=max(v['peak'] for v in results),max_block_ms=max(v['dsp']['max_ms'] for v in results),overruns=sum(v['dsp']['overruns'] for v in results),xruns=sum(v['dsp']['xruns'] for v in results),clipped=sum(v['clipped'] for v in results))
(out/'verification.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
