"""Bounded LV2 bundle installer. Metadata inspection never loads uploaded code.

The privileged service runs a root-owned copy of this single module. RPC accepts
opaque upload/bundle IDs, never paths or shell commands. LV2 execution occurs
only later when the musician chooses an installed plugin in the audio host.
"""
from pathlib import Path, PurePosixPath
import argparse
import grp
import hashlib
import json
import os
import pwd
import queue
import re
import resource
import secrets
import socket
import shutil
import socketserver
import stat
import struct
import subprocess
import tarfile
import tempfile
import threading
import time
import zipfile
from urllib.parse import urlsplit,unquote

STATE=Path('/var/lib/machinista/lv2')
RUNTIME=Path('/run/machinista-lv2')
MAX_ARCHIVE=128*1024**2
MAX_EXPANDED=256*1024**2
MAX_FILES=4096
ID=re.compile(r'^[a-f0-9]{32}$')


def atomic_json(path,value):
    temporary=path.with_name(path.name+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False));os.chmod(temporary,0o644);os.replace(temporary,path)


def elf(path,shared=True):
    """Inspect ELF headers, not ldd/dlopen (which could execute the upload)."""
    with Path(path).open('rb') as stream:data=stream.read(64)
    if len(data)<52 or data[:4]!=b'\x7fELF':raise ValueError('Not a Linux ELF binary.')
    bits={1:32,2:64}.get(data[4]);order={1:'<',2:'>'}.get(data[5])
    if bits is None or order is None or data[6]!=1:raise ValueError('Invalid ELF header.')
    kind,machine=struct.unpack_from(order+'HH',data,16)
    if kind!=3 and (shared or kind!=2):raise ValueError('The binary is not a shared library.')
    if data[7] not in (0,3):raise ValueError('Unsupported ELF operating-system ABI.')
    return dict(bits=bits,machine=machine,endian=data[5],label={183:'ARM64',40:'ARM32',62:'x86-64',3:'x86'}.get(machine,'ELF '+str(machine)))


def needed_libraries(path):
    """Read DT_NEEDED/RUNPATH without invoking the dynamic loader."""
    with path.open('rb') as f:
        head=f.read(64);bits=head[4];order='<' if head[5]==1 else '>'
        phoff=struct.unpack_from(order+('Q' if bits==2 else 'I'),head,32 if bits==2 else 28)[0]
        entsize,count=struct.unpack_from(order+'HH',head,54 if bits==2 else 42)
        expected=56 if bits==2 else 32
        if entsize!=expected or count>1024:raise ValueError('Invalid ELF program headers.')
        loads=[];dynamic=None
        for index in range(count):
            f.seek(phoff+index*entsize);data=f.read(entsize)
            if len(data)!=entsize:raise ValueError('Incomplete ELF program headers.')
            values=struct.unpack(order+('IIQQQQQQ' if bits==2 else 'IIIIIIII'),data)
            kind=values[0];offset,vaddr,size=(values[2],values[3],values[5]) if bits==2 else (values[1],values[2],values[4])
            if kind==1:loads.append((vaddr,offset,size))
            if kind==2:dynamic=(offset,size)
        if dynamic is None:raise ValueError('ELF has no dynamic linking section.')
        offset,size=dynamic;step=16 if bits==2 else 8
        if size>1024*1024:raise ValueError('ELF dynamic section is too large.')
        f.seek(offset);data=f.read(size);entries=[]
        for start in range(0,len(data)-step+1,step):
            tag,value=struct.unpack_from(order+('qQ' if bits==2 else 'iI'),data,start)
            if tag==0:break
            entries.append((tag,value))
        address=next((v for t,v in entries if t==5),None)
        needed=[v for t,v in entries if t==1];search=[v for t,v in entries if t in (15,29)]
        if address is None:
            if needed:raise ValueError('ELF string table missing.')
            return [],[]
        load=next((item for item in loads if item[0]<=address<item[0]+item[2]),None)
        if load is None:raise ValueError('ELF string table outside load segments.')
        string_offset=load[1]+address-load[0]
        def string(value):
            f.seek(string_offset+value);raw=f.read(4096)
            if b'\0' not in raw:raise ValueError('Invalid ELF dependency name.')
            return raw.split(b'\0',1)[0].decode('utf-8')
        return [string(v) for v in needed],[string(v) for v in search]


def check_dependencies(binary,bundle,system):
    needed,search=needed_libraries(binary)
    directories=[]
    for value in search:
        for entry in value.split(':'):
            if '$ORIGIN' in entry or '${ORIGIN}' in entry:
                path=Path(entry.replace('${ORIGIN}',str(binary.parent)).replace('$ORIGIN',str(binary.parent))).resolve()
                if path.is_relative_to(bundle.resolve()):directories.append(path)
    for name in needed:
        if '/' in name:raise ValueError('Absolute/path-based shared-library dependency is not supported.')
        if name in system:continue
        if any((path/name).is_file() for path in directories):continue
        raise ValueError(binary.name+': required library '+name+' is not available.')


def archive_path(name):
    while name.startswith('./'):name=name[2:]
    p=PurePosixPath(name)
    if not name or name.startswith('/') or '\\' in name or '\0' in name or any(ord(c)<32 for c in name) or any(x in ('.','..') for x in name.rstrip('/').split('/')) or len(name.encode())>512:
        raise ValueError('Unsafe archive path.')
    if len(p.parts)>16:raise ValueError('Archive folders are too deeply nested.')
    return p


def unpack(archive,destination):
    """No extractall: reject links, devices, traversal, duplicates and bombs."""
    seen=set();total=0;count=0
    def extract(name,size,isdir,opener):
        nonlocal total,count
        if name in ('.','./'):return
        p=archive_path(name)
        if '__MACOSX' in p.parts or p.name=='.DS_Store':return
        if str(p) in seen:raise ValueError('Duplicate archive path.')
        seen.add(str(p));count+=1;total+=size
        if count>MAX_FILES or total>MAX_EXPANDED:raise ValueError('Archive exceeds 4,096 files or 256 MiB unpacked.')
        target=destination.joinpath(*p.parts)
        if isdir:target.mkdir(parents=True,exist_ok=True);return
        target.parent.mkdir(parents=True,exist_ok=True)
        with opener() as source,target.open('xb') as out:
            remaining=size
            while remaining:
                data=source.read(min(65536,remaining))
                if not data:raise ValueError('Incomplete archive member.')
                out.write(data);remaining-=len(data)
        os.chmod(target,0o644)
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as z:
            for item in z.infolist():
                mode=item.external_attr>>16
                if stat.S_ISLNK(mode) or stat.S_IFMT(mode) not in (0,stat.S_IFREG,stat.S_IFDIR):raise ValueError('Links and special files are not allowed.')
                if item.flag_bits&1:raise ValueError('Encrypted archives are not supported.')
                extract(item.filename,item.file_size,item.is_dir(),lambda item=item:z.open(item))
    else:
        try:
            with tarfile.open(archive,'r:*') as t:
                for item in t:
                    if not (item.isdir() or item.isfile()):raise ValueError('Links and special files are not allowed.')
                    extract(item.name,item.size,item.isdir(),lambda item=item:t.extractfile(item))
        except tarfile.TarError as error:raise ValueError('Upload a ZIP, TAR.GZ or TGZ containing compiled .lv2 folders.') from error
    bundles=sorted(destination.rglob('*.lv2'))
    if not bundles or any(not p.is_dir() for p in bundles):raise ValueError('No .lv2 bundle folder found. Upload the complete compiled bundle.')
    if len(bundles)>64 or any(a in b.parents for a in bundles for b in bundles if a!=b):raise ValueError('Invalid nested LV2 bundles.')
    if len({p.name for p in bundles})!=len(bundles):raise ValueError('Duplicate LV2 bundle names.')
    for bundle in bundles:
        if not (bundle/'manifest.ttl').is_file():raise ValueError(bundle.name+': manifest.ttl is missing.')
    return bundles


def file_path(value):
    if value.startswith('file:'):
        parsed=urlsplit(value)
        if parsed.netloc not in ('','localhost'):raise ValueError('Non-local plugin file URI.')
        return Path(unquote(parsed.path))
    return Path(value)


class Manager:
    def __init__(self,root,state=STATE,runtime=RUNTIME,roots=None,probe=None,target=None,scanner=None):
        self.root=Path(root);self.state=Path(state);self.runtime=Path(runtime)
        self.scanner=Path(scanner) if scanner else self.root/'build/audio_engine'
        self.active=self.state/'plugins';self.incoming=self.state/'incoming';self.trash=self.state/'removed'
        for p in (self.state,self.active,self.incoming,self.trash,self.runtime):p.mkdir(parents=True,exist_ok=True)
        self.roots=[self.active]+list(roots if roots is not None else (Path('/usr/local/lib/lv2'),Path('/usr/lib/lv2'),Path.home()/'.lv2'))
        self.target=target or elf(self.scanner,shared=False)
        self.probe=probe or self.metadata
        self.system_libraries=None
        self.lock=threading.RLock();self.jobs={};self.catalog=[];self.error='';self.running=False
        self.revision=secrets.token_hex(16)
        self.pending=queue.Queue(maxsize=1)

    def metadata(self,paths):
        # Production metadata inspection lives in a separate nobody-owned
        # service. The root installer never parses LV2 metadata itself.
        if os.geteuid()==0:
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
                client.settimeout(15)
                for attempt in range(50):
                    try:client.connect('/run/machinista-lv2-scan/control.sock');break
                    except (FileNotFoundError,ConnectionRefusedError):
                        if attempt==49:raise
                        time.sleep(.1)
                client.sendall(json.dumps(dict(paths=[str(p) for p in paths])).encode()+b'\n')
                with client.makefile('rb') as stream:raw=stream.readline(4*1024**2+1)
            result=json.loads(raw)
            if result.get('error'):raise ValueError(result['error'])
            return result['plugins']
        def limits():
            step='resource limits'
            try:
                resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_CPU,(5,5))
                resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2));resource.setrlimit(resource.RLIMIT_FSIZE,(4*1024**2,4*1024**2))
            except BaseException as error:
                os.write(2,('Scanner sandbox '+step+': '+str(error)).encode());os._exit(127)
        # --plugins disables dynamic manifests before Lilv scans. No instantiate,
        # run, dlopen or ldd is called for uploaded libraries during validation.
        with tempfile.TemporaryFile() as output,tempfile.TemporaryFile() as errors:
            result=subprocess.run([str(self.scanner),'--plugins'],stdout=output,stderr=errors,timeout=12,preexec_fn=limits,
                env={'PATH':'/usr/bin:/bin','LC_ALL':'C','HOME':'/nonexistent','LV2_PATH':':'.join(str(p) for p in paths)})
            if result.returncode:
                errors.seek(0);reason=errors.read(400).decode('utf-8',errors='replace')
                raise ValueError('LV2 metadata check failed. '+reason)
            if output.tell()>4*1024**2:raise ValueError('LV2 metadata is too large.')
            output.seek(0)
            try:rows=json.load(output)
            except (ValueError,UnicodeError) as error:raise ValueError('Invalid LV2 metadata.') from error
        if not isinstance(rows,list):raise ValueError('Invalid LV2 metadata.')
        return rows

    def usage(self):
        try:
            p=self.runtime/'in-use.json'
            data=json.loads(p.read_text())
            if time.time()-p.stat().st_mtime>8:raise ValueError()
            return data
        except (OSError,ValueError):return dict(busy=True,uris=[],unavailable=True)

    def refresh(self):
        rows=self.probe([p for p in self.roots if p.is_dir()]);groups={}
        for item in rows:
            group=None
            try:
                path=file_path(item['bundle']).resolve()
                if path.parent not in [p.resolve() for p in self.roots] or not path.name.endswith('.lv2'):continue
                key=hashlib.sha256(str(path).encode()).hexdigest()[:32]
                group=groups.setdefault(key,dict(id=key,name=path.name,path=str(path),managed=path.parent==self.active.resolve(),plugins=[],status='OK',reason=''))
                binary=file_path(item['binary']).resolve()
                if not binary.is_relative_to(path):raise ValueError('Plugin binary is outside its bundle.')
                architecture=elf(binary)
                compatible=all(architecture[k]==self.target[k] for k in ('bits','machine','endian'))
                good=compatible and item.get('supported',False)
                group['plugins'].append(dict(uri=item['uri'],name=item['name'],kind=item['kind'],supported=good))
                group['architecture']=architecture['label']
                if not good:group['status']='NOT OK';group['reason']='Wrong architecture or unsupported LV2 features/ports.'
            except (KeyError,OSError,ValueError) as error:
                if group is not None:group['status']='NOT OK';group['reason']=str(error)
        with self.lock:self.catalog=sorted(groups.values(),key=lambda r:r['name'].casefold());self.error=''
        self.revision=secrets.token_hex(16);atomic_json(self.runtime/'revision.json',dict(revision=self.revision))

    def status(self):
        try:applied=json.loads((self.runtime/'catalog-applied.json').read_text()).get('revision')==self.revision
        except (OSError,ValueError):applied=False
        use=self.usage();uris=set(use.get('uris',[]));rows=[]
        with self.lock:
            for item in self.catalog:
                item=dict(item);item['inUse']=any(p['uri'] in uris for p in item['plugins'])
                item['canDelete']=not item['inUse'] and not use.get('busy',True) and not use.get('unavailable',False)
                rows.append(item)
            return dict(target=self.target['label'],bundles=rows,jobs=list(self.jobs.values()),busy=self.running,error=self.error,
                transportBusy=use.get('busy',True),applicationAvailable=not use.get('unavailable',False),browserReady=applied,revision=self.revision)

    def submit(self,operation,identifier=None,name=None):
        if operation not in ('upload','delete','refresh'):raise ValueError('Unknown LV2 operation.')
        if operation!='refresh' and (not isinstance(identifier,str) or not ID.fullmatch(identifier)):raise ValueError('Invalid ID.')
        with self.lock:
            if self.running:raise BlockingIOError('Another LV2 operation is in progress.')
            self.running=True;job=secrets.token_hex(16)
            if len(self.jobs)>=24:self.jobs.pop(next(iter(self.jobs)))
            self.jobs[job]=dict(id=job,name=str(name or operation)[:160],state='CHECKING',ok=None,message='Checking package…')
            self.pending.put_nowait((job,operation,identifier))
            return dict(job=job)

    def job(self,key,**changes):
        with self.lock:self.jobs[key].update(changes)

    def check(self,archive,destination):
        bundles=unpack(archive,destination)
        if self.system_libraries is None:
            cache=subprocess.run(['/sbin/ldconfig','-p'],capture_output=True,text=True,check=True,timeout=5).stdout
            self.system_libraries={line.strip().split()[0] for line in cache.splitlines() if '=>' in line}
        for bundle in bundles:
            count=0
            for p in bundle.rglob('*'):
                if not p.is_file():continue
                with p.open('rb') as f:signature=f.read(4)
                if signature==b'\x7fELF' or '.so' in p.name:
                    info=elf(p);count+=1
                    if any(info[k]!=self.target[k] for k in ('bits','machine','endian')):raise ValueError(p.name+': '+info['label']+' does not match '+self.target['label']+'.')
                    check_dependencies(p,bundle,self.system_libraries)
                elif p.suffix.lower() in ('.dll','.dylib','.exe'):raise ValueError(p.name+': not a Linux ARM bundle.')
            if not count:raise ValueError(bundle.name+': no compiled Linux shared library found.')
        # Probe each bundle through a scan root containing only valid .lv2 dirs.
        scan=destination/'scan';scan.mkdir()
        for bundle in bundles:shutil.move(str(bundle),scan/bundle.name)
        bundles=sorted(scan.iterdir());rows=self.probe([scan]);known={p['uri'] for b in self.catalog for p in b['plugins']};seen=set()
        for b in bundles:
            plugins=[p for p in rows if file_path(p.get('bundle','')).resolve()==b.resolve()]
            if not plugins:raise ValueError(b.name+': no supported LV2 plugin metadata found.')
            for item in plugins:
                if not item.get('supported'):raise ValueError(item.get('name',b.name)+': unsupported LV2 features or audio ports.')
                binary=file_path(item['binary']).resolve()
                if not binary.is_relative_to(b.resolve()) or not binary.is_file():raise ValueError('A plugin binary points outside its bundle or is missing.')
                if item['uri'] in known or item['uri'] in seen:raise ValueError('This plugin URI is already installed or duplicated. Existing plugins were preserved.')
                seen.add(item['uri'])
            if any((p/b.name).exists() for p in self.roots):raise ValueError(b.name+' is already installed. Existing files were preserved.')
        return bundles,rows

    def install(self,key,identifier):
        path=self.incoming/(identifier+'.upload')
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
        try:
            st=os.fstat(fd)
            if not stat.S_ISREG(st.st_mode) or not 0<st.st_size<=MAX_ARCHIVE:raise ValueError('Invalid upload size.')
            if shutil.disk_usage(self.state).free<MAX_EXPANDED+256*1024**2:raise ValueError('Not enough free space; 256 MiB is reserved.')
            with tempfile.TemporaryDirectory(prefix='check-',dir=self.state) as tmp:
                tmp=Path(tmp);tmp.chmod(0o755);copy=tmp/'package';copy.write_bytes(b'')
                with os.fdopen(os.dup(fd),'rb') as source,copy.open('wb') as target:
                    remaining=st.st_size
                    while remaining:
                        data=source.read(min(65536,remaining))
                        if not data:raise ValueError('Upload incomplete.')
                        target.write(data);remaining-=len(data)
                    if source.read(1):raise ValueError('Upload changed while checking.')
                unpacked=tmp/'unpacked';unpacked.mkdir()
                bundles,rows=self.check(copy,unpacked)
                self.job(key,ok=True,state='WAITING',message='OK — waiting for playback and recording to stop.')
                while self.usage().get('busy',True):time.sleep(.5)
                moved=[]
                try:
                    for b in bundles:
                        target=self.active/b.name
                        if target.exists():raise FileExistsError('A bundle with this name is already installed.')
                        os.rename(b,target);moved.append(target)
                    self.refresh()
                except BaseException:
                    for p in moved:shutil.rmtree(p)
                    raise
                self.job(key,ok=True,state='ACTIVE',message='OK — installed. Available in the plug-in browser after its scan.',plugins=[p['name'] for p in rows])
        finally:os.close(fd);path.unlink(missing_ok=True)

    def remove(self,key,identifier):
        use=self.usage()
        if use.get('busy',True):raise ValueError('Stop playback and recording before removing plugins.')
        item=next((b for b in self.catalog if b['id']==identifier),None)
        if not item:raise ValueError('Plugin bundle is no longer installed. Refresh the list.')
        if any(p['uri'] in use.get('uris',[]) for p in item['plugins']):raise ValueError('This bundle is used by the current project. Remove its chain assignments first.')
        path=Path(item['path'])
        if path.is_symlink() or path.resolve().parent not in [p.resolve() for p in self.roots] or not path.name.endswith('.lv2'):raise ValueError('Invalid bundle location.')
        backup=self.trash/(identifier+'-'+secrets.token_hex(6));backup.mkdir()
        shutil.move(str(path),backup/path.name)
        atomic_json(backup/'receipt.json',dict(original=str(path),plugins=item['plugins'],removed=time.time()))
        try:self.refresh()
        except BaseException:
            shutil.move(str(backup/path.name),path);raise
        self.job(key,ok=True,state='REMOVED',message='Removed from the plug-in browser. A recovery copy was kept.')

    def work(self):
        while True:
            key,operation,identifier=self.pending.get()
            try:
                if operation=='upload':self.install(key,identifier)
                elif operation=='delete':self.remove(key,identifier)
                else:self.refresh();self.job(key,ok=True,state='DONE',message='Installed plugins refreshed.')
            except Exception as error:
                self.job(key,ok=False,state='NOT OK',message=str(error)[:300])
            finally:
                with self.lock:self.running=False


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.request.settimeout(10)
        try:
            raw=self.rfile.readline(4097)
            if len(raw)>4096:raise ValueError('Request too large.')
            request=json.loads(raw);manager=self.server.manager
            result=manager.status() if request.get('operation')=='status' else manager.submit(request.get('operation'),request.get('id'),request.get('name'))
        except Exception as error:result=dict(error=str(error)[:300])
        self.wfile.write(json.dumps(result).encode()+b'\n')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--user',default='machinista');parser.add_argument('--scanner',type=Path);parser.add_argument('--scan-server',action='store_true');args=parser.parse_args()
    if args.scan_server:
        if os.geteuid()==0:raise SystemExit('The scanner service must run without root privileges.')
        scan_server(args.scanner);return
    manager=Manager(args.root,roots=[Path('/usr/local/lib/lv2'),Path('/usr/lib/lv2'),Path(pwd.getpwnam(args.user).pw_dir)/'.lv2'],scanner=args.scanner)
    group=pwd.getpwnam(args.user).pw_gid
    os.chmod(manager.incoming,0o2770);os.chown(manager.incoming,0,group)
    os.chmod(manager.runtime,0o2770);os.chown(manager.runtime,0,group)
    endpoint=RUNTIME/'control.sock';endpoint.unlink(missing_ok=True)
    class Server(socketserver.ThreadingUnixStreamServer):daemon_threads=True
    with Server(str(endpoint),Handler) as server:
        server.manager=manager;os.chmod(endpoint,0o660);os.chown(endpoint,0,group)
        threading.Thread(target=manager.work,daemon=True).start()
        manager.submit('refresh');server.serve_forever()


def scan_server(scanner):
    """Read-only static inspection in an independent unprivileged service."""
    manager=object.__new__(Manager);manager.scanner=scanner
    class ScanHandler(socketserver.StreamRequestHandler):
        def handle(self):
            self.request.settimeout(15)
            try:
                raw=self.rfile.readline(4097)
                if len(raw)>4096:raise ValueError('Scan request too large.')
                paths=json.loads(raw)['paths']
                if not isinstance(paths,list) or len(paths)>16:raise ValueError('Invalid scan paths.')
                allowed=[STATE.resolve(),Path('/usr/lib/lv2'),Path('/usr/local/lib/lv2')]
                checked=[]
                for value in paths:
                    path=Path(value).resolve()
                    user_bundle=path.name=='.lv2' and path.parent.parent==Path('/home')
                    if not user_bundle and not any(path==base or path.is_relative_to(base) for base in allowed):raise ValueError('Invalid scan location.')
                    checked.append(path)
                result=dict(plugins=manager.metadata(checked))
            except Exception as error:result=dict(error=str(error)[:400])
            self.wfile.write(json.dumps(result).encode()+b'\n')
    endpoint=Path('/run/machinista-lv2-scan/control.sock');endpoint.unlink(missing_ok=True)
    with socketserver.UnixStreamServer(str(endpoint),ScanHandler) as server:
        endpoint.chmod(0o600);server.serve_forever()

if __name__=='__main__':main()
