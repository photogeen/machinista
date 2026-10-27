"""Saved project transfer, isolated from the running sequencer and audio engine."""
from contextlib import contextmanager
from pathlib import Path,PurePosixPath
import copy
import io
import json
import os
import re
import secrets
import shutil
import stat
import tempfile
import zipfile

MAX_JSON=8*1024**2
MAX_PACKAGE=1024**3
RESERVE=256*1024**2
PROJECT=re.compile(r'PROJECT-[0-9]{4}\.json$')


def parts(value):
    if not isinstance(value,str) or not value or value.startswith('/') or '\\' in value or any(ord(c)<32 for c in value):raise ValueError('Invalid project asset path.')
    p=PurePosixPath(value)
    if any(v in ('','..','.') for v in value.rstrip('/').split('/')) or len(p.parts)>24:raise ValueError('Invalid project asset path.')
    return p.parts


def read_project(data):
    from app.model import validate_project
    if len(data)>MAX_JSON:raise ValueError('Project JSON exceeds 8 MiB.')
    try:
        def invalid(v):raise ValueError('Non-finite JSON value.')
        value=json.loads(data,parse_constant=invalid)
        if not isinstance(value,dict):raise ValueError('Project must be an object.')
        return validate_project(value)
    except (KeyError,TypeError,IndexError,OverflowError,RecursionError,UnicodeError) as error:raise ValueError('Invalid Machinista project.') from error


def plugins(project):
    for target in [project]+project['groups']+[p for g in project['groups'] for p in g['pads']]:
        yield from target.get('plugins',[])


class Projects:
    def __init__(self,library):
        self.library=library;self.folder=library.root/'projects'
    @contextmanager
    def opened(self,path,roots):
        path=Path(path).absolute()
        # Canonical checks plus descriptor-relative nofollow traversal. Never
        # expose settings, arbitrary system files or symlinked asset trees.
        match=next((Path(r).absolute() for r in roots if path.is_relative_to(Path(r).absolute())),None)
        if match is None:raise PermissionError('Project asset is outside project/sample storage.')
        relative=path.relative_to(match)
        if '..' in relative.parts or not relative.parts:raise PermissionError('Invalid project asset.')
        fd=os.open(match,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            for component in relative.parts[:-1]:
                child=os.open(component,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=child
            child=os.open(relative.name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=fd)
        finally:os.close(fd)
        with os.fdopen(child,'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):raise PermissionError('Not a regular project asset.')
            yield stream
    def document(self,name):
        if name!='current.json' and not PROJECT.fullmatch(name):raise ValueError('Invalid project ID.')
        with self.opened(self.folder/name,[self.folder]) as stream:return read_project(stream.read(MAX_JSON+1))
    def list(self):
        if not self.folder.is_dir():return []
        rows=[]
        for p in sorted(self.folder.iterdir()):
            if p.is_symlink() or not p.is_file() or p.name!='current.json' and not PROJECT.fullmatch(p.name):continue
            try:
                project=self.document(p.name);info=p.stat()
                rows.append(dict(id=p.name,name=project['name'],current=p.name=='current.json',size=info.st_size,modified=info.st_mtime))
            except (ValueError,OSError):continue
        return sorted(rows,key=lambda r:(not r['current'],r['name'].casefold(),r['id']))
    def roots(self):return [self.folder,self.library.samples]+[s.path for s in self.library.scan()]
    def asset(self,value,base):
        if not isinstance(value,str):raise ValueError('Invalid asset reference.')
        path=Path(value)
        # Normalize ordinary relative ../samples references before the safe open.
        return Path(os.path.abspath(path if path.is_absolute() else Path(base)/path))
    @contextmanager
    def download(self,name,kind='zip'):
        project=self.document(name)
        if kind=='json':
            body=json.dumps(project,indent=2).encode()+b'\n';yield io.BytesIO(body),'application/json',project['name']+'.json';return
        if kind!='zip':raise ValueError('Unsupported project download.')
        if not self.library.upload_lock.acquire(blocking=False):raise BlockingIOError('Another transfer is in progress.')
        try:
            with tempfile.TemporaryFile(dir=self.folder) as output:
                total=0;count=0
                def add(z,source,destination):
                    nonlocal total,count
                    with self.opened(source,self.roots()) as stream:
                        size=os.fstat(stream.fileno()).st_size;total+=size;count+=1
                        if total>MAX_PACKAGE or count>4096:raise ValueError('Project exceeds 1 GiB or 4,096 assets.')
                        if shutil.disk_usage(self.folder).free<size+RESERVE:raise OSError('Not enough space to prepare project download.')
                        stamp=os.fstat(stream.fileno()).st_mtime_ns
                        with z.open(destination,'w',force_zip64=True) as target:
                            remaining=size
                            while remaining:
                                chunk=stream.read(min(65536,remaining))
                                if not chunk:raise ValueError('Project asset changed. Save and retry.')
                                target.write(chunk);remaining-=len(chunk)
                        if os.fstat(stream.fileno()).st_mtime_ns!=stamp:raise ValueError('Project asset changed. Save and retry.')
                with zipfile.ZipFile(output,'w',zipfile.ZIP_STORED) as z:
                    from app.assets import sample_references
                    copied={}
                    for obj,key in sample_references(project):
                        source=self.asset(obj[key],self.folder)
                        if source not in copied:
                            destination=f'samples/{len(copied)+1:04}.wav';add(z,source,destination);copied[source]=destination
                        obj[key]=copied[source]
                    for index,plugin in enumerate(plugins(project)):
                        if not plugin.get('state'):continue
                        state=self.asset(plugin['state'],self.folder)
                        if state.name!='state.ttl' or not state.parent.is_relative_to(self.folder) or state.parent==self.folder:raise ValueError('Invalid plug-in state location.')
                        for p in state.parent.rglob('*'):
                            if p.is_symlink():raise ValueError('Symlinked plug-in state is unsupported.')
                            if p.is_file():add(z,p,f'plugins/{index}/'+p.relative_to(state.parent).as_posix())
                        with self.opened(state,[self.folder]):pass
                        plugin['state']=f'plugins/{index}/state.ttl'
                    z.writestr('Project.json',json.dumps(project,indent=2))
                output.seek(0);yield output,'application/zip',project['name']+'.zip'
        finally:self.library.upload_lock.release()
    def upload(self,name,stream,length):
        kind=Path(name).suffix.lower()
        if kind not in ('.json','.zip'):raise ValueError('Upload a Machinista project ZIP or JSON.')
        limit=MAX_JSON if kind=='.json' else MAX_PACKAGE
        if not 0<length<=limit:raise ValueError('Maximum 8 MiB for JSON or 1 GiB for project ZIP.')
        if not self.library.upload_lock.acquire(blocking=False):raise BlockingIOError('Another transfer is in progress.')
        self.folder.mkdir(exist_ok=True,parents=True)
        try:
            if shutil.disk_usage(self.folder).free<length+RESERVE:raise OSError('Not enough space for project upload.')
            with tempfile.TemporaryDirectory(prefix='.web-project-',dir=self.folder) as work:
                work=Path(work);archive=work/'upload';remaining=length
                with archive.open('wb') as target:
                    while remaining:
                        data=stream.read(min(65536,remaining))
                        if not data:raise ValueError('Project upload incomplete.')
                        target.write(data);remaining-=len(data)
                base=self.folder;assets=None
                if kind=='.json':project=read_project(archive.read_bytes())
                else:
                    assets=work/'assets';assets.mkdir()
                    try:
                        with zipfile.ZipFile(archive) as z:
                            items=z.infolist();total=sum(i.file_size for i in items)
                            if len(items)>4096 or total>MAX_PACKAGE:raise ValueError('Project ZIP exceeds 4,096 entries or 1 GiB expanded.')
                            if shutil.disk_usage(self.folder).free<total+RESERVE:raise OSError('Not enough space to unpack project.')
                            seen=set()
                            for item in items:
                                path=parts(item.filename);key='/'.join(path)
                                if key in seen:raise ValueError('Duplicate project ZIP path.')
                                seen.add(key);mode=item.external_attr>>16
                                if stat.S_IFMT(mode) not in (0,stat.S_IFREG,stat.S_IFDIR) or item.flag_bits&1:raise ValueError('Project ZIP links, special files and encryption are unsupported.')
                                destination=assets.joinpath(*path)
                                if item.is_dir():destination.mkdir(exist_ok=True,parents=True);continue
                                destination.parent.mkdir(exist_ok=True,parents=True)
                                with z.open(item) as source,destination.open('xb') as target:
                                    shutil.copyfileobj(source,target,65536);target.flush();os.fsync(target.fileno())
                        manifests=list(assets.rglob('Project.json'))
                        if len(manifests)!=1:raise ValueError('Project ZIP must contain one Project.json.')
                        manifest=manifests[0];base=manifest.parent
                        with manifest.open('rb') as f:project=read_project(f.read(MAX_JSON+1))
                    except zipfile.BadZipFile as error:raise ValueError('Invalid or damaged project ZIP.') from error
                from app.assets import sample_references
                references=[(obj,key) for obj,key in sample_references(project)]
                references.extend((p,'state') for p in plugins(project) if p.get('state'))
                for obj,key in references:
                    if assets is not None:parts(obj[key])
                    source=self.asset(obj[key],base)
                    with self.opened(source,[base] if assets is not None else self.roots()):pass
                    obj[key]=str(source)
                names={r['name'].casefold() for r in self.list()};original=project['name'];n=2
                while project['name'].casefold() in names:
                    suffix=f' IMPORT {n}';project['name']=original[:32-len(suffix)]+suffix;n+=1
                destination=None;published=None
                try:
                    if assets is not None:
                        destination=self.folder/('import-'+secrets.token_hex(12));os.rename(assets,destination)
                        for obj,key in references:obj[key]=str(destination/Path(obj[key]).relative_to(assets))
                    from app.assets import relative_assets
                    # High slots avoid colliding with ordinary controller New
                    # allocations. Exclusive link publication never replaces a slot.
                    for number in range(9999,0,-1):
                        identity=f'PROJECT-{number:04}';project['file_id']=identity
                        data=relative_assets(project,self.folder);temporary=work/'project.json';temporary.write_text(json.dumps(data,indent=2)+'\n')
                        with temporary.open('rb') as f:os.fsync(f.fileno())
                        try:os.link(temporary,self.folder/(identity+'.json'))
                        except FileExistsError:continue
                        published=identity+'.json';break
                    if published is None:raise ValueError('All project slots are occupied.')
                    directory=os.open(self.folder,os.O_RDONLY|os.O_DIRECTORY)
                    try:os.fsync(directory)
                    finally:os.close(directory)
                    return dict(id=published,name=project['name'],message='Project imported. Open it with LOAD on the controller.')
                finally:
                    if destination is not None and published is None:shutil.rmtree(destination)
        finally:self.library.upload_lock.release()
