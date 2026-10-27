"""Named projects with stable file IDs and a controller-operated name editor."""
import random
import re
from app.storage import load_json,save_json

NAME_CHARS=' ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_'
MANAGE=('NEW PROJECT','RENAME','SAVE AS','DELETE','COLLECT SAMPLES','SAVE SOUND','LOAD SOUND','SAVE GROUP','LOAD GROUP','RELINK SAMPLES','EXPORT AUDIO','EXPORT MIDI','SAMPLE RAM')
from app.project_names import FIRST,SECOND


class ProjectManager:
    def init_project_manager(self):
        self.init_relink()
        self.manage_index=0
        self.name_value=''
        self.name_cursor=0
        self.name_action=None
        self.name_origin='PROJECT'
        self.name_target=None
        self.project_label_cache={}
        self.name_suggestion_bag=[]

    def project_files(self):
        return sorted(p for p in (self.root/'projects').glob('PROJECT-*.json')
                      if re.fullmatch(r'PROJECT-[0-9]{4}\.json',p.name) and not p.is_symlink())

    def project_label(self,path):
        stamp=path.stat().st_mtime_ns
        cached=self.project_label_cache.get(path)
        if cached is None or cached[0]!=stamp:
            try:label=load_json(path,{})['name']
            except (ValueError,KeyError):label=path.stem
            cached=(stamp,label)
            self.project_label_cache[path]=cached
        return cached[1]

    def active_project_file(self):
        file_id=self.project.get('file_id')
        if file_id is None:
            candidate=self.project.get('name','')
            if re.fullmatch(r'PROJECT-[0-9]{4}',candidate) and (self.root/'projects'/(candidate+'.json')).is_file():
                file_id=candidate
        if file_id and re.fullmatch(r'PROJECT-[0-9]{4}',file_id):
            return self.root/'projects'/(file_id+'.json')
        return None

    def next_project_id(self):
        used={p.stem for p in self.project_files()}
        for i in range(1,10000):
            name=f'PROJECT-{i:04}'
            if name not in used:return name
        raise ValueError('project slots full')

    def name_available(self,name,target=None):
        return all(p==target or self.project_label(p).casefold()!=name.casefold() for p in self.project_files())

    def random_project_name(self):
        recent=self.settings.get('recent_project_names',[])
        if not isinstance(recent,list):recent=[]
        recent=[name for name in recent if isinstance(name,str)][-512:]
        occupied={self.project_label(p).casefold() for p in self.project_files()}
        occupied.add(self.project['name'].casefold())
        if not self.name_suggestion_bag:
            self.name_suggestion_bag=[a+' '+b for a in FIRST for b in SECOND
                                      if a+' '+b not in recent and (a+' '+b).casefold() not in occupied]
            random.shuffle(self.name_suggestion_bag)
        while self.name_suggestion_bag:
            name=self.name_suggestion_bag.pop()
            if name not in recent and name.casefold() not in occupied:break
        else:
            name='GROOVE '+str(random.randrange(100000,1000000))
            while name in recent or name.casefold() in occupied:
                name='GROOVE '+str(random.randrange(100000,1000000))
        self.settings['recent_project_names']=(recent+[name])[-512:]
        save_json(self.settings_path,self.settings)
        return name

    def open_name_dialog(self,action,target=None):
        self.name_origin=self.page
        self.name_action=action
        self.name_target=target
        if action=='RENAME':
            self.name_value=self.project['name'] if target is None else self.project_label(target)
        else:
            self.name_value='' if action=='NEW' or action.startswith('AUTO ') else self.random_project_name()
        self.name_cursor=0
        self.page='PROJECT NAME'

    def save_as(self):
        self.open_name_dialog('SAVE AS')

    def start_new(self):
        self.open_name_dialog('NEW')

    def finish_project_name(self):
        if self.name_action in ('AUTO NAME','AUTO FOLDER'):
            value=self.name_value.strip()
            if not value and self.name_action=='AUTO NAME':self.message='ENTER A NAME';return
            self.auto_config['name' if self.name_action=='AUTO NAME' else 'folder']=value
            self.page='AUTOSAMPLER';return
        if self.name_action in ('SAVE SOUND','SAVE GROUP'):self.finish_preset_name();return
        name=self.name_value.strip()
        if not re.fullmatch(r'[A-Za-z0-9 _-]{1,32}',name):
            self.message='ENTER A NAME';return
        if not self.name_available(name,self.name_target if self.name_action=='RENAME' else None):
            self.message='NAME ALREADY EXISTS';return
        action=self.name_action
        if action=='NEW':
            from app.model import new_project
            # Archive the outgoing working copy before creating the new slot.
            if self.active_project_file() is None:
                self.project['file_id']=self.next_project_id()
            self.save()
            self.project_generation+=1
            self.automation_restore()
            self.project=new_project();self.project.update(name=name,file_id=self.next_project_id())
            self.playing=self.recording=False
            self.group=self.pad=self.pattern=self.scene=0
            self.active_patterns=[0]*8;self.step=-1;self.undo.clear()
            self.init_workspaces();self.init_surface();self.init_live_fx();self.live_fx_send(0,0,pressed=False);self.init_sampler();self.init_slicing();self.init_navigation()
            self.actions.extend([('panic',None),('reload',None)])
            self.save();self.page=self.control_home()
        elif action=='SAVE AS':
            # Keep the old named slot intact; a new stable ID holds the copy.
            self.project.update(name=name,file_id=self.next_project_id())
            self.save();self.page='PROJECT'
        elif action=='RENAME':
            active=self.active_project_file()
            if self.name_target is None or self.name_target==active:
                self.project['name']=name
                if active is None:self.project['file_id']=self.next_project_id()
                self.save()
            else:
                project=load_json(self.name_target,{})
                project['name']=name;save_json(self.name_target,project)
            self.page=self.name_origin
            self.message='PROJECT RENAMED'
        self.name_action=None

    def delete_project(self,path):
        active=path==self.active_project_file()
        path.unlink()
        self.project_label_cache.pop(path,None)
        if active:
            self.project.pop('file_id',None)
            # Keep the unsaved working copy; saving must not recreate the deleted slot.
            self.project['name']='UNTITLED'
            save_json(self.project_path,self.project)
            self.dirty=True
        self.project_choice=max(0,min(self.project_choice,len(self.project_files())-1))
        self.page='PROJECT LOAD'
        self.message='PROJECT DELETED'

    def confirm_project_delete(self,path):
        if path is None or not path.exists():
            self.message='NO SAVED PROJECT';return
        self.confirm('DELETE '+self.project_label(path)+'?',lambda:self.delete_project(path))

    def project_manager_button(self,name,pressed):
        if not pressed or name=='SHIFT':return False
        if self.page=='PROJECT' and name=='F3':
            self.page='PROJECT MANAGE';self.manage_index=0;return True
        if self.page=='SAMPLE RAM':
            if name in ('F1','MAIN','ENTER'):self.page='PROJECT MANAGE'
            elif name=='F2':self.actions.append(('sample_memory',None))
            elif name=='F3':
                if self.playing or self.recording or self.capture_started is not None or self.capture_armed or self.export_busy:self.message='STOP RECORD/PLAY FIRST'
                else:self.confirm('FREE UNUSED SAMPLE RAM?',self.request_sample_purge)
            else:return False
            return True
        if self.page=='PROJECT LOAD':
            files=self.project_files()
            target=files[min(self.project_choice,len(files)-1)] if files else None
            if name=='F3' and not self.shift:self.start_new();return True
            if self.shift and name=='F1' and target:self.open_name_dialog('RENAME',target);return True
            if self.shift and name in ('F3','ERASE'):
                self.confirm_project_delete(target);return True
        if self.page=='PROJECT MANAGE':
            if name in ('F1','F3'):self.page='PROJECT';return True
            if name in ('F2','ENTER','ENCODER PUSH'):
                choice=MANAGE[self.manage_index]
                if choice=='NEW PROJECT':self.start_new()
                elif choice=='RENAME':self.open_name_dialog('RENAME',self.active_project_file())
                elif choice=='SAVE AS':self.save_as()
                elif choice in ('SAVE SOUND','SAVE GROUP'):self.open_preset_save(choice.split()[1])
                elif choice in ('LOAD SOUND','LOAD GROUP'):self.open_preset_load(choice.split()[1])
                elif choice=='EXPORT AUDIO':self.open_export()
                elif choice=='EXPORT MIDI':self.open_export('MIDI')
                elif choice=='SAMPLE RAM':self.page='SAMPLE RAM';self.actions.append(('sample_memory',None))
                elif choice=='RELINK SAMPLES':self.request_missing_check(True)
                elif choice=='COLLECT SAMPLES':
                    import copy
                    self.save()
                    self.actions.append(('collect_project',(self.revision,copy.deepcopy(self.project))));self.page='PROJECT';self.message='COLLECTING SAMPLES'
                else:self.confirm_project_delete(self.active_project_file())
                return True
            if name in ('NAV LEFT','NAV RIGHT'):
                self.manage_index=max(0,min(len(MANAGE)-1,self.manage_index+(-1 if name=='NAV LEFT' else 1)))
            return True
        if self.page=='PROJECT NAME':
            if name=='F1':
                if self.shift:self.name_value='';self.name_cursor=0
                else:self.page=self.name_origin;self.name_action=None
            elif name=='F2':self.name_value=self.random_project_name();self.name_cursor=0
            elif name in ('F3','ENTER','ENCODER PUSH'):self.finish_project_name()
            elif name in ('NAV LEFT','NAV RIGHT'):
                self.name_cursor=max(0,min(31,self.name_cursor+(-1 if name=='NAV LEFT' else 1)))
            elif name=='ERASE':
                value=self.name_value.ljust(32);self.name_value=(value[:self.name_cursor]+' '+value[self.name_cursor+1:]).rstrip()
            return True
        return False

    def project_manager_rotate(self,delta):
        if self.page=='PROJECT MANAGE':self.manage_index=max(0,min(len(MANAGE)-1,self.manage_index+delta));return True
        if self.page=='PROJECT NAME':
            value=self.name_value.upper().ljust(32)
            old=value[self.name_cursor]
            index=NAME_CHARS.index(old) if old in NAME_CHARS else 0
            self.name_value=(value[:self.name_cursor]+NAME_CHARS[(index+delta)%len(NAME_CHARS)]+value[self.name_cursor+1:]).rstrip()
            return True
        return False

    def project_manager_softkeys(self):
        if self.page=='PROJECT NAME':return ('CLEAR' if self.shift else 'CANCEL','RANDOM','OK')
        return {'PROJECT':('SAVE','LOAD','MANAGE'),'PROJECT MANAGE':('BACK','OPEN','BACK'),
                'PROJECT NAME':('CANCEL','RANDOM','OK')}.get(self.page)

    def request_sample_purge(self):
        if self.playing or self.recording or self.capture_started is not None or self.capture_armed or self.export_busy:
            self.message='STOP RECORD/PLAY FIRST';return
        self.actions.append(('sample_purge',None));self.message='FREEING UNUSED RAM'
