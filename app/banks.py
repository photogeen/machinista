"""Pattern/scene banks and non-destructive pattern lengths."""
import copy
from app.layout import MAX_GROUPS

MAX_PATTERNS=1024
MAX_SCENES=1024
MAX_STEPS=4096


class Banks:
    def init_banks(self):
        self.scene_options_index=0
        self.pattern_bank=self.scene_bank=0;self.group_bank=self.group//8;self.active_clips=[True]*len(self.project['groups'])
        for group in self.project['groups']:
            group.setdefault('pattern_created',[0]+[i for i,p in enumerate(group['patterns']) if any(any(l) for l in p)])
            group.setdefault('pattern_lengths',{})
        self.project.setdefault('scene_created',[0]+[i for i,s in enumerate(self.project['scenes']) if any(s)])
        self.project.setdefault('scene_lengths',{})
        self.activate_scene(self.scene)

    def group_name(self,index=None):
        index=self.group if index is None else index
        return chr(65+index%8)+(str(index//8+1) if index>=8 else '')
    def ensure_group_bank(self,bank):
        count=(bank+1)*8
        if count>MAX_GROUPS:self.message='GROUP BANK LIMIT';return False
        if count>len(self.project['groups']):
            from app.model import new_project
            self.remember();old=len(self.project['groups'])
            self.project['groups'].extend(copy.deepcopy(new_project()['groups'][0]) for _ in range(count-old))
            for scene in self.project['scenes']:scene.extend([None]*(count-old))
            self.active_patterns.extend([0]*(count-old));self.active_clips.extend([False]*(count-old))
            for group in self.project['groups'][old:]:
                group.update(pattern_created=[],pattern_lengths={},events={},extra_events={})
                for pad,track in enumerate(group['pads']):track.update(source='SAMPLE',note=36+pad,channel=1)
            self.init_performance();self.actions.append(('reload',None))
        self.group_bank=bank;return True

    def pattern_steps(self,group=None,pattern=None):
        group=self.group if group is None else group;pattern=self.pattern if pattern is None else pattern
        data=self.project['groups'][group]
        return data.get('pattern_lengths',{}).get(str(pattern),len(data['patterns'][pattern][0]))

    def set_pattern_length(self,length):
        length=max(1,min(MAX_STEPS,length));group=self.project['groups'][self.group];pattern=group['patterns'][self.pattern]
        self.remember()
        for lane in pattern:
            if len(lane)<length:lane.extend([False]*(length-len(lane)))
        group['pattern_lengths'][str(self.pattern)]=length
        self.bank=min(self.bank,(self.step_cell_count()-1)//16);self.event_step=min(self.event_step,length-1)

    def adjust_pattern_length(self,delta):
        length=self.pattern_steps()
        if self.encoder_held or self.shift:target=length+delta
        elif delta>0:target=(length//16+delta)*16
        elif delta<0:target=((length+15)//16+delta)*16
        else:return
        self.set_pattern_length(target)

    def ensure_pattern_bank(self,bank):
        group=self.project['groups'][self.group];count=(bank+1)*16
        if count>MAX_PATTERNS:self.message='PATTERN BANK LIMIT';return False
        if count>len(group['patterns']):self.remember();group['patterns'].extend([[[False]*16 for _ in range(16)] for _ in range(count-len(group['patterns']))])
        self.pattern_bank=bank;return True

    def ensure_scene_bank(self,bank):
        count=(bank+1)*16
        if count>MAX_SCENES:self.message='SCENE BANK LIMIT';return False
        if count>len(self.project['scenes']):self.remember();self.project['scenes'].extend([[None]*len(self.project['groups']) for _ in range(count-len(self.project['scenes']))])
        self.scene_bank=bank;return True

    def scene_options(self):
        return ('AUTO LENGTH','UNIQUE PATTERNS','DELETE SCENE')

    def scene_options_button(self,name,pressed):
        if self.page!='SCENE OPTIONS' or not pressed:return False
        if name=='F1':self.page='SCENE';return True
        if name in ('F2','ENTER'):
            if self.scene_options_index==0:
                self.remember();self.project['scene_lengths'].pop(str(self.scene),None)
                self.message='SCENE LENGTH AUTO';self.page='SCENE'
            else:
                action=self.unique_scene if self.scene_options_index==1 else self.delete_scene
                self.confirm('UNIQUE PATTERNS?' if self.scene_options_index==1 else 'DELETE SCENE?',action)
            return True
        return False

    def bank_button(self,name,pressed):
        if self.scene_options_button(name,pressed):return True
        if pressed and name=='ENCODER PUSH' and self.page in ('PATTERN','SCENE'):self.encoder_held=True;return True
        if not pressed or name not in ('NAV LEFT','NAV RIGHT') or not self.shift:return False
        delta=-1 if name=='NAV LEFT' else 1
        if self.page=='GROUP':self.ensure_group_bank(max(0,self.group_bank+delta));return True
        if self.page=='PATTERN':self.ensure_pattern_bank(max(0,self.pattern_bank+delta));return True
        if self.page=='SCENE':self.ensure_scene_bank(max(0,self.scene_bank+delta));return True
        return False

    def activate_scene(self,index):
        self.scene=index;clips=self.project['scenes'][index]
        self.active_clips=[p is not None for p in clips];self.active_patterns=[p if p is not None else 0 for p in clips]
        self.pattern=self.active_patterns[self.group];self.pattern_bank=self.pattern//16;self.scene_bank=index//16

    def scene_steps(self,index=None):
        index=self.scene if index is None else index
        automatic=max([self.pattern_steps(g,p) for g,p in enumerate(self.project['scenes'][index]) if p is not None] or [16])
        return self.project['scene_lengths'].get(str(index),automatic)

    def unique_scene(self):
        self.remember();clips=self.project['scenes'][self.scene]
        for g,source in enumerate(clips):
            if source is None:continue
            group=self.project['groups'][g];created=group['pattern_created'];dest=max(created,default=-1)+1
            if dest>=MAX_PATTERNS:continue
            while dest>=len(group['patterns']):group['patterns'].extend([[[False]*16 for _ in range(16)] for _ in range(16)])
            group['patterns'][dest]=copy.deepcopy(group['patterns'][source]);created.append(dest)
            for name in ('events','extra_events'):
                additions={f'{dest}:'+key.split(':',1)[1]:copy.deepcopy(value) for key,value in group[name].items() if key.startswith(f'{source}:')};group[name].update(additions)
            self.copy_automation(g,source,g,dest)
            group['pattern_lengths'][str(dest)]=self.pattern_steps(g,source);clips[g]=dest
        self.activate_scene(self.scene);self.message='SCENE PATTERNS UNIQUE'

    def delete_scene(self):
        self.remember();old=self.scene;self.project['scenes'].pop(old)
        self.project['scene_created']=[i-1 if i>old else i for i in self.project['scene_created'] if i!=old]
        self.project['scene_lengths']={str(int(k)-1 if int(k)>old else int(k)):v for k,v in self.project['scene_lengths'].items() if int(k)!=old}
        for entry in reversed([n for n,scene in enumerate(self.project['song']) if scene==old]):self.song_automation_remap(entry,True)
        self.project['song']=[i-1 if i>old else i for i in self.project['song'] if i!=old]
        while len(self.project['scenes'])<16 or len(self.project['scenes'])%16:self.project['scenes'].append([None]*len(self.project['groups']))
        self.activate_scene(min(old,max(self.project['scene_created'],default=0)));self.message='SCENE DELETED'
