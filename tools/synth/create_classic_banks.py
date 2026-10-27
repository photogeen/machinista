"""Original classic-inspired patches. Numeric settings only; no sampled content."""
import copy,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0,str(ROOT))
from app.plugin_profiles import profile,validate_bank
from app.synth_library import URI,FACTORY
P=profile(URI);DEFAULT={p['symbol']:p['default'] for p in P['parameters']}
TARGETS=dict((label,index) for index,label in next(p for p in P['parameters'] if p['symbol']=='mod1_target')['choices'])

def osc(wave,level,semi=0,fine=0,pan=0,**kw):
 return dict(wave=FACTORY.index(wave),level=level,semi=semi,fine=fine,pan=pan,free=1,**kw)
def env(attack,decay,sustain,release,**kw):return dict(attack=attack,decay=decay,sustain=sustain,release=release,**kw)
def route(c,index,source,target,amount):
 pre=f'mod{index}_';c.update({pre+'source':source,pre+'target':TARGETS[target],pre+'amount':amount})
def patch(name,description,oscs,amp,cutoff=3000,res=.12,depth=0,flt=None,mono=False,**kw):
 c=copy.deepcopy(DEFAULT);c.update(polyphony=8,output=.65,velocity=.6,voice_drift=1.5,global_drift=.6,filter1_type=2,filter1_cutoff=cutoff,filter1_resonance=res,filter1_env=depth)
 for n in range(1,5):c[f'osc{n}_level']=0
 for n,settings in enumerate(oscs,1):c.update({f'osc{n}_{k}':v for k,v in settings.items()})
 c.update({'env1_'+k:v for k,v in amp.items()});c.update({'env2_'+k:v for k,v in (flt or env(5,350,0,200)).items()})
 if mono:c.update(mono=1,polyphony=4,glide=35,legato=1)
 c.update(kw)
 return dict(name=name,description=description,controls=c)

banks=[]
def bank(title,family,patches):
 assert len(patches)==10
 banks.append(dict(schema=1,uri=URI,name='Machinista '+title,family=family,patches=patches))

# Single-oscillator/sub-style voicing. Paired PWM creates a light stereo halo;
# an external chorus may be added, but no third-party effect is required.
J=[]
J.append(patch('Junista Velvet','Soft saw pad with sub and a gently moving pulse.',[osc('Saw',.58),osc('Pulse',.23,pan=.25,shape=.46),osc('Sine',.2,-12)],env(240,900,.72,1100),2500,.13,.7,env(320,1000,.35,800)))
J.append(patch('Junista Subline','Rounded octave bass with a short filter contour.',[osc('Pulse',.62,shape=.38),osc('Sine',.4,-12)],env(3,350,.55,100),480,.2,2.6,env(2,230,.08,80),mono=True,velocity=.3))
J.append(patch('Junista Silkwave','Wide pulse strings with slow pulse-width movement.',[osc('Pulse',.55,fine=-2.5,pan=-.5,shape=.4),osc('Pulse',.44,fine=2.5,pan=.5,shape=.61)],env(420,1100,.82,1400),4300,.1,.4,lfo1_rate=.22))
route(J[-1]['controls'],1,10,'osc1_shape',.19);route(J[-1]['controls'],2,10,'osc2_shape',-.17)
J.append(patch('Junista Brassworks','Compact saw brass with a snappy filter opening.',[osc('Saw',.7),osc('Pulse',.16,shape=.48),osc('Sine',.14,-12)],env(18,500,.68,230),1300,.18,2.1,env(35,320,.3,180)))
J.append(patch('Junista Copper Pluck','Short resonant pluck with a low octave body.',[osc('Saw',.62),osc('Triangle',.22,-12)],env(2,420,0,110),700,.32,3.2,env(1,220,0,70)))
J.append(patch('Junista Slow Drift','A warm, gently unstable string bed.',[osc('Saw',.49,fine=-3,pan=-.6),osc('Saw',.42,fine=3,pan=.6),osc('Triangle',.14,-12)],env(650,1400,.83,1600),1900,.08,1.2,env(1000,1600,.4,1000),voice_drift=3))
J.append(patch('Junista Hollow Keys','Hollow pulse keys with a softly falling envelope.',[osc('Pulse',.67,shape=.5),osc('Triangle',.22,12)],env(4,700,.3,380),3400,.18,1.4,env(3,350,.1,200)))
J.append(patch('Junista Midnight','Dark sustained pad with a muted sub layer.',[osc('Saw',.49,fine=-2,pan=-.25),osc('Warm Sine',.3,-12),osc('Pulse',.2,fine=2,pan=.25,shape=.58)],env(500,1400,.75,1600),750,.2,.8,env(650,1500,.28,1000)))
J.append(patch('Junista Glasshouse','Soft triangle keys with a quiet bright octave.',[osc('Triangle',.68),osc('Sine',.24,12),osc('Pulse',.13,12,shape=.25,decay=500)],env(2,1100,.08,500),6500,.1,0))
J.append(patch('Junista Dawn Sweep','Slowly opening saw/pulse sweep.',[osc('Saw',.58,pan=-.3),osc('Pulse',.35,pan=.3,shape=.43)],env(350,1000,.82,1300),380,.22,4.2,env(1500,900,.6,1000)))
bank('Junista','Juno-inspired',J)

V=[]
V.append(patch('Jovista Horizon','Wide dual-saw pad with a quiet octave.',[osc('Saw',.52,fine=-6,pan=-.65),osc('Saw',.48,fine=6,pan=.65),osc('Triangle',.13,12)],env(350,1000,.8,1500),4200,.1,1.2,env(600,1100,.4,900)))
V.append(patch('Jovista Solar Brass','Bright two-oscillator brass stab.',[osc('Saw',.63,fine=-4,pan=-.25),osc('Saw',.49,fine=4,pan=.25)],env(15,550,.65,240),1600,.19,2.5,env(30,350,.28,180)))
V.append(patch('Jovista Orbit Lead','Detuned mono lead with smooth glide.',[osc('Saw',.58,fine=-5),osc('Pulse',.43,fine=5,shape=.38)],env(5,450,.8,180),4800,.15,.8,mono=True,glide=80,unison=2,unison_detune=4,spread=.55))
V.append(patch('Jovista Star Keys','Bright plucked poly keys with octave sparkle.',[osc('Saw',.49),osc('Pulse',.28,12,shape=.34,decay=900),osc('Triangle',.23,-12)],env(3,850,.2,380),2300,.22,2.4,env(2,450,.05,170)))
V.append(patch('Jovista Alloy Pluck','Tight dual-oscillator analog sequence voice.',[osc('Saw',.53,fine=-3),osc('Pulse',.38,fine=3,shape=.32)],env(2,300,0,90),900,.35,3.8,env(1,150,0,70)))
V.append(patch('Jovista Stringline','Slow upper-register saw strings.',[osc('Saw',.48,fine=-7,pan=-.7),osc('Saw',.46,fine=7,pan=.7),osc('Pulse',.16,12,shape=.49)],env(700,1400,.9,1600),5500,.08,.6,voice_drift=2.5))
V.append(patch('Jovista Octave Engine','Punchy octaved bass for moving sequences.',[osc('Saw',.53,-12),osc('Pulse',.4,shape=.46),osc('Sine',.23,-12)],env(3,480,.5,120),850,.2,2.5,env(1,280,.05,100),mono=True,glide=0))
V.append(patch('Jovista Lunar Bells','Soft harmonic bell keys without FM.',[osc('Triangle',.61),osc('Sine',.24,12,decay=1500),osc('Sine',.1,19,decay=550)],env(2,1700,0,700),9000,.08))
V.append(patch('Jovista Motion Grid','Tempo-linked pulsing filter on a sustained pad.',[osc('Saw',.5,fine=-5,pan=-.5),osc('Pulse',.42,fine=5,pan=.5,shape=.4)],env(80,700,.85,650),1800,.25,.7,lfo1_wave=1,lfo1_sync=6))
route(V[-1]['controls'],1,10,'filter1_cutoff',.1)
V.append(patch('Jovista Airlock','Filtered noise and airy high strings.',[osc('Saw',.45,pan=-.3),osc('Triangle',.23,12,pan=.3),osc('Noise White',.09,tone=.24)],env(700,1300,.7,1500),5000,.1,1.4,env(900,1300,.45,900)))
bank('Jovista','Jupiter-inspired',V)

O=[]
O.append(patch('Oberista Skyline','Broad dual-saw brass with a gentle 12 dB filter.',[osc('Saw',.6,fine=-6,pan=-.45),osc('Saw',.53,fine=6,pan=.45)],env(12,650,.75,320),1600,.19,2.1,env(35,450,.38,240),filter1_type=1))
O.append(patch('Oberista Cathedral','Slow, wide analog pad.',[osc('Saw',.5,fine=-8,pan=-.7),osc('Pulse',.45,fine=8,pan=.7,shape=.44)],env(800,1200,.86,1700),3200,.12,.8,env(800,1500,.45,1000),filter1_type=1,voice_drift=3))
O.append(patch('Oberista Vector Bass','Firm saw/square bass with a fast transient.',[osc('Saw',.59),osc('Square',.32,-12)],env(3,380,.5,100),580,.22,3.4,env(1,180,0,90),mono=True,glide=0,filter1_drive=.08))
O.append(patch('Oberista Pulsefield','Wide moving PWM chords.',[osc('Pulse',.54,fine=-5,pan=-.6,shape=.32),osc('Pulse',.48,fine=5,pan=.6,shape=.6)],env(90,800,.82,900),4000,.16,.7,filter1_type=1,lfo1_rate=.34))
route(O[-1]['controls'],1,10,'osc1_shape',.15);route(O[-1]['controls'],2,10,'osc2_shape',-.13)
O.append(patch('Oberista Copper Horn','Brassy fifth blend with a warm attack.',[osc('Saw',.63),osc('Saw',.24,7,fine=3),osc('Pulse',.15,shape=.45)],env(30,600,.6,280),1800,.2,1.9,env(55,380,.25,200),filter1_type=1))
O.append(patch('Oberista Poly Relay','Short, bright two-oscillator chord stabs.',[osc('Saw',.58,fine=-4,pan=-.3),osc('Pulse',.4,fine=4,pan=.3,shape=.4)],env(3,550,.1,220),2000,.2,2.8,env(2,250,0,150),filter1_type=1))
O.append(patch('Oberista Satin Lead','Round square lead with delayed vibrato.',[osc('Square',.59),osc('Triangle',.25,-12)],env(12,500,.8,220),3600,.18,.6,mono=True,lfo1_rate=5.4,lfo1_delay=450,lfo1_fade=350))
route(O[-1]['controls'],1,10,'osc1_fine',.025)
O.append(patch('Oberista Amber Strings','Gentle detuned strings with a long release.',[osc('Saw',.51,fine=-5,pan=-.65),osc('Saw',.47,fine=5,pan=.65)],env(420,950,.88,1500),2600,.1,.9,filter1_type=1))
O.append(patch('Oberista Bandglass','Narrow, hollow band-pass keyboard texture.',[osc('Saw',.6,fine=-3),osc('Pulse',.4,fine=3,shape=.4)],env(4,950,.28,450),1600,.35,.65,env(5,500,.15,280),filter1_type=5))
O.append(patch('Oberista Horizon Fifth','Wide sustained saw chords with a subtle fifth.',[osc('Saw',.48,fine=-5,pan=-.5),osc('Saw',.42,fine=5,pan=.5),osc('Triangle',.17,7)],env(170,1000,.8,1100),3100,.15,1,filter1_type=1))
bank('Oberista','Oberheim-inspired',O)

M=[]
M.append(patch('Monista Foundry Bass','Three-layer rounded bass with a fast filter decay.',[osc('Saw',.53),osc('Square',.3,-12),osc('Triangle',.18)],env(2,420,.65,100),400,.23,3.4,env(2,240,.1,80),mono=True,filter1_drive=.12))
M.append(patch('Monista Ladder Lead','Three oscillator lead with glide and delayed vibrato.',[osc('Saw',.5,fine=-4),osc('Saw',.38,fine=4),osc('Triangle',.21,-12)],env(8,600,.85,230),3800,.26,.8,mono=True,glide=95,filter1_drive=.07,lfo1_rate=5.3,lfo1_delay=350,lfo1_fade=350))
for n in (1,2):route(M[-1]['controls'],n,10,f'osc{n}_fine',.025)
M.append(patch('Monista Rubberline','Bouncy pulse bass with strong filter motion.',[osc('Pulse',.64,shape=.36),osc('Sine',.35,-12)],env(2,350,.25,100),250,.5,4,env(2,170,.03,80),mono=True,glide=18,filter1_drive=.1))
M.append(patch('Monista Whistlewire','Soft triangle whistle lead.',[osc('Triangle',.65),osc('Sine',.2,12)],env(25,500,.8,300),5000,.3,.25,mono=True,glide=100,lfo1_rate=5,lfo1_delay=500,lfo1_fade=300))
route(M[-1]['controls'],1,10,'osc1_fine',.02)
M.append(patch('Monista Acid Foundry','Resonant short sequence bass.',[osc('Saw',.68),osc('Square',.15,-12)],env(2,280,.02,70),240,.63,4.2,env(1,140,0,60),mono=True,glide=0,filter1_drive=.16))
M.append(patch('Monista Pressure Lead','Driving saw lead with a thick low octave.',[osc('Saw',.55,fine=-5),osc('Saw',.4,fine=5),osc('Pulse',.2,-12,shape=.4)],env(3,500,.85,170),6200,.15,.4,mono=True,glide=45,filter1_drive=.12))
M.append(patch('Monista Low Orbit','Deep sine/triangle sub with a gentle pulse edge.',[osc('Sine',.59,-12),osc('Triangle',.38,-12),osc('Pulse',.12,shape=.44)],env(4,700,.65,180),700,.14,.5,mono=True,glide=55,velocity=.25))
M.append(patch('Monista Wood Pluck','Hollow, wood-like resonant pluck.',[osc('Triangle',.6),osc('Pulse',.2,12,shape=.22)],env(1,470,0,130),900,.43,2.3,env(1,170,0,70),mono=True,glide=0))
M.append(patch('Monista Coil Fifth','Three-oscillator fifth lead with soft glide.',[osc('Saw',.52),osc('Pulse',.26,7,shape=.45),osc('Triangle',.24,-12)],env(12,650,.78,250),2400,.24,1.3,env(15,420,.25,200),mono=True,glide=70))
M.append(patch('Monista Steam Valve','Noisy resonant rise and fall.',[osc('Noise Pink',.58,tone=.35),osc('Saw',.2,-12)],env(180,1500,.15,600),450,.4,4.8,env(700,1000,0,400),mono=True,glide=0,filter1_drive=.1))
bank('Monista','Moog-inspired',M)

K=[]
def kpatch(name,description,oscs,amp,cut=1800,hp=100,res=.3,depth=2,flt=None,**kw):
 return patch(name,description,oscs,amp,hp,.18,.12,flt or env(2,300,.1,150),mono=True,filter1_type=3,filter2_type=1,filter2_cutoff=cut,filter2_resonance=res,filter2_env=depth,filter2_drive=.08,**kw)
K.append(kpatch('Korgista Voltage Bass','Punchy high-pass/low-pass bass.',[osc('Saw',.6),osc('Pulse',.34,-12,shape=.39)],env(2,400,.4,110),cut=650,hp=35,res=.34,depth=3,glide=0))
K.append(kpatch('Korgista Rust Lead','Bright nasal lead with filter drive.',[osc('Saw',.56,fine=-4),osc('Pulse',.39,fine=4,shape=.27)],env(5,500,.8,190),cut=3500,hp=220,res=.38,depth=1.3,glide=55))
K.append(kpatch('Korgista Resonant Wire','Thin resonant pluck between two filter edges.',[osc('Saw',.67),osc('Square',.24,12)],env(1,450,0,120),cut=1100,hp=520,res=.6,depth=2.2,glide=0))
K.append(kpatch('Korgista Ring Foundry','Metallic three-component ring tone.',[osc('Pulse',.62,shape=.38,ring=.7,ring_semi=7),osc('Triangle',.23,-12)],env(2,1000,.1,350),cut=4600,hp=170,res=.22,depth=.4,glide=0,ring1_semi3=19,ring1_level3=.7))
K.append(kpatch('Korgista Switch Sequence','Dry resonant pulse for fast patterns.',[osc('Pulse',.7,shape=.3),osc('Saw',.18,12,decay=220)],env(1,200,0,60),cut=550,hp=70,res=.48,depth=4,flt=env(1,110,0,50),glide=0))
K.append(kpatch('Korgista Dust Circuit','Band-limited noise percussion.',[osc('Noise White',.85,tone=.6)],env(1,220,0,60),cut=4800,hp=850,res=.32,depth=.6,flt=env(1,140,0,50),glide=0))
K.append(kpatch('Korgista Dark Signal','A moving, hollow two-filter sustain.',[osc('Saw',.56,fine=-3),osc('Pulse',.4,fine=3,shape=.45)],env(90,900,.8,650),cut=2000,hp=350,res=.4,depth=.7,lfo1_rate=.28))
route(K[-1]['controls'],1,10,'filter2_cutoff',.09)
K.append(kpatch('Korgista Hollow Reed','Nasal pulse/reed lead with delayed vibrato.',[osc('Pulse',.61,shape=.22),osc('Triangle',.25,-12)],env(20,550,.72,220),cut=3000,hp=260,res=.3,depth=.9,lfo1_rate=5.6,lfo1_delay=400,lfo1_fade=300))
route(K[-1]['controls'],1,10,'osc1_fine',.025)
K.append(kpatch('Korgista Alarm Coil','Rhythmic pitch modulation on a bright lead.',[osc('Square',.58),osc('Saw',.22,12)],env(8,500,.8,180),cut=5800,hp=150,res=.23,depth=.2,lfo1_wave=1,lfo1_rate=3.2))
route(K[-1]['controls'],1,10,'osc1_semi',.015);route(K[-1]['controls'],2,10,'osc2_semi',.015)
K.append(kpatch('Korgista Circuit Sweep','Noise and saw with a slow resonant sweep.',[osc('Saw',.43),osc('Noise Pink',.32,tone=.3)],env(350,1100,.55,800),cut=600,hp=180,res=.45,depth=4.1,flt=env(1100,900,.3,700),glide=0))
bank('Korgista','Korg MS-20-inspired',K)

from tools.synth.classic_expansion import expand
expand(banks,patch,osc,env,route,kpatch)
from tools.synth.classic_trio import extend
extend(banks,patch,osc,env,route)

def write():
 destination=ROOT/'presets/plugin-banks/machinista-synth';destination.mkdir(parents=True,exist_ok=True)
 evidence=ROOT/'output/native-synth/classic-banks';evidence.mkdir(parents=True,exist_ok=True)
 # Render calibration applies only linear output/amp/filter gain; bank IDs remain stable on update.
 calibration_path=evidence/'calibration.json';calibration=json.loads(calibration_path.read_text()) if calibration_path.exists() else {}
 previous=json.loads((evidence/"manifest.json").read_text()) if (evidence/"manifest.json").exists() else []
 identities={b["name"]:Path(b["file"]).stem for b in previous}
 result=[]
 for b in banks:
  b=copy.deepcopy(b)
  for patch in b['patches']:
   settings=calibration.get(patch['name'],{})
   if isinstance(settings,dict):patch['controls'].update(settings)
   else:patch['controls']['output']=settings
  validate_bank(b,P);encoded=(json.dumps(b,ensure_ascii=True,sort_keys=True,indent=2)+'\n').encode();identity=identities.get(b['name'],hashlib.sha256(encoded).hexdigest()[:24])
  path=destination/(identity+'.json');path.write_bytes(encoded)
  result.append(dict(name=b['name'],family=b['family'],file=str(path.relative_to(ROOT)),patches=[dict(name=p['name'],description=p['description']) for p in b['patches']]))
 (evidence/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
 guide=['# Machinista Classic Banks','', '256 original patches (32 per bank) for Machinista Synth. Select BANK, then PATCH on the first controller page, or WebUI > Synth. All use built-in waves; no LV2 or samples required. These are inspired voicings, not circuit emulations or imported factory presets. Junista does not include a separate chorus effect.','']
 for b in result:
  guide+=['## '+b['name']+' ('+b['family']+')','']
  guide += [f"{i}. **{p['name']}** - {p['description']}" for i,p in enumerate(b['patches'],1)];guide+=['']
 guide += ['## References and limits','',
 'These are original recipes inspired by well-known sound families and factory patch categories. Names such as Leap Brass, Sawyer Sweep and Royal Party describe a direction, not an exact artist preset. The set is curated, not a ranking of the 32 most famous patches.',
 '', 'Reference material: [Roland Juno-60 owner manual](https://cdn.roland.com/assets/media/pdf/JUNO-60_OM.pdf), [original Jupiter-8 patch charts](https://www.synthmania.com/Roland%20Jupiter-8/Images/Roland%20Jupiter-8%20Factory%20patch%20sheets.pdf), [Oberheim OB-X8](https://oberheim.com/products/ob-x8/), [Oberheim factory-program documentation](https://oberheim.com/wp-content/uploads/2023/09/OB-X8-Manual-V2_2.pdf), [Korg MS-20 patchbook](https://www.korg.com/us/support/download/manual/0/134/2443/). Monista follows the classic three-oscillator subtractive bass/lead architecture rather than claiming specific song settings.',
 '', 'Additional references: [Sequential original Prophet-5 patch charts](https://sequential.com/wp-content/uploads/2020/10/Original-Prophet-5-Patch-Sheets-1.1.pdf), [Yamaha CS-80 architecture](https://jp.yamaha.com/products/music_production/synthesizers/cs-80/features.html), [Korg ARP Odyssey synthesis](https://www.korg.com/uk/products/synthesizers/arpodyssey/features.php). Prophista emphasizes dual-oscillator polyphonic voicing. Cineista uses a shared serial HP/LP spectral window, not two independent CS-80 synth channels. Arpista combines Odyssey-style sharp leads with 2600-style modular effects; it does not reproduce Odyssey duophonic oscillator allocation. Poly-Mod FM, hard sync, CS ribbon behavior and original filter circuits are not recreated. Pressure and mod wheel brighten several Cineista patches when a suitable MIDI controller is available.',
 '', 'The engine does not model the original oscillator circuits, hard sync, filter nonlinearities, chorus or complete patch-panel routing. Electric pianos, acoustic instruments and voices are analog-style approximations. Percussion remains pitched and follows the played key. Train Chug and Clap Circuit generate their modulation only while a note is held.',
 '', 'The first ten patches and their control values are preserved. Updated installed banks retain their IDs so saved projects keep their bank and patch indices. Import this ZIP only on a system without these banks; an additional import can create a duplicate bank.', '']
 (ROOT/'docs/synth/CLASSIC_BANKS.md').write_text('\n'.join(guide)+'\n')
 print(json.dumps(dict(banks=len(result),patches=sum(len(b['patches']) for b in result),files=[b['file'] for b in result])))
if __name__=='__main__':write()
