"""Real utility workflow content, shared by controller layouts.

The old text fallback is insufficient for modern project/export/relink pages.
Keep all selections tied to the engine's existing indices and actions.
"""
from pathlib import Path


def group_status(a):
    """Detached bank feedback: label, mute, solo, focus, audible."""
    groups=a.project['groups'];solo=any(g.get('solo',False) for g in groups)
    return tuple((a.group_name(i),bool(g.get('mute',False)),bool(g.get('solo',False)),
                  i==a.group,not g.get('mute',False) and (not solo or g.get('solo',False)))
                 for i,g in enumerate(groups) if i//8==a.group_bank)


def listing(title,items,index,footer=''):
    items=list(items);index=max(0,min(max(0,len(items)-1),index));first=max(0,min(index-1,len(items)-3))
    return title,tuple(('>' if first+i==index else '')+str(row) for i,row in enumerate(items[first:first+3])) or ('EMPTY',),footer


def utility_data(a):
    p=a.page
    if p in ('AUDIO LOOP','BOUNCE TO PAD'):
        return listing(p,[f'{k}: {v}' for k,v in a.audio_tool_fields()],a.audio_tool_field,'SELECT FIELD / ENCODER EDIT')
    if p=='LIVE FX':
        from app.live_fx import LIVE_FX,LIVE_FX_MODES
        return 'LIVE FX / '+LIVE_FX_MODES[a.live_fx_mode],(LIVE_FX[a.live_fx_current],f'DEPTH {a.live_fx_depth}%'),'SHIFT+SOLO: BACK / F1-F3: MODE'
    from app.preferences import PREFERENCES
    from app.controller_settings import preference_values
    if p in PREFERENCES:
        key,_,_=PREFERENCES[p]
        value=preference_values(a,key)[key]
        return p,(str(value)+(' MS' if p=='MIDI OFFSET' else ''),),'ENCODER: EDIT / SHIFT+F1: RESET'
    if p=='PROJECT MANAGE':
        from app.project_manager import MANAGE
        return listing('PROJECT / MANAGE',MANAGE,a.manage_index,f'{a.manage_index+1}/{len(MANAGE)}')
    if p=='PROJECT NAME':return a.name_action or 'PROJECT NAME',(a.name_value or '_',f'CHAR {a.name_cursor+1:02}/32'),'SHIFT: CLEAR'
    if p=='PRESET LOAD':return listing('LOAD '+a.preset_kind,[path.parent.name for path in a.preset_files()],a.preset_index,'ENTER LOAD')
    if p=='MISSING SAMPLES':
        if a.relink_busy:return 'MISSING SAMPLES',('SCANNING...',),'BACKGROUND SEARCH'
        return listing('MISSING SAMPLES',[Path(row['path']).name for row in a.missing_rows],a.missing_index,'SCAN / SEARCH / BROWSE') if a.missing_rows else ('MISSING SAMPLES',('NO MISSING SAMPLES',),'SCAN TO CHECK')
    if p=='RELINK RESULTS':
        if a.relink_busy:return 'RELINK',('SEARCHING...',),'BACKGROUND SEARCH'
        return listing('RELINK / MATCHES',[str(path) for path in a.relink_paths],a.relink_index,'ENTER SELECT') if a.relink_paths else ('RELINK',('NO MATCHING FILE','BROWSE TO CHOOSE'), 'ORIGINAL REFERENCES KEPT')
    if p=='RELINK BROWSE':
        b=a.relink_browser
        return listing(b.title(),[b.label(path) for path in b.entries()],b.index,'ENTER SELECT') if b else ('RELINK',('NO FOLDER',),'BACK')
    if p=='MACRO ASSIGN':
        choices=a.macro_targets()
        return listing('MACRO / ASSIGN',[row['name'] for row in choices],a.macro_choice,'APPLY TARGET') if choices else ('MACRO / ASSIGN',('NO LV2 PARAMETERS',),'BACK')
    if p=='PLUGIN SLOTS':
        items=a.plugin_target().get('plugins',[])
        return listing('PLUGIN CHAIN',[f'{i+1}. '+(a.plugin_metadata(v['uri']) or {}).get('name',v['uri']) for i,v in enumerate(items)],a.plugin_slot,'ADD / REMOVE / BYPASS')
    if p=='PLUGIN BROWSE':
        items=['REMOVE PLUGIN' if a.plugin_selected() else '*EMPTY SLOT*']+[v['name'] for v in a.plugin_items()]
        return listing('LV2 / '+a.plugin_filter,items,a.plugin_browser_index+1,'LOAD SELECTED SLOT')
    if p=='PLUGIN MOVE':return 'MOVE PLUGIN',(f'DESTINATION SLOT {a.plugin_move_to+1}',),'MOVE / CANCEL'
    if p=='SAMPLE DELETE':return listing('REMOVE SAMPLE',('REMOVE FROM PAD','DELETE FILE'),a.sample_delete_index,'ENTER CONFIRM')
    if p=='EXPORT':
        if a.export_busy:return 'EXPORT / '+a.export_kind,(a.export_status,),'CANCEL'
        fields=a.export_fields();index=min(a.export_field,len(fields)-1)
        return 'EXPORT / '+a.export_kind,('>'+fields[index]+' '+str(a.export_value()),f'{index+1}/{len(fields)} OPTIONS'),'EXPORT / BACK'
    if p=='EXPORT DONE':return 'EXPORT COMPLETE',(a.export_result_device,Path(a.export_result).name),'NEW EXPORT / BACK'
    if p=='OPTIONS':return 'GRID / QUANTIZE',(f'GRID {a.timing()["grid"]}',f'NUDGE {a.timing()["nudge"]}',f'SWING {a.timing()["swing"]}%'),'EDIT BELOW'
    if p=='RECORD SETTINGS':return 'RECORD SETUP',(f'COUNT {a.timing()["count_bars"]} BAR','QUANTIZE '+('ON' if a.timing()['record_quantize'] else 'OFF')),'METRONOME / COUNT-IN'
    if p=='RECORD PREPARE':return 'RECORD PREPARE',(f'{a.pattern_steps()/16:g} BAR',f'GRID {a.timing()["grid"]}'),'LOOP LENGTH'
    if p=='DUPLICATE':return 'DUPLICATE',('SELECT SOURCE PAD' if a.duplicate_source is None else 'SELECT TARGET PAD','WITH EVENTS' if a.duplicate_events else 'SOUND ONLY'),'PADS SELECT'
    return a.display()
