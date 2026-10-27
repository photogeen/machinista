#!/usr/bin/env python3
"""Build original Warm Circuits voices; no third-party preset data is used.

JSON retains Dexed output/filter/controller settings. SYX contains the portable
DX7 voice parameters (ten-character hardware names). FM8 is a sonic reference,
not the source of any preset data or a supported import format.
"""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.plugin_profiles import profile,validate_bank
from app.dexed_banks import OP_FIELDS,GLOBAL_FIELDS,decode_sysex
URI='https://github.com/dcoredump/dexed.lv2'
# Algorithm carrier operator numbers; matches upstream fm_core.cc output buses.
CARRIERS={1:{1,3},3:{1,4},5:{1,3,5},7:{1,3},10:{1,4},16:{1},19:{1,4,5},20:{1,2,4},21:{1,2,4,5},22:{1,3,4,5},24:{1,2,3,4,5},26:{1,2,4},28:{1,3,6},29:{1,2,3,5},30:{1,2,3,6},32:{1,2,3,4,5,6}}
# name, hardware name, family, algorithm, six ratios OP1..OP6,
# six outputs, attack/decay/sustain/release, feedback, cutoff, description.
SPECS=[
 ('Velvet Tines','VELVT TINE','Keys',5,[1,1,1,3,1,7],[92,68,86,56,72,41],[96,42,18,40],1,.94,'Rounded tine body; short upper shimmer and velocity-controlled bite.'),
 ('Amber Reeds','AMBER REED','Keys',19,[1,1,2,1,1,2],[92,61,48,82,76,65],[91,48,23,43],2,.90,'Reedy midrange layered with two soft detuned fundamentals.'),
 ('Felt Current','FELT CURNT','Keys',3,[1,1,2,1,2,4],[93,63,35,78,52,29],[84,55,0,48],0,.88,'Muted struck keys with a soft attack and compact woody overtones.'),
 ('Midnight EP','MIDNITE EP','Keys',5,[1,1,1,2,1,14],[94,65,88,58,72,36],[98,38,24,37],0,.95,'Long dark electric-piano decay with a restrained high tine.'),
 ('Soft Glass','SOFT GLASS','Keys',7,[1,2,1,3,5,1],[91,45,83,57,33,26],[92,48,8,44],1,.96,'Glass edge wrapped around a warm two-carrier body.'),
 ('Satin Clav','SATIN CLAV','Keys',16,[1,1,2,3,1,4],[97,65,51,54,46,39],[99,65,0,68],3,.91,'Dry, touch-sensitive muted clavinet character.'),
 ('Dust Keys','DUST KEYS','Keys',20,[1,2,1,1,3,1],[86,74,63,84,43,34],[88,46,15,48],2,.87,'Hollow dusty chords with an octave layer and gentle detuning.'),
 ('Ivory Glow','IVORY GLOW','Keys',1,[1,1,1,2,3,5],[94,62,86,57,39,27],[95,46,5,43],1,.94,'Piano-like FM keys: fundamental warmth with a brief complex attack.'),
 ('Copper Clouds','COPPR CLDS','Pads',21,[1,1,1,1,2,1],[84,82,57,76,68,49],[49,39,82,33],1,.88,'Wide-beating soft pad with four carriers and restrained modulation.'),
 ('Slow Embers','SLOW EMBER','Pads',3,[1,1,2,1,1,3],[91,65,33,84,58,29],[38,31,77,29],2,.89,'Slowly opening dual-stack harmonic cloud.'),
 ('Haze Choir','HAZE CHOIR','Pads',19,[1,2,3,1,2,3],[88,58,44,76,67,63],[54,36,80,37],0,.92,'Breathy vowel-like spectrum, without samples or a formant filter.'),
 ('Silk Circuit','SILK CIRCT','Pads',5,[1,1,1,2,1,3],[87,58,83,52,76,45],[61,35,84,36],0,.90,'Smooth sustained three-pair pad with a lightly moving upper layer.'),
 ('Dusk Bloom','DUSK BLOOM','Pads',10,[1,1,2,1,3,1],[89,62,46,83,49,37],[46,29,73,31],2,.86,'Dark slow bloom with differently timed modulation branches.'),
 ('Warm Orbit','WARM ORBIT','Pads',22,[1,1,1,2,1,1],[82,54,77,68,73,51],[59,38,86,39],1,.92,'Choral, lightly animated partial cluster over a stable fundamental.'),
 ('Prism Veil','PRISM VEIL','Pads',28,[1,1,2,3,1,2],[83,55,78,42,34,69],[51,34,76,30],0,.95,'Soft prismatic upper harmonics above warm independent carriers.'),
 ('Afterglow','AFTERGLOW','Pads',32,[1,1,2,3,4,6],[87,83,68,55,43,30],[57,30,88,27],0,.91,'Additive sine-ensemble pad; deliberately free of FM edge.'),
 ('Round Relay','ROUND RELY','Bass',5,[1,1,1,2,.5,1],[94,72,78,47,86,39],[99,60,65,65],1,.90,'Solid fundamental with a separate half-ratio sub and soft upper bite.'),
 ('Low Current','LOW CURRNT','Bass',16,[1,1,2,1,3,2],[99,69,46,44,33,25],[99,67,58,69],2,.92,'Focused single-carrier deep bass; transient modulation falls away.'),
 ('Sub Velvet','SUB VELVET','Bass',32,[1,.5,2,3,1,4],[92,84,55,34,0,19],[95,48,85,55],0,.88,'Pure rounded additive sub-bass with no harsh modulator stack.'),
 ('Rubber Coil','RUBBR COIL','Bass',3,[1,2,1,1,3,2],[95,72,45,79,57,37],[99,58,48,66],3,.93,'Elastic FM bass with a punchy attack and darker sustain.'),
 ('Wooden Pulse','WOOD PULSE','Bass',7,[1,1,2,3,1,2],[96,68,79,57,41,34],[98,69,20,72],1,.89,'Short hollow woody bass that leaves space between notes.'),
 ('Soft Drive','SOFT DRIVE','Bass',1,[1,1,1,2,1,1],[96,68,83,59,47,38],[97,57,66,61],4,.86,'Dense rounded FM bass; moderate feedback, controlled top end.'),
 ('Felt Pluck','FELT PLUCK','Plucks',5,[1,2,1,3,2,5],[92,53,80,42,62,31],[91,62,0,60],0,.88,'Soft muted string attack and a quick warm decay.'),
 ('Honey Mallet','HONEY MALT','Plucks',3,[1,3,2,1,2,7],[92,51,30,79,44,28],[97,52,0,51],0,.95,'Rounded marimba-like FM mallet with a subtle high overtone.'),
 ('Glass Thread','GLASS THRD','Plucks',26,[1,2,3,1,1,7],[87,61,44,83,37,32],[99,46,0,45],1,.97,'Delicate glass pluck layered with a soft independent sine.'),
 ('Bloom Harp','BLOOM HARP','Plucks',29,[1,2,1,3,2,5],[86,65,80,43,63,37],[92,42,0,43],0,.94,'Long warm harp-like pluck with overlapping harmonic decays.'),
 ('Copper Kalimba','COPPR KALM','Plucks',16,[1,2,3,5,7,1],[95,61,42,36,29,40],[99,59,0,56],1,.94,'Compact thumb-piano-like strike with a softly metallic attack.'),
 ('Silk Lead','SILK LEAD','Leads',5,[1,1,1,2,1,3],[92,68,85,54,70,42],[83,48,82,54],1,.92,'Smooth detuned singing lead; equally usable as a warm chord voice.'),
 ('Amber Solo','AMBER SOLO','Leads',3,[1,1,2,1,2,3],[94,73,42,78,58,35],[90,44,79,59],3,.93,'Focused mellow solo lead with delayed gentle vibrato.'),
 ('Mellow Brass','MELLO BRAS','Leads',22,[1,1,1,2,1,2],[88,63,83,69,73,59],[81,49,78,58],2,.91,'Soft FM brass stab that rounds into a sustained horn-like body.'),
 ('Breathy Wire','BREATHWIRE','Leads',20,[1,2,1,1,3,2],[88,71,64,84,43,32],[75,43,85,51],1,.92,'Airy, hollow lead with a warm octave voice and velocity nuance.'),
 ('Neon Horn','NEON HORN','Leads',19,[1,1,2,1,2,1],[93,71,43,78,69,65],[86,53,75,57],3,.95,'Forward modern brass lead with a controlled, expressive FM edge.'),
]

# Output trims from six-note velocity127 ARM renders at44100Hz; target peak0.28.
LEVEL_TRIMS={'Velvet Tines': 1.0, 'Amber Reeds': 1.012, 'Felt Current': 1.579, 'Midnight EP': 0.778, 'Soft Glass': 1.355, 'Satin Clav': 2.0, 'Dust Keys': 1.52, 'Ivory Glow': 0.964, 'Copper Clouds': 1.645, 'Slow Embers': 2.0, 'Haze Choir': 1.876, 'Silk Circuit': 1.31, 'Dusk Bloom': 1.837, 'Warm Orbit': 1.973, 'Prism Veil': 2.0, 'Afterglow': 1.671, 'Round Relay': 0.963, 'Low Current': 0.884, 'Sub Velvet': 1.377, 'Rubber Coil': 1.071, 'Wooden Pulse': 0.944, 'Soft Drive': 0.855, 'Felt Pluck': 2.0, 'Honey Mallet': 1.561, 'Glass Thread': 1.648, 'Bloom Harp': 1.733, 'Copper Kalimba': 1.819, 'Silk Lead': 1.116, 'Amber Solo': 1.265, 'Mellow Brass': 1.294, 'Breathy Wire': 1.436, 'Neon Horn': 1.385}

def build():
    p=profile(URI);patches=[];manifest=[]
    for number,(name,short,family,alg,ratios,outputs,env,fb,cut,description) in enumerate(SPECS):
        c={v['symbol']:v['default'] for v in p['parameters']}
        c.update(algorithm_num=alg,feedback=fb,transpose=24,oscillator_sync=0,lfo_sync=0,
                 lfo_waveform=4,lfo_speed=24+number%7,lfo_delay=35 if family=='Leads' else 48,
                 lfo_pitch_mod_depth=2 if family in ('Pads','Leads') else 0,lfo_amp_mod_depth=0,
                 pitch_mod_sensitivity=2,cutoff=cut,resonance=0,output=LEVEL_TRIMS[name],
                 number_of_voices=16,polymono=0,master_tune=0,pitch_bend_range=2,
                 mod_wheel_range=40,mod_wheel_assign=1,aftertouch_range=25,aftertouch_assign=1,
                 foot_ctrl_assign=0,breath_ctrl_assign=0)
        for k in range(1,5):c[f'pitch_eg_rate_{k}']=99;c[f'pitch_eg_level_{k}']=50
        for op in range(1,7):
            carrier=op in CARRIERS[alg];prefix=f'op{op}_';attack,decay,sustain,release=env
            # Low indices and modulator envelope decay make the warm tone itself;
            # the optional Dexed LPF is merely a final polish (not required by SYX).
            if not carrier:
                attack=min(99,attack+(8 if family=='Pads' else 3))
                decay=max(15,decay-7 if family=='Pads' else decay+8)
                sustain=max(0,sustain-14 if family=='Pads' else sustain-30)
                release=min(99,release+7)
            rates=(attack,min(99,decay),max(15,decay-9),release)
            levels=(99,max(0,min(99,sustain+9)),sustain,0)
            for k,v in enumerate(rates,1):c[prefix+f'eg_rate_{k}']=v
            for k,v in enumerate(levels,1):c[prefix+f'eg_level_{k}']=v
            c.update({prefix+'operator_output_level':outputs[op-1],prefix+'osc_mode':0,
                prefix+'osc_freq_coarse':0 if ratios[op-1]==.5 else ratios[op-1],prefix+'osc_freq_fine':0,
                prefix+'osc_detune':([-3,0,3,1,-1,2][op-1] if family=='Pads' else [-1,0,1,0,-2,1][op-1]),
                prefix+'key_vel_sensitivity':(2 if carrier else 4) if family in ('Keys','Plucks') else (1 if carrier else 2),
                prefix+'amp_mod_sensitivity':0,prefix+'kbd_rate_scaling':2 if family in ('Keys','Plucks') else 1,
                prefix+'kbd_lev_scl_brk_pt':39,prefix+'kbd_lev_scl_lft_depth':0,
                prefix+'kbd_lev_scl_rht_depth':8 if carrier else 18,prefix+'kbd_lev_scl_lft_curve':0,prefix+'kbd_lev_scl_rht_curve':0})
        patches.append(dict(name=name,controls=c))
        manifest.append(dict(slot=number+1,name=name,dx7_name=short,category=family,algorithm=alg,description=description))
    bank=validate_bank(dict(schema=1,uri=URI,name='Machinista Warm Circuits',patches=patches),p)
    return bank,manifest

def sysex(bank):
    payload=bytearray()
    for patch,spec in zip(bank['patches'],SPECS):
        c=patch['controls']
        for op in range(6,0,-1):
            v=[int(c[f'op{op}_{key}'])+(7 if key=='osc_detune' else 0) for key in OP_FIELDS]
            payload.extend(v[:11]+[v[11]|v[12]<<2,v[13]|v[20]<<3,v[14]|v[15]<<2,v[16],v[17]|v[18]<<1,v[19]])
        g=[int(c[k])-(1 if k=='algorithm_num' else 0) for k in GLOBAL_FIELDS]
        payload.extend(g[:8]+[g[8],g[9]|g[10]<<3,*g[11:15],g[15]|g[16]<<1|g[17]<<4,g[18]])
        payload.extend(spec[1].encode('ascii').ljust(10,b' ')[:10])
    assert len(payload)==4096
    return b'\xf0\x43\x00\x09\x20\x00'+payload+bytes(((-sum(payload))&127,0xf7))

def main():
    root=Path(__file__).resolve().parents[1];out=root/'output/patchbanks/dexed-warm-circuits';out.mkdir(parents=True,exist_ok=True)
    bank,manifest=build();data=sysex(bank);decoded=decode_sysex(data,profile(URI),bank['name'])
    for original,restored in zip(bank['patches'],decoded['patches']):
        for key in [f'op{op}_{field}' for op in range(1,7) for field in OP_FIELDS]+list(GLOBAL_FIELDS):assert original['controls'][key]==restored['controls'][key],key
    text=json.dumps(bank,indent=2)+'\n';(out/'Machinista-Warm-Circuits.json').write_text(text)
    (out/'Machinista-Warm-Circuits.syx').write_bytes(data);(out/'patch-list.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(f'{len(bank["patches"])} voices, {len(data)}-byte checked DX7 SysEx, full native JSON')
if __name__=='__main__':main()
