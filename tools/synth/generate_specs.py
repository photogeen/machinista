"""Single source for stable native parameter indices and controller pages."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ports=[];pages=[]
def page(title,items):
 names=[]
 for item in items:
  symbol,name,lo,hi,default,*rest=item;options=rest[0] if rest else {};p=dict(index=len(ports),symbol=symbol,name=name,min=lo,max=hi,default=default,integer=False,toggle=False,log=False)|options;p['unit']='signed_percent' if p.get('unit')=='percent' and lo<0 else p.get('unit','');ports.append(p);names.append(symbol)
 pages.append(dict(title=title,controls=names))
def choice(values):return dict(integer=True,choices=list(enumerate(values)))
P=dict(unit='percent');MS=dict(unit='ms',log=True);HZ=dict(unit='hz',log=True);C=dict(unit='cents',display_scale=1);I=dict(integer=True)
WAVES=['Sine','Triangle','Saw','Square','Pulse','Warm Sine','Saw-Square','Noise White','Noise Pink','Odd Harmonics','Even Harmonics','Hollow','Organ Soft','Organ Bright','Reed','Nasal','Metal','Bell','Vowel A','Vowel E','Vowel O','Digital 1','Digital 2','Digital 3','Table Basic','Table Pulse','Table Hollow','Table Organ','Table Vowel','Table Metal','Table Bright','Table Digital','User Wave']
page('SYNTH / MAIN',[(s,n,lo,hi,d,o) for s,n,lo,hi,d,o in [('output','OUTPUT',0,1,.7,P),('tune','TUNE',-100,100,0,C),('polyphony','VOICES',1,32,16,I),('mono','MONO',0,1,0,dict(toggle=True,integer=True)),('glide','GLIDE',0,2000,0,dict(unit='ms')),('legato','LEGATO',0,1,1,dict(toggle=True,integer=True)),('bend_up','BEND UP',0,24,2,I),('bend_down','BEND DOWN',0,24,2,I)]])
page('SYNTH / VOICING',[('unison','UNISON',1,4,1,I),('unison_detune','DETUNE',0,50,10,C),('spread','SPREAD',0,1,.5,P),('stack_curve','DISTRIBUTION',0,3,0,choice(['Linear','Classic','Parabolic','Random'])),('global_drift','GLOBAL DRIFT',0,25,0,C),('voice_drift','VOICE DRIFT',0,25,0,C),('timbre','TIMBRE SHIFT',-24,24,0,I),('velocity','VEL TO AMP',0,1,1,P)])
for i in range(4):
 pre=f'osc{i+1}_';title=f'OSC {i+1}'
 page(title+' / WAVE',[(pre+'wave','WAVE',0,32,2 if i==0 else 0,choice(WAVES)),(pre+'semi','SEMI',-36,36,0,I),(pre+'fine','FINE',-100,100,0,C),(pre+'level','LEVEL',0,1,.65 if i==0 else 0,P),(pre+'pan','PAN',-1,1,0,dict(unit='percent')),(pre+'shape','SHAPE / POSITION',0,1,.5,P),(pre+'decay','DECAY',0,20000,0,dict(unit='ms')),(pre+'phase','PHASE',0,1,0,P)])
 page(title+' / CHARACTER',[(pre+'on','ON',0,1,1,dict(integer=True,toggle=True)),(pre+'free','FREE PHASE',0,1,0,dict(integer=True,toggle=True)),(pre+'tone','TONE',0,1,1,P),(pre+'xfade','TABLE XFADE',0,1,1,P),(pre+'fuzz','FUZZ',0,1,0,P),(pre+'precision','PRECISION',0,1,1,P),(pre+'direction','SAW DIRECTION',0,1,0,choice(['Up','Down'])),(pre+'ring','RING',0,1,0,P)])
 page(title+' / RESPONSE',[(pre+'vel_lo','VEL LOW',1,127,1,I),(pre+'vel_hi','VEL HIGH',1,127,127,I),(pre+'random_pitch','RAND PITCH',0,50,0,C),(pre+'random_level','RAND LEVEL',0,1,0,P),(pre+'random_pan','RAND PAN',0,1,0,P),(pre+'random_phase','RAND PHASE',0,1,0,P),(pre+'ring_semi','RING SEMI',-36,36,12,I),(pre+'keytrack','KEY TRACK',0,1,1,P)])
for i in range(2):
 pre=f'filter{i+1}_'
 page(f'FILTER {i+1}',[(pre+'type','TYPE',0,8,1 if i==0 else 0,choice(['Off','LP12','LP24','HP12','HP24','BP12','BP24','Notch12','Notch24'])),(pre+'cutoff','CUTOFF',20,20000,12000,HZ),(pre+'resonance','RESONANCE',0,1,.1,P),(pre+'env','ENV DEPTH',-8,8,0,dict(unit='octaves')),(pre+'keytrack','KEY TRACK',0,1,0,P),(pre+'velocity','VEL TO CUT',-6,6,0,dict(unit='octaves')),(pre+'drive','DRIVE',0,1,0,P),(pre+'gain','OUTPUT',0,2,1,P)])
page('FILTER / ROUTING',[('filter_parallel','ROUTING',0,1,0,choice(['Serial','Parallel'])),('filter_blend','BLEND',0,1,.5,P),('amp_pan','PAN',-1,1,0,P),('ramp1','RAMP 1',1,20000,1000,MS),('ramp2','RAMP 2',1,20000,2000,MS),('counter1','COUNTER 1',2,64,4,I),('counter2','COUNTER 2',2,64,8,I),('velocity_pan','VEL TO PAN',-1,1,0,P)])
for i,name in enumerate(['AMP','FILTER','PITCH','AUX']):
 pre=f'env{i+1}_'
 page(name+' ENV',[(pre+'delay','DELAY',0,20000,0,dict(unit='ms')),(pre+'attack','ATTACK',.1,20000,5 if i==0 else 10,MS),(pre+'hold','HOLD',0,20000,0,dict(unit='ms')),(pre+'decay','DECAY',.1,20000,250,MS),(pre+'sustain','SUSTAIN',0,1,.8 if i==0 else 0,P),(pre+'release','RELEASE',1,20000,200,MS),(pre+'depth','AMP SCALE' if i==0 else 'DEPTH',-48 if i==2 else 0,48 if i==2 else 4,0 if i==2 else 1,dict(unit='semitones' if i==2 else 'percent')),(pre+'curve','CURVE',-1,1,0,P)])
 page(name+' ENV / LOOP',[(pre+'loop','LOOP',0,1,0,dict(integer=True,toggle=True)),(pre+'sync','SYNC',0,12,0,choice(['Off','4 Bars','2 Bars','1 Bar','1/2','1/4','1/8','1/16','1/32','1/8T','1/16T','1/8D','1/16D'])),(pre+'scale','TIME SCALE',.1,4,1,P),(pre+'global','GLOBAL',0,1,0,dict(integer=True,toggle=True)),(pre+'vel_attack','VEL ATTACK',-1,1,0,P),(pre+'vel_depth','VEL DEPTH',-1,1,0,P),(pre+'random_attack','RAND ATTACK',0,1,0,P),(pre+'random_decay','RAND DECAY',0,1,0,P)])
for i in range(4):
 pre=f'lfo{i+1}_'
 page(('GLOBAL ' if i>1 else '')+f'LFO {i%2+1}',[(pre+'wave','WAVE',0,6,0,choice(['Sine','Triangle','Saw Up','Saw Down','Square','S&H','Random Glide'])),(pre+'rate','RATE',.01,40,1,HZ),(pre+'sync','SYNC',0,12,0,choice(['Off','4 Bars','2 Bars','1 Bar','1/2','1/4','1/8','1/16','1/32','1/8T','1/16T','1/8D','1/16D'])),(pre+'delay','DELAY',0,20000,0,dict(unit='ms')),(pre+'fade','FADE IN',0,20000,0,dict(unit='ms')),(pre+'reset','RESET',0,1,1,dict(integer=True,toggle=True)),(pre+'phase','PHASE',0,1,0,P),(pre+'level','LEVEL',0,1,1,P)])
for i in range(4):
 pre=f'ring{i+1}_'
 page(f'OSC {i+1} / RING',[(pre+'semi3','PART 3 SEMI',-36,36,7,I),(pre+'decay2','PART 2 DECAY',0,20000,0,dict(unit='ms')),(pre+'decay3','PART 3 DECAY',0,20000,0,dict(unit='ms')),(pre+'level3','PART 3 LEVEL',0,1,1,P),(pre+'fine2','PART 2 FINE',-100,100,0,C),(pre+'fine3','PART 3 FINE',-100,100,0,C),(pre+'phase2','PART 2 PHASE',0,1,0,P),(pre+'phase3','PART 3 PHASE',0,1,0,P)])
page('SYNTH / PERFORMANCE',[('glide_sync','GLIDE SYNC',0,12,0,choice(['Off','4 Bars','2 Bars','1 Bar','1/2','1/4','1/8','1/16','1/32','1/8T','1/16T','1/8D','1/16D'])),('mono_retrig','MONO RETRIG',0,1,0,dict(integer=True,toggle=True)),('global_semi','GLOBAL SEMI',-36,36,0,I),('velocity_curve','VEL AMP CURVE',-1,1,0,P)])
pages[-1]['controls']+=['glide','legato','velocity','tune']
for group in range(8):
 items=[]
 for n in range(group*4,group*4+4):
  items += [(f'matrix{n+1}_shape',f'{n+1} SHAPER',0,5,0,choice(['Off','Square','Cube','Soft Bend','Steps','Gate'])),(f'matrix{n+1}_shape_amount',f'{n+1} SHAPE AMT',0,1,1,P)]
 page(f'MOD SHAPERS {group*4+1:02}-{group*4+4:02}',items)
# Matrix targets use stable parameter symbols, not editable enum ordinals from a scan.
base_count=len(ports)
allowed=[p for p in ports if (not p['integer'] and not p['toggle'] or p['symbol'].endswith(('_semi','_semi3'))) and (p['symbol'].startswith(('osc','ring','filter','env','lfo1_','lfo2_')) or p['symbol'] in ('amp_pan','velocity','velocity_pan','unison_detune','spread'))]
TARGETS=['Off']+[p['symbol'] for p in allowed]
SOURCES=['Off','Velocity','Key','Mod Wheel','Pressure','Random','Amp Env','Filter Env','Pitch Env','Aux Env','LFO 1','LFO 2','Global LFO 1','Global LFO 2','Ramp 1','Ramp 2','Counter 1','Counter 2']
for i in range(32):
 pre=f'mod{i+1}_'
 page(f'MOD MATRIX {i+1:02}',[(pre+'source','SOURCE',0,len(SOURCES)-1,0,choice(SOURCES)),(pre+'target','TARGET',0,len(TARGETS)-1,0,choice(TARGETS)),(pre+'amount','AMOUNT',-1,1,0,P),(pre+'via','VIA',0,len(SOURCES)-1,0,choice(SOURCES)),(pre+'via_amount','VIA AMOUNT',-1,1,1,P),(pre+'unipolar','DIRECTION',0,1,0,choice(['Bipolar','Unipolar'])),(pre+'min','MIN',0,1,0,P),(pre+'max','MAX',0,1,1,P)])
profile=dict(schema=1,id='machinista-synth',uri='urn:machinista:instrument:synth',title='Machinista Synth',provider='parameter-bank',extensions=['.json'],parameters=ports,overrides={p['symbol']:{k:v for k,v in p.items() if k in ('unit','choices','display_scale')} for p in ports},pages=[dict(title='SYNTH / PRESETS',controls=['@bank','@patch','output','polyphony','mono','glide','unison','spread'])]+pages)
# Preserve every stable DSP parameter and the full desktop editor layout.
# Controller pages are deliberately curated instead of exposing 75 pages.
profile['web_pages']=profile['pages']
profile['controller_compact']=True
profile['pages']=[
 dict(title='SYNTH / PRESETS',controls=['@bank','@patch','output','mono','glide','unison','unison_detune','spread']),
 *[dict(title=f'OSC {n} / WAVE',controls=[f'osc{n}_{key}' for key in ('wave','semi','fine','level','pan','shape','fuzz','ring')]) for n in range(1,5)],
 dict(title='FILTER 1',controls=['filter1_type','filter1_cutoff','filter1_resonance','filter1_env','filter1_drive','filter1_keytrack','filter1_velocity','filter1_gain']),
 dict(title='AMP / FILTER ENV',controls=['env1_attack','env1_decay','env1_sustain','env1_release','env2_attack','env2_decay','env2_sustain','env2_release'],labels={**{f'env1_{k}':'AMP '+k.upper() for k in ('attack','decay','sustain','release')},**{f'env2_{k}':'FLT '+k.upper() for k in ('attack','decay','sustain','release')}}),
 dict(title='LFO 1',controls=['lfo1_wave','lfo1_rate','lfo1_sync','lfo1_level','mod1_source','mod1_target','mod1_amount','mod1_via'])]
(ROOT/'app/plugin_profiles_data/machinista-synth.json').write_text(json.dumps(profile,indent=2)+'\n')
# Emit standalone metadata for direct C++ DSP tests and host inventory.
out=['// Generated by tools/synth/generate_specs.py. Append stable parameters; do not reorder.',f'inline static constexpr unsigned base_count={base_count},param_count={len(ports)};', 'struct Port {const char* symbol;const char* name;float lo,hi,initial;bool integer,toggle,logarithmic;};', f'inline static constexpr std::array<Port,{len(ports)}> ports{{{{']
for p in ports:
 def f(v):return str(float(v))+'f'
 out.append('{'+','.join([json.dumps(p['symbol']),json.dumps(p['name']),f(p['min']),f(p['max']),f(p['default']),str(p['integer']).lower(),str(p['toggle']).lower(),str(p['log']).lower()])+'},')
out+=['}};', 'enum Parameter { '+','.join(p['symbol'].upper()+'='+str(p['index']) for p in ports)+' };', 'inline static constexpr std::array<unsigned,'+str(len(allowed))+'> targets{{'+','.join(str(p['index']) for p in allowed)+'}};']
(ROOT/'src/audio/synth_specs.inc').write_text('\n'.join(out)+'\n')
print(len(ports),'parameters',base_count,'base',len(pages),'pages')
