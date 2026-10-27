"""Standalone mixer controls over the existing Sound/Group/Master buses."""
from app.layout import GROUP_BASE, MASTER
from app.routing import route_defaults

GROUP_PADS=(12,13,14,15,8,9,10,11)


class Mixer:
    def init_mixer(self):
        self.mixer_level=2
        self.mixer_field=0
        self.mixer_levels={}
        self.mixer_master=(0,0)
        self.mixer_peaks={}
        self.mixer_reset_serial=0

    def mixer_bus(self):
        return MASTER if self.mixer_level==0 else GROUP_BASE+self.group if self.mixer_level==1 else self.group*16+self.pad

    def mixer_target(self):
        return self.project if self.mixer_level==0 else self.project['groups'][self.group] if self.mixer_level==1 else self.track()

    def mixer_watch(self):
        if self.mixer_level==0:return (MASTER,1)
        if self.mixer_level==1:
            first=self.group//8*8
            return (GROUP_BASE+first,min(8,len(self.project['groups'])-first))
        return (self.group*16+self.pad//8*8,8)

    def mixer_select_group(self,index):
        self.group=max(0,min(len(self.project['groups'])-1,index))
        self.group_bank=self.group//8
        self.pattern=self.active_patterns[self.group]
        self.pattern_bank=self.pattern//16
        self.keyboard_root=self.performance()['root']

    def reset_mixer_peaks(self):
        self.mixer_peaks={}
        self.mixer_reset_serial+=1

    def mixer_button(self,name,pressed):
        if pressed and (name=='RESTART' or name=='PLAY' and not self.playing):
            self.reset_mixer_peaks()
        if self.page!='MIXER':return False
        if name=='ENCODER PUSH':
            if pressed:self.mixer_field=0 if self.mixer_field else 1
            return True
        if not pressed:return False
        if name in ('F1','F2','F3'):
            if self.shift:
                if name=='F2':self.mixer_field=0 if self.mixer_field==2 else 2
                if name=='F3':self.reset_mixer_peaks();self.message='PEAK RESET'
            else:self.mixer_level=int(name[1])-1
            return True
        if name in ('NAV LEFT','NAV RIGHT'):
            delta=-8 if name=='NAV LEFT' else 8
            if self.mixer_level==2:self.pad=max(0,min(15,self.pad+delta))
            elif self.mixer_level==1:self.mixer_select_group(self.group+delta)
            return True
        return False

    def mixer_rotate(self,delta):
        if self.page!='MIXER':return False
        target=self.mixer_target()
        if self.mixer_field==2:
            from app.audio_ports import ports
            from app.routing import build_graph
            choices=('PARENT','CUE','NONE')+ports(self.audio.output_channels if self.audio else 0,'OUT')
            current=route_defaults(target)['dest'];index=choices.index(current) if current in choices else 0
            value=choices[max(0,min(len(choices)-1,index+delta))]
            if value!=current:
                self.remember();route=target.setdefault('routing',route_defaults(target));route['dest']=value
                try:build_graph(self.project)
                except ValueError:route['dest']=current;self.message='ROUTING CYCLE'
            return True
        if self.mixer_field==0:
            value=max(0,min(100,target.get('gain',100)+delta))
            if value!=target.get('gain',100):self.remember();target['gain']=value
        else:
            value=max(-100,min(100,route_defaults(target)['pan']+delta))
            if value!=route_defaults(target)['pan']:
                self.remember();target.setdefault('routing',route_defaults(target))['pan']=value
        return True

    def mixer_pad(self,slot):
        if self.page!='MIXER' or self.mixer_level!=1 or self.shift:return False
        if slot in GROUP_PADS:
            index=self.group//8*8+GROUP_PADS.index(slot)
            if index<len(self.project['groups']):self.mixer_select_group(index)
        return True
