"""Filesystem browser with SD sample library and dynamically mounted USB roots."""
from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class Source:
    name: str
    path: Path
    identity: str = ''
    read_only: bool = False


class Browser:
    def __init__(self, samples, internal_sources=()):
        self.samples = Path(samples)
        self.internal_sources = tuple(internal_sources)
        self.sources = [Source('SD CARD', self.samples)]
        self.directory = self.samples
        self.index = 0
        self.prehear = False
        self.started = False
        self.error = ''

    def refresh(self, sources):
        self.sources = [Source('SD CARD', self.samples)]+[source for source in self.internal_sources if source.path.is_dir()]+list(sources)
        if self.directory is not None:
            root = self.current_root()
            if root is None or not self.directory.is_dir():
                self.directory = None
                self.index = 0
                self.error = 'MEDIA REMOVED'

    def current_root(self):
        if self.directory is None:
            return None
        resolved = self.directory.resolve()
        roots=[source.path.resolve() for source in self.sources if resolved.is_relative_to(source.path.resolve())]
        return max(roots,key=lambda p:len(p.parts)) if roots else None

    def entries(self):
        if self.directory is None:
            return [source.path for source in self.sources]
        root = self.current_root()
        if root is None:
            self.directory, self.index = None, 0
            return [source.path for source in self.sources]
        result = []
        try:
            for path in self.directory.iterdir():
                if path.name.startswith('.') or not path.resolve().is_relative_to(root):
                    continue
                if path.is_dir() and (path/'Preset.json').is_file() and not (path/'Preset.json').is_symlink():result.append(path/'Preset.json')
                elif path.is_dir() or path.suffix.lower() in ('.wav','.mp3','.sound'):result.append(path)
            self.error = ''
        except OSError:
            self.error = 'FOLDER UNAVAILABLE'
        return sorted(result, key=lambda p: (not p.is_dir(), p.name.casefold()))

    def label(self, path):
        if self.directory is None:
            return next(source.name for source in self.sources if source.path == path)
        if path.name=='Preset.json':return path.parent.name
        if path.suffix.lower()=='.sound':return path.stem
        return ('/' if path.is_dir() else '')+path.name

    def title(self):
        if self.directory is None:
            return 'SD / USB'
        root = self.current_root()
        if root is None:
            return 'SD / USB'
        source = next(s for s in self.sources if s.path.resolve() == root)
        relative = self.directory.resolve().relative_to(root)
        return source.name if str(relative) == '.' else str(relative)

    def up(self):
        child=self.directory
        if self.directory is not None:
            root = self.current_root()
            self.directory = None if root == self.directory.resolve() else self.directory.parent
        entries=self.entries()
        self.index=entries.index(child) if child in entries else 0

    def selected(self):
        entries = self.entries()
        self.index = min(self.index, max(0, len(entries)-1))
        return entries[self.index] if entries else None

    def locate(self, sample):
        """Focus an existing sample within a currently available source, without loading."""
        if not sample:
            return 'NO SAMPLE'
        try:
            path = Path(sample).resolve()
            if not path.is_file():
                return 'SAMPLE MISSING'
            if not any(path.is_relative_to(source.path.resolve()) for source in self.sources):
                return 'SOURCE UNAVAILABLE'
            # Do not change the user's current folder when the target is hidden,
            # unsupported or no longer visible in a freshly enumerated directory.
            probe = Browser(self.samples)
            probe.sources = self.sources
            probe.directory = path.parent
            entries = probe.entries()
            index = next((i for i, entry in enumerate(entries) if entry.resolve() == path), None)
            if index is None:
                return 'SAMPLE UNAVAILABLE'
            self.directory, self.index = path.parent, index
            self.started, self.error = True, ''
            return ''
        except (OSError, RuntimeError):
            return 'SOURCE UNAVAILABLE'

    def open(self):
        path = self.selected()
        if path is None:
            return None
        if path.is_dir():
            self.directory, self.index = path, 0
            return None
        # Verify again at load time; directory state may change on hotplug.
        root = self.current_root()
        if root is None or not path.resolve().is_relative_to(root):
            raise OSError('sample is outside its source')
        return path


def mount_identities(path=Path('/proc/self/mountinfo')):
    def unescape(value):
        for code,char in (('\\040',' '),('\\011','\t'),('\\012','\n'),('\\134','\\')):value=value.replace(code,char)
        return value
    result={}
    try:
        for line in path.read_text().splitlines():
            left,right=line.split(' - ',1);fields=left.split();other=right.split()
            if len(fields)<6 or len(other)<2:continue
            result[unescape(fields[4])]=(json.dumps([fields[0],fields[2],fields[3],other[0],unescape(other[1])]),'ro' in fields[5].split(','))
    except (OSError,ValueError):pass
    return result


def mounted_sources(manifest=Path('/run/maschineos-media.json'),mountinfo=Path('/proc/self/mountinfo')):
    try:
        rows=json.loads(manifest.read_text());identities=mount_identities(mountinfo)
        return [Source('USB '+row['name'],Path(row['path']),json.dumps([row.get('uuid',''),identities[row['path']][0]]) if row['path'] in identities else '',identities.get(row['path'],('',True))[1]) for row in rows
                if Path(row['path']).is_dir() and any(Path(row['path']).is_relative_to(base)
                    for base in ('/media','/mnt','/run/media'))]
    except (OSError,ValueError,KeyError,TypeError):return []
