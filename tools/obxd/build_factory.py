"""Original OB-Xd patches using the legacy 2DaT port's actual parameter curves.

No manufacturer presets, samples or third-party bank files are used.
Times below are milliseconds, detune is cents, oscillator intervals semitones.
Run from the Machinista source root; outputs four explicit CC0 JSON banks.
"""
import json,math
from pathlib import Path
from app.plugin_profiles import profile,validate_bank
ROOT=Path(__file__).resolve().parents[2]
URI='urn:machinista:ports:obxd-2dat'
# Peaks calibrated with single notes and eight-note chords at 44.1/48 kHz.
OUTPUT_LEVELS={'Jumpstart Brass': 0.4843, 'Purple Poly': 0.787, 'Grand Horns': 0.4445, 'Slow Brass Choir': 0.5475, 'OB Comp Clav': 0.85, 'Poly Tines': 0.5122, 'Octave Chimes': 0.6577, 'Soft Pulse Comp': 0.3663, 'Sawyer Sweep': 0.6945, 'Two Pole Punch': 0.85, 'Four Pole Rubber': 0.85, 'Octave Weight': 0.85, 'OB Pulse Round': 0.85, 'Unison Machine': 0.5821, 'PWM Low Motion': 0.7309, 'Resonant Stepper': 0.85, 'Eight Voice Solo': 0.5032, 'Silky Pulse Solo': 0.5596, 'Sync Torque': 0.8288, 'Fifth Avenue': 0.85, 'Narrow Neon': 0.6305, 'Brass Call': 0.6253, 'Notch Voyager': 0.85, 'Poly Glide Anthem': 0.5022, 'Eight Voice Strings': 0.4447, 'Silk PWM Ensemble': 0.2862, 'Cinema Octaves': 0.5349, 'Hollow Two Pole': 0.5755, 'Warm Filter Bloom': 0.5551, 'Glassy Fifths': 0.4758, 'Highpass Halo': 0.3025, 'Sustained Horizons': 0.3787}
def inverse(value,lo,hi,rolloff=19):
 return round(math.log1p(max(0,min(1,(value-lo)/(hi-lo)))*rolloff)/math.log1p(rolloff),7)
def patch(name,*,waves=('saw','saw'),interval=0,detune=7,cutoff=.52,res=.12,env=.23,amp=(6,550,.8,180),flt=(15,500,.18,180),pole=0,pwm=0,width=.5,lfo_hz=.5,mono=False,unison=False,glide=0,mix=(.72,.68),pan=.5,variation=.13,velocity=.15,**extra):
 c={v['symbol']:v['default'] for v in profile(URI)['parameters']}
 c.update(volume=.48,voice_count=0 if mono else 1,unison=int(unison),tune=.5,octave=.5,
  osc1p=0,osc2p=interval/48,osc2_det=inverse(detune/100,.001,.6),oscquantize=1,
  osc1mix=mix[0],osc2mix=mix[1],noisemix=0,osc1saw=int(waves[0] in ('saw','both')),
  osc2saw=int(waves[1] in ('saw','both')),osc1pul=int(waves[0] in ('pulse','both')),
  osc2pul=int(waves[1] in ('pulse','both')),pw=width/.95,pw_osc2_ofs=0,pw_env=0,
  cutoff=cutoff,resonance=res,envelope_amt=env,fourpole=pole,multimode=0,bandpass=0,flt_kf=.45,
  latk=inverse(amp[0],4,60000,900),ldec=inverse(amp[1],4,60000,900),lsus=amp[2],lrel=inverse(amp[3],8,60000,900),
  fatk=inverse(flt[0],1,60000,900),fdec=inverse(flt[1],1,60000,900),fsus=flt[2],frel=inverse(flt[3],1,60000,900),
  lfofreq=inverse(lfo_hz,0,50,120),lfosinwave=1,lfosquarewave=0,lfoshwave=0,
  lfo1amt=0,lfo2amt=pwm/.7,lfopw1=int(pwm>0),lfopw2=int(pwm>0),lfofilter=0,lfoosc1=0,lfoosc2=0,lfo_sync=0,
  xmod=0,osc2hs=0,envpitch=0,env_pitch_both=0,fenv_invert=0,self_osc_push=0,
  filterder=variation,envder=variation*.5,portader=variation*.3,level_dif=.12,udet=.2,
  portamento=glide,legatomode=0,asplayedallocation=0,vampenv=velocity,vfltenv=0,bendlforate=.45,filter_warm=1,economy_mode=0)
 for i in range(8):c['pan'+str(i+1)]=round(.5+pan*(.8 if i%2 else -.8)*((i//2+1)/4),4)
 c.update(extra)
 c['volume']=OUTPUT_LEVELS.get(name,c['volume'])
 return dict(name=name,controls=c)

def banks():
 # Distinct, idiomatic two-VCO programs rather than the same template with new names.
 return {
 'keys':('Machinista Keys',[
 patch('Jumpstart Brass',cutoff=.60,env=.17,amp=(5,800,.88,130),flt=(20,600,.27,160),detune=9,pan=.4),
 patch('Purple Poly',cutoff=.48,env=.30,amp=(4,620,.70,110),flt=(5,480,.08,130),detune=5,pole=1,pan=.28),
 patch('Grand Horns',cutoff=.50,env=.28,amp=(45,900,.87,240),flt=(90,850,.23,300),detune=10,mix=(.8,.75),pan=.45),
 patch('Slow Brass Choir',cutoff=.45,env=.26,amp=(270,1000,.85,650),flt=(450,1100,.3,700),detune=12,pan=.55),
 patch('OB Comp Clav',waves=('pulse','saw'),cutoff=.36,res=.22,env=.35,amp=(4,320,.08,75),flt=(1,200,0,85),detune=2,width=.33,pole=1,pan=.2),
 patch('Poly Tines',waves=('pulse','pulse'),interval=12,cutoff=.48,env=.16,amp=(4,1400,.12,300),flt=(1,450,.05,250),mix=(.85,.25),width=.47,detune=3,pan=.32),
 patch('Octave Chimes',interval=12,cutoff=.40,env=.26,amp=(4,950,.10,340),flt=(1,550,.03,300),detune=6,mix=(.75,.45),res=.3,pan=.48),
 patch('Soft Pulse Comp',waves=('pulse','pulse'),cutoff=.49,env=.08,amp=(9,950,.65,240),flt=(25,650,.4,250),detune=8,width=.52,pwm=.035,lfo_hz=.7,pan=.35)]),
 'pads':('Machinista Pads',[
 patch('Eight Voice Strings',cutoff=.64,env=.08,amp=(380,1300,.9,1100),flt=(550,1600,.7,1200),detune=11,pan=.58),
 patch('Silk PWM Ensemble',waves=('pulse','pulse'),cutoff=.59,env=.08,amp=(520,1500,.88,1400),flt=(800,1300,.6,1500),width=.46,pwm=.15,lfo_hz=.26,detune=4,pan=.6),
 patch('Cinema Octaves',interval=12,cutoff=.50,env=.13,amp=(850,1900,.9,1900),flt=(1500,2000,.65,1900),detune=13,mix=(.8,.4),pan=.55),
 patch('Hollow Two Pole',waves=('pulse','pulse'),cutoff=.48,res=.28,env=.12,amp=(200,1100,.85,850),flt=(650,1400,.4,1000),width=.5,pwm=.055,lfo_hz=.18,detune=5,multimode=.43,pan=.5),
 patch('Warm Filter Bloom',cutoff=.32,env=.35,amp=(240,1800,.86,1300),flt=(1700,2000,.35,1500),detune=8,pan=.4),
 patch('Glassy Fifths',interval=7,cutoff=.53,env=.11,amp=(130,2100,.6,1500),flt=(420,1400,.15,1500),mix=(.75,.36),detune=5,res=.25,pan=.5),
 patch('Highpass Halo',waves=('both','saw'),cutoff=.40,env=.09,amp=(750,1600,.9,1900),flt=(1000,1600,.7,2000),detune=14,multimode=1,res=.15,pwm=.025,lfo_hz=.22,pan=.6),
 patch('Sustained Horizons',waves=('saw','pulse'),cutoff=.52,env=.12,amp=(1200,2000,.9,2400),flt=(2200,2200,.6,2300),detune=9,pwm=.09,lfo_hz=.13,width=.38,pan=.58)]),
 'bass':('Machinista Bass',[
 patch('Sawyer Sweep',cutoff=.30,res=.33,env=.43,amp=(4,1100,.7,120),flt=(1,1100,0,130),detune=7,mono=True,pole=0,pan=0),
 patch('Two Pole Punch',cutoff=.25,env=.32,amp=(4,450,.48,85),flt=(1,310,.05,80),detune=3,mono=True,pan=0),
 patch('Four Pole Rubber',waves=('pulse','saw'),cutoff=.21,res=.32,env=.38,amp=(4,550,.48,95),flt=(1,480,.06,100),width=.45,pole=1,detune=2,mono=True,pan=0),
 patch('Octave Weight',waves=('saw','pulse'),interval=12,cutoff=.31,env=.22,amp=(4,650,.6,110),flt=(3,460,.08,130),mix=(.85,.38),width=.5,detune=3,mono=True,pole=1,pan=0),
 patch('OB Pulse Round',waves=('pulse','pulse'),cutoff=.34,env=.09,amp=(6,650,.8,160),flt=(12,700,.45,180),width=.5,detune=2,mono=True,pan=0),
 patch('Unison Machine',cutoff=.40,env=.18,amp=(4,650,.8,150),flt=(1,500,.15,180),detune=3,unison=True,glide=.09,pan=.15,udet=.25),
 patch('PWM Low Motion',waves=('pulse','pulse'),cutoff=.36,env=.15,amp=(5,800,.72,130),flt=(5,650,.25,150),pwm=.11,lfo_hz=.8,width=.38,detune=3,mono=True,pan=0),
 patch('Resonant Stepper',waves=('saw','pulse'),cutoff=.22,res=.57,env=.43,amp=(4,340,.15,65),flt=(1,210,0,80),mix=(.8,.28),width=.36,detune=1,mono=True,pole=1,pan=0)]),
 'leads':('Machinista Leads',[
 patch('Eight Voice Solo',cutoff=.63,env=.12,amp=(5,850,.8,190),flt=(12,700,.5,220),unison=True,glide=.11,udet=.28,pan=.3,detune=5),
 patch('Silky Pulse Solo',waves=('pulse','pulse'),cutoff=.58,env=.08,amp=(12,900,.9,250),flt=(45,900,.5,260),detune=4,pwm=.055,lfo_hz=4.5,width=.42,mono=True,glide=.13,pan=0),
 patch('Sync Torque',cutoff=.56,env=.20,amp=(4,900,.72,160),flt=(1,850,.1,170),osc2hs=1,osc2p=12/48,envpitch=.14,mono=True,pan=0),
 patch('Fifth Avenue',interval=7,cutoff=.60,env=.1,amp=(8,900,.8,260),flt=(15,700,.35,300),detune=6,mix=(.8,.5),mono=True,glide=.08,pan=0),
 patch('Narrow Neon',waves=('pulse','pulse'),cutoff=.66,env=.07,amp=(5,700,.8,120),flt=(1,400,.4,140),width=.18,pwm=.025,lfo_hz=1.7,detune=2,mono=True,pan=0),
 patch('Brass Call',waves=('saw','both'),cutoff=.49,env=.28,amp=(35,650,.8,180),flt=(55,600,.15,220),width=.4,detune=8,mono=True,pan=0),
 patch('Notch Voyager',waves=('saw','pulse'),cutoff=.43,res=.35,env=.22,amp=(7,800,.8,400),flt=(1,1200,.25,420),detune=10,multimode=.5,mono=True,pan=0),
 patch('Poly Glide Anthem',cutoff=.59,env=.14,amp=(10,900,.85,380),flt=(35,800,.3,400),detune=12,glide=.18,pan=.5)])}

def build(root=ROOT):
 p=profile(URI);folder=Path(root)/'presets/plugin-banks/obxd';folder.mkdir(parents=True,exist_ok=True)
 for identity,(name,patches) in banks().items():
  data=dict(schema=1,uri=URI,name=name,patches=patches,author='Machinista',license='CC0-1.0',revision=2,description='Original Oberheim-style two-VCO patches for the legacy OB-Xd port; independently programmed, not manufacturer presets.')
  validate_bank(data,p);(folder/('machinista-'+identity+'.json')).write_text(json.dumps(data,indent=2)+'\n')
if __name__=='__main__':build()
