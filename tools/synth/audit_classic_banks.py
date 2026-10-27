"""Offline signal/recipe audit; scores indicate candidates, not listening verdicts."""
import json,sys,wave,collections
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from app.synth_library import FACTORY
manifest=json.loads((ROOT/'output/native-synth/classic-banks/manifest.json').read_text())
audio=Path(sys.argv[1]);out=ROOT/'output/native-synth/preset-audit';out.mkdir(exist_ok=True)
patches=[];summaries=[]
for bank in manifest:
 items=json.loads((ROOT/bank['file']).read_text())['patches'];waves=collections.Counter();combinations=collections.Counter()
 for patch in items:
  c=patch['controls'];active=[i for i in range(1,5) if c[f'osc{i}_on'] and c[f'osc{i}_level']>0];ws=sorted(FACTORY[round(c[f'osc{i}_wave'])] for i in active);waves.update(ws);combinations[' + '.join(ws)]+=1
  path=audio/(patch['name'].replace(' ','-')+'-44100.wav')
  with wave.open(str(path)) as f:rate=f.getframerate();x=np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').astype(float).reshape(-1,2)/32768
  mono=x.mean(axis=1);n=4096;hop=1024;frames=np.lib.stride_tricks.sliding_window_view(mono,n)[::hop];power=abs(np.fft.rfft(frames*np.hanning(n),axis=1))**2
  frequencies=np.fft.rfftfreq(n,1/rate);edges=np.geomspace(40,18000,49);bands=np.array([power[:,(frequencies>=lo)&(frequencies<hi)].sum(axis=1) for lo,hi in zip(edges[:-1],edges[1:])]).T
  seconds=(np.arange(len(frames))*hop+n/2)/rate;spectra=[]
  for lo,hi in ((.125,.4),(.4,1.2),(1.2,2.6)):
   b=bands[(seconds>=lo)&(seconds<hi)].sum(axis=0);spectra.append(np.sqrt(b/max(1e-20,b.sum())))
  size=round(rate*.05);env=np.sqrt(np.mean(mono[:len(mono)//size*size].reshape(-1,size)**2,axis=1));env=np.clip(20*np.log10(np.maximum(env/max(1e-10,env.max()),.001)),-60,0)
  width=np.sqrt(np.mean(((x[:,0]-x[:,1])/2)**2))/max(1e-10,np.sqrt(np.mean(x*x)))
  patches.append(dict(name=patch['name'],bank=bank['name'],mono=bool(c['mono']),waves=ws,spectra=np.array(spectra),envelope=env,width=width))
 summaries.append(dict(bank=bank['name'],patches=len(items),wave_occurrences=dict(waves),wave_combinations=dict(combinations)))
pairs=[]
for i,a in enumerate(patches):
 for b in patches[i+1:]:
  if a['mono']!=b['mono']:continue # Render harness uses different played notes for mono/poly.
  spectral=np.mean(np.linalg.norm(a['spectra']-b['spectra'],axis=1))/np.sqrt(2)
  envelope=np.sqrt(np.mean((a['envelope']-b['envelope'])**2))/60
  stereo=abs(a['width']-b['width'])
  distance=.6*spectral+.3*envelope+.1*stereo
  pairs.append(dict(a=a['name'],b=b['name'],different_banks=a['bank']!=b['bank'],distance=float(distance),spectral_distance=float(spectral),envelope_distance=float(envelope)))
pairs.sort(key=lambda v:v['distance']);counts=collections.Counter(' + '.join(p['waves']) for p in patches)
result=dict(patches=len(patches),bank_summaries=summaries,common_wave_combinations=dict(counts.most_common()),nearest_pairs=pairs[:80],method='44100 Hz velocity100 existing native DSP renders; three phase log-spaced spectral energy distributions, level-normalized 50ms envelope and stereo width. Same mono/poly only; heuristic distances, no perceptual threshold or hardware matching claim.',classic_bank_engines=1,hardware_specific_filter_models=0)
(out/'analysis.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(patches=len(patches),common_combinations=counts.most_common(5),nearest_cross_bank=[p for p in pairs if p['different_banks']][:10]),indent=2))
