"""Small display-only context, shared by controller snapshots."""
import time
from pathlib import Path


def nav_preview(a):
    from app.mikro_pages import position
    from app.sampler import SAMPLER_PAGES,ZONE_PAGES
    if a.page=='SAMPLING NAV':
        page=('SAMPLING','SAMPLE EDIT','CHOP','ZONE','AUTOSAMPLER')[a.sampling_nav]
        module=('RECORD','EDIT','SLICE','ZONE','AUTO')[a.sampling_nav]
    else:
        choices=a.parameter_choices();i=min(a.parameter_choice,len(choices)-1)
        module=choices[i]
        if a.parameter_kind=='CHNL':page={'OUTPUT':'CHANNEL'}.get(module,module)
        elif a.sampler_slot_present() and i==0:page='SAMPLER'
        else:
            slot=i-int(a.sampler_slot_present());chain=a.plugin_target().get('plugins',[])
            if slot>=len(chain):return dict(module='ADD PLUGIN',section='SELECT PLUGIN',index=0,total=1)
            item=chain[slot];meta=a.plugin_metadata(item['uri']) or {}
            from app.plugin_profiles import controls
            ports=controls(a,item,meta.get('ports',[])) if meta else []
            total=max(1,(len(ports)+7)//8)
            index=min(total-1,a.plugin_param//8) if slot==a.plugin_slot else 0
            first=index*8;names=[p['name'] for p in ports[first:first+8]]
            section=ports[first].get('section') if names else None
            return dict(module=module,section=section or (' / '.join(names[::max(1,len(names)-1)]) if names else 'NO PARAMETERS'),index=index,total=total)
    index,total=position(a,page) or (0,1)
    section={'CHANNEL':lambda:('AUDIO','AUX 1','AUX 2','MIDI')[a.channel_page],
        'SAMPLER':lambda:SAMPLER_PAGES[a.sampler_page][0],
        'ZONE':lambda:ZONE_PAGES[a.zone_page][0],
        'SAMPLE EDIT':lambda:('PLAY RANGE','SELECTION')[a.range_page],
        'SAMPLING':lambda:('SOURCE','INPUT SETUP')[a.capture_section if total>1 else 0],
        'CHOP':lambda:'DETECT ENGINE' if a.slice_section and a.slice_mode=='DETECT' else a.slice_mode,
    }.get(page,lambda:module)()
    return dict(module=module,section=section,index=index,total=total)


def sound_context(a):
    from app.sound_names import sound_name
    name=sound_name(a)
    return f'{a.group_name()}:{a.pad+1:02} {name}'


def pinned(a):
    from app.surface import TEMPORARY
    return bool(a.wave_view_active and a.wave_view_pinned) or any(mode in a.pinned_modes and (a.page==page or mode=='VIEW' and a.page=='VIEW NAV') for mode,page in TEMPORARY.items())


def visible_message(a):
    """Show transient status messages for one second on both controllers."""
    message=a.message;previous,started=getattr(a,'_ui_notice',('',0))
    now=time.monotonic()
    if previous!=message:started=now;a._ui_notice=(message,started)
    return '' if now-started>=1 else message
