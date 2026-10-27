"""Named portable sampler Sounds, immutable assets and folder/tag discovery.

Visible .sound links can move; backing bundles keep stable paths so existing
projects never lose their samples when the catalog is edited or reorganized.
"""
from contextlib import contextmanager
import copy
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import shutil
import stat
import wave
from app.sampler import default_zone,validate_sampler,DEFAULTS

MAX_JSON=1024*1024
MAX_ZONES=128

def worker_priority():
    if __import__('sys').platform.startswith('linux'):
        try:os.nice(10)
        except OSError:pass

RESERVE=256*1024**2


def name(value):
    if isinstance(value,str):value=value.strip()
    if not isinstance(value,str) or not value.strip() or value.startswith('.') or len(value.encode())>160 or any(c in value for c in '/\\\0') or any(ord(c)<32 for c in value):raise ValueError('Invalid Sound or folder name.')
    return value.strip()


def folders(value):
    if not isinstance(value,str) or len(value.split('/'))>8:raise ValueError('Maximum 8 folder levels.')
    return '/'.join(name(part) for part in value.split('/')) if value else ''


def tags(value):
    if not isinstance(value,list) or len(value)>24 or any(not isinstance(v,str) or len(v)>40 or any(ord(c)<32 for c in v) for v in value):raise ValueError('Maximum 24 tags, 40 characters each.')
    return list(dict.fromkeys(v.strip() for v in value if v.strip()))


def mapping(rows,extend=True):
    """Midpoint splits for original pitches, preserving velocity layer bounds."""
    result=copy.deepcopy(rows);roots=sorted(set(int(r['root']) for r in result))
    for r in result:
        i=roots.index(int(r['root']));r['key_lo']=0 if i==0 and extend else roots[0] if i==0 else (roots[i-1]+roots[i])//2+1
        r['key_hi']=127 if i==len(roots)-1 and extend else roots[-1] if i==len(roots)-1 else (roots[i]+roots[i+1])//2
    return result


class SoundLibrary:
    def __init__(self,root):self.root=Path(root).resolve();self.folder=self.root/'presets/Sounds'
    @staticmethod
    def identity(identity):
        if not isinstance(identity,str) or len(identity)!=32 or any(c not in '0123456789abcdef' for c in identity):raise ValueError('Invalid Sound ID.')
        return identity
    @contextmanager
    def directory(self,relative='',create=False):
        relative=folders(relative) if relative else ''
        self.folder.mkdir(parents=True,exist_ok=True)
        fd=os.open(self.folder,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            for part in relative.split('/') if relative else []:
                if create:
                    try:os.mkdir(part,0o755,dir_fd=fd)
                    except FileExistsError:pass
                child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=child
            yield fd
        finally:os.close(fd)
    def bundle(self,identity):
        identity=self.identity(identity);path=self.folder/'.library'/identity
        for p in (self.folder,self.folder/'.library',path):
            if p.is_symlink() or not p.is_dir():raise ValueError('Invalid or missing Sound bundle.')
        return path
    def scan(self):
        rows=[];directories={''};bank_presence={}
        def walk(relative,depth):
            if depth>8:return
            with self.directory(relative) as fd:
                for item in sorted(os.scandir(fd),key=lambda x:x.name.casefold()):
                    if item.name.startswith('.') or item.is_symlink():continue
                    if item.is_dir(follow_symlinks=False):
                        # Existing controller-saved preset folders remain available in Browser.
                        candidate=self.folder/relative/item.name
                        if (candidate/'Preset.json').is_file():continue
                        child='/'.join(filter(None,(relative,item.name)));directories.add(child);walk(child,depth+1)
                    elif item.name.endswith('.sound') and item.is_file(follow_symlinks=False):
                        try:
                            f=os.open(item.name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=fd)
                            with os.fdopen(f,'rb') as stream:value=json.loads(stream.read(MAX_JSON+1))
                            identity=self.identity(value['id'])
                            if value.get('format')=='Machinista-bank-sound':
                                from app.bank_sounds import bank_exists
                                from app.plugin_profiles import profile
                                key=(value['uri'],value['bank'])
                                if key not in bank_presence:bank_presence[key]=bank_exists(self.root,value)
                                if not bank_presence[key]:continue
                                rows.append(dict(id=identity,name=name(value['name']),folder=relative,tags=[value['bank_name']],kind='SYNTH' if value['uri']=='urn:machinista:instrument:synth' else 'LV2',instrument=profile(value['uri'])['title'],bank=value['bank'],bank_name=value['bank_name'],zones=0,readonly=True,link=str((self.folder/relative/item.name).relative_to(self.folder))))
                                continue
                            if value.get('format')!='Machinista-sound-link':continue
                            rows.append(dict(id=identity,name=name(value['name']),folder=relative,tags=tags(value.get('tags',[])),kind=value.get('kind','SAMPLER'),zones=value.get('zones',0),link=str((self.folder/relative/item.name).relative_to(self.folder))))
                        except (OSError,ValueError,KeyError,TypeError,RecursionError):continue
                    if len(rows)>2048:raise ValueError('More than 2048 Sounds.')
        if self.folder.is_dir():walk('',0)
        return {'sounds':rows,'folders':sorted(directories)}
    def row(self,identity):
        self.identity(identity);return next((r for r in self.scan()['sounds'] if r['id']==identity),None)
    def manifest(self,identity):
        row=self.row(identity)
        if row and row.get('readonly'):
            from app.bank_sounds import project
            path=self.folder/row['link']
            if path.is_symlink() or path.stat().st_size>MAX_JSON:raise ValueError('Invalid bank Sound.')
            return dict(format='Machinista-preset',version=1,kind='SOUND',project=project(self.root,json.loads(path.read_text())))
        base=self.bundle(identity);file=base/'Preset.json'
        if file.is_symlink() or file.stat().st_size>MAX_JSON:raise ValueError('Invalid Sound manifest.')
        return json.loads(file.read_text())
    def read(self,identity):
        from app.assets import resolve_assets
        from app.model import validate_project
        row=self.row(identity)
        if row and row.get('readonly'):return copy.deepcopy(self.manifest(identity)['project']['groups'][0]['pads'][0])
        base=self.bundle(identity);data=self.manifest(identity)
        if data.get('format')!='Machinista-preset' or data.get('kind')!='SOUND':raise ValueError('Invalid Sound.')
        project=resolve_assets(copy.deepcopy(data['project']),base);validate_project(project)
        track=project['groups'][0]['pads'][0]
        for zone in track.get('zones',[]):
            p=Path(zone['sample'])
            if not p.is_relative_to(base) or not p.is_file() or any(part.is_symlink() for part in (p,*p.parents) if part.is_relative_to(base)):raise ValueError('Invalid Sound sample.')
        return track
    def draft(self,identity):
        row=self.row(identity)
        if row is None:raise FileNotFoundError('Sound not found.')
        if row.get('readonly'):raise ValueError('Bank patch: load it, then Save current Sound to create an editable copy.')
        data=self.manifest(identity);track=copy.deepcopy(data['project']['groups'][0]['pads'][0])
        for zone in track.get('zones',[]):
            zone['label']=zone.get('name') or Path(zone['sample']).name
            zone['asset']={'sound':identity,'path':zone.pop('sample')}
        return dict(id=identity,name=row['name'],folder=row['folder'],tags=row['tags'],kind=row['kind'],plugins=[dict(name=p.get('name') or p['uri'],kind=p['kind'],uri=p['uri']) for p in track.get('plugins',[])],sampler=track.get('sampler',{}),zones=track.get('zones',[]),version=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest())
    def opened_asset(self,identity,relative):
        base=self.bundle(identity)
        if not isinstance(relative,str) or not relative.startswith('samples/') or len(relative.split('/'))!=2 or relative.split('/')[1].startswith('.'):raise ValueError('Invalid Sound asset.')
        filename=relative.split('/')[1]
        if '/' in filename or '\\' in filename or '\0' in filename:raise ValueError('Invalid Sound asset.')
        fd=os.open(base/'samples',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:child=os.open(filename,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=fd)
        finally:os.close(fd)
        stream=os.fdopen(child,'rb')
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):stream.close();raise ValueError('Invalid Sound sample.')
        return stream
    @contextmanager
    def writing(self):
        self.folder.mkdir(parents=True,exist_ok=True)
        fd=os.open(self.folder/'.write.lock',os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW,0o600)
        try:fcntl.flock(fd,fcntl.LOCK_EX);yield
        finally:os.close(fd)
    def save(self,draft,opener,expected=None):
        with self.writing():return self._save(draft,opener,expected or draft.get('version'))
    def _save(self,draft,opener,expected=None):
        """Copy bounded assets off the live thread, then atomically publish manifest.

        opener(asset) must return a nofollow stream from trusted sample storage.
        Old asset files are retained for projects referencing previous versions.
        """
        from app.model import new_project,validate_project
        title=name(draft.get('name'));category=folders(draft.get('folder',''));labels=tags(draft.get('tags',[]));rows=draft.get('zones',[])
        if draft.get('id') and self.row(draft['id']) and self.row(draft['id'])['kind']=='LV2':return self.metadata(draft)
        if not isinstance(rows,list) or not 1<=len(rows)<=MAX_ZONES:raise ValueError('A Sound needs 1–128 zones.')
        sampler=draft.get('sampler',{})
        if not isinstance(sampler,dict):raise ValueError('Invalid sampler settings.')
        identity=self.identity(draft['id']) if draft.get('id') else secrets.token_hex(16)
        existing=self.row(identity)
        if draft.get('id') and existing is None:raise FileNotFoundError('Sound no longer exists.')
        if existing and expected and hashlib.sha256(json.dumps(self.manifest(identity),sort_keys=True).encode()).hexdigest()!=expected:raise ValueError('Sound changed. Reload it before saving.')
        # An independent link name makes names unique within a folder.
        linkname=title+'.sound'
        with self.directory(category,True) as fd:
            for other in os.listdir(fd):
                if other.casefold()==linkname.casefold() and (not existing or existing['link']!='/'.join(filter(None,(category,other)))):raise FileExistsError('A Sound with this name already exists in that folder.')
        self.folder.mkdir(parents=True,exist_ok=True);store=self.folder/'.library'
        if store.is_symlink():raise ValueError('Invalid Sound store.')
        store.mkdir(exist_ok=True);base=store/identity
        if base.is_symlink():raise ValueError('Invalid Sound bundle.')
        base.mkdir(exist_ok=True);assets=base/'samples'
        if assets.is_symlink():raise ValueError('Invalid Sound samples.')
        assets.mkdir(exist_ok=True);zones=[];total=0;copied={}
        for row in rows:
            ref=row.get('asset');key=json.dumps(ref,sort_keys=True)
            if key not in copied:
                temporary=assets/('.'+secrets.token_hex(16));digest=hashlib.sha256();size=0
                try:
                    with opener(ref) as source,temporary.open('xb') as out:
                        for block in iter(lambda:source.read(65536),b''):
                            size+=len(block)
                            if size>64*1024**2:raise ValueError('A zone sample exceeds 64 MiB.')
                            if shutil.disk_usage(self.folder).free<len(block)+RESERVE:raise OSError('Not enough free storage.')
                            digest.update(block);out.write(block)
                        out.flush();os.fsync(out.fileno())
                    with wave.open(str(temporary),'rb') as wav:
                        if wav.getnchannels() not in (1,2) or wav.getsampwidth() not in (1,2,3,4):raise ValueError('Use mono/stereo PCM WAV samples.')
                        frames=wav.getnframes()
                        if frames*8>64*1024**2 or frames<=0:raise ValueError('Sample exceeds the decoded zone limit.')
                    filename=digest.hexdigest()[:32]+'.wav';destination=assets/filename
                    if destination.is_symlink():raise ValueError('Invalid Sound sample destination.')
                    if not destination.exists():os.replace(temporary,destination)
                    copied[key]=(str(destination.relative_to(base)),frames,size)
                finally:temporary.unlink(missing_ok=True)
            path,frames,size=copied[key];total+=size
            if total>512*1024**2:raise ValueError('Sound exceeds 512 MiB of zone samples.')
            zone=default_zone(dict(sample=path,start=0,end=frames,note=60))
            zone.update({k:v for k,v in row.items() if k in zone and k!='sample'});zone['sample']=path
            zone['name']=str(row.get('label') or row.get('name') or (ref.get('name') if isinstance(ref,dict) else None) or Path(path).name)[:128]
            validate_sampler(dict(sample=path,start=0,end=frames,zones=[zone],sampler=sampler));zones.append(zone)
        project=new_project()
        if existing:project['groups'][0]['pads'][0]=copy.deepcopy(self.manifest(identity)['project']['groups'][0]['pads'][0])
        track=project['groups'][0]['pads'][0];track.update(name=title,sample=zones[0]['sample'],start=zones[0]['start'],end=zones[0]['end'],zones=zones,sampler=sampler)
        if existing:track['plugins']=copy.deepcopy(self.manifest(identity)['project']['groups'][0]['pads'][0].get('plugins',[]))
        validate_project(project)
        manifest=dict(format='Machinista-preset',version=1,kind='SOUND',name=title,tags=labels,project=project)
        self.atomic(base/'Preset.json',manifest)
        link=dict(format='Machinista-sound-link',version=1,id=identity,name=title,tags=labels,kind='SAMPLER',zones=len(zones))
        with self.directory(category,True) as fd:self.atomic_fd(fd,linkname,link)
        newpath='/'.join(filter(None,(category,linkname)))
        if existing and existing['link']!=newpath:
            old=Path(existing['link'])
            with self.directory(str(old.parent) if str(old.parent)!='.' else '') as fd:os.unlink(old.name,dir_fd=fd)
        return self.draft(identity)
    def metadata(self,draft):
        identity=self.identity(draft['id']);old=self.row(identity)
        if old is None:raise FileNotFoundError('Sound missing.')
        document=self.manifest(identity)
        if draft.get('version') and draft['version']!=hashlib.sha256(json.dumps(document,sort_keys=True).encode()).hexdigest():raise ValueError('Sound changed; reload before saving.')
        title=name(draft.get('name'));category=folders(draft.get('folder',''));labels=tags(draft.get('tags',[]));linkname=title+'.sound'
        newpath='/'.join(filter(None,(category,linkname)))
        with self.directory(category,True) as fd:
            if any(n.casefold()==linkname.casefold() for n in os.listdir(fd)) and old['link']!=newpath:raise FileExistsError('Sound name exists.')
            document['name']=title;document['tags']=labels;document['project']['groups'][0]['pads'][0]['name']=title
            self.atomic(self.bundle(identity)/'Preset.json',document)
            self.atomic_fd(fd,linkname,dict(format='Machinista-sound-link',version=1,id=identity,name=title,tags=labels,kind=old['kind'],zones=old['zones']))
        if old['link']!=newpath:
            previous=Path(old['link'])
            with self.directory('' if str(previous.parent)=='.' else str(previous.parent)) as fd:os.unlink(previous.name,dir_fd=fd)
        return self.draft(identity)
    def save_project(self,project,metadata):
        from app.assets import collect_project
        from app.model import validate_project
        title=name(metadata.get('name'));category=folders(metadata.get('folder',''));labels=tags(metadata.get('tags',[]));validate_project(project)
        with self.writing():
            with self.directory(category,True) as fd:
                if any(n.casefold()==(title+'.sound').casefold() for n in os.listdir(fd)):raise FileExistsError('Sound name exists.')
            store=self.folder/'.library'
            if store.is_symlink():raise ValueError('Invalid Sound store.')
            store.mkdir(exist_ok=True);identity=secrets.token_hex(16);base=store/identity
            for target in [project['groups'][0]['pads'][0]]:
                for plugin in target.get('plugins',[]):
                    state=Path(plugin.get('state',''))
                    if not state.is_file() or state.is_symlink() or any(p.is_symlink() for p in state.parent.rglob('*')):raise ValueError('Plugin state was not saved.')
            collect_project(project,base);saved=json.loads((base/'Project.json').read_text());track=saved['groups'][0]['pads'][0];track['name']=title
            kind=('SYNTH' if track['plugins'][0]['uri']=='urn:machinista:instrument:synth' else 'LV2') if track.get('plugins') and track['plugins'][0]['kind']=='INSTRUMENT' else 'SAMPLER'
            if kind=='SAMPLER' and not track.get('sample'):raise ValueError('The current Sound has no samples or instrument.')
            self.atomic(base/'Preset.json',dict(format='Machinista-preset',version=1,kind='SOUND',name=title,tags=labels,project=saved));(base/'Project.json').unlink()
            with self.directory(category,True) as fd:self.atomic_fd(fd,title+'.sound',dict(format='Machinista-sound-link',version=1,id=identity,name=title,tags=labels,kind=kind,zones=len(track.get('zones',[]))))
        return self.draft(identity)
    @staticmethod
    def atomic(path,value):
        fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:SoundLibrary.atomic_fd(fd,path.name,value)
        finally:os.close(fd)
    @staticmethod
    def atomic_fd(fd,filename,value):
        tmp='.'+secrets.token_hex(16);f=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644,dir_fd=fd)
        try:
            with os.fdopen(f,'w') as stream:json.dump(value,stream,ensure_ascii=False);stream.flush();os.fsync(stream.fileno())
            os.replace(tmp,filename,src_dir_fd=fd,dst_dir_fd=fd);os.fsync(fd)
        finally:
            try:os.unlink(tmp,dir_fd=fd)
            except FileNotFoundError:pass
