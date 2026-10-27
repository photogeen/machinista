"""Mikro VIEW: held workspace picker with compact immutable LCD snapshots."""
VIEWS=('SONG','MIXER','PATTERN GRID','LIVE FX')
LABELS=('SONG','MIXER','EVENTS','LIVE FX')
WAVES=('SAMPLE EDIT','CHOP')
GRIDS=('PATTERN GRID','GRID EDIT')

def canonical(page):return 'PATTERN GRID' if page=='GRID EDIT' else page

def index(page):
    page=canonical(page)
    return VIEWS.index(page) if page in VIEWS else -1

def select(a,delta):
    if not delta:return
    a.view_index=max(0,min(3,a.view_index+delta))
    destination=VIEWS[a.view_index]
    if canonical(a.view_origin)!=destination:a.select_view(destination)

def keys(a):
    if a.view_tool=='GRID':return ('BACK','SCROLL' if a.view_field else 'ZOOM','FOLLOW')
    context='WAVE' if a.view_entry in WAVES else 'GRID' if a.view_entry in GRIDS else '-'
    active=a.view_index>=0 and canonical(a.view_origin)==VIEWS[a.view_index]
    return ('BACK',context,'OFF' if active else 'OPEN')

def button(a,name,pressed):
    if getattr(a,'controller_source','mikro')!='mikro':return False
    if name=='VIEW' and (not a.shift or not pressed and a.view_selector):
        if pressed:
            a.view_entry=a.view_origin=a.page;a.view_selector=True;a.view_tool=None
            a.view_index=index(a.page);a.page='VIEW NAV'
            a.wave_view_active=a.wave_view_pinned=False
            if a.view_entry=='LIVE FX':a.view_returns.setdefault('LIVE FX',a.live_fx_origin)
        elif a.view_selector:
            if a.view_tool=='WAVE':
                if not a.wave_view_pinned:a.wave_view_active=False
            elif a.page=='VIEW NAV':a.activate_view()
            a.view_selector=False;a.view_tool=None
        return True
    if not a.view_selector or a.page!='VIEW NAV':return False
    if name=='MAIN':return True  # Workspace selection always commits on release.
    if not pressed:return name in ('F1','F2','F3','ENTER','ENCODER PUSH','NAV LEFT','NAV RIGHT')
    if name=='F1':
        a.view_tool=None;a.view_origin=a.control_home();a.view_index=-1
        return True
    if name=='F2':
        if a.view_tool=='GRID':a.view_field=1-a.view_field
        elif a.view_entry in WAVES:
            a.page=a.view_entry;a.view_tool='WAVE';a.wave_view_active=a.wave_selected=True;a.wave_view_pinned=False
        elif a.view_entry in GRIDS:a.view_tool='GRID';a.view_field=0;a.view_target='PAT'
        return True
    if a.view_tool=='GRID':
        if name=='F3':a.toggle_grid_follow();return True
        return False
    if name in ('F3','ENTER','ENCODER PUSH'):
        if a.view_index<0:select(a,1)
        else:a.select_view(VIEWS[a.view_index])
        return True
    if name in ('NAV LEFT','NAV RIGHT'):
        select(a,-1 if name=='NAV LEFT' else 1);return True
    return False

def state(a):
    return dict(kind='MIKRO NAV',keys=keys(a),focus=a.view_index,active=index(a.view_origin))

def render(state):
    from app.fokus import Canvas
    from app.fokus_mk2 import navigate_icon
    c=Canvas();c.header(state['keys']);c.title('NAVIGATE')
    for i,kind in enumerate((2,3,5,6)):
        x=2+i*31;active=i==state['active'];focus=i==state['focus']
        c.rect(x,25,29,24,c.ink,False)
        if active:c.rect(x+1,26,27,22)
        ink=c.bg if active else c.ink
        navigate_icon(c,x+5,28,kind,ink)
        if focus:c.rect(x,50,29,1)
    focus=state['focus']
    text=LABELS[focus]+(' / OPEN' if focus==state['active'] else ' / OFF') if focus>=0 else 'TURN TO SELECT'
    c.rect(2,54,124,8);c.text(4,56,text,120,ink=c.bg,center=64)
    return c.finish()
