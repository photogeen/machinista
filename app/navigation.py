"""Contextual Mikro parameter NAV and held/pinned VIEW navigation."""
from app.storage import save_json
import copy
from app.audio_loop import is_audio_sound

CONTROL_PAGES=('PAD','SAMPLER','PLUGIN','CHANNEL','INPUT','GROOVE','MACRO')
CONTROL_FIELDS=('channel_page','channel_field','input_field','groove_field','macro_index','sampler_page','sampler_field','plugin_slot','plugin_param')


class Navigation:
    def init_navigation(self):
        self.control_views={};self.control_last='PAD'
        self.parameter_origin='PAD'
        self.parameter_kind='CHNL'
        self.parameter_choice=0
        self.output_page=0
        self.view_origin='PAD'
        self.view_entry='PAD'
        self.view_returns={}
        self.view_selector=False;self.view_index=-1;self.view_tool=None
        self.view_target='PAT'
        self.view_field=0
        self.view_first=0
        self.view_count=16
        self.view_song_first=0
        self.view_song_count=8

    def remember_control_view(self):
        if self.page in CONTROL_PAGES:
            self.control_last=self.page
            self.control_views[self.control_level]={'page':self.page,**{k:getattr(self,k) for k in CONTROL_FIELDS}}

    def control_home(self):
        return getattr(self,'control_last','PAD')

    def control_button(self,name,pressed):
        if self.page in CONTROL_PAGES:self.remember_control_view()
        if name=='NAV' and self.page in CONTROL_PAGES+('PARAM NAV',):
            if pressed and self.page!='PARAM NAV':
                origin=self.page;self.parameter_origin=origin
                self.parameter_kind='PLUG-IN' if origin in ('SAMPLER','PLUGIN') else 'CHNL'
                if self.parameter_kind=='CHNL':
                    choice={'PAD':'OUTPUT','CHANNEL':'OUTPUT','INPUT':'INPUT','GROOVE':'GROOVE','MACRO':'MACRO'}[origin]
                    self.parameter_choice=self.parameter_choices().index(choice)
                else:self.parameter_choice=0 if origin=='SAMPLER' else self.plugin_slot+int(self.sampler_slot_present())
                self.page='PARAM NAV'
            elif not pressed and self.page=='PARAM NAV':
                self.parameter_choice=min(self.parameter_choice,len(self.parameter_choices())-1)
                self.page=self.parameter_destination();self.remember_control_view()
            return True
        if self.page=='PARAM NAV' and pressed and name in ('NAV LEFT','NAV RIGHT'):
            delta=-1 if name=='NAV LEFT' else 1;choice=self.parameter_choices()[self.parameter_choice]
            if self.parameter_kind=='CHNL' and choice=='OUTPUT':
                self.channel_page=max(0,min(3 if self.control_level==2 else 2,self.channel_page+delta));self.channel_field=0
            elif self.parameter_kind=='PLUG-IN' and choice=='SAMPLER':
                self.sampler_page=max(0,min(5,self.sampler_page+delta));self.sampler_field=0
            elif self.parameter_kind=='PLUG-IN':
                self.select_plugin_slot(self.parameter_choice-int(self.sampler_slot_present()))
                self.plugin_param=max(0,min(max(0,len(self.plugin_controls())-1),self.plugin_param+8*delta))
            return True
        if self.page in CONTROL_PAGES and pressed and name in ('F1','F2','F3') and not self.shift:
            self.remember_control_view();self.control_level=int(name[1])-1
            state=self.control_views.get(self.control_level,{'page':'PAD'})
            for key in CONTROL_FIELDS:
                if key in state:setattr(self,key,state[key])
            self.page=state['page']
            if self.page=='SAMPLER' and not self.sampler_slot_present():self.page='PLUGIN'
            if self.page in ('PAD','CHANNEL') and self.control_level!=2:self.channel_page=min(2,self.channel_page)
            self.remember_control_view();return True
        return False

    def sampler_slot_present(self):
        chain=self.plugin_target().get('plugins',[])
        return self.control_level==2 and bool(self.track().get('sample') or self.track().get('zones')) and not (chain and chain[0].get('kind')=='INSTRUMENT')

    def parameter_choices(self):
        if self.parameter_kind=='PLUG-IN':return tuple(['AUDIO' if is_audio_sound(self.track()) else 'SAMPLER'] if self.sampler_slot_present() else [])+tuple(f'{i+1+int(self.sampler_slot_present())}. '+((self.plugin_metadata(p['uri']) or {}).get('name') or p['uri'].rsplit('/',1)[-1]) for i,p in enumerate(self.plugin_target().get('plugins',[])))+('ADD PLUGIN',)
        return ('OUTPUT','GROOVE','MACRO') if self.control_level==0 else ('INPUT','OUTPUT','GROOVE','MACRO')

    def select_plugin_slot(self,slot):
        previous=self.plugin_selected()
        self.plugin_slot=max(0,min(len(self.plugin_target().get('plugins',[])),slot))
        origin=self.parameter_origin if self.page=='PARAM NAV' else self.page
        if self.plugin_selected() is not previous or origin!='PLUGIN':self.plugin_param=0
        self.plugin_param=max(0,min(max(0,len(self.plugin_controls())-1),self.plugin_param))

    def parameter_destination(self):
        self.parameter_choice=min(self.parameter_choice,len(self.parameter_choices())-1)
        choice=self.parameter_choices()[self.parameter_choice]
        if self.parameter_kind=='PLUG-IN':
            offset=1 if self.sampler_slot_present() else 0
            if self.sampler_slot_present() and self.parameter_choice==0:
                if is_audio_sound(self.track()):
                    self.audio_tool_field=0;self.audio_tool_origin=self.control_home();return 'AUDIO LOOP'
                return 'SAMPLER'
            self.select_plugin_slot(self.parameter_choice-offset)
            return 'PLUGIN' if self.plugin_slot<len(self.plugin_target().get('plugins',[])) else 'PLUGIN BROWSE'
        if choice=='GROOVE':return 'GROOVE'
        if choice=='MACRO':return 'MACRO'
        if choice=='INPUT':return 'INPUT'
        if choice=='OUTPUT':return 'CHANNEL'
        return 'MIDI TRACK' if self.control_level==2 and self.output_page else 'PAD'

    def pin_view(self):
        if 'VIEW' in self.pinned_modes:self.pinned_modes.remove('VIEW')
        else:self.pinned_modes.add('VIEW')
        self.settings['pinned_modes']=sorted(self.pinned_modes)
        save_json(self.settings_path,self.settings)
        self.message='PIN ON' if 'VIEW' in self.pinned_modes else 'PIN OFF'

    def select_view(self, destination):
        """Toggle a Navigate workspace without losing the view it replaced."""
        current='PATTERN GRID' if self.view_origin=='GRID EDIT' else self.view_origin
        if current==destination:
            previous=self.view_returns.get(destination,self.control_home())
            self.view_origin=self.control_home() if previous in (destination,'VIEW NAV') else previous
        else:
            entry='PATTERN GRID' if self.view_entry=='GRID EDIT' else self.view_entry
            if entry!=destination:self.view_returns[destination]=self.view_entry
            self.view_origin=destination
        self.view_target='SCENE' if self.view_origin in ('SCENE','SONG') else 'PAT'

    def activate_view(self):
        """Commit a preview, initializing Live FX only when it is opened."""
        if self.view_origin=='LIVE FX':
            if self.view_entry=='LIVE FX':self.page='LIVE FX'
            else:self.open_live_fx(self.view_returns.get('LIVE FX',self.control_home()))
        else:
            if self.view_entry=='LIVE FX':self.live_fx_off()
            if self.view_origin=='PATTERN GRID' and self.keyboard_enabled and self.view_entry not in ('PATTERN GRID','GRID EDIT'):
                self.open_pattern_grid()
            else:self.page=self.view_origin

    def navigation_button(self,name,pressed):
        from app.mikro_navigate import button
        if button(self,name,pressed):return True
        if pressed and 'NAV' in self.held_buttons and self.page in ('SAMPLER','PLUGIN','CHANNEL') and name in ('F2','F3'):
            self.parameter_kind='CHNL' if name=='F2' else 'PLUG-IN';self.parameter_choice=(1 if self.control_level else 0) if name=='F2' else 0;self.page='PARAM NAV';return True
        if name=='VIEW' and self.page not in ('SAMPLE EDIT','CHOP','ZONE') and not self.shift:
            if pressed:
                self.view_selector=False;self.view_tool=None
                if self.page=='VIEW NAV':self.activate_view()
                else:
                    self.view_entry=self.view_origin=self.page;self.page='VIEW NAV'
                    if self.view_origin in ('SONG','SCENE'):self.view_target='SCENE'
            elif self.page=='VIEW NAV' and 'VIEW' not in self.pinned_modes:self.activate_view()
            return True
        if self.page=='VIEW NAV':
            if pressed and name=='MAIN' and 'VIEW' in self.held_buttons:
                self.pin_view();return True
            if pressed and name in ('F1','F2'):
                self.view_target='SCENE' if name=='F1' else 'PAT';return True
            if name=='F3':return True
            if pressed and name in ('NAV LEFT','NAV RIGHT'):
                self.view_field=int(name=='NAV RIGHT');return True
            if pressed and name in ('MAIN','SAMPLING','BROWSE'):
                self.page=self.view_origin
            else:return name not in ('PLAY','REC','RESTART','SHIFT')
        if name=='NAV' and self.page in ('SAMPLER','PLUGIN','CHANNEL'):return True
        if name=='NAV' and self.page in ('PAD','MIDI TRACK','PARAM NAV','INPUT','MACRO'):
            if pressed and self.page!='PARAM NAV':
                self.parameter_origin=self.page
                self.parameter_kind='PLUG-IN' if self.page=='SAMPLER' else 'CHNL'
                self.parameter_choice=1 if self.control_level else 0;self.page='PARAM NAV'
            elif not pressed and self.page=='PARAM NAV':self.page=self.parameter_destination()
            return True
        if self.page=='PARAM NAV':
            if not pressed:return False
            if name=='F2':self.parameter_kind='CHNL';self.parameter_choice=self.parameter_choices().index('OUTPUT')
            elif name=='F3':self.parameter_kind='PLUG-IN';self.parameter_choice=0
            elif name in ('NAV LEFT','NAV RIGHT') and self.parameter_kind=='CHNL' and self.control_level==2:
                self.channel_page=max(0,min(3,self.channel_page+(-1 if name=='NAV LEFT' else 1)))
            elif name=='MAIN':self.open_settings()
            return True
        # NAV is a context modifier, never a standalone project menu.
        if name=='NAV' and self.page not in ('SAMPLING','SAMPLE EDIT','CHOP','ZONE','SAMPLING NAV'):return True
        return False

    def navigation_rotate(self,delta):
        if self.page=='VIEW NAV' and self.view_selector and self.view_tool is None and getattr(self,'controller_source','mikro')=='mikro':
            from app.mikro_navigate import select
            select(self,delta);return True
        if self.page=='PARAM NAV':
            self.parameter_choice=max(0,min(len(self.parameter_choices())-1,self.parameter_choice+delta));return True
        if self.page=='VIEW NAV':
            if self.view_field==0:
                for _ in range(min(16,abs(delta))):self.navigation_pad(5 if delta>0 else 1)
            else:
                for _ in range(min(128,abs(delta))):self.navigation_pad(2 if delta>0 else 0)
            return True
        return False

    def navigation_pad(self,slot):
        if self.page=='PARAM NAV':
            if self.shift and self.parameter_kind=='PLUG-IN':
                index=slot-12-int(self.sampler_slot_present());items=self.plugin_target().get('plugins',[])
                if 0<=index<len(items):
                    self.remember();items[index]['bypass']=not items[index].get('bypass',False);self.plugin_update()
                return True
            if self.parameter_kind=='PLUG-IN':
                offset=1 if self.sampler_slot_present() else 0
                self.parameter_choice=max(0,min(len(self.parameter_choices())-1,slot-12))
            elif slot in (12,13,14,15):
                value=slot-12-(1 if self.control_level==0 else 0)
                if value>=0:self.parameter_choice=value
            return True
        if self.page!='VIEW NAV':return False
        if self.view_selector and self.view_tool is None:return True
        if self.view_target=='SCENE':
            total=max(1,len(self.project['song']));count=self.view_song_count;first=self.view_song_first
        else:
            total=self.grid_length();count=self.view_count;first=self.view_first
        if slot in (1,5):count=max(4,min(64,count//2 if slot==5 else count*2))
        elif slot in (0,2):
            first+=(-1 if slot==0 else 1)*max(1,count//4)
            if self.view_target=='PAT':self.grid_follow=False
        elif self.view_target=='PAT' and self.grid_notes and slot in (3,7):
            self.grid_note=max(0,min(127,self.grid_note+(-1 if slot==3 else 1)))
        first=max(0,min(max(0,total-count),first))
        if self.view_target=='SCENE':self.view_song_count,self.view_song_first=count,first
        else:self.view_count,self.view_first=count,first
        return True
