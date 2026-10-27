"""Optional user-installed VirtualJV configuration, excluded from clean images.

Machinista ships no emulator, ROMs or preparation tool. This UI manages only an
explicitly installed add-on in the user's preset directory.
"""
from pathlib import Path
import hashlib,json,os,subprocess,sys,tempfile,shutil
from app.web_server import filename
HELPER_SHA='4365ce5860aeacfc887b57fbee64a71e8367b28847afa230455dad2d355185d9'
URIS={'urn:machinista:ports:virtualjv','urn:machinista:ports:virtualjv-multi'}
IDENTITIES_SHA='c6a58e410f371494f61548cbdaf78e80abbd77066dad7f1b528d3c4a6aa70d9f'

class VirtualJV:
    def __init__(self,library):self.library=library;self.root=library.root/'presets/virtualjv'
    def installed_bundles(self):
        try:
            from app.lv2_client import request
            return [b for b in request('status').get('bundles',[]) if b.get('status')=='OK' and any(p.get('uri') in URIS for p in b.get('plugins',[]))]
        except (OSError,ValueError,KeyError):return []
    def helper(self,bundles=None):
        candidates=[self.root/'tools/roms.py']
        for bundle in self.installed_bundles() if bundles is None else bundles:
            base=Path(bundle['path']).resolve();helper=base/'configuration/roms.py'
            if helper.resolve().is_relative_to(base):candidates.append(helper)
        for path in candidates:
            identities=path.with_name('rom-identities.json')
            if path.is_file() and not path.is_symlink() and identities.is_file() and not identities.is_symlink():
                if path.stat().st_size<65536 and identities.stat().st_size<65536 and hashlib.sha256(path.read_bytes()).hexdigest()==HELPER_SHA and hashlib.sha256(identities.read_bytes()).hexdigest()==IDENTITIES_SHA:return path
        return None
    def status(self):
        bundles=self.installed_bundles()
        if not bundles:return dict(installed=False,available=False,banks=[],uploads=[],runtime={})
        catalog=self.root/'prepared/catalog.json';data={'banks':[]}
        if catalog.is_file() and not catalog.is_symlink():
            if catalog.stat().st_size>2*1024**2:raise ValueError('ROM catalog is too large.')
            data=json.loads(catalog.read_text())
        raw=self.root/'raw';uploads=[]
        if raw.is_dir():uploads=[dict(name=p.name,bytes=p.stat().st_size) for p in sorted(raw.iterdir()) if p.is_file() and not p.is_symlink()]
        return dict(installed=True,available=self.helper(bundles) is not None,banks=data.get('banks',[]),uploads=uploads,runtime=self.library.sounds.runtime())
    def upload(self,name,stream,length):
        filename(name)
        if Path(name).suffix.lower() not in ('.bin','.rom') or length not in (32768,131072,262144,2097152,8388608):raise ValueError('Expected a complete JV-880 or 2/8 MiB expansion ROM.')
        raw=self.root/'raw';raw.mkdir(parents=True,exist_ok=True)
        if raw.is_symlink():raise ValueError('Invalid ROM directory.')
        if len(list(raw.iterdir()))>=64:raise ValueError('ROM file limit reached.')
        usage=os.statvfs(raw)
        if usage.f_bavail*usage.f_frsize<length+256*1024**2:raise ValueError('Insufficient storage space.')
        target=raw/name;fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        try:
            with os.fdopen(fd,'wb') as out:
                remaining=length
                while remaining:
                    block=stream.read(min(65536,remaining))
                    if not block:raise ValueError('Incomplete ROM upload.')
                    out.write(block);remaining-=len(block)
        except BaseException:target.unlink(missing_ok=True);raise
        return {'ok':True,'message':'ROM saved. Choose Prepare ROMs after uploading the complete set.'}
    def delete(self,name):
        filename(name)
        runtime=self.library.sounds.runtime()
        if not runtime.get('available') or any(runtime.get(k) for k in ('busy','playing','recording')):
            raise ValueError('Stop playback and recording before deleting ROMs.')
        raw=self.root/'raw';target=raw/name;prepared=self.root/'prepared'
        if raw.is_symlink() or target.is_symlink() or not target.is_file() or target.suffix.lower() not in ('.bin','.rom'):
            raise ValueError('ROM upload not found.')
        if prepared.is_symlink():raise ValueError('Invalid prepared ROM directory.')
        helper=self.helper();installed=False
        with tempfile.TemporaryDirectory(prefix='.rom-delete-',dir=self.root) as temporary:
            work=Path(temporary);removed=work/name;old=work/'old-prepared';fresh=work/'prepared'
            target.replace(removed)
            try:
                if helper is not None:
                    result=subprocess.run([sys.executable,str(helper),str(raw),str(fresh)],capture_output=True,text=True,timeout=60)
                    if result.returncode:
                        if 'Missing/unsupported base ROMs:' not in result.stderr:
                            raise ValueError((result.stderr or result.stdout or 'ROM update failed.')[-2000:])
                        shutil.rmtree(fresh,ignore_errors=True)
                    else:installed=True
                if prepared.exists():prepared.replace(old)
                if installed:fresh.replace(prepared)
            except BaseException:
                if old.exists():
                    if prepared.exists():shutil.rmtree(prepared)
                    old.replace(prepared)
                removed.replace(target)
                raise
        return {'ok':True,'message':'ROM deleted. Remaining banks rebuilt.' if installed else 'ROM deleted. Prepared banks cleared; restore the base ROM set and choose Prepare ROMs to use the instrument.'}

    def prepare(self):
        runtime=self.library.sounds.runtime()
        if not runtime.get('available') or runtime.get('busy') or runtime.get('playing') or runtime.get('recording'):raise ValueError('Stop playback and recording before preparing ROMs.')
        helper=self.helper()
        if helper is None:raise ValueError('Install the separate VirtualJV add-on first.')
        result=subprocess.run([sys.executable,str(helper),str(self.root/'raw'),str(self.root/'prepared')],capture_output=True,text=True,timeout=60)
        if result.returncode:raise ValueError((result.stderr or result.stdout or 'ROM preparation failed.')[-2000:])
        return {'ok':True,'message':'ROMs prepared. Available banks and patches refreshed.'}
