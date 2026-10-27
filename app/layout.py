"""Stable bus/slot identities across dynamically created group banks."""
MAX_GROUPS=64
SOUNDS=MAX_GROUPS*16
GROUP_BASE=SOUNDS
MASTER=GROUP_BASE+MAX_GROUPS
BUSES=MASTER+1
PREVIEW=SOUNDS
CLICK=SOUNDS+1
ZONE_BASE=SOUNDS+3
SAMPLE_SLOTS=ZONE_BASE+SOUNDS*128

def bus_targets(project):
    return {**{g*16+p:pad for g,group in enumerate(project['groups']) for p,pad in enumerate(group['pads'])},**{GROUP_BASE+g:group for g,group in enumerate(project['groups'])},MASTER:project}
