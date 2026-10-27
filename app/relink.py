"""Explicit missing-WAV recovery with bounded background searches."""
import copy
import os
import time
import wave
from pathlib import Path
from app.assets import sample_references
from app.browser import Browser,Source


def sample_requirements(project):
    rows={}
    for group,bank in enumerate(project['groups']):
        for pad,track in enumerate(bank['pads']):
            objects=[track,track.get('slice_source',{})]+track.get('zones',[])
            for obj in objects:
                path=obj.get('sample')
                if not path:continue
                row=rows.setdefault(path,dict(path=path,end=0,slots=[]))
                row['end']=max(row['end'],*(obj.get(k,0) for k in ('end','selection_end','loop_end')))
                if (group,pad) not in row['slots']:row['slots'].append((group,pad))
    return list(rows.values())


def missing_samples(rows):
    return [row for row in rows if not Path(row['path']).is_file()]


def validate_replacement(row,path):
    path=Path(path).resolve();before=path.stat()
    with wave.open(str(path),'rb') as wav:
        if wav.getcomptype()!='NONE' or wav.getsampwidth() not in (1,2,3,4) or wav.getnchannels() not in (1,2):raise ValueError('UNSUPPORTED WAV')
        if wav.getnframes()<row['end']:raise ValueError('SAMPLE TOO SHORT')
        if wav.getframerate()<=0:raise ValueError('INVALID SAMPLE RATE')
        if row['end']:
            wav.setpos(row['end']-1)
            if len(wav.readframes(1))!=wav.getnchannels()*wav.getsampwidth():raise ValueError('TRUNCATED WAV')
    after=path.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('FILE CHANGED: RETRY')
    return dict(path=str(path),size=after.st_size,stamp=after.st_mtime_ns)


def find_replacements(row,roots,max_files=50000,max_seconds=15):
    name=Path(row['path']).name.casefold();found=[];seen=set();count=0;started=time.monotonic();limited=False
    for root in roots:
        root=Path(root).resolve()
        if not root.is_dir():continue
        for directory,dirs,files in os.walk(root,followlinks=False):
            if time.monotonic()-started>max_seconds:limited=True;break
            dirs[:]=sorted(d for d in dirs if not d.startswith('.') and not (Path(directory)/d).is_symlink())
            for filename in sorted(files):
                count+=1
                if count>max_files or time.monotonic()-started>max_seconds:limited=True;break
                if count%128==0:time.sleep(0)
                if filename.casefold()!=name:continue
                path=(Path(directory)/filename).resolve()
                if not path.is_relative_to(root) or path in seen:continue
                seen.add(path)
                try:validate_replacement(row,path)
                except (OSError,ValueError,wave.Error,EOFError):continue
                found.append(str(path))
                if len(found)>=64:limited=True;break
            if limited:break
        if limited:break
    return dict(paths=sorted(found,key=str.casefold),limited=limited)


class Relink:
    def init_relink(self):
        self.missing_rows=[];self.missing_index=0;self.relink_paths=[];self.relink_index=0
        self.relink_context=None;self.relink_busy=False;self.relink_browser=None;self.relink_row=None
        self.relink_serial=getattr(self,'relink_serial',0)+1
    def relink_roots(self):
        return list(dict.fromkeys([str(self.samples),str(self.root/'projects'),str(self.root/'presets')]+[str(s.path) for s in self.browser.sources]))
    def request_missing_check(self,show=False):
        self.relink_serial+=1;self.relink_busy=True
        context=dict(generation=self.project_generation,revision=self.revision,serial=self.relink_serial,show=show)
        self.relink_context=context
        if show:self.page='MISSING SAMPLES';self.missing_rows=[];self.missing_index=0
        self.actions.append(('missing_check',(context,sample_requirements(self.project))))
    def relink_valid(self,context):
        return context['generation']==self.project_generation and context['revision']==self.revision and context['serial']==self.relink_serial
    def finish_missing_check(self,context,rows):
        if not self.relink_valid(context):
            if context['serial']==self.relink_serial:self.relink_busy=False;self.message='PROJECT CHANGED: RESCAN'
            return
        self.missing_rows=rows;self.missing_index=min(self.missing_index,max(0,len(rows)-1));self.relink_busy=False
        self.message=f'{len(rows)} SAMPLES MISSING' if rows else 'ALL SAMPLES FOUND'
    def selected_missing(self):
        return self.missing_rows[min(self.missing_index,len(self.missing_rows)-1)] if self.missing_rows else None
    def open_relink_browser(self):
        self.relink_browser=Browser(self.samples)
        self.relink_browser.refresh([Source('PROJECT ASSETS',self.root/'projects'),Source('PRESET ASSETS',self.root/'presets')]+list(self.browser.sources[1:]))
        self.relink_browser.directory=None;self.page='RELINK BROWSE'
    def request_relink_search(self):
        row=self.selected_missing()
        if not row:return
        if self.relink_context is None or not self.relink_valid(self.relink_context):self.request_missing_check(True);return
        self.relink_row=copy.deepcopy(row);self.relink_paths=[];self.relink_index=0;self.relink_busy=True;self.page='RELINK RESULTS'
        self.actions.append(('relink_search',(copy.deepcopy(self.relink_context),self.relink_row,self.relink_roots())))
    def finish_relink_search(self,context,result):
        if not self.relink_valid(context):self.relink_busy=False;self.message='PROJECT CHANGED: RESCAN';return
        self.relink_busy=False;self.relink_paths=result['paths'];self.relink_index=0
        self.message='SEARCH LIMIT: USE BROWSE' if result['limited'] else 'CHOOSE FILE' if self.relink_paths else 'NO MATCH: USE BROWSE'
    def choose_relink(self,path):
        row=self.relink_row
        if row is None:return
        context=copy.deepcopy(self.relink_context)
        self.confirm('RELINK ALL REFERENCES?',lambda:self.request_relink_apply(context,row,path))
    def request_relink_apply(self,context,row,path):
        if self.playing or self.recording or self.capture_started is not None or self.capture_armed:self.message='STOP RECORD/PLAY FIRST';return
        if not self.relink_valid(context):self.message='PROJECT CHANGED: RESCAN';return
        self.relink_busy=True
        self.actions.append(('relink_validate',(context,copy.deepcopy(row),str(path))))
    def finish_relink_apply(self,context,row,result):
        self.relink_busy=False
        if not self.relink_valid(context):self.message='PROJECT CHANGED: RESCAN';return
        if self.playing or self.recording or self.capture_started is not None or self.capture_armed:self.message='TRANSPORT STARTED: CANCELED';return
        if Path(row['path']).is_file():self.message='ORIGINAL AVAILABLE: RESCAN';return
        stat=Path(result['path']).stat()
        if (stat.st_size,stat.st_mtime_ns)!=(result['size'],result['stamp']):self.message='FILE CHANGED: RETRY';return
        candidate=self.project_for_save();changed=[]
        for g,bank in enumerate(candidate['groups']):
            for p,track in enumerate(bank['pads']):
                matched=False
                for obj in [track,track.get('slice_source',{})]+track.get('zones',[]):
                    if obj.get('sample')==row['path']:obj['sample']=result['path'];matched=True
                if matched:changed.append((g,p))
        if not changed:self.message='NO MATCHING REFERENCES';return
        from app.model import validate_project
        validate_project(candidate);self.automation_restore();self.remember();self.project=candidate
        for g,p in changed:self.actions.append(('load',(g,p,copy.deepcopy(candidate['groups'][g]['pads'][p]))))
        self.request_missing_check(True);self.message='SAMPLE RELINKED: SAVE PROJECT'
    def relink_button(self,name,pressed):
        if not pressed or self.page not in ('MISSING SAMPLES','RELINK RESULTS','RELINK BROWSE'):return False
        if name=='F1':
            if self.page=='MISSING SAMPLES':self.page='PROJECT MANAGE'
            elif self.page=='RELINK RESULTS':self.page='MISSING SAMPLES'
            else:self.relink_browser.up()
        elif name=='F3':
            if self.page=='RELINK BROWSE':self.page='MISSING SAMPLES'
            else:
                row=self.selected_missing() if self.page=='MISSING SAMPLES' else self.relink_row
                if row:self.relink_row=copy.deepcopy(row);self.open_relink_browser()
        elif name in ('F2','ENTER','ENCODER PUSH'):
            if self.relink_busy:return True
            if self.page=='MISSING SAMPLES':
                if self.missing_rows:self.request_relink_search()
                else:self.request_missing_check(True)
            elif self.page=='RELINK RESULTS':
                if self.relink_paths:self.choose_relink(self.relink_paths[self.relink_index])
            else:
                try:path=self.relink_browser.open()
                except OSError:self.message='MEDIA REMOVED';return True
                if path:self.choose_relink(path)
        else:return False
        return True
    def relink_rotate(self,delta):
        if self.page=='MISSING SAMPLES':self.missing_index=max(0,min(max(0,len(self.missing_rows)-1),self.missing_index+delta))
        elif self.page=='RELINK RESULTS':self.relink_index=max(0,min(max(0,len(self.relink_paths)-1),self.relink_index+delta))
        elif self.page=='RELINK BROWSE':self.relink_browser.index=max(0,min(max(0,len(self.relink_browser.entries())-1),self.relink_browser.index+delta))
        else:return False
        return True
