"""Import -> portable native Sound -> source removed -> restored audio and graph."""
import array,copy,io,json,math,os,shutil,subprocess,sys,tempfile,wave
from pathlib import Path
from app.model import Application
from app.sound_library import SoundLibrary
from app.synth_library import URI,upload,asset,delete
from app.synth_display import view
engine=Path(sys.argv[1]).resolve();evidence=Path(sys.argv[2]);evidence.parent.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(prefix='native-synth-portable-') as tmp:
 root=Path(tmp);(root/'build').mkdir();(root/'build/audio_engine').symlink_to(engine)
 buffer=io.BytesIO()
 with wave.open(buffer,'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(44100);f.writeframes(array.array('h',(round(20000*math.sin(math.tau*i/600)) for i in range(600))).tobytes())
 data=buffer.getvalue();row=upload(root,'User Sine.wav',io.BytesIO(data),len(data))
 prepared=asset(root,row['id']);assert prepared.read_bytes()[:8]==b'MWAVET02','The real upload must run offline preparation'
 state=root/'initial-state';params=next(p for p in json.loads(subprocess.check_output([str(engine),'--plugins'],text=True)) if p['uri']==URI)['ports']
 cmds=['plugins 0 '+json.dumps(URI),'synth_wave 0 0 0 '+json.dumps(str(prepared)),'plugin_save 0 0 '+json.dumps(str(state)),'quit','']
 r=subprocess.run([str(engine),'--offline-render'],input='\n'.join(cmds),text=True,capture_output=True,timeout=30);assert r.returncode==0,r.stderr
 assert (state/'osc1.mwave').read_bytes()[:8]==b'MWAVET02'
 a=Application(root);a.control_level=2;a.track()['plugins']=[dict(uri=URI,kind='INSTRUMENT',state=str(state/'state.ttl'),controls={p['symbol']:p['default'] for p in params},synth_waves={'1':dict(id=row['id'],name=row['name'])})];a.track()['plugins'][0]['controls']['osc1_wave']=32
 store=SoundLibrary(root);saved=store.save_project(a.project,dict(name='Imported Wave Test',folder='Keys/Textures',tags=['test']));assert saved['kind']=='SYNTH'
 delete(root,row['id']);prepared.unlink();(prepared.parent/(row['id']+'.wav')).unlink();shutil.rmtree(state)
 restored=store.read(saved['id']);a.project['groups'][0]['pads'][0]=copy.deepcopy(restored);a.page='PLUGIN';a.plugin_catalog=[dict(uri=URI,name='Machinista Synth',kind='INSTRUMENT',supported=True,ports=params)]
 a.plugin_param=next(i for i,p in enumerate(a.plugin_controls()) if p['symbol']=='osc1_wave');graph=view(a);assert graph and not graph.get('missing') and len(graph['points'])==64,graph
 output=root/'restored.wav';wave_index=next(p['index'] for p in params if p['symbol']=='osc1_wave')
 cmds=['plugins 0 '+json.dumps(URI),'plugin_restore 0 0 '+json.dumps(restored['plugins'][0]['state']),f'plugin_param 0 0 {wave_index} 32','sequence_begin','sequence_lane 768','sequence_event 24 96 100 0','plugin_note 0 60 100','sequence_commit','sequence_seek 0 1','sequence_transport 120 1 0 0','render_start '+json.dumps(str(output))+' 48000 0 16 WAV 0 0','dsp_status','quit','']
 r=subprocess.run([str(engine),'--offline-render'],input='\n'.join(cmds),text=True,capture_output=True,timeout=30);assert r.returncode==0,r.stderr
 rows=[json.loads(s) for s in r.stdout.splitlines() if s.startswith('{')];assert not any(v.get('status')=='error' for v in rows),rows
 export=next(v for v in rows if v['kind']=='export');assert export['peak']>.01,rows
 result=dict(passed=True,prepared_upload=True,native_sound_kind=saved['kind'],original_sources_removed=True,portable_state_audio=True,portable_state_graph=True,export=export)
 evidence.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
