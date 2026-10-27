"""Trusted updater core (stdlib + OpenSSL); no imports from user-owned app code.

Installed as a root-owned standalone module beside update_service.py. Network,
APT and file work run only in the update service, never the audio/UI process.
"""
import fcntl
import base64,hashlib,json,os,platform,re,shutil,stat,subprocess,tarfile,tempfile,threading,time
from pathlib import Path,PurePosixPath
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.parse import urlsplit

CHANNELS=('beta','release');MAX_ARCHIVE=256*1024**2;MAX_EXPANDED=768*1024**2
BUSY=('CHECKING','DOWNLOADING','VALIDATING','SAVING','OS UPDATE','INSTALLING','RESTARTING')
ALLOWED=('app','web','assets','build','tools','docs','captures','output')

def version(value):
    match=re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)(?:-(beta|rc)\.(\d+))?',value or '')
    if not match:raise ValueError('Invalid version.')
    a,b,c,kind,n=match.groups();return (int(a),int(b),int(c),{'beta':0,'rc':1,None:2}[kind],int(n or 0))

def atomic(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    data=json.dumps(value,indent=2).encode()+b'\n';tmp=path.with_name(path.name+'.pending')
    with tmp.open('wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    os.replace(tmp,path);fd=os.open(path.parent,os.O_RDONLY);os.fsync(fd);os.close(fd)

def trusted_json(path):
    path=Path(path);info=path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid() or info.st_mode&0o022 or info.st_size>16384:raise ValueError('Update configuration must be root-owned and not writable by other users.')
    return json.loads(path.read_text())

def config(path):
    value=trusted_json(path)
    if type(value.get('enabled')) is not bool:raise ValueError('Invalid updater edition.')
    repo=value.get('repository','')
    if repo and not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo):raise ValueError('Invalid GitHub repository.')
    version(value.get('current_version',''))
    return value

class Redirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        u=urlsplit(newurl)
        if u.scheme!='https' or u.hostname not in ('github.com','raw.githubusercontent.com','release-assets.githubusercontent.com','objects.githubusercontent.com'):raise ValueError('Untrusted update redirect.')
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def download(url,limit,destination=None):
    u=urlsplit(url)
    if u.scheme!='https' or u.username or u.password or u.hostname not in ('github.com','raw.githubusercontent.com'):raise ValueError('Invalid update URL.')
    opener=build_opener(Redirect());result=bytearray();total=0
    with opener.open(Request(url,headers={'User-Agent':'Machinista-Updater/1'}),timeout=20) as response:
        with (Path(destination).open('wb') if destination else tempfile.TemporaryFile()) as f:
            while True:
                chunk=response.read(65536)
                if not chunk:break
                total+=len(chunk)
                if total>limit:raise ValueError('Update download exceeds its declared size.')
                f.write(chunk)
            f.flush();os.fsync(f.fileno())
            if destination:return total
            f.seek(0);return f.read()

def verify_signature(raw,signature,key,run=subprocess.run):
    key=Path(key);info=key.lstat()
    if info.st_uid!=os.geteuid() or not stat.S_ISREG(info.st_mode) or info.st_mode&0o022:raise ValueError('Untrusted update signing key.')
    with tempfile.TemporaryDirectory(prefix='machinista-signature-') as folder:
        root=Path(folder);(root/'manifest').write_bytes(raw)
        try:sig=base64.b64decode(signature.strip(),validate=True)
        except ValueError:raise ValueError('Invalid update signature.')
        if len(sig)!=64:raise ValueError('Invalid update signature.')
        (root/'signature').write_bytes(sig)
        run(['openssl','pkeyutl','-verify','-pubin','-inkey',str(key),'-rawin','-in',str(root/'manifest'),'-sigfile',str(root/'signature')],check=True,capture_output=True,timeout=10)

def manifest(raw,channel,cfg,os_name,machine):
    m=json.loads(raw);version(m.get('version'));version(m.get('minimum_version'))
    if m.get('schema')!=1 or m.get('channel')!=channel:raise ValueError('Update channel/schema mismatch.')
    if m.get('architecture')!='arm64' or machine not in ('aarch64','arm64'):raise ValueError('Update needs an ARM64 system.')
    if m.get('os_codename')!=os_name:raise ValueError('This update needs a different OS image.')
    if channel=='release' and '-' in m['version']:raise ValueError('Release channel needs a final version.')
    if version(m['minimum_version'])>version(m['version']):raise ValueError('Invalid minimum update version.')
    artifact=m.get('artifact',{});u=urlsplit(artifact.get('url',''))
    prefix='/'+cfg['repository']+'/releases/download/'
    if u.scheme!='https' or u.netloc!='github.com' or not u.path.startswith(prefix) or not u.path.endswith('.tar.gz') or u.query or u.fragment:raise ValueError('Update artifact must belong to the configured GitHub repository.')
    if type(artifact.get('size')) is not int or not 0<artifact['size']<=MAX_ARCHIVE or not re.fullmatch('[0-9a-f]{64}',artifact.get('sha256','')):raise ValueError('Invalid update size/checksum.')
    if not isinstance(m.get('notes',''),str) or len(m.get('notes',''))>4000:raise ValueError('Invalid release notes.')
    return m

def members(path):
    total=0;seen=set();result=[]
    with tarfile.open(path,'r:gz') as archive:
        for m in archive:
            parts=PurePosixPath(m.name).parts
            if not parts or m.name.startswith('/') or '..' in parts or '\\' in m.name or len(m.name)>240:raise ValueError('Unsafe update path.')
            if m.isdir():continue
            if not m.isfile() or m.name in seen or len(parts)<2 or parts[0] not in ALLOWED:raise ValueError('Unsupported update file or link.')
            if parts[0]=='output' and (len(parts)!=3 or parts[1]!='pdf' or not parts[2].endswith('.pdf')):raise ValueError('Unsupported update output file.')
            total+=m.size
            if total>MAX_EXPANDED or len(result)>=4096:raise ValueError('Expanded update is too large.')
            if m.size<0 or m.size>128*1024**2:raise ValueError('Update file is too large.')
            if parts[0]=='build':
                data=archive.extractfile(m).read(20)
                if data[:5]!=b'\x7fELF\x02' or data[5]!=1 or data[18:20]!=b'\xb7\x00':raise ValueError('Update contains a non-ARM64 binary.')
            seen.add(m.name);result.append(m.name)
    if not {'app/branding.py','tools/machinista.py','build/audio_engine'}<=seen:raise ValueError('Incomplete application update.')
    return result

# Descriptor-relative operations never follow user-controlled destination links.
def parent(root,name,create=False):
    fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
    try:
        parts=Path(root).parts[1:]+PurePosixPath(name).parts[:-1]
        for part in parts:
            try:nxt=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
            except FileNotFoundError:
                if not create:raise
                os.mkdir(part,0o755,dir_fd=fd);nxt=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
            os.close(fd);fd=nxt
        return fd,PurePosixPath(name).name
    except BaseException:os.close(fd);raise

def read_file(root,name):
    fd,leaf=parent(root,name)
    try:
        file=os.open(leaf,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=fd)
        with os.fdopen(file,'rb') as f:
            if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):raise ValueError('Invalid installed file.')
            return f.read(MAX_EXPANDED+1)
    finally:os.close(fd)

def replace_file(root,name,data,uid,gid):
    fd,leaf=parent(root,name,True);tmp='.'+leaf+'.update-'+str(os.getpid())
    try:
        # Refuse replacing a symlink, even though rename itself would not follow it.
        try:
            if not stat.S_ISREG(os.stat(leaf,dir_fd=fd,follow_symlinks=False).st_mode):raise ValueError('Invalid destination file.')
        except FileNotFoundError:pass
        file=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o755 if name.startswith('build/') else 0o644,dir_fd=fd)
        with os.fdopen(file,'wb') as f:
            if os.geteuid()==0:os.fchown(f.fileno(),uid,gid)
            f.write(data);f.flush();os.fsync(f.fileno())
        os.rename(tmp,leaf,src_dir_fd=fd,dst_dir_fd=fd);os.fsync(fd)
    finally:
        try:os.unlink(tmp,dir_fd=fd)
        except FileNotFoundError:pass
        os.close(fd)

def remove_file(root,name):
    fd,leaf=parent(root,name)
    try:os.unlink(leaf,dir_fd=fd);os.fsync(fd)
    finally:os.close(fd)

class Manager:
    def __init__(self,cfg,root,state,runtime,uid,gid,fetch=download,verify=verify_signature,run=None,os_name=None,machine=None,lease_path='/run/machinista-power/maintenance.lock'):
        self.cfg=cfg;self.root=Path(root);self.state=Path(state);self.runtime=Path(runtime);self.uid=uid;self.gid=gid
        self.fetch=fetch;self.verify=verify;self.run=run or self.execute_command
        self.os_name=os_name or self.os_info().get('VERSION_CODENAME','');self.machine=machine or platform.machine()
        self.state.mkdir(parents=True,exist_ok=True);self.lock=threading.Lock();self.latest=None;self.thread=None;self.lease=None;self.lease_path=Path(lease_path)
        self.channel='release';self.current=cfg['current_version'];self.phase='IDLE';self.error='';self.progress=0;self.reboot_required=False;self.checked=None
        try:self.channel=json.loads((self.state/'channel.json').read_text())['channel'];assert self.channel in CHANNELS
        except (OSError,ValueError,KeyError,AssertionError):self.channel='release'
        try:self.current=json.loads((self.state/'installed.json').read_text())['version'];version(self.current)
        except (OSError,ValueError,KeyError):self.current=cfg['current_version']
        self.recover()
    @staticmethod
    def os_info():
        try:return dict(line.split('=',1) for line in Path('/etc/os-release').read_text().replace('"','').splitlines() if '=' in line)
        except OSError:return {}
    def status(self):
        configured=bool(self.cfg.get('repository') and self.cfg.get('public_key'))
        return dict(enabled=self.cfg['enabled'],configured=configured,current=self.current,latest=self.latest['version'] if self.latest else None,
            channel=self.channel,state=self.phase,error=self.error,message=self.error or ('Ready' if configured else 'Update source not configured'),
            progress=self.progress,busy=self.phase in BUSY,available=bool(self.latest and version(self.latest['version'])>version(self.current)),
            notes=self.latest.get('notes','') if self.latest else '',os=self.os_name,kernel=platform.release(),os_included=True,reboot_required=self.reboot_required,checked=self.checked)
    def publish(self,phase=None,progress=None,error=None):
        if phase is not None:self.phase=phase
        if progress is not None:self.progress=progress
        if error is not None:self.error=error
        self.runtime.mkdir(parents=True,exist_ok=True);atomic(self.runtime/'state.json',self.status());atomic(self.state/'status.json',self.status())
    def idle(self):
        try:
            p=self.runtime/'app/status.json';s=json.loads(p.read_text())
            if p.stat().st_uid!=self.uid or not 0<=time.time()-s['updated']<3 or s['busy'] or s['playing']:raise ValueError('Stop playback/recording and finish processing first.')
        except (OSError,KeyError,TypeError):raise ValueError('Application not ready for update.')
    def command(self,op,channel=None,expected=None):
        with self.lock:
            if op=='status':return self.status()
            if not self.cfg['enabled']:raise ValueError('Updates are not enabled in this image edition.')
            if self.phase in BUSY:raise ValueError('An update operation is already running.')
            if op=='channel':
                if channel not in CHANNELS:raise ValueError('Choose beta or release.')
                self.channel=channel;self.latest=None;self.checked=None;atomic(self.state/'channel.json',{'channel':channel});self.publish('IDLE',0,'');return self.status()
            if op not in ('check','install'):raise ValueError('Invalid update operation.')
            if not self.status()['configured']:raise ValueError('GitHub repository and signing key are not configured yet.')
            if op=='install':
                self.idle()
                if not self.status()['available'] or expected!=self.latest['version'] or channel!=self.channel:raise ValueError('Check the selected channel again before installing.')
            if op=='install':
                self.lease=os.fdopen(os.open(self.lease_path,os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW,0o600),'w')
                try:fcntl.flock(self.lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except OSError:self.lease.close();self.lease=None;raise ValueError('A power or update operation is already running.')
            self.publish('CHECKING' if op=='check' else 'DOWNLOADING',0,'')
            self.thread=threading.Thread(target=self.work,args=(op,self.lease if op=='install' else None),daemon=True,name='update-job');self.thread.start()
            return self.status()
    def work(self,op,lease=None):
        try:
            if op=='check':
                base=f"https://raw.githubusercontent.com/{self.cfg['repository']}/{self.channel}/updates/"
                raw=self.fetch(base+'update.json',32768);signature=self.fetch(base+'update.json.sig',1024)
                self.verify(raw,signature,self.cfg['public_key'])
                latest=manifest(raw,self.channel,self.cfg,self.os_name,self.machine)
                if version(self.current)<version(latest['minimum_version']):raise ValueError('Install a newer image before this update.')
                self.latest=latest;self.checked=time.time();self.publish('AVAILABLE' if version(latest['version'])>version(self.current) else 'UP TO DATE',100)
            else:self.install()
        except Exception as e:self.publish('ERROR',error=(self.error+str(e))[:240])
        finally:
            if lease:
                lease.close()
                if self.lease is lease:self.lease=None
    def execute_command(self,args,timeout=1800):
        logfile=self.state/'update.log'
        if logfile.exists() and logfile.stat().st_size>2*1024**2:logfile.unlink()
        with logfile.open('ab') as log:
            env=dict(os.environ,DEBIAN_FRONTEND='noninteractive',NEEDRESTART_MODE='l')
            return subprocess.run(args,check=True,stdout=log,stderr=subprocess.STDOUT,timeout=timeout,env=env)
    def rollback(self,transaction):
        with tarfile.open(self.state/'rollback.tar.gz') as archive:
            for member in archive:
                if member.name in transaction['files']:replace_file(self.root,member.name,archive.extractfile(member).read(),self.uid,self.gid)
        for name in transaction['new']:
            try:remove_file(self.root,name)
            except FileNotFoundError:pass
        if transaction.get('previous_version'):
            self.current=transaction['previous_version'];atomic(self.state/'installed.json',dict(version=self.current))
        os.sync()
    def recover(self):
        path=self.state/'transaction.json'
        if path.exists():
            transaction=json.loads(path.read_text());self.rollback(transaction);path.unlink()
            self.phase='ERROR';self.error='Interrupted update: application restored. OS packages may need repair; see update.log.'
            self.run(['systemctl','start','--no-block','machinista.service'],10)
        else:
            try:previous=json.loads((self.state/'status.json').read_text())
            except (OSError,ValueError):previous={}
            if previous.get('state') in ('SAVING','OS UPDATE','INSTALLING','RESTARTING'):
                self.phase='ERROR';self.error='Interrupted update. Application restart requested; see update.log.'
                self.run(['systemctl','start','--no-block','machinista.service'],10)
    def install(self):
        transaction=None;stopped=False;os_started=False
        try:
            self.idle()
            if shutil.disk_usage(self.root).free<max(2*1024**3,self.latest['artifact']['size']*4):raise ValueError('At least 2 GiB free space is required.')
            artifact=self.latest['artifact'];package=self.state/'download.tar.gz'
            size=self.fetch(artifact['url'],artifact['size'],package)
            if size!=artifact['size'] or hashlib.sha256(package.read_bytes()).hexdigest()!=artifact['sha256']:raise ValueError('Update checksum or size mismatch.')
            self.publish('VALIDATING',20);files=members(package);self.idle()
            with tarfile.open(package) as archive:
                branding=archive.extractfile('app/branding.py').read(65536)
            found=re.search(rb'VERSION\s*=\s*[\'"]([^\'"]+)',branding)
            if not found or found[1].decode()!=self.latest['version']:raise ValueError('Payload version does not match signed manifest.')
            self.run(['runuser','-u','machinista','--','/usr/bin/python3','/usr/local/lib/machinista/update_rpc.py','--root',str(self.root)],10)
            self.old_pid=json.loads((self.runtime/'app/status.json').read_text())['pid']
            self.publish('SAVING',25);self.run(['systemctl','stop','machinista.service'],45);stopped=True
            result=self.run(['systemctl','show','machinista.service','--property=Result','--value'],10) if self.run!=self.execute_command else subprocess.run(['systemctl','show','machinista.service','--property=Result','--value'],check=True,capture_output=True,text=True,timeout=10)
            if result and getattr(result,'stdout',None) and result.stdout.strip()!='success':raise ValueError('Application did not save/stop cleanly.')
            new=[]
            with tarfile.open(self.state/'rollback.tar.gz','w:gz') as backup:
                for name in files+['config/settings.json','projects/current.json']:
                    try:data=read_file(self.root,name)
                    except FileNotFoundError:
                        if name in files:new.append(name)
                        continue
                    import io
                    member=tarfile.TarInfo(name);member.size=len(data);backup.addfile(member,io.BytesIO(data))
            with (self.state/'rollback.tar.gz').open('rb') as f:os.fsync(f.fileno())
            transaction=dict(files=files,new=new,previous_version=self.current);atomic(self.state/'transaction.json',transaction);os.sync()
            self.publish('OS UPDATE',30);os_started=True
            self.run(['apt-get','update'],900)
            self.run(['apt-get','-y','--no-remove','-o','Dpkg::Options::=--force-confold','dist-upgrade'],3600)
            self.publish('INSTALLING',75)
            with tarfile.open(package) as archive:
                for member in archive:
                    if member.isfile():replace_file(self.root,member.name,archive.extractfile(member).read(),self.uid,self.gid)
            os.sync();self.publish('RESTARTING',90);self.run(['systemctl','start','machinista.service'],45)
            self.healthy();self.run(['systemctl','restart','machinista-web.service'],45)
            self.current=self.latest['version'];atomic(self.state/'installed.json',dict(version=self.current,channel=self.channel,installed=time.time()))
            (self.state/'transaction.json').unlink();self.reboot_required=True;self.publish('COMPLETE',100)
        except BaseException:
            if transaction:self.rollback(transaction);(self.state/'transaction.json').unlink(missing_ok=True)
            if stopped:
                self.run(['systemctl','start','machinista.service'],45)
                self.run(['systemctl','restart','machinista-web.service'],45)
            if os_started:self.error='OS packages may already be changed. Application code restored. '
            raise
    def healthy(self):
        deadline=time.monotonic()+35
        while time.monotonic()<deadline:
            try:
                pulse=json.loads((self.runtime/'app/status.json').read_text())
                if 0<=time.time()-pulse['updated']<2 and not pulse['busy'] and pulse.get('pid')!=self.old_pid:return
            except (OSError,ValueError,KeyError):pass
            time.sleep(.5)
        raise ValueError('Updated application did not become ready; restoring previous code.')
