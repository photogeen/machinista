"""Pinned export directories and removable-media identity checks, off the UI thread."""
import os
from pathlib import Path
from app.browser import mounted_sources


class ExportLocation:
    def __init__(self,root,request):
        self.media=request.get('destination');self.fd=None;self.root_fd=None
        self.root=Path(self.media['path']) if self.media else Path(root)
        try:
            self.verify()
            self.root_fd=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            info=os.fstat(self.root_fd);self.signature=(info.st_dev,info.st_ino)
            self.verify()
            if os.fstatvfs(self.root_fd).f_flag&os.ST_RDONLY:raise ValueError('USB READ ONLY' if self.media else 'SD READ ONLY')
            fd=os.dup(self.root_fd)
            try:
                for name in (('Machinista','exports') if self.media else ('exports',)):
                    try:os.mkdir(name,dir_fd=fd)
                    except FileExistsError:pass
                    child=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
                    os.fsync(fd);os.close(fd);fd=child
                self.fd=fd;fd=None
            finally:
                if fd is not None:os.close(fd)
            self.actual=self.root/('Machinista/exports' if self.media else 'exports')
            # Linux child renderers address the parent's pinned directory, never a replacement mount.
            self.base=Path(f'/proc/{os.getpid()}/fd/{self.fd}') if Path('/proc/self/fd').is_dir() else self.actual
            self.verify()
        except Exception:
            self.close();raise
    def verify(self):
        if self.media:
            if not self.media.get('identity') or not any(str(s.path)==self.media['path'] and s.identity==self.media['identity'] for s in mounted_sources()):raise ValueError('USB REMOVED OR CHANGED')
            if self.root_fd is not None:
                try:
                    info=self.root.stat()
                    if (info.st_dev,info.st_ino)!=self.signature:raise ValueError('USB REMOVED OR CHANGED')
                except OSError as error:raise ValueError('USB REMOVED OR CHANGED') from error
    def result(self,name):return self.actual/name
    def close(self):
        for key in ('fd','root_fd'):
            value=getattr(self,key,None)
            if value is not None:os.close(value);setattr(self,key,None)
