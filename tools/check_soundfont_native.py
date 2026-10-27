"""Isolated SF2 conversion and native-engine render; never changes a live project."""
import array,io,json,math,subprocess,sys,tempfile,time,wave
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.web_server import Library
from app.audio import AudioBackend
from app.soundfont import Font
from tests.test_soundfont import sf2

def run(root,engine,extra=None):
 root=Path(root);root.mkdir(parents=True,exist_ok=True);library=Library(root,source_scan=lambda:[])
 def wait():
  for i in range(1000):
   s=library.soundfonts.status()
   if not s['busy']:
    if s['job']['state']=='ERROR':raise ValueError(s['job']['message'])
    return s['job']
   time.sleep(.01)
  raise ValueError('SoundFont job timeout')
 data=sf2(izones=[[(53,0),(54,3),(34,-12000),(36,-1200),(37,30),(38,-2400)]])
 library.soundfonts.upload('Native Test.sf2',io.BytesIO(data),len(data));identity=wait()['font']
 library.soundfonts.import_sound(dict(font=identity,preset=0,name='Native Test',folder='Tests',tags=['test'],accept_warnings=True));sound=wait()['sound'];track=library.sounds.store.read(sound);results=[]
 for rate in (44100,48000):
  b=AudioBackend.__new__(AudioBackend);b.root=root;b.cache=root/'cache';b.cache.mkdir(exist_ok=True);b.loaded={};b.tempo=120;b.on_message=lambda m:(_ for _ in ()).throw(ValueError(m));commands=[f'offline_rate {rate}'];b.command=commands.append
  b.load(0,0,track);commands+=['sequence_begin','sequence_lane 768','sequence_event 0 192 100 0'];b.hit(0,0,100,track,semitones=60-track['note'],voice_token=9)
  # The native sequencer emits key release after 192 ticks (one second).
  commands+=['sequence_commit','sequence_seek 0 1','sequence_transport 120 1 0 0']
  dest=root/('native-'+str(rate)+'.wav');commands+=['render_start '+json.dumps(str(dest))+f' {rate*2} 1088 16 WAV 0 0','dsp_status','quit','']
  (root/('commands-'+str(rate)+'.txt')).write_text('\n'.join(commands))
  p=subprocess.run([str(engine),'--offline-render'],input='\n'.join(commands),text=True,capture_output=True,timeout=15);assert p.returncode==0,(p.stdout,p.stderr)
  rows=[json.loads(v) for v in p.stdout.splitlines() if v.startswith('{')];assert not any(v.get('status')=='error' for v in rows),(rows,p.stderr)
  with wave.open(str(dest)) as w:a=array.array('h');a.frombytes(w.readframes(w.getnframes()))
  peak=max(map(abs,a));assert 100<peak<32767,peak
  tail=max(map(abs,a[int(rate*1.8)*2:]));assert tail<3,tail
  results.append(dict(rate=rate,peak=peak,tail=tail,dsp=next(v for v in rows if v.get('kind')=='dsp_status')))
 # All seven real upstream Calf SF2s exercise parser compatibility, not their LV2 DSP.
 extra_results=[]
 if extra:
  for p in Path(extra).glob('*.sf2'):
   with Font(p) as f:
    plans=[f.plan(i) for i in range(len(f.presets))];extra_results.append(dict(name=p.name,presets=len(plans),zones=[r['zone_count'] for r in plans],blockers=[r['blockers'] for r in plans]));assert all(not r['blockers'] for r in plans),extra_results[-1]
 library.soundfonts.delete(dict(font=identity));assert Path(library.sounds.store.read(sound)['sample']).is_file()
 library.soundfonts.pool.shutdown();library.sounds.pool.shutdown()
 result=dict(native=True,plugins=track.get('plugins',[]),renders=results,real_fonts=extra_results);(root/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':run(*sys.argv[1:])
