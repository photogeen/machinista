"""DX7 voice-dump import into the dcoredump Dexed LV2 port's numeric controls.

VMEM = 128 packed bytes/operator 6 first; VCED = 155 unpacked bytes.
No SysEx is executed or sent to hardware. See the upstream DX7 format notes
and this port's set_params() for the algorithm/detune representation changes.
"""
from app.plugin_profiles import validate_bank

OP_FIELDS=('eg_rate_1','eg_rate_2','eg_rate_3','eg_rate_4',
           'eg_level_1','eg_level_2','eg_level_3','eg_level_4',
           'kbd_lev_scl_brk_pt','kbd_lev_scl_lft_depth','kbd_lev_scl_rht_depth',
           'kbd_lev_scl_lft_curve','kbd_lev_scl_rht_curve','kbd_rate_scaling',
           'amp_mod_sensitivity','key_vel_sensitivity','operator_output_level',
           'osc_mode','osc_freq_coarse','osc_freq_fine','osc_detune')
GLOBAL_FIELDS=tuple(f'pitch_eg_{k}_{n}' for k in ('rate','level') for n in range(1,5))+(
    'algorithm_num','feedback','oscillator_sync','lfo_speed','lfo_delay',
    'lfo_pitch_mod_depth','lfo_amp_mod_depth','lfo_sync','lfo_waveform',
    'pitch_mod_sensitivity','transpose')

def unpack_voice(packed):
    if len(packed)!=128:raise ValueError('DX7 packed voice must contain 128 bytes.')
    voice=bytearray(155)
    for op in range(6):
        source=packed[op*17:op*17+17];offset=op*21
        voice[offset:offset+11]=source[:11]
        voice[offset+11:offset+21]=bytes((source[11]&3,(source[11]>>2)&3,
            source[12]&7,source[13]&3,(source[13]>>2)&7,source[14],
            source[15]&1,(source[15]>>1)&31,source[16],(source[12]>>3)&15))
    voice[126:134]=packed[102:110]
    voice[134:145]=bytes((packed[110]&31,packed[111]&7,(packed[111]>>3)&1,
        *packed[112:116],packed[116]&1,(packed[116]>>1)&7,
        (packed[116]>>4)&7,packed[117]))
    voice[145:155]=packed[118:128]
    return bytes(voice)

def voice_patch(voice,p):
    values={s['symbol']:s['default'] for s in p['parameters']}
    for block in range(6):
        for i,field in enumerate(OP_FIELDS):
            value=voice[block*21+i]-(7 if field=='osc_detune' else 0)
            values[f'op{6-block}_{field}']=value
    for i,symbol in enumerate(GLOBAL_FIELDS):values[symbol]=voice[126+i]+(1 if symbol=='algorithm_num' else 0)
    # Legacy hardware names contain ten display bytes, not UTF-8 strings.
    title=''.join(chr(b) if 32<=b<=126 else ' ' for b in voice[145:155]).strip() or 'Untitled'
    return dict(name=title,controls=values)

def decode_sysex(data,p,name):
    patches=[];offset=0
    while offset<len(data):
        header=data[offset:offset+6]
        if len(header)!=6 or header[:2]!=b'\xf0\x43' or header[2]>15:raise ValueError('Expected a Yamaha DX7 voice dump (.syx).')
        length=(header[4]<<7)|header[5];expected={0:155,9:4096}.get(header[3])
        if expected is None or length!=expected:raise ValueError('Supports DX7 single voices and 32-voice banks only.')
        end=offset+length+8
        if end>len(data) or data[end-1]!=0xf7:raise ValueError('Incomplete DX7 SysEx message.')
        payload=data[offset+6:end-2];checksum=data[end-2]
        if any(b>127 for b in data[offset+2:end-1]):raise ValueError('Invalid DX7 SysEx data byte.')
        if (sum(payload)+checksum)&127:raise ValueError('DX7 SysEx checksum mismatch.')
        voices=[payload] if length==155 else [unpack_voice(payload[n:n+128]) for n in range(0,4096,128)]
        patches.extend(voice_patch(v,p) for v in voices);offset=end
        if len(patches)>256:raise ValueError('Maximum 256 patches per imported bank.')
    return validate_bank(dict(schema=1,uri=p['uri'],name=name[:128],patches=patches),p)
