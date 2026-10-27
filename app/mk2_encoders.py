"""Travel per UI step for MK2 smooth knobs, derived from the bound control.

Categorical choices need more travel than levels, time/sample positions or
continuous LV2 ports. This classification performs no I/O and changes neither
parameter ranges nor the underlying engine's edit operations.
"""
from app.preferences import PREFERENCES
from app.performance import ARP_DEFAULTS
from app.sampler import ZONE_PAGES

# Deliberate turns for menus/modes; tiny movements must not skip choices.
CHOICE_TRAVEL=32


def choice_binding(surface,field):
    a=surface.app
    if field is None:return False
    attrs=dict(field.attributes)
    if any(k in attrs for k in ('_record_quant','_dac_mute','_grid','_target_group','_target_sound','_bluetooth','_name_cursor','export_field')):return True
    if '_auto' in attrs:return attrs['_auto'] in (0,4,8,9,10,11,12,13)
    if '_sample_tool' in attrs:return a.page=='BOUNCE TO PAD' or attrs['_sample_tool'] in (0,1,2)
    if '_hardware_select' in attrs:return True
    if '_hardware_level' in attrs:return (a.interface_control() or {}).get('kind')=='switch'
    if '_controller_key' in attrs:return attrs['_controller_key'] in ('pad_curve','invert')
    if '_mixer' in attrs:return a.mixer_field==2
    if 'sampler_field' in attrs:
        key,_,default,_=a.sampler_fields()[attrs['sampler_field']]
        return isinstance(default,(str,bool)) or key=='polyphony'
    if 'channel_field' in attrs:
        key=a.channel_fields()[attrs['channel_field']]
        return key.endswith('dest') or key in ('aux1_pre','aux2_pre','midi_send','midi_target','channel')
    if 'input_field' in attrs:return attrs['input_field']==0
    if 'groove_field' in attrs:return attrs['groove_field'] in (1,2)
    if 'capture_field' in attrs:return a.capture_fields()[attrs['capture_field']]!='threshold'
    if 'slice_field' in attrs:
        if a.slice_edit:return False
        index=attrs['slice_field']
        if attrs.get('slice_section',a.slice_section):return True
        if index==1:return a.slice_mode!='DETECT'
        if index==3:return a.slice_options()['bpm_mode']=='AUTO'
        return True
    if 'slice_target_field' in attrs:return True
    if 'zone_field' in attrs:return ZONE_PAGES[a.zone_page][1][attrs['zone_field']]=='loop'
    if 'pad_field' in attrs:return (attrs['pad_field'] in (1,2,3,4,6,9,11)) if a.keyboard_enabled else attrs['pad_field'] in (0,1,2,3,5)
    if 'arp_field' in attrs:return tuple(ARP_DEFAULTS)[attrs['arp_field']] in ('rate','division','type','hold')
    if 'grid_field' in attrs:return attrs['grid_tab']==2 or (attrs['grid_tab']==0 and attrs['grid_field']==1)
    if 'record_field' in attrs:return attrs['record_field']!=0
    if 'prepare_field' in attrs:return attrs['prepare_field']==1
    if 'plugin_param' in attrs:
        ports=a.plugin_controls();index=attrs['plugin_param']
        return index<len(ports) and bool(ports[index].get('toggle') or ports[index].get('choice'))
    if '_utility' in attrs:
        if a.page in PREFERENCES:return isinstance(PREFERENCES[a.page][1],str)
        return a.page in ('SETTINGS','BROWSE','PLUGIN BROWSE','PROJECT LOAD','PROJECT MANAGE','PRESET LOAD','MISSING SAMPLES','RELINK RESULTS','PROJECT NAME','MACRO ASSIGN','PLUGIN MOVE','PLUGIN SC','AUDIO BUFFER','AUDIO RATE','MIDI CHANNEL','AUDIO','MIDI IN','MIDI OUT','MAIN OUTPUT','CUE OUTPUT','PLUGIN DELAY','INVERT','MIDI LEARN','SONG AUTO','SONG','SCENE OPTIONS')
    return False


def quantum(surface,field):
    return CHOICE_TRAVEL if choice_binding(surface,field) else 8
