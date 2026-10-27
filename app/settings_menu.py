"""MAIN folders with fixed Audio / MIDI / System softkeys."""
from app.preferences import PREFERENCES
from app.storage import save_json
from app.controller_settings import DISPLAY_PAGES,is_mk2,preference_values,reset_display

SETTINGS_FOLDERS = {
    'AUDIO': ('AUDIO', 'AUDIO RATE', 'AUDIO BUFFER', 'MAIN OUTPUT', 'CUE OUTPUT', 'CUE LEVEL', 'PLUGIN DELAY', 'DAC', 'INTERFACE MIXER'),
    'MIDI': ('MIDI IN', 'MIDI OUT', 'MIDI CHANNEL', 'MIDI SYNC', 'MIDI OFFSET', 'MIDI LEARN', 'TEMPO', 'BLUETOOTH MIDI'),
    'SYSTEM': ('DISPLAY', 'PADS', 'WORKFLOW', 'PROJECT SETTINGS', 'SYSTEM', 'UPDATE', 'POWER'),
}
SYSTEM_SECTIONS = {
    'DISPLAY': ('BRIGHTNESS','CONTRAST','INVERT'),
    'PADS': ('PAD SENS','PAD CURVE'),
    'WORKFLOW': ('PERFORM GRID','RETRIGGER','ARRANGE GRID'),
    'PROJECT SETTINGS': ('AUTOSAVE','PROJECT'),
    'DAC': ('HEADPHONE LEVEL','SPEAKER LEVEL','INPUT GAIN'),
    'POWER': ('REBOOT','SHUTDOWN'),
}
SETTING_PAGES = tuple(dict.fromkeys(p for pages in (*SETTINGS_FOLDERS.values(),*SYSTEM_SECTIONS.values()) for p in pages if p not in SYSTEM_SECTIONS))+('CONTRAST L','CONTRAST R')
# Project retains its editing keys after opening from MAIN.
SETTINGS_VIEWS = ('SETTINGS',) + tuple(p for p in SETTING_PAGES if p != 'PROJECT')
SETTINGS_LABELS = {'AUDIO': 'INTERFACE', 'AUDIO RATE': 'SAMPLE RATE', 'AUDIO BUFFER': 'BUFFER', 'MIDI IN': 'INPUT', 'MIDI OUT': 'OUTPUT', 'MIDI CHANNEL': 'CHANNEL', 'MIDI SYNC': 'CLOCK', 'MIDI OFFSET': 'CLOCK OFFSET', 'SYSTEM': 'SYSTEM INFO', 'PADS': 'PAD RESPONSE', 'POWER': 'POWER', 'REBOOT': 'RESTART', 'SHUTDOWN': 'SHUT DOWN', 'DAC': 'DAC SETTINGS', 'PROJECT SETTINGS': 'PROJECT', 'PROJECT':'PROJECT MANAGER', 'BACK':'< BACK'}

class SettingsMenu:
    def init_settings_menu(self):
        self.settings_folder = 'AUDIO'
        self.settings_section = None
        self.settings_positions = dict.fromkeys(SETTINGS_FOLDERS, 0)
        self.audio_status = {}
        self.interface_mixer_context = None
        self.interface_mixer_controls = []
        self.interface_mixer_index = 0
        self.interface_mixer_error = ''
        self.pdc_status = {}
        self.system_index = 0
        self.system_stats = {'cpu': None, 'ram': None, 'storage': []}
        self.bluetooth_status={'enabled':False,'devices':[]}
        self.bluetooth_index=0
        from app.updater import initial
        self.update_status=initial(self.root)
        if type(self.settings.setdefault('ble_midi',False)) is not bool:raise ValueError('invalid BLE MIDI preference')

    def settings_title(self):
        return self.settings_section or self.settings_folder

    def setting_entries(self):
        entries=SYSTEM_SECTIONS[self.settings_section] if self.settings_section else SETTINGS_FOLDERS[self.settings_folder]
        if self.settings_section=='DISPLAY' and is_mk2(self):entries=('BRIGHTNESS','CONTRAST L','CONTRAST R','INVERT')
        if not self.update_status.get('enabled'):entries=tuple(v for v in entries if v!='UPDATE')
        return entries+('BACK',) if self.settings_section else entries

    def settings_position_key(self):
        return (self.settings_folder,self.settings_section) if self.settings_section else self.settings_folder

    def open_settings(self, folder=None):
        if folder is not None:
            self.settings_folder = folder
            self.settings_section = None
        self.main_controls=False
        self.page = 'SETTINGS'
        self.menu = max(0,min(len(self.setting_entries())-1,self.settings_positions.get(self.settings_position_key(),0)))

    def open_setting(self):
        self.menu=max(0,min(len(self.setting_entries())-1,self.menu))
        self.settings_positions[self.settings_position_key()]=self.menu
        selected=self.setting_entries()[self.menu]
        if selected=='BACK':self.settings_back()
        elif not self.settings_section and selected in SYSTEM_SECTIONS:
            self.settings_section=selected;self.open_settings()
        elif selected in ('REBOOT','SHUTDOWN'):
            action='reboot' if selected=='REBOOT' else 'shutdown'
            self.confirm('SAVE AND RESTART?' if action=='reboot' else 'SAVE AND SHUT DOWN?',lambda:self.request_power(action))
        else:self.page=selected;self.system_index=0

    def settings_back(self):
        if self.page!='SETTINGS':self.open_settings()
        elif self.settings_section:self.settings_section=None;self.open_settings()
        else:self.page=self.control_home()

    def request_power(self,action):
        if self.recording or self.capture_started is not None or self.capture_armed or self.export_busy:
            self.message='STOP RECORD/PROCESS FIRST';return
        self.actions.append(('power',action))
        self.message='POWER REQUEST...'

    def set_dac_mute(self,page,value=None):
        from app.codec_levels import MUTES,supported
        if not supported(self.audio):self.message='ULTRA HAT ONLY';return
        key,_=MUTES[page];self.settings[key]=not self.settings[key] if value is None else bool(value)
        save_json(self.settings_path,self.settings);self.actions.append(('codec_levels',None))

    def settings_button(self, name, pressed):
        from app.updater import button as update_button
        if update_button(self,name,pressed):return True
        from app.bluetooth_midi import button
        if button(self,name,pressed):return True
        if self.page not in SETTINGS_VIEWS:
            return False
        from app.codec_levels import dac_context
        if dac_context(self) and name in ('F1','F2','F3'):
            if pressed:
                if name=='F3':self.settings_back()
                else:self.set_dac_mute('HEADPHONE MUTE' if name=='F1' else 'SPEAKER MUTE')
            return True
        if self.page=='TEMPO' and name=='ENCODER PUSH':
            self.encoder_held=pressed
            return True
        if not pressed:
            return name in ('F1', 'F2', 'F3', 'MAIN', 'ENTER', 'ENCODER PUSH', 'NAV LEFT', 'NAV RIGHT')
        if self.shift and name == 'F1' and self.page in DISPLAY_PAGES + tuple(PREFERENCES):
            if self.page in PREFERENCES:
                key,value,_=PREFERENCES[self.page];preference_values(self,key)[key]=value
                save_json(self.settings_path,self.settings)
            else:reset_display(self)
            return True
        if name in ('F1', 'F2', 'F3'):
            self.open_settings(tuple(SETTINGS_FOLDERS)[int(name[1])-1])
            return True
        if name in ('MAIN', 'ENTER', 'ENCODER PUSH'):
            if self.page == 'SETTINGS':
                if name == 'MAIN':
                    self.settings_back()
                else:self.open_setting()
            else:
                self.open_settings()
            return True
        if self.page=='INTERFACE MIXER' and name in ('NAV LEFT','NAV RIGHT'):
            self.select_interface_control(-1 if name=='NAV LEFT' else 1);return True
        if name in ('NAV LEFT', 'NAV RIGHT'):
            if name=='NAV LEFT' and (self.page!='SYSTEM' or self.system_index==0):self.settings_back();return True
            if self.page == 'SYSTEM':
                self.settings_rotate(-1 if name == 'NAV LEFT' else 1)
            return True
        return False

    def interface_control(self):
        if not self.interface_mixer_controls:return None
        self.interface_mixer_index=max(0,min(len(self.interface_mixer_controls)-1,self.interface_mixer_index))
        return self.interface_mixer_controls[self.interface_mixer_index]

    def select_interface_control(self,delta):
        self.interface_mixer_index=max(0,min(max(0,len(self.interface_mixer_controls)-1),self.interface_mixer_index+delta))

    def interface_level(self,delta):
        from app.interface_mixer import context
        control=self.interface_control()
        if not control or context(self.audio)!=self.interface_mixer_context:return
        value=max(0,min(100 if control['kind']=='level' else 1,control['value']+delta*control.get('step',1)))
        if value==control['value']:return
        control.update(value=value,values=[value],db=())
        self.actions.append(('interface_mixer',(self.interface_mixer_context,control['id'],value)))

    def settings_rotate(self, delta):
        if self.page=='UPDATE':
            from app.updater import command
            if delta:command(self,'channel','release' if delta>0 else 'beta')
            return True
        if self.page=='INTERFACE MIXER':
            self.interface_level(delta);return True
        if self.page=='BLUETOOTH MIDI':
            self.bluetooth_index=max(0,min(len(self.bluetooth_status.get('devices',[]))-1,self.bluetooth_index+delta));return True
        from app.codec_levels import CONTROLS,MUTES,supported
        if self.page in MUTES:
            if delta:self.set_dac_mute(self.page,delta>0)
            return True
        if self.page in CONTROLS:
            if not supported(self.audio):
                self.message='ULTRA HAT ONLY';return True
            key,_,maximum,_=CONTROLS[self.page]
            value=max(0,min(maximum,self.settings[key]+delta))
            if value!=self.settings[key]:
                self.settings[key]=value;save_json(self.settings_path,self.settings)
                self.actions.append(('codec_levels',None))
            return True
        if self.page=='PLUGIN DELAY':
            if self.playing or self.recording or self.capture_started is not None or self.capture_armed:
                self.message='STOP RECORD/PLAY FIRST';return True
            value=delta>0 if delta else self.settings['plugin_delay']
            if value!=self.settings['plugin_delay']:
                self.settings['plugin_delay']=value;save_json(self.settings_path,self.settings)
                self.actions.append(('plugin_delay',value))
            return True
        if self.page in ('MAIN OUTPUT','CUE OUTPUT','CUE LEVEL'):
            key={'MAIN OUTPUT':'main_output','CUE OUTPUT':'cue_output','CUE LEVEL':'cue_level'}[self.page]
            if key=='cue_level':value=max(0,min(100,self.settings[key]+delta))
            else:
                from app.audio_ports import ports
                choices=ports(self.audio.output_channels if self.audio else 0,'OUT')
                if key=='cue_output':choices=('OFF',)+choices
                if not choices:self.message='NO AUDIO DEVICE';return True
                current=self.settings[key];index=choices.index(current) if current in choices else 0
                value=choices[max(0,min(len(choices)-1,index+delta))]
                other=self.settings['main_output' if key=='cue_output' else 'cue_output']
                from app.audio_ports import port
                if set(port(value,'OUT') or ()) & set(port(other,'OUT') or ()):self.message='MAIN / CUE MUST DIFFER';return True
            self.settings[key]=value;save_json(self.settings_path,self.settings)
            self.actions.append(('audio_outputs',None));return True
        if self.page == 'SETTINGS':
            self.menu = max(0, min(len(self.setting_entries())-1, self.menu + delta))
            self.settings_positions[self.settings_position_key()] = self.menu
            return True
        if self.page == 'SYSTEM':
            from app.system_info import system_page_count
            self.system_index = max(0, min(system_page_count(self.system_stats,'mk2' if is_mk2(self) else 'mikro')-1, self.system_index + delta))
            return True
        return False
