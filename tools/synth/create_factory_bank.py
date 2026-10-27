"""One original factory collection, selected for contrast, with generated spectra."""
import copy,hashlib,json,math,struct,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.synth.create_classic_banks import patch,osc,env,route,P
from app.plugin_profiles import validate_bank
from app.synth_library import URI
OUT=ROOT/'output/native-synth/factory-bank';OUT.mkdir(parents=True,exist_ok=True)
BASE=ROOT/'presets/Oscillators';BASE.mkdir(parents=True,exist_ok=True);(BASE/'.assets').mkdir(exist_ok=True)

def table(title,kind,frames=8):
 n=1024;phase=np.arange(n)/n;data=[]
 for t in np.linspace(0,1,frames):
  v=np.zeros(n)
  for h in range(1,97):
   if kind=='tine':a={1:1,2:.12+.33*t,3:.02+.22*t,4:.01+.3*t,6:.13*t,9:.07*t}.get(h,0)
   elif kind=='reed':a=(1 if h%2 else .15+.25*t)*math.exp(-h/(2+15*t))/h**.65
   elif kind=='hammer':a=math.exp(-h/(2.4+18*t))*(.8+.2*math.cos(h*.52))/h**1.05
   elif kind=='wire':a=math.sin(h*math.pi*.19)*math.exp(-h/(2+35*t))/h**1.05
   elif kind=='clav':a=math.sin(h*math.pi*.12)*(1 if h%2 else .3)*math.exp(-h/(3+35*t))/h**.6
   elif kind=='glass':a={1:1,3:.12+.1*t,5:.1+.25*t,8:.2*t,11:.15*t,17:.08*t}.get(h,0)
   elif kind=='vocal':a=(math.exp(-.5*((h-(3+5*t))/1.25)**2)+.5*math.exp(-.5*((h-(13-5*t))/2)**2)+(.6 if h==1 else 0))/h**.55
   elif kind=='drawbar':a={1:1,2:.5,3:.2+.35*t,4:.3,6:.2*t,8:.08+.25*t,10:.12*t,12:.1*t,16:.08*t}.get(h,0)
   else:a=math.sin(h*h*(.11+.22*t))*math.exp(-h/(4+28*t))/h**.7
   v+=a*np.sin(2*math.pi*h*phase)
  data.append(v)
 values=np.array(data);values-=values.mean(axis=1)[:,None];values*=.8/max(abs(values).max(),1e-9)
 raw=b'MWAVE001'+struct.pack('<II',frames,n)+values.astype('<f4').tobytes();identity=hashlib.sha256(raw).hexdigest()[:32]
 row=dict(schema=1,id=identity,name=title,folder='Machinista Factory',tags=['factory','generated',kind],frames=frames,cycle=n,rate=44100,kind='Wavetable')
 asset=BASE/'.assets'/(identity+'.mwave')
 # Preserve an already prepared copy; its input identity remains the raw table hash.
 if not asset.exists():asset.write_bytes(raw)
 pcm=values.astype('<f4').tobytes();fmt=struct.pack('<HHIIHH',3,1,44100,44100*4,4,32)
 wav=b'RIFF'+struct.pack('<I',36+len(pcm))+b'WAVEfmt '+struct.pack('<I',16)+fmt+b'data'+struct.pack('<I',len(pcm))+pcm
 (BASE/'.assets'/(identity+'.wav')).write_bytes(wav);(BASE/(identity+'.json')).write_text(json.dumps(row,indent=2)+'\n');return row

waves={kind:table(title,kind,16 if kind in ('vocal','digital') else 8) for kind,title in [('tine','Tine Spectrum'),('reed','Reed Spectrum'),('hammer','Hammer Spectrum'),('wire','Plucked Wire'),('clav','Clav Spectrum'),('glass','Glass Spectrum'),('vocal','Vocal Spectrum'),('digital','Digital Spectrum'),('drawbar','Drawbar Spectrum')]}
select=[
 ('Monista Foundry Bass','BASS Round Foundation'),('Monista Rubberline','BASS Rubber Pulse'),('Monista Low Orbit','BASS Deep Sub'),('Monista Acid Foundry','BASS Acid Sequence'),
 ('Monista Ladder Lead','LEAD Saw Glide'),('Monista Whistlewire','LEAD Soft Whistle'),('Oberista Satin Lead','LEAD Square Satin'),('Korgista Hollow Reed','LEAD Nasal Reed'),('Korgista Ring Foundry','LEAD Ring Metal'),('Jovista Orbit Lead','LEAD Wide Unison'),
 ('Junista Velvet','PAD Warm Velvet'),('Oberista Pulsefield','PAD Moving Pulse'),('Cineista Slow Cinema','PAD Slow Cinema'),('Cineista Vowel Curtain','PAD Vowel Curtain'),('Jovista Airlock','PAD Air Strings'),('Prophista Reverse Bloom','PAD Reverse Bloom'),
 ('Junista Copper Pluck','PLUCK Copper'),('Monista Wood Pluck','PLUCK Hollow Wood'),('Jovista Lunar Bells','KEY Lunar Bells'),('Jovista Silk Sitar','PLUCK Sitar Wire'),
 ('Junista Organ Two','ORGAN Bright Octaves'),('Jovista Pipe Organ','ORGAN Pure Pipes'),('Oberista Leap Brass','BRASS Bright Stab'),('Cineista Rain Brass','BRASS Expressive Bloom'),
 ('Junista Space Race','FX Stepped Filter'),('Korgista Circuit Sweep','FX Resonant Sweep'),('Arpista Robot Voice','FX Robot Ring'),('Arpista Orbit Machine','FX Random Orbit'),('Jovista Train Chug','FX Noise Rhythm'),
 ('Korgista Kick Drum','DRUM Synth Kick'),('Arpista Noise Snare','DRUM Noise Snare'),('Korgista Closed Static','DRUM Closed Noise')]
source=json.loads((Path(__file__).with_name('factory-selections.json')).read_text())
patches=[]
for old,new in select:
 p=copy.deepcopy(source[old]);p.update(name=new,origin=old);patches.append(p)
p=copy.deepcopy(source['Pure Sine']);p.update(name='UTIL Pure Sine',description='Unlayered sine reference and simple soft lead.');patches.append(p)
# Restore every prior sound except the closest redundant variants and requested percussion exclusions.
omissions=json.loads(Path(__file__).with_name('factory-omissions.json').read_text())['omissions']
restored=[]
excluded={row['removed'] for row in omissions};selected={old for old,new in select}|{'Pure Sine'}
for name,preset in source.items():
 if name not in selected and name not in excluded:
  p=copy.deepcopy(preset);p['origin']=name;restored.append(p)


def wt(name,desc,kind,amp,decay=1100,level=.7,position=.05,depth=.8,**kw):
 w=waves[kind];p=patch(name,desc,[dict(wave=32,level=level,semi=0,fine=0,pan=0,free=1)],env(*amp),**kw)
 p['synth_waves']={'1':{k:w[k] for k in ('id','name','frames','cycle')}};c=p['controls'];c.update(osc1_shape=position,env3_attack=1,env3_decay=decay,env3_sustain=0,env3_release=200)
 route(c,1,8,'osc1_shape',depth);patches.append(p);return c
c=wt('KEY Tine Piano','Synthesized tine electric piano: changing partials, soft fundamental and a brief inharmonic bell layer. No recorded Rhodes samples.','tine',(1,2600,.03,650),1500,cutoff=10500,velocity=.85)
c.update(osc2_wave=0,osc2_level=.11,osc2_semi=31,osc2_fine=45,osc2_decay=250,filter1_velocity=1.2);route(c,2,1,'osc1_shape',.12)
c=wt('KEY Reed Piano','Barking reed electric-piano approximation with velocity-brightened odd harmonics. No recorded Wurlitzer samples.','reed',(2,2100,.08,420),900,cutoff=5200,filter1_drive=.04,filter1_velocity=1.8,velocity=.9);route(c,2,1,'osc1_shape',.15)
c=wt('KEY Hammer Piano','Synthetic piano-style keys with a bright hammer spectrum and short noise attack; not an acoustic-piano multisample.','hammer',(1,3100,.01,750),1700,cutoff=11500,filter1_velocity=1.5,velocity=.9)
c.update(osc2_wave=8,osc2_level=.035,osc2_decay=22,osc3_wave=0,osc3_level=.12,osc3_semi=-12,osc3_decay=1700);route(c,2,1,'osc1_shape',.12)
wt('KEY Dry Clav','Dry struck-string keyboard with a comb-shaped spectrum and fast harmonic decay.','clav',(1,540,0,85),210,cutoff=8500,velocity=.8)
wt('PLUCK Nylon String','Warm plucked-string approximation with disappearing upper partials; not a sampled nylon guitar.','wire',(2,1600,0,470),520,position=.02,depth=.43,cutoff=7000,velocity=.8)
c=wt('PLUCK Steel String','Bright plucked-string approximation with a short pick transient and fast harmonic fall.','wire',(1,2300,0,550),650,position=.03,depth=.91,cutoff=12500,velocity=.85);c.update(osc2_wave=7,osc2_level=.027,osc2_decay=15)
wt('PLUCK Muted Guitar','Short muted-string impression for rhythmic parts; synthesized rather than acoustic guitar.','wire',(1,200,0,65),85,depth=.62,cutoff=3200,res=.2,velocity=.9)
wt('KEY Glass Mallet','Bright sparse-partial mallet with a long soft fundamental.','glass',(1,2400,0,950),450,cutoff=13500,velocity=.8)
c=wt('PAD Bell and Air','Workstation-style layered bell attack and sustained soft pulse; no D-50 PCM data.','glass',(4,2100,.68,1600),850,cutoff=8500,velocity=.5);c.update(osc1_decay=1800,osc2_wave=4,osc2_level=.42,osc2_shape=.4,osc2_fine=3,osc2_pan=.35,osc1_pan=-.3);route(c,3,10,'osc2_shape',.09);c['lfo1_rate']=.3
c=wt('PAD Air Choir','Moving formant wavetable with a quiet breath layer; not a recorded choir.','vocal',(650,1700,.8,1800),3200,depth=.55,cutoff=8500,velocity=.5);c.update(osc2_wave=8,osc2_level=.04,osc1_pan=-.25);route(c,2,10,'osc1_shape',.1);c['lfo1_rate']=.18
c=wt('SYN Poly Edge','Bright virtual-analog/digital poly keys with a changing complex spectrum; no Nord model emulation.','digital',(2,850,.4,330),750,depth=.7,cutoff=3200,res=.22,filter1_velocity=1.8);c.update(osc2_wave=2,osc2_level=.25,osc2_fine=5,osc2_pan=.3,osc1_pan=-.3)
c=wt('SYN Moving Spectrum','Slow continuous wavetable motion across a harmonically complex texture.','digital',(400,1500,.82,1500),3000,position=.5,depth=0,cutoff=6500,velocity=.45);route(c,1,10,'osc1_shape',.42);c.update(lfo1_rate=.13,lfo1_wave=1)
c=wt('ORGAN Drawbar Keys','Generated drawbar-like partials with a short percussion octave.','drawbar',(2,900,1,110),300,position=.65,depth=.2,cutoff=12000,velocity=.2);c.update(osc2_wave=0,osc2_level=.16,osc2_semi=12,osc2_decay=180)
wt('PLUCK Metallic Digital','Sharp digital pluck with a brief complex attack and rounded tail.','digital',(1,820,0,260),210,depth=.95,cutoff=10000,res=.16)
cal=OUT/'calibration.json';cal=json.loads(cal.read_text()) if cal.exists() else {}
for p in patches:p['controls'].update(cal.get(p['name'],{}))
# Exclude all drum/percussion recipes at the user's request.
percussion=set(json.loads(Path(__file__).with_name('factory-omissions.json').read_text())['percussion_exclusions'])
patches=[p for p in patches if p.get('origin',p['name']) not in percussion]
restored=[p for p in restored if p.get('origin',p['name']) not in percussion]
# Keep the first collection's order; append restored sounds with their familiar names.
patches.sort(key=lambda p:p['name']);patches.extend(sorted(restored,key=lambda p:p['name']));bank=dict(schema=1,uri=URI,name='Machinista Factory',description='Original synthesized sounds and generated wavetable instruments; not hardware emulations.',patches=patches)
validate_bank(bank,P)
path=ROOT/'presets/plugin-banks/machinista-synth/factory.json';path.write_text(json.dumps(bank,ensure_ascii=True,sort_keys=True,indent=2)+'\n')
categories=json.loads(Path(__file__).with_name('factory-categories.json').read_text())
assert set(categories)=={p['name'] for p in patches},'Every patch needs one reviewed category'
labels=json.loads(Path(__file__).with_name('factory-bank-labels.json').read_text())
category_banks=[]
for category in sorted(set(categories.values())):
 slug=category.lower().replace(' & ','-').replace(' ','-')
 items=[p for p in patches if categories[p['name']]==category]
 target=path.with_name('category-'+slug+'.json')
 collection=dict(schema=1,uri=URI,name=labels[category]['name'],description=labels[category]['description'],patches=items)
 validate_bank(collection,P);target.write_text(json.dumps(collection,ensure_ascii=True,sort_keys=True,indent=2)+'\n')
 category_banks.append(dict(category=labels[category]['name'],key=category,file=str(target.relative_to(ROOT)),patches=len(items)))
manifest=dict(bank=str(path.relative_to(ROOT)),patches=len(patches),categories=category_banks,waves=list(waves.values()),retired=['5bfa91def7078657feb30c1f.json', '63cd1075a7f4a967db6379ac.json', '1da2da24fe97fbff72f4a421.json', 'c1497e1207dec77912739051.json', 'aaa01c2aa8da9b0c64318aa1.json', 'ab693f7950cdfc29f0eb8991.json', '512f8c14f9e4ee09b94c4109.json', '494d0d709001310556969310.json'])
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
(ROOT/'assets/synth-factory.json').write_text(json.dumps(dict(schema=1,bank=manifest['bank'],category_banks=category_banks,waves=manifest['waves'],provenance='Original mathematically generated harmonic tables'),indent=2)+'\n')
guide=['# Machinista Factory','',f'{len(patches)} original patches in one bank: 250 retained previous sounds and 14 newly designed wavetable patches. No hardware-emulation claim.','', 'The nine generated waveforms contain only mathematically synthesized harmonics. There are no third-party recordings or manufacturer ROM waveforms. Tine, reed and plucked timbres are synthesized approximations. Natural acoustic piano/guitar realism requires appropriate transient and multisample material.','', '## Consolidation audit','', 'Restored the full previous collection except two especially close flute variants and the explicitly excluded drum/percussion patches. Matching oscillator families alone is not a reason to remove a sound. All other strings, brass, keys, organs, basses and effects remain available. Melodic mallets, bells and plucks remain; kicks, snares, hats, claps, toms and noise percussion are excluded. The similarity scores are heuristic candidates, not proof of identical sounds.','']+[f"- {row['removed']} → {row['retained']}: {row['reason']}" for row in omissions]+['', '## Category banks','', 'Machinista Factory is the complete collection. Category banks contain the same sounds, each assigned to exactly one category. No extra synth instance is created by choosing a category.','']+[f"- **{b['category']}**: {b['patches']} patches" for b in category_banks]+['', '## Patches','']
guide += [f"{i}. **{p['name']}** — {p.get('description','Original synthesized sound.')}" for i,p in enumerate(patches,1)]
guide += ['', '## Installation and use','', 'On the controller: select Machinista Synth, BANK Machinista Factory, then PATCH. WebUI Synth offers the same presets. Both paths load waveform assignments together with the parameters.','', 'When installing elsewhere, upload the nine WAV files through WebUI Oscillators using cycle size 1024, then import the desired bank JSON files for Machinista Synth. The waveform content IDs are deterministic. Missing waveform assets produce an explicit error instead of playing an unrelated previously loaded waveform.','', 'The former eight family banks and the original small factory bank are retired. Existing saved sound parameters remain in projects; their old preset-bank references may show MISSING BANK.']
(ROOT/'docs/synth/FACTORY_BANK.md').write_text('\n'.join(guide)+'\n')
print(json.dumps(dict(patches=len(patches),new_wavetables=len(waves),bank=str(path))))
