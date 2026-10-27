"""Additional standalone preferences with persistent values."""
from app.storage import save_json
from app.controller_settings import preference_values
PREFERENCES={
 'AUTOSAVE':('autosave','ON',('OFF','ON')),
 'MIDI SYNC':('midi_sync','OFF',('OFF','IN','OUT')),
 'MIDI OFFSET':('midi_offset',0,(-100,100)),
 'PAD CURVE':('pad_curve','LINEAR',('SOFT','LINEAR','HARD','FIXED')),
 'PERFORM GRID':('perform_grid','SCENE',('SCENE','IMMEDIATE','1 BAR','1/2','1/4','1/8','1/16')),
 'RETRIGGER':('scene_retrigger','OFF',('OFF','ON')),
 'ARRANGE GRID':('arrange_grid','1 BAR',('1 BAR','1/2','1/4','1/8','1/16')),
 'PAD SENS':('pad_sensitivity',100,(25,200)),
}
class Preferences:
    def init_preferences(self):
        for page,(key,default,bounds) in PREFERENCES.items():
            self.settings.setdefault(key,default);value=self.settings[key]
            if isinstance(default,str):valid=value in bounds
            else:valid=type(value) is int and bounds[0]<=value<=bounds[1]
            if not valid:raise ValueError('invalid preference '+key)
    def preferences_button(self,name,pressed):
        if self.page not in PREFERENCES:return False
        if pressed and name in ('F3','MAIN','ENTER'):self.page='SETTINGS';return True
        if pressed and name=='F1':
            key,default,_=PREFERENCES[self.page];preference_values(self,key)[key]=default;save_json(self.settings_path,self.settings);return True
        return name in ('F2','NAV LEFT','NAV RIGHT')
    def preferences_rotate(self,delta):
        if self.page not in PREFERENCES:return False
        key,default,bounds=PREFERENCES[self.page];values=preference_values(self,key);old=values[key]
        values[key]=bounds[max(0,min(len(bounds)-1,bounds.index(old)+delta))] if isinstance(default,str) else max(bounds[0],min(bounds[1],old+delta))
        save_json(self.settings_path,self.settings);return True
    def pad_velocity(self,raw,source='mikro'):
        values=preference_values(self,'pad_sensitivity',source)
        # MK3's event decoder already supplies MIDI velocity (1..127).
        # Other HID readers supply raw pressure counts; applying that scale to
        # MK3 a second time crushed even the strongest hit to velocity 6.
        level=raw/127 if source in ('mk3','plus') else (raw-60)/1500
        normalized=max(0,min(1,level*(1 if source in ('mk3','plus') else values['pad_sensitivity']/100)))
        curve=values['pad_curve']
        if curve=='FIXED':return self.velocity_value
        if curve=='SOFT':normalized=normalized**.6
        elif curve=='HARD':normalized=normalized**1.6
        return max(1,min(127,round(normalized*127)))
