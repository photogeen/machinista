"""Master performance shortcuts; SHIFT+MAIN opens standalone settings."""
class MainControls:
    def main_controls_active(self):
        return getattr(self,'main_controls',False) and self.page in ('CHANNEL','GROOVE','TEMPO')

    def open_main_controls(self):
        if self.main_controls_active():
            self.main_controls=False
            self.page=getattr(self,'main_origin',self.control_home())
            self.control_level=getattr(self,'main_level',2)
            for key,value in getattr(self,'main_fields',{}).items():setattr(self,key,value)
            self.remember_control_view()
            return
        from app.navigation import CONTROL_FIELDS
        self.main_origin=self.page;self.main_level=self.control_level
        self.main_fields={key:getattr(self,key) for key in CONTROL_FIELDS}
        self.main_controls=True
        self.select_main_control(getattr(self,'main_tab',2))

    def select_main_control(self, index):
        self.main_tab=index;self.control_level=0
        self.page=('CHANNEL','GROOVE','TEMPO')[index]
        if index==0:self.channel_page=0;self.channel_field=0
        if index==1:self.groove_field=0

    def main_controls_button(self,name,pressed):
        if not self.main_controls_active():return False
        if name=='ENCODER PUSH':
            self.encoder_held=pressed;return True
        if pressed and name in ('F1','F2','F3'):
            self.select_main_control(int(name[1])-1);return True
        if pressed and name=='MAIN':
            self.open_main_controls();return True
        if pressed and name in ('NAV','GROUP','SAMPLING','BROWSE','SCENE','PATTERN','PAD MODE','VIEW','SELECT','MUTE','SOLO','NOTE REPEAT','GRID'):
            self.main_controls=False
        return False
