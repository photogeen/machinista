"""Portable Sound/Group presets; asset work stays off the controller thread."""
import copy
import json
import re
import shutil
import uuid
from pathlib import Path
from app.assets import collect_project,resolve_assets
from app.layout import GROUP_BASE,bus_targets

KINDS=('SOUND','GROUP')
PATTERN_KEYS=('patterns','events','extra_events','automation','pattern_lengths','pattern_created')


def remap_targets(targets,mapping):
    for target in targets:
        target['macros']={k:dict(v,bus=mapping[v['bus']]) for k,v in target.get('macros',{}).items() if v['bus'] in mapping}
        routing=target.get('routing',{})
        references=[(routing,key) for key in ('dest','aux1_dest','aux2_dest','midi_target')]+[(plugin,'sidechain') for plugin in target.get('plugins',[]) if 'sidechain' in plugin]
        for reference,key in references:
            value=reference.get(key,'')
            if value.startswith('SOUND '):
                bus=int(value.split()[1]);reference[key]=f'SOUND {mapping[bus]}' if bus in mapping else ('NONE' if key in ('sidechain','midi_target') else 'MASTER')
            elif value.startswith('GROUP '):
                bus=GROUP_BASE+int(value.split()[1]);reference[key]=f'GROUP {mapping[bus]-GROUP_BASE}' if bus in mapping else ('NONE' if key in ('sidechain','midi_target') else 'MASTER')


def preset_snapshot(app,kind):
    if kind not in KINDS:raise ValueError('INVALID PRESET TYPE')
    from app.model import new_project,validate_project
    project=validate_project(new_project());project['bus_layout']=2
    saved=app.project_for_save();group=app.group;pad=app.pad
    if kind=='SOUND':
        from app.virtualjv_multi import internal_destination
        if internal_destination(saved['groups'][group]['pads'][pad]):raise ValueError('SAVE SHARED RACK AS GROUP OR PROJECT')
        target=copy.deepcopy(saved['groups'][group]['pads'][pad]);project['groups'][0]['pads'][0]=target
        remap_targets([target],{group*16+pad:0})
        chains={0:(group*16+pad,target.get('plugins',[]))}
    else:
        target=copy.deepcopy(saved['groups'][group]);blank=project['groups'][0]
        for key in PATTERN_KEYS:
            if key in blank:target[key]=copy.deepcopy(blank[key])
            else:target.pop(key,None)
        project['groups'][0]=target
        remap_targets([target]+target['pads'],{**{group*16+i:i for i in range(16)},GROUP_BASE+group:GROUP_BASE})
        chains={bus:(GROUP_BASE+group if bus==GROUP_BASE else group*16+bus,t.get('plugins',[])) for bus,t in bus_targets(project).items() if (bus==GROUP_BASE or bus<16)}
    return project,chains


def prepare_preset_state(audio,request,root):
    directory=Path(root)/'cache'/'preset-state'/uuid.uuid4().hex
    for local,(bus,chain) in request.pop('chains').items():
        for index,plugin in enumerate(chain):
            folder=directory/str(local)/str(index);plugin['state']=str(folder/'state.ttl')
            audio.command(f'plugin_save {bus} {index} '+json.dumps(str(folder)))
    audio.command('state_barrier')


def write_preset(request,root):
    kind=request['kind'];name=request['name']
    if kind not in KINDS or not re.fullmatch(r'[A-Za-z0-9 _-]{1,32}',name):raise ValueError('INVALID PRESET NAME')
    folder=Path(root)/'presets'/('Sounds' if kind=='SOUND' else 'Groups')
    folder.mkdir(parents=True,exist_ok=True)
    if any(p.name.casefold()==name.casefold() for p in folder.iterdir() if not p.name.startswith('.')):raise ValueError('PRESET NAME EXISTS')
    temporary=folder/('.'+uuid.uuid4().hex)
    try:
        project=request['project']
        for target in bus_targets(project).values():
            for plugin in target.get('plugins',[]):
                if not plugin.get('state') or not Path(plugin['state']).is_file():raise ValueError('PLUGIN STATE FAILED')
        collect_project(project,temporary)
        (temporary/'Preset.json').write_text(json.dumps({'format':'Machinista-preset','version':1,'kind':kind,'name':name,'project':json.loads((temporary/'Project.json').read_text())},indent=2))
        (temporary/'Project.json').unlink();temporary.rename(folder/name)
        return name
    finally:
        if temporary.exists():shutil.rmtree(temporary)


def read_preset(path,kind,root):
    from app.model import validate_project
    path=Path(path)
    if path.suffix.lower()=='.sound':
        from app.sound_library import SoundLibrary
        library=SoundLibrary(root)
        if path.is_symlink() or not path.resolve().is_relative_to(library.folder.resolve()) or path.stat().st_size>1024*1024:raise ValueError('INVALID SOUND LINK')
        link=json.loads(path.read_text())
        if link.get('format')=='Machinista-bank-sound' and kind=='SOUND':
            from app.bank_sounds import project
            return project(root,link)['groups'][0]['pads'][0]
        if link.get('format')!='Machinista-sound-link' or kind!='SOUND':raise ValueError('INVALID SOUND')
        path=library.bundle(link.get('id'))/'Preset.json'
    base=path.parent.resolve();data=json.loads(path.read_text())
    if data.get('format') not in ('Machinista-preset','Machinist-preset','maschineOS-preset') or data.get('version')!=1 or data.get('kind')!=kind:raise ValueError('INVALID PRESET')
    project=resolve_assets(data['project'],base);validate_project(project)
    # All bundled assets must remain inside the preset, including state resources.
    from app.assets import sample_references
    for obj,key in sample_references(project):
        asset=Path(obj[key])
        if not asset.is_relative_to(base) or not asset.is_file():raise ValueError('MISSING PRESET SAMPLE')
    targets=[project['groups'][0]]+project['groups'][0]['pads'] if kind=='GROUP' else [project['groups'][0]['pads'][0]]
    directory=Path(root)/'projects'/'plugin-states'/uuid.uuid4().hex
    try:
        for tindex,target in enumerate(targets):
            for index,plugin in enumerate(target.get('plugins',[])):
                state=Path(plugin.get('state',''))
                if not state.is_relative_to(base) or not state.is_file():raise ValueError('MISSING PLUGIN STATE')
                if any(p.is_symlink() for p in state.parent.rglob('*')):raise ValueError('INVALID STATE RESOURCE')
                destination=directory/f'{tindex}-{index}';shutil.copytree(state.parent,destination)
                plugin['state']=str(destination/state.name)
        return targets[0]
    except Exception:
        if directory.exists():shutil.rmtree(directory)
        raise


class Presets:
    def init_presets(self):
        self.preset_kind='SOUND';self.preset_index=0;self.preset_origin='PROJECT MANAGE';self.preset_context=None
    def preset_files(self):
        folder=self.root/'presets'/('Sounds' if self.preset_kind=='SOUND' else 'Groups')
        return sorted((p/'Preset.json' for p in folder.iterdir() if p.is_dir() and not p.name.startswith('.') and (p/'Preset.json').is_file()),key=lambda p:p.parent.name.casefold()) if folder.exists() else []
    def open_preset_save(self,kind):
        from app.virtualjv_multi import internal_destination
        if kind=='SOUND' and internal_destination(self.track()):self.message='SAVE RACK AS GROUP OR PROJECT';return
        if self.playing or self.recording or self.capture_started is not None or self.capture_armed:self.message='STOP RECORD/PLAY FIRST';return
        self.preset_kind=kind;self.preset_context=(self.group,self.pad,self.project_generation,self.revision)
        self.open_name_dialog('SAVE '+kind);self.name_value=''
    def finish_preset_name(self):
        if self.playing or self.recording or self.capture_started is not None or self.capture_armed:self.message='STOP RECORD/PLAY FIRST';return
        name=self.name_value.strip()
        if not re.fullmatch(r'[A-Za-z0-9 _-]{1,32}',name):self.message='ENTER A NAME';return
        if self.preset_context!=(self.group,self.pad,self.project_generation,self.revision):self.message='SOURCE CHANGED';return
        if any(p.parent.name.casefold()==name.casefold() for p in self.preset_files()):self.message='PRESET NAME EXISTS';return
        project,chains=preset_snapshot(self,self.preset_kind)
        self.actions.append(('preset_save',dict(kind=self.preset_kind,name=name,project=project,chains=chains)))
        self.page=self.name_origin;self.name_action=None;self.message='SAVING PRESET'
    def open_preset_load(self,kind):
        self.preset_kind=kind;self.preset_index=0;self.preset_origin=self.page;self.page='PRESET LOAD'
    def request_preset_load(self,path,kind,group,pad):
        if self.playing or self.recording or self.capture_started is not None or self.capture_armed:self.message='STOP RECORD/PLAY FIRST';return
        self.actions.append(('preset_load',dict(path=str(path),kind=kind,group=group,pad=pad,generation=self.project_generation,revision=self.revision)))
        self.message='LOADING PRESET'
    def finish_preset_load(self,request,target):
        if self.playing or self.recording or self.capture_started is not None or self.capture_armed:self.message='TRANSPORT STARTED: CANCELED';return
        if request['generation']!=self.project_generation or request['revision']!=self.revision:self.message='PROJECT CHANGED: CANCELED';return
        group,pad=request['group'],request['pad'];kind=request['kind']
        targets=[target]+target['pads'] if kind=='GROUP' else [target]
        if any(not self.plugin_metadata(p['uri']) or not self.plugin_metadata(p['uri']).get('supported') for t in targets for p in t.get('plugins',[])):
            self.message='PLUGIN NOT INSTALLED';return
        mapping={**{i:group*16+i for i in range(16)},GROUP_BASE:GROUP_BASE+group} if kind=='GROUP' else {0:group*16+pad}
        remap_targets(targets,mapping)
        # Validate a prospective replacement before changing the working project.
        from app.model import validate_project
        candidate=self.project_for_save()
        if kind=='GROUP':
            for key in PATTERN_KEYS:
                if key in candidate['groups'][group]:target[key]=copy.deepcopy(candidate['groups'][group][key])
            candidate['groups'][group]=target
        else:candidate['groups'][group]['pads'][pad]=target
        # Old automation/macros targeting replaced chains cannot carry into new ones.
        for g in candidate['groups']:
            if 'automation' not in g:continue
            g['automation']={k:v for k,v in g.get('automation',{}).items() if int(k.split(':',4)[1]) not in mapping.values()}
        for bus,t in bus_targets(candidate).items():
            if bus not in mapping.values() and 'macros' in t:t['macros']={k:v for k,v in t.get('macros',{}).items() if v['bus'] not in mapping.values()}
        validate_project(candidate)
        self.automation_restore()
        for bus,chain in request.get('previous',{}).items():
            bus_targets(self.project)[bus]['plugins']=copy.deepcopy(chain)
        self.remember();self.project=candidate;self.automation_cache=None
        self.group=group;self.group_bank=group//8;self.pad=pad;self.pattern=self.active_patterns[group];self.zone_index=0;self.plugin_slot=self.plugin_param=0
        self.keyboard_root=self.performance()['root'];self.actions.extend([('panic',None),('reload',None)])
        self.page=self.control_home()
        if kind=='SOUND' and target.get('plugins') and target['plugins'][0]['kind']=='INSTRUMENT':
            self.control_level=2;self.parameter_kind='PLUG-IN';self.parameter_choice=0;self.page='PLUGIN'
            self.remember_control_view()
        self.message=kind+' PRESET LOADED'
    def presets_button(self,name,pressed):
        if not pressed or self.page!='PRESET LOAD':return False
        if name in ('F1','F3'):self.page=self.preset_origin
        elif name in ('F2','ENTER','ENCODER PUSH'):
            files=self.preset_files()
            if not files:self.message='NO PRESETS';return True
            path=files[min(self.preset_index,len(files)-1)];kind=self.preset_kind;group,pad=self.group,self.pad
            self.confirm('REPLACE '+kind+'?',lambda:self.request_preset_load(path,kind,group,pad),origin='PRESET LOAD')
        else:return False
        return True
    def presets_rotate(self,delta):
        if self.page!='PRESET LOAD':return False
        self.preset_index=max(0,min(max(0,len(self.preset_files())-1),self.preset_index+delta));return True
