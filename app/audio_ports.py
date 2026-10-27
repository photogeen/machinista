"""Named physical USB channels; absent mappings are retained, never redirected."""
MAX_CHANNELS = 64

def ports(channels, prefix):
    channels = min(MAX_CHANNELS, max(0, channels))
    return tuple(f'{prefix} {i+1}' for i in range(channels)) + tuple(f'{prefix} {i+1}/{i+2}' for i in range(0, channels-1, 2))

def port(value, prefix):
    if not isinstance(value,str) or not value.startswith(prefix+' '):return None
    try:
        numbers=tuple(int(n)-1 for n in value.split()[1].split('/'))
    except (ValueError,IndexError):raise ValueError('invalid physical channel')
    if len(numbers) not in (1,2) or any(not 0<=n<MAX_CHANNELS for n in numbers) or len(numbers)==2 and (numbers[0]%2 or numbers[1]!=numbers[0]+1):raise ValueError('invalid physical channel')
    return numbers

def cue_sound(project, group, pad):
    bank=project['groups'][group];route=bank['pads'][pad].get('routing',{}).get('dest','PARENT')
    return route=='CUE' or route=='PARENT' and bank.get('routing',{}).get('dest','PARENT')=='CUE'
