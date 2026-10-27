"""User chord storage; no imports, scans or file reads in controller rendering."""
from contextlib import contextmanager
import json
import os
import secrets
import stat
import threading
from pathlib import Path
from app.chords import MAX_BYTES,normalize,parse


class ChordLibrary:
    def __init__(self,root):self.samples=Path(root)/'samples'

    @contextmanager
    def directory(self):
        base=os.open(self.samples,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            try:os.mkdir('.chords',0o700,dir_fd=base)
            except FileExistsError:pass
            fd=os.open('.chords',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=base)
        finally:os.close(base)
        try:yield fd
        finally:os.close(fd)

    @staticmethod
    def identity(value):
        if len(value)!=32 or any(c not in '0123456789abcdef' for c in value):raise ValueError('Invalid chord preset ID.')
        return value+'.json'

    def list(self):
        rows=[]
        with self.directory() as fd:
            for name in sorted(os.listdir(fd))[:512]:
                try:
                    self.identity(name[:-5])
                    f=os.open(name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=fd)
                    with os.fdopen(f,'rb') as stream:
                        info=os.fstat(stream.fileno())
                        if not stat.S_ISREG(info.st_mode) or info.st_size>MAX_BYTES:continue
                        value=normalize(json.loads(stream.read(MAX_BYTES+1)))
                    rows.append(dict(id=name[:-5],preset=value))
                except (OSError,ValueError,TypeError,RecursionError):continue
        return sorted(rows,key=lambda row:(row['preset']['name'].casefold(),row['id']))

    def save(self,preset,identity=None):
        value=normalize(preset);identity=identity or secrets.token_hex(16);name=self.identity(identity)
        payload=json.dumps(value,ensure_ascii=False).encode()
        if len(payload)>MAX_BYTES:raise ValueError('Preset exceeds 1 MiB.')
        with self.directory() as fd:
            tmp='.'+secrets.token_hex(16)
            try:
                f=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=fd)
                with os.fdopen(f,'wb') as stream:stream.write(payload);stream.flush();os.fsync(stream.fileno())
                os.replace(tmp,name,src_dir_fd=fd,dst_dir_fd=fd);os.fsync(fd)
            finally:
                try:os.unlink(tmp,dir_fd=fd)
                except FileNotFoundError:pass
        return {'id':identity,'preset':value}

    def delete(self,identity):
        with self.directory() as fd:os.unlink(self.identity(identity),dir_fd=fd);os.fsync(fd)
        return {'ok':True}


class ChordCatalog:
    """Worker owns disk access. Application thread receives immutable snapshots."""
    def __init__(self,root):
        self.library=ChordLibrary(root);self.rows=();self.stop=threading.Event()
        self.thread=threading.Thread(target=self.run,name='chord-catalog',daemon=True);self.thread.start()
    def run(self):
        while not self.stop.is_set():
            try:self.rows=tuple(self.library.list())
            except OSError:pass
            self.stop.wait(2)
    def close(self):self.stop.set();self.thread.join(3)
