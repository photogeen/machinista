"""Primitive visible-grid snapshots for the independent LCD process."""
from app.ni_display import rect,label,tiny_label,note_name,finish_frame,dotted_rect,softkey_label


def pattern_state(app):
    from app.ui_context import pinned,visible_message
    app.grid_step=min(app.grid_step,app.grid_length()-1);app.grid_targets()
    length=app.grid_length();unit=app.grid_ticks();start=min(app.view_first,max(0,length-1));count=app.view_count
    columns=min(16,count);first=max(4,min(15,app.pad+2));top=min(127,max(4,app.grid_note+2))
    values=[top-row if app.grid_notes else first-row for row in range(5)]
    visible={}
    for key,event in app.event_notes().items():
        pad,tick=key[:2];cell=tick//unit
        if not start<=cell<min(length,start+count) or app.grid_notes and pad!=app.pad:continue
        value=event.get('note',app.track().get('note',36+pad)) if app.grid_notes else pad
        if value not in values:continue
        index=(values.index(value),(cell-start)*columns//count)
        visible[index]=visible.get(index,False) or key in app.grid_selected
    rows=[]
    for row,value in enumerate(values):
        focused=value==(app.grid_note if app.grid_notes else app.pad)
        cells=[]
        for col in range(columns):
            step=start+col*count//columns;last=start+(col+1)*count//columns
            cells.append((step<length,(row,col) in visible,visible.get((row,col),False),focused and step<=app.grid_step<last))
        rows.append((note_name(value) if app.grid_notes else f'{value+1:02}',focused,cells))
    candidates=sorted(app.grid_cursor_candidates())
    voice=f'V{candidates.index(app.grid_voice)+1}/{len(candidates)}' if app.grid_voice in candidates else ''
    return dict(kind='PATTERN GRID',keys=app.softkeys(),active=tuple(app.active_softkeys()),
                title=app.transport_title() if app.playing or app.recording or app.count_remaining else f'PAT {app.pattern+1:02} GROUP {app.group_name()}',
                first=start+1,last=min(length,start+count),follow=app.grid_follow,voice=voice,rows=rows,columns=columns,
                selection_range=app.grid_selection_range,playhead=app.pattern_playhead_x(),message=visible_message(app),pinned=pinned(app),
                footer=f'{app.pad+1:02} {note_name(app.grid_note if app.grid_notes else app.grid_pitch(app.pad,app.grid_step))} S{app.grid_step+1:02} SEL:{len(app.grid_selected)}')


def pattern_body(p,state):
    tiny_label(p,2,23,f'{state["first"]:02}-{state["last"]:02}')
    tiny_label(p,91,23,'FOL ON' if state['follow'] else 'FOL OFF')
    if state['voice']:tiny_label(p,40,23,state['voice'])
    cell_width=96//state['columns']
    for row,(caption,focused,cells) in enumerate(state['rows']):
        y=29+row*5
        if focused:rect(p,1,y,25,5,0)
        tiny_label(p,2,y,caption,1 if focused else 0)
        for col,(valid,present,selected,cursor) in enumerate(cells):
            if not valid:continue
            x=29+col*cell_width
            if col%4==0:rect(p,x,y,1,5,0)
            if present:
                if selected:rect(p,x,y,cell_width,5,0,False)
                else:rect(p,x+1,y+1,cell_width-2,3,0)
            if cursor:rect(p,x,y,cell_width,5,0,False)
    if state['playhead'] is not None:
        for y in range(29,54):p[y*128+state['playhead']]^=1
    label(p,2,56,state['footer'])


def pattern_frame(state):
    pixels=legacy_pattern_frame(state)
    from app.fokus import enabled,live
    return live(state,pixels) if enabled() else pixels


def legacy_pattern_frame(state):
    p=bytearray([1]*8192)
    for i,key in enumerate(state['keys']):
        x=i*43;w=40 if i==2 else 41;active=i in state['active'];disabled=key in ('','-')
        if disabled:dotted_rect(p,x+1,1,w,10)
        else:rect(p,x+1,1,w,10,0,active)
        if not disabled:softkey_label(p,x+1,w,key,1 if active else 0)
    rect(p,1,12,126,11,0);label(p,4,15,state['title'],1,bold=True,max_width=120)
    pattern_body(p,state)
    if 'view_nav_footer' in state:
        rect(p,0,55,127,8,1);label(p,2,56,state['view_nav_footer'])
    from app.fokus import enabled
    if state['message'] and not enabled():
        rect(p,0,55,128,8,0);label(p,2,56,state['message'],1)
    return bytes(finish_frame(p))
