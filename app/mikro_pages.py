"""Page positions follow Mikro NAV + arrows, independently of MK2 banks."""
def position(a,page=None):
    page=page or a.page
    if page in ('PAD','CHANNEL'):return a.channel_page,4 if a.control_level==2 else 3
    if page=='AUTOSAMPLER':
        a.auto_setup();return a.auto_field,24
    if page=='SAMPLER':return a.sampler_page,6
    if page=='ZONE':return a.zone_page,5
    if page=='SAMPLE EDIT':return a.range_page,2
    if page=='SAMPLING':return a.capture_section,1 if a.capture_options()['source']=='INTERNAL' else 2
    if page=='CHOP':return a.slice_section,2 if a.slice_mode=='DETECT' else 1
    if page=='PLUGIN':return a.plugin_param//8,max(1,(len(a.plugin_controls())+7)//8)
    if page in ('INPUT','GROOVE','MACRO'):return 0,1
    if page=='INTERFACE MIXER':return a.interface_mixer_index,max(1,len(a.interface_mixer_controls))
    if page=='SYSTEM':
        from app.system_info import system_page_count
        return a.system_index,system_page_count(a.system_stats)
    if page=='SAMPLING NAV':return position(a,('SAMPLING','SAMPLE EDIT','CHOP','ZONE','AUTOSAMPLER')[a.sampling_nav])
    if page=='PARAM NAV':
        choices=a.parameter_choices();choice=choices[min(a.parameter_choice,len(choices)-1)]
        if a.parameter_kind=='CHNL':return position(a,{'OUTPUT':'CHANNEL','INPUT':'INPUT','GROOVE':'GROOVE','MACRO':'MACRO'}.get(choice,'')) if choice in ('OUTPUT','INPUT','GROOVE','MACRO') else None
        if a.sampler_slot_present() and a.parameter_choice==0:return position(a,'SAMPLER')
        slot=a.parameter_choice-int(a.sampler_slot_present())
        return position(a,'PLUGIN') if slot==a.plugin_slot else None
    return None


def marker(index,total):
    total=max(1,total);index=max(0,min(total-1,index))
    return ('<' if index else ' ')+f'{index+1}/{total}'+('>' if index+1<total else ' ')
