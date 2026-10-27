"""Isolated native-host Pitch Up/Down render checks; never touches live state."""
import array,json,math,subprocess,sys,wave
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.audio import AudioBackend
from app.model import Application

def run(engine,folder):
 root=Path(folder);root.mkdir(exist_ok=True,parents=True);results=[]
 for rate in (44100,48000):
  source=root/f'input-{rate}.wav';values=array.array('h')
  for i in range(rate*3):
   value=round(8500*math.sin(math.tau*437*i/rate));values.extend((value,-value))
  with wave.open(str(source),'wb') as w:w.setparams((2,2,rate,0,'NONE',''));w.writeframes(values.tobytes())
  for effect in (14,15):
   a=Application(root);track=a.track();track.update(sample=str(source),start=0,end=rate*3,zones=[]);track['sampler']={'type':'ONESHOT','vel_volume':0}
   b=AudioBackend.__new__(AudioBackend);b.root=root;b.cache=root/'cache';b.cache.mkdir(exist_ok=True);b.loaded={};b.tempo=120;b.sample_rate=rate;b.on_message=lambda text:(_ for _ in ()).throw(ValueError(text));commands=[f'offline_rate {rate}'];b.command=commands.append
   b.load(0,0,track);commands+=['sequence_begin','sequence_lane 768','sequence_event 0 768 100 0'];b.hit(0,0,127,track);commands+=['sequence_commit','sequence_seek 0 1','sequence_transport 120 1 0 0']
   dest=root/f'pitch-{effect}-{rate}.wav'
   commands += ['offline_control '+str(rate//2)+' '+json.dumps(f'live_fx 0 {effect} 127 1 120'),'offline_control '+str(rate*5//2)+' '+json.dumps('live_fx 0 0 0 0 120'),'render_start '+json.dumps(str(dest))+f' {rate*3} 1088 16 WAV 0 0','dsp_status','quit','']
   (root/f'commands-{effect}-{rate}.txt').write_text('\n'.join(commands))
   p=subprocess.run([str(Path(engine).resolve()),'--offline-render'],input='\n'.join(commands),capture_output=True,text=True,timeout=30);assert p.returncode==0,(p.stdout,p.stderr)
   events=[json.loads(line) for line in p.stdout.splitlines() if line.startswith('{')];assert not any(e.get('status')=='error' for e in events),events
   with wave.open(str(dest)) as w:pcm=array.array('h');pcm.frombytes(w.readframes(w.getnframes()))
   mono=pcm[rate*2:rate*4:2];ratio=.5 if effect==14 else 2
   energy=sum(x*x for x in mono)/len(mono);re=sum(x*math.cos(math.tau*437*ratio*i/rate) for i,x in enumerate(mono))/len(mono);im=sum(x*math.sin(math.tau*437*ratio*i/rate) for i,x in enumerate(mono))/len(mono)
   amplitude=2*math.hypot(re,im);residual=math.sqrt(max(0,energy-amplitude*amplitude/2));peak=max(map(abs,pcm));assert 100<peak<32767,peak;assert amplitude>2000,(effect,amplitude);assert residual<amplitude*.025,(effect,residual,amplitude)
   assert max(abs(pcm[i]+pcm[i+1]) for i in range(0,len(pcm),2))<5,'Stereo phase changed'
   dsp=next(e for e in events if e.get('kind')=='dsp_status');export=next(e for e in events if e.get('kind')=='export');assert export['overflow']==0
   results.append(dict(rate=rate,effect=effect,amplitude=amplitude,residual=residual,peak=peak,dsp=dsp))
 (root/'verification.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results))
if __name__=='__main__':run(*sys.argv[1:])
