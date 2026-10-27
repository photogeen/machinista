"""Controller units for LV2 controls; saved/native values stay unchanged."""
def normalized(port):
    return (port.get('unit') in ('percent','signed_percent') or 0<=port.get('min',-1)<1 and port.get('max')==1 and not port.get('unit')) and not any(port.get(k) for k in ('integer','toggle','choices','choice','profile_action'))

def advance(port,value,delta,fine=False):
    # Retain the fractional offset of imported presets. Each encoder step has
    # identical travel; do not quantize a loaded patch merely to display it.
    return max(port['min'],min(port['max'],round(value+delta/(1000 if fine else 100),9)))

def percent(value):
    return f'{max(0,int(value*100+.5))}%'

def cents(port,value):
    return value*port['display_scale']+port.get('display_offset',0)

def advance_cents(port,value,delta,fine=False):
    step=(.1 if fine else 1)/port['display_scale']
    return max(port['min'],min(port['max'],round(value+delta*step,12)))

def cents_label(port,value):
    number=round(cents(port,value),1)
    if number==0:number=0
    return f'{number:+g} CT' if number else '0 CT'
