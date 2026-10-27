"""Background recovery checkpoints; never clear undo or replace explicit saves."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import json
import re
import shutil
import threading
import time
import uuid
from app.assets import relative_assets,resolve_assets
from app.layout import bus_targets
from app.storage import _save_json,load_json


def identity(project):
    value=project.get('file_id','CURRENT')
    return value if isinstance(value,str) and re.fullmatch(r'PROJECT-[0-9]{4}',value) else 'CURRENT'

def stamp(path):
    try:return Path(path).stat().st_mtime_ns
    except FileNotFoundError:return 0

def recover(root,project,baseline,validate):
    root=Path(root);path=root/'projects/.autosave'/(identity(project)+'.json')
    try:
        # Explicit saves always win. Recovery never overwrites those files.
        saved=load_json(path,{})
        if not isinstance(saved,dict) or not isinstance(saved.get('baseline'),dict) or not isinstance(saved.get('project'),dict):return project,False
        if saved.get('baseline',{}).get(Path(baseline).name)!=stamp(baseline):return project,False
        candidate=saved['project']
        if identity(candidate)!=identity(project):return project,False
        candidate=validate(resolve_assets(candidate,root/'projects'))
        return candidate,True
    except (OSError,ValueError,KeyError,TypeError):return project,False

class Autosave:
    def __init__(self,root,interval=60):
        self.root=Path(root);self.interval=interval;self.next=None;self.future=None
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='project-autosave')
        self.last=None;self.closing=threading.Event()
    def write(self,project,checkpoint,required,baseline,protected=()):
        deadline=time.monotonic()+15
        # State files are written by the existing native host's non-render path.
        # New unique paths ensure no older state can satisfy this checkpoint.
        while not all(p.is_file() for p in required):
            if self.closing.is_set():return
            if time.monotonic()>=deadline:raise OSError('Plug-in state was not saved')
            time.sleep(.05)
        _save_json(checkpoint,dict(project=relative_assets(project,self.root/'projects'),baseline=baseline))
        # Only prune our own old state snapshots, retaining current live paths
        # (including a recovered state) and the two newest recovery generations.
        folder=checkpoint.parent/'states'/checkpoint.stem
        if folder.is_dir():
            candidates=sorted((p for p in folder.iterdir() if p.is_dir() and not p.is_symlink()),key=lambda p:p.stat().st_mtime_ns,reverse=True)
            for old in candidates[2:]:
                if not any(Path(path).is_relative_to(old) for path in protected):shutil.rmtree(old)
    def poll(self,app,audio,now,busy=False):
        if self.future is not None and self.future.done():
            future,self.future=self.future,None
            try:future.result()
            except (OSError,ValueError):app.message='AUTOSAVE FAILED';self.last=None
        if app.settings.get('autosave','ON')!='ON':self.next=None;return
        if self.next is None:self.next=now+self.interval
        if now<self.next or busy or self.future is not None:return
        self.next=now+self.interval
        project=app.project_for_save()
        fingerprint=hashlib.sha256(json.dumps(project,sort_keys=True).encode()).hexdigest()
        if self.last==(app.project_generation,fingerprint):return
        key=identity(project);base=self.root/'projects/.autosave'
        state=base/'states'/key/uuid.uuid4().hex
        required=[];protected=[]
        for bus,target in bus_targets(project).items():
            for index,plugin in enumerate(target.get('plugins',[])):
                if plugin.get('state'):protected.append(plugin['state'])
                path=state/f'{bus}-{index}'/'state.ttl';plugin['state']=str(path);required.append(path)
        if required:audio.save_plugin_state(project)
        baseline={'current.json':stamp(app.project_path)}
        named=app.active_project_file()
        if named is not None:baseline[named.name]=stamp(named)
        self.future=self.pool.submit(self.write,project,base/(key+'.json'),required,baseline,protected)
        self.last=(app.project_generation,fingerprint)
    def close(self):
        self.closing.set();self.pool.shutdown(wait=True,cancel_futures=True)
