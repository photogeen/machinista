"""Read RaffoSynth's legacy GUI .dat single-patch format as data only."""
from app.plugin_profiles import validate_bank

def decode_dat(data,p,name):
    try:values=[float(v) for v in data.decode('ascii').split()]
    except (UnicodeError,ValueError) as e:raise ValueError('RaffoSynth DAT must contain 32 numeric values.') from e
    order=[f'{field}{osc}' for osc in range(4) for field in ('oscButton','range','tuning','wave','vol')]+['filter_cutoff','filter_attack','filter_decay','filter_sustain','filter_release','filter_resonance','attack','decay','sustain','release','glide','volume']
    if len(values)!=len(order):raise ValueError('RaffoSynth DAT must contain exactly 32 values.')
    return validate_bank(dict(schema=1,uri=p['uri'],name=name[:128],patches=[dict(name=name[:128],controls=dict(zip(order,values)))]),p)
