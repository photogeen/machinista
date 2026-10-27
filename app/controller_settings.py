"""Device-local hardware preferences; legacy flat keys belong to Mikro only."""
from contextlib import contextmanager
from functools import wraps
from app.storage import save_json

DISPLAY_PAGES=('BRIGHTNESS','CONTRAST','CONTRAST L','CONTRAST R','INVERT')
DEVICE_PAGES=DISPLAY_PAGES+('PAD SENS','PAD CURVE')
MK2_DEFAULTS=dict(invert=False,brightness=None,contrast_left=None,contrast_right=None,pad_sensitivity=100,pad_curve='LINEAR')

def init_controller_settings(app):
    app.controller_source='mikro'
    if type(app.settings.setdefault('display_invert',False)) is not bool:raise ValueError('invalid display inversion')
    controllers=app.settings.setdefault('controllers',{})
    if not isinstance(controllers,dict):raise ValueError('invalid controller settings')
    for device in ('mk2','mk1','mikro_mk2','mk3','plus'):
        values=controllers.setdefault(device,{})
        if not isinstance(values,dict):raise ValueError('invalid '+device+' settings')
        defaults=dict(MK2_DEFAULTS)
        if device=='mikro_mk2':defaults.update(display_brightness=100,display_contrast=42,display_invert=False)
        if device=='mk1':defaults.update(brightness=72,contrast_left=29,contrast_right=29)
        for key,default in defaults.items():
            value=values.setdefault(key,default)
            if key in ('invert','display_invert'):valid=type(value) is bool
            elif key=='pad_curve':valid=value in ('SOFT','LINEAR','HARD','FIXED')
            elif key=='pad_sensitivity':valid=type(value) is int and 25<=value<=200
            else:valid=value is None or type(value) is int and 0<=value<=100
            if not valid:raise ValueError('invalid '+device+' '+key)

@contextmanager
def controller_context(app,source):
    previous=getattr(app,'controller_source','mikro');app.controller_source=source
    try:yield
    finally:app.controller_source=previous

def on_controller(source):
    def decorate(function):
        @wraps(function)
        def wrapped(surface,*args,**kwargs):
            with controller_context(surface.app,getattr(surface,'source',source)):return function(surface,*args,**kwargs)
        return wrapped
    return decorate

def is_mk2(app):return getattr(app,'controller_source','mikro') in ('mk2','mk1','mk3','plus')
def preference_values(app,key,source=None):
    source=source or getattr(app,'controller_source','mikro')
    source=mikro_device(app) if source=='mikro' else source
    return app.settings['controllers'][source] if source in ('mk2','mk1','mikro_mk2','mk3','plus') and key in ('pad_sensitivity','pad_curve') else app.settings

def display_key(app,page=None):
    page=page or app.page
    if page=='INVERT':return 'invert' if is_mk2(app) else 'display_invert'
    if is_mk2(app):return 'brightness' if page=='BRIGHTNESS' else 'contrast_right' if page=='CONTRAST R' else 'contrast_left'
    return 'display_brightness' if page=='BRIGHTNESS' else 'display_contrast'
def mikro_device(app):return getattr(app,'mikro_model','mikro')
def display_values(app):
    if is_mk2(app):return app.settings['controllers'][app.controller_source]
    return app.settings['controllers']['mikro_mk2'] if mikro_device(app)=='mikro_mk2' else app.settings
def mikro_display_settings(app):
    values=app.settings['controllers']['mikro_mk2'] if mikro_device(app)=='mikro_mk2' else app.settings
    return values['display_brightness'],values['display_contrast'],values.get('display_invert',False)
def display_value(app):
    key=display_key(app);value=display_values(app)[key]
    return value if value is not None else 100 if key=='brightness' else 42

def save_display(app,key,value):
    display_values(app)[key]=value;save_json(app.settings_path,app.settings)
    app.actions.append(('controller_display_settings',app.controller_source) if is_mk2(app) else ('display_settings',None))
def change_display(app,delta):
    value=(delta>0 if delta else display_value(app)) if app.page=='INVERT' else max(0,min(100,display_value(app)+delta))
    save_display(app,display_key(app),value)
def reset_display(app):
    key=display_key(app)
    if app.page=='INVERT':save_display(app,key,False);return
    default=(72 if 'brightness' in key else 29) if getattr(app,'controller_source','mikro')=='mk1' else (100 if 'brightness' in key else 42)
    save_display(app,key,default)

def seed_mk2_settings(app,actual,source="mk2"):
    values=app.settings['controllers'][source];changed=False
    for key in ('brightness','contrast_left','contrast_right'):
        if values[key] is None:values[key]=actual[key];changed=True
    if changed:save_json(app.settings_path,app.settings)
