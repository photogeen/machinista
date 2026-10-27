"""Background, data-only SoundFont ingestion into portable native Sounds."""
import copy,hashlib,json,os,re,secrets,shutil,tempfile,threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from app.soundfont import Font,MAX_FILE
from app.sound_library import SoundLibrary,worker_priority,RESERVE,name,folders,tags

class SoundFonts:
 def __init__(self,library):
  self.library=library;self.store=SoundLibrary(library.root);self.base=Path(library.root)/'presets/Sounds/.imports/soundfonts';self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='soundfont-import',initializer=worker_priority);self.guard=threading.Lock();self.future=None;self.last=dict(state='IDLE',sequence=0);self.sequence=0
 def directory(self):
  for p in (Path(self.library.root)/'presets',self.store.folder,self.store.folder/'.imports',self.base):
   if p.is_symlink():raise ValueError('Invalid SoundFont storage.')
   p.mkdir(exist_ok=True)
 def path(self,identity):
  if not isinstance(identity,str) or not re.fullmatch('[0-9a-f]{32}',identity):raise ValueError('Invalid SoundFont ID.')
  self.directory();p=self.base/(identity+'.sf2')
  if p.is_symlink() or not p.is_file():raise FileNotFoundError('SoundFont not found.')
  return p
 def status(self):
  with self.guard:
   if self.future and self.future.done():
    try:self.last.update(self.future.result())
    except Exception as e:self.last.update(state='ERROR',message=str(e))
    self.future=None
   rows=[]
   if self.base.is_dir() and not self.base.is_symlink():
    for p in sorted(self.base.glob('*.json'))[:64]:
     if p.is_symlink() or p.stat().st_size>1024**2:continue
     try:
      d=json.loads(p.read_text());self.path(d['id']);rows.append(d)
     except (OSError,ValueError,KeyError):continue
   return dict(files=rows,job=copy.deepcopy(self.last),busy=self.future is not None or self.last['state']=='UPLOADING')
 def begin(self,state):
  self.status()
  if not self.library.upload_lock.acquire(blocking=False):raise BlockingIOError('Another upload or save is in progress.')
  with self.guard:
   if self.future is not None:self.library.upload_lock.release();raise BlockingIOError('A SoundFont job is already in progress.')
   self.sequence+=1;self.last=dict(state=state,sequence=self.sequence)
 def submit(self,work):
  def guarded():
   try:return work()
   finally:self.library.upload_lock.release()
  try:
   with self.guard:self.future=self.pool.submit(guarded)
  except BaseException:self.library.upload_lock.release();raise
  return {'ok':True,'sequence':self.sequence}
 def upload(self,filename,stream,length):
  if not isinstance(filename,str) or not filename.lower().endswith('.sf2') or '/' in filename or '\\' in filename or len(filename)>240 or any(ord(c)<32 for c in filename):raise ValueError('Choose an uncompressed .sf2 file.')
  if type(length) is not int or not 0<length<=MAX_FILE:raise ValueError('Maximum SoundFont size is 512 MiB.')
  self.begin('UPLOADING');temporary=None
  try:
   self.directory()
   if len(list(self.base.glob('*.sf2')))>=64:raise ValueError('Maximum 64 uploaded SoundFonts. Remove an unused upload first.')
   if shutil.disk_usage(self.base).free<length+RESERVE:raise OSError('Not enough free storage for SoundFont upload.')
   temporary=self.base/('.'+secrets.token_hex(16));digest=hashlib.sha256();remaining=length
   with temporary.open('xb') as out:
    while remaining:
     block=stream.read(min(65536,remaining))
     if not block:raise ValueError('Incomplete SoundFont upload.')
     out.write(block);digest.update(block);remaining-=len(block)
    out.flush();os.fsync(out.fileno())
   identity=digest.hexdigest()[:32]
   def work():
    try:
     with Font(temporary) as font:metadata=dict(id=identity,name=filename[:-4],bytes=length,presets=font.presets)
     destination=self.base/(identity+'.sf2')
     if destination.is_symlink():raise ValueError('Invalid SoundFont destination.')
     if not destination.exists():os.replace(temporary,destination)
     self.store.atomic(self.base/(identity+'.json'),metadata)
     return dict(state='READY',font=identity,message='Choose an instrument to inspect.')
    finally:temporary.unlink(missing_ok=True)
   self.last['state']='PARSING';return self.submit(work)
  except BaseException:
   if temporary is not None:temporary.unlink(missing_ok=True)
   self.last.update(state='ERROR',message='SoundFont upload failed.');self.library.upload_lock.release();raise
 def inspect(self,value):
  p=self.path(value.get('font'));index=value.get('preset');self.begin('ANALYZING')
  def work():
   with Font(p) as f:plan=f.plan(index)
   return dict(state='REVIEW',font=value['font'],preset=index,preview={k:v for k,v in plan.items() if k!='zones'},message='Review mapping and compatibility before importing.')
  return self.submit(work)
 def import_sound(self,value):
  p=self.path(value.get('font'));index=value.get('preset');title=name(value.get('name'));category=folders(value.get('folder',''));labels=tags(value.get('tags',[]));self.begin('IMPORTING')
  def work():
   with Font(p) as f:
    plan=f.plan(index)
    if plan['blockers']:raise ValueError('; '.join(plan['blockers']))
    if plan['warnings'] and value.get('accept_warnings') is not True:raise ValueError('Review and accept the SoundFont compatibility notes before importing.')
    estimated=sum((z['end']-z['start'])*3+44 for z in plan['zones'])
    if estimated>512*1024**2:raise ValueError('Sound exceeds the 512 MiB sample limit.')
    if shutil.disk_usage(self.base).free<estimated*2+RESERVE:raise OSError('Not enough free storage to extract SoundFont samples.')
    # All PCM extraction and Sound creation stays on this low-priority worker.
    with tempfile.TemporaryDirectory(prefix='.sf2-',dir=self.base) as tmp:
     paths={};rows=[]
     for z in plan['zones']:
      key=(z['sample_id'],z['start'],z['end'],z['rate']);identity=hashlib.sha256(repr(key).encode()).hexdigest()[:24]
      if identity not in paths:
       target=Path(tmp)/(identity+'.wav');f.extract(z,target);paths[identity]=target
      row={k:v for k,v in z.items() if k not in ('sample_id','rate','start','end')};row.update(asset={'id':identity},start=0,end=z['end']-z['start']);rows.append(row)
     def opener(ref):return paths[ref['id']].open('rb')
     result=self.store.save(dict(name=title,folder=category,tags=labels,zones=rows,sampler=plan['sampler']),opener)
   self.store.atomic(self.store.bundle(result['id'])/'SoundFont.json',dict(font=value['font'],preset=plan['preset'],warnings=plan['warnings'],native=True))
   return dict(state='DONE',sound=result['id'],message='SoundFont instrument imported as a native sampler Sound.')
  return self.submit(work)
 def delete(self,value):
  p=self.path(value.get('font'));self.begin('DELETING')
  try:
   p.unlink();p.with_suffix('.json').unlink(missing_ok=True);self.last.update(state='IDLE',message='Upload removed. Imported Sounds keep their copied samples.');return {'ok':True}
  finally:self.library.upload_lock.release()
