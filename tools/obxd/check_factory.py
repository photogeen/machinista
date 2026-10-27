"""Render original banks through an actual OB-Xd LV2; never opens ALSA/project files."""
import array,hashlib,json,math,os,subprocess,sys,time,wave
from pathlib import Path

def check(engine,folder,out,rates=(44100,48000)):
 engine=Path(engine).resolve();folder=Path(folder);out=Path(out);out.mkdir(parents=True,exist_ok=True)
 meta=next(p for p in json.loads(subprocess.check_output([str(engine),'--plugins'],text=True)) if p['uri']=='urn:machinista:ports:obxd-2dat')
 indices={p['symbol']:p['index'] for p in meta['ports']};results=[]
 for bankfile in sorted(folder.glob('machinista-*.json')):
  bank=json.loads(bankfile.read_text())
  for program,patch in enumerate(bank['patches']):
   for rate in rates:
    name=patch['name'];base=36 if bankfile.stem.endswith('bass') else 60
    path=out/(bankfile.stem+f'-{program+1:02}-{rate}.wav')
    commands=[f'offline_rate {rate}','plugins 0 '+json.dumps(bank['uri'])]+[f'plugin_param 0 0 {indices[k]} {v}' for k,v in patch['controls'].items()]
    commands+=['sequence_begin','sequence_lane 4000']
    for tick,length,velocity,notes in [(0,288,50,[base]),(480,288,100,[base]),(960,672,127,[base-12,base-5,base,base+4,base+7,base+12,base+16,base+19])]:
     commands+=[f'sequence_event {tick} {length} 100 0']+[f'plugin_note 0 {n} {velocity}' for n in notes]
    commands+=['sequence_commit','sequence_seek 0 1','sequence_transport 120 1 0 0','render_start '+json.dumps(str(path))+f' {rate*14} 0 16 WAV 0 0','quit','']
    began=time.monotonic();r=subprocess.run([str(engine),'--offline-render'],input='\n'.join(commands),text=True,capture_output=True,timeout=60)
    assert r.returncode==0,(name,r.stderr)
    rows=[json.loads(line) for line in r.stdout.splitlines() if line.startswith('{')];assert not any(v.get('status')=='error' for v in rows),(name,rows)
    exported=next(v for v in rows if v.get('kind')=='export');assert exported['frames']==rate*14 and not exported['overflow'],(name,exported)
    with wave.open(str(path)) as f:
     assert f.getframerate()==rate and f.getnchannels()==2
     pcm=array.array('h');pcm.frombytes(f.readframes(f.getnframes()))
    def rms(lo,hi):
     v=pcm[round(rate*lo)*2:round(rate*hi)*2:4]
     return math.sqrt(sum(n*n for n in v)/len(v))/32768
    row=dict(bank=bankfile.stem,program=program,name=name,rate=rate,peak=exported['peak'],rms=rms(0,6),tail_rms=rms(13,14),clipped=pcm.count(32767)+pcm.count(-32768),sha256=hashlib.sha256(pcm.tobytes()).hexdigest(),render_seconds=round(time.monotonic()-began,3))
    assert math.isfinite(row['peak']) and row['rms']>.0001,row
    results.append(row);(out/'results.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(row),flush=True)
 print(json.dumps(dict(renders=len(results),max_peak=max(v['peak'] for v in results),clipped=sum(v['clipped'] for v in results))))
 return results
if __name__=='__main__':check(*sys.argv[1:4])
