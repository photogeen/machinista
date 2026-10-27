"""Built-in sidechain dynamics: direct source selection and bounded meter polling."""
import math
from app.layout import GROUP_BASE

URI='urn:machinista:effect:ducktor'

def sources(app):
    result=[('NONE','NONE'),('EXT STEREO','EXT STEREO')]
    for g,group in enumerate(app.project['groups']):
        letter=app.group_name(g);result.append((f'GROUP {g}',f'GROUP {letter}'))
        for i,track in enumerate(group['pads']):
            result.append((f'SOUND {g*16+i}',f'{letter}:{i+1:02} '+app.sound_name(track)))
    return result

def controls(app,selected,ports):
    from app.plugin_profiles import profile
    p=profile(URI);items=sources(app);source=selected.get('sidechain','NONE');index=next((i for i,(key,_) in enumerate(items) if key==source),0)
    selector=dict(symbol='@source',name='SOURCE',default=index,min=0,max=len(items)-1,integer=True,choice=True,choices=list(enumerate(label for _,label in items)),profile_action='ducktor_source')
    by={v['symbol']:v for v in ports};result=[]
    for page in p['pages']:
        for symbol in page['controls']:
            v=dict(selector) if symbol=='@source' else dict(by[symbol],**p.get('overrides',{}).get(symbol,{}))
            v['section']=page['title'];result.append(v)
    return result

def rotate_source(app,selected,delta):
    from app.routing import build_graph
    items=sources(app);old=selected.get('sidechain','NONE');index=next((i for i,(key,_) in enumerate(items) if key==old),0)
    step=1 if delta>0 else -1
    new=old;present='sidechain' in selected
    for _ in range(abs(delta)):
        candidate=index+step
        while 0<=candidate<len(items):
            selected['sidechain']=items[candidate][0]
            try:build_graph(app.project);break
            except ValueError:candidate+=step
        if not 0<=candidate<len(items):break
        index=candidate;new=items[index][0]
    if present:selected['sidechain']=old
    else:selected.pop('sidechain',None)
    if old!=new:app.remember();selected['sidechain']=new;app.plugin_update()
    return True

def view(app):
    if app.page!='PLUGIN':return None
    plugin=app.plugin_selected()
    if not plugin or plugin['uri']!=URI:return None
    source=plugin.get('sidechain','NONE');label=next((name for key,name in sources(app) if key==source),source)
    key=(app.plugin_bus(),app.plugin_slot);meter=getattr(app,'ducktor_meter',{})
    peak,reduction=(meter.get('input',0),meter.get('reduction',0)) if meter.get('key')==key else (0,0)
    return dict(source=label,input_db=max(-60,20*math.log10(max(.001,peak))),reduction=reduction,depth=plugin.get('controls',{}).get('depth',24))

def poll(app,audio,now):
    plugin=app.plugin_selected() if app.page=='PLUGIN' else None
    if not plugin or plugin['uri']!=URI:return
    if now<getattr(app,'ducktor_next',0):return
    app.ducktor_next=now+.1;audio.command(f'ducktor_meter {app.plugin_bus()} {app.plugin_slot}')

def receive(app,event):
    if event.get('kind')!='ducktor_meter':return False
    if app.page=='PLUGIN' and app.plugin_selected() and app.plugin_selected()['uri']==URI:
        key=(event['bus'],event['slot'])
        if key==(app.plugin_bus(),app.plugin_slot):app.ducktor_meter=dict(key=key,input=event['input'],reduction=event['reduction'])
    return True
