"""Apply explicit web parameter edits on the app thread, using normal undo/audio actions."""
import copy
import math


def apply_parameters(app,value):
    slot=value.get('slot');plugins=app.track().get('plugins',[])
    if type(slot) is not int or not 0<=slot<len(plugins):raise ValueError('Select an installed plugin on the current Sound first.')
    plugin=plugins[slot]
    if value.get('uri')!=plugin['uri']:raise ValueError('Plugin changed. Refresh first.')
    metadata=app.plugin_metadata(plugin['uri'])
    if not metadata:raise ValueError('Plugin metadata unavailable.')
    ports={port['symbol']:port for port in metadata['ports']};updates=value.get('controls')
    if not isinstance(updates,dict) or not 1<=len(updates)<=128:raise ValueError('Invalid plugin parameter request.')
    changes={}
    for symbol,number in updates.items():
        port=ports.get(symbol)
        if not port or type(number) not in (int,float) or not math.isfinite(number):raise ValueError('Invalid plugin parameter.')
        if not port['min']<=number<=port['max'] or ((port.get('integer') or port.get('toggle')) and int(number)!=number):raise ValueError('Plugin parameter out of range.')
        changes[symbol]=number
    app.remember();plugin.setdefault('controls',{}).update(changes)
    app.actions.append(('plugins',(app.group*16+app.pad,copy.deepcopy(plugins))))
