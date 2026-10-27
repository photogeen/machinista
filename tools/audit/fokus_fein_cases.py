"""Inventory of actual MK2 renderer states, including secondary/temporary views.

Only fixture data is mutated. Hardware, application bindings and native audio
are never used by the gallery generator or these regression cases.
"""
from app.ui_inventory import WORKFLOWS
from app.sampler import ZONE_PAGES


def cases():
    result=[]
    def add(label,page,**values):result.append((label,page,values))
    for family,pages in WORKFLOWS.items():
        for page in dict.fromkeys(pages):add(family+' / '+page,page)
    for scope in range(3):
        for channel in range(4 if scope==2 else 3):add(f'Output / scope {scope} / page {channel+1}','CHANNEL',control_level=scope,channel_page=channel)
        for channel in range(2):add(f'Input / scope {scope} / page {channel+1}','INPUT',control_level=scope,input_page=channel)
    for page in range(6):
        for kind in ('ONESHOT','ADSR','AHD') if page==1 else ('ADSR',):
            for extra in range(2 if page==2 else 1):add(f'Sampler / {page+1} / {kind} / bank {extra+1}','SAMPLER',sampler_page=page,sampler_kind=kind,sampler_subpage=extra)
    for page,(_,fields) in enumerate(ZONE_PAGES):
        for bank in range((len(fields)+1)//2):add(f'Zones / page {page+1} / bank {bank+1}','ZONE',zone_page=page,zone_subpage=bank)
    for mode in ('SPLIT','GRID','DETECT','MANUAL'):
        for bank in range(3):add(f'Slice / {mode} / bank {bank+1}','CHOP',slice_mode=mode,slice_subpage=bank)
        add('Slice / '+mode+' / edit','CHOP',slice_mode=mode,slice_edit=True)
    for section in range(2):
        for mode in ('INTERNAL','EXT MONO','EXT STEREO'):
            for recmode in ('DETECT','SYNC'):add(f'Record / {mode} / {recmode} / {section+1}','SAMPLING',capture_section=section,capture_source=mode,capture_mode=recmode)
    add('Record / running','SAMPLING',capture_started=100,capture_peaks=(.43,.39))
    for selection in (0,1):add('Edit / '+('selection' if selection else 'play range'),'SAMPLE EDIT',range_page=selection)
    for first in (None,0,15):add('Apply / first '+str(first),'SLICE TARGET',slice_target_group=7,slice_target_sound=first)
    for keyboard in (False,True):
        for bank in range(2 if not keyboard else 1):add(f'Pad config / keyboard {keyboard} / {bank+1}','PAD CONFIG',keyboard_enabled=keyboard,pad_page=bank)
    for page in ('PLUGIN','PLUGIN MOVE','PLUGIN BROWSE'):
        for bank in range(3):add(f'Plugins / {page} / bank {bank+1}',page,populated_plugins=True,plugin_param=bank*8)
    for page in ('BROWSE','PLUGIN','SETTINGS','CONFIRM','PROJECT NAME','CHOP','SAMPLING','STRETCH','MUTE','SELECT','SLICE TARGET','SYSTEM','PATTERN GRID','MIXER'):
        add('SHIFT / '+page,page,shift=True)
        add('Notice / '+page,page,message='SAVED / LONG STATUS MESSAGE')
    for page in ('PAD','SAMPLER','PLUGIN','PATTERN GRID','STEP','MIXER'):
        add('Transport / '+page,page,playing=True,recording=True,clock_phase=440,step=18)
        add('Automation / '+page,page,playing=True,auto_locked=True)
    for level in range(3):
        for field in range(3):add(f'Mixer / scope {level} / field {field}','MIXER',mixer_level=level,mixer_field=field,meters=True)
    for notes in (False,True):add(f'Editor / pitches {notes}','PATTERN GRID',grid_notes=notes,populated_notes=True)
    for name in ('VOLUME','SWING','TEMPO'):add('Master / '+name,'PAD',master_mode=name,main_controls=True)
    for bank in range(3):add(f'Storage / bank {bank+1}','SYSTEM',storage_bank=bank)
    for folder in ('AUDIO','MIDI','SYSTEM'):
        for index in (0,3,7):add(f'Settings / {folder} / row {index+1}','SETTINGS',settings_folder=folder,menu=index)
    for page in ('PAD','SAMPLER','GROUP','MUTE','SOLO'):add('Group mute / '+page,page,group_muted=True)
    for state in ('STARTING','SCANNING','CONNECTED','ERROR'):add('BLE / '+state,'BLUETOOTH MIDI',ble_state=state)
    for state in ('EMPTY','LONG','BUSY'):add('Projects / '+state,'PROJECT NAME' if state!='BUSY' else 'EXPORT',name_value='' if state=='EMPTY' else 'WWWW WWWW WWWW WWWW WWWW WWWW WWWW',name_cursor=31,export_busy=state=='BUSY')
    return result


def apply(a,surface,page,values):
    a.page=page
    special={'sampler_kind','capture_source','capture_mode','capture_peaks','populated_plugins','populated_notes','meters','storage_bank','group_muted','ble_state'}
    surface_keys={'sampler_subpage','zone_subpage','slice_subpage','pad_page','master_mode','auto_locked'}
    for key,value in values.items():
        if key in special:continue
        setattr(surface if key in surface_keys else a,key,value)
    surface.auto_page=surface.master_page=a.page
    if 'sampler_kind' in values:a.track()['sampler']['type']=values['sampler_kind']
    if 'capture_source' in values:
        a.capture_options().update(source=values['capture_source'],input='MASTER' if values['capture_source']=='INTERNAL' else 'IN 1 L' if values['capture_source']=='EXT MONO' else 'IN 1')
    if 'capture_mode' in values:a.capture_options()['mode']=values['capture_mode']
    if 'capture_peaks' in values:a.capture_stereo_peak=values['capture_peaks']
    if values.get('populated_plugins'):
        ports=[dict(index=i,symbol=f'ctrl{i}',name='Long Parameter '+str(i+1),default=.5,min=0,max=1) for i in range(24)]
        a.plugin_catalog=[dict(uri='urn:fein:test',name='Long Plugin Name For Display Review',kind='EFFECT',supported=True,ports=ports)]
        a.track()['plugins']=[dict(uri='urn:fein:test',kind='EFFECT',bypass=i==1,controls={}) for i in range(3)]
        a.plugin_move_to=2
    if values.get('populated_notes'):
        for row in range(5):a.put_note(row,row*24,dict(velocity=90,length=24,probability=100,note=36+row))
    if values.get('meters'):
        bus,count=a.mixer_watch();a.mixer_levels={bus+i:(.12+i*.03,.1+i*.03) for i in range(count)}
        a.mixer_peaks={bus+i:(.2+i*.03,.18+i*.03) for i in range(count)}
    if 'storage_bank' in values:
        a.system_stats['storage']=[dict(name='SD CARD' if i==0 else 'USB '+str(i),percent=20+i*10,used=(i+2)*1e9,total=32e9) for i in range(5)]
        a.system_index=values['storage_bank']
    if values.get('group_muted'):a.project['groups'][0]['mute']=True
    if 'ble_state' in values:
        state=values['ble_state'];a.bluetooth_status={'enabled':True,'starting':state=='STARTING','scanning':state=='SCANNING','devices':[dict(name='USB Keyboard with a very long name',address='00:00:00:00:00:01',connected=True)] if state=='CONNECTED' else []}
        if state=='ERROR':a.bluetooth_status['error']='BLUETOOTH UNAVAILABLE'
