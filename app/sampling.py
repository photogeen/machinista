"""Sampling workspace: NI-style held NAV pages and explicit sample removal."""
import copy
import json
from pathlib import Path
from app.assets import sample_references,resolve_assets
import time
import wave

PAGES = ('SAMPLING', 'SAMPLE EDIT', 'CHOP', 'ZONE', 'AUTOSAMPLER')
LABELS = ('RECORD', 'EDIT', 'SLICE', 'ZONE', 'AUTO')
CAPTURE_FIELDS=('source','input','mode','threshold')
CAPTURE_DEFAULTS={'source':'EXT STEREO','input':'IN 1','mode':'DETECT','bars':1,'threshold':-24,'monitor':False}


from app.autosampler_ui import AutosamplerUI
from app.audio_loop import AudioLoops

class Sampling(AudioLoops,AutosamplerUI):
    def commit_sampling_nav(self):
        target=PAGES[self.sampling_nav]
        if target==getattr(self,'sampling_nav_origin',None):self.page=target
        else:self.open_sampling_page(target)

    def capture_actions(self):
        if self.capture_started is not None:return ('STOP','CANCEL','','')
        if self.capture_armed:return ('TRIGGER' if (getattr(self,'capture_job',None) or {}).get('options',self.capture_options())['mode']=='DETECT' else 'WAIT','CANCEL','','')
        history=self.record_history.get((self.group,self.pad),[])
        cursor=min(len(history)-1,max(-1,self.record_cursor.get((self.group,self.pad),len(history)-1)))
        return ('START','DELETE' if self.track().get('sample') else '',
                'PREV' if cursor>0 else '', 'NEXT' if 0<=cursor<len(history)-1 else '')

    def open_sampling_page(self,page):
        self.page=page
        if page=='AUTOSAMPLER':self.auto_setup()
        if page=='CHOP':self.prepare_slice_editor()
        elif page in ('SAMPLE EDIT','ZONE') and self.track().get('zones'):
            self.sync_zone()
            if page=='SAMPLE EDIT':
                self.track().update(selection_start=self.track()['start'],selection_end=self.track()['end'])

    def capture_options(self):
        options=self.project.setdefault('sampling',{})
        source=options.get('source')
        if source in ('EXT LEFT','EXT RIGHT'):options.update(source='EXT MONO',input='IN 1 L' if source=='EXT LEFT' else 'IN 1 R')
        elif source in ('GROUP','MASTER'):options.update(source='INTERNAL',input=f'GROUP {self.group}' if source=='GROUP' else 'MASTER')
        if options.get('mode')=='MANUAL':options['mode']='DETECT'
        for key,value in CAPTURE_DEFAULTS.items():options.setdefault(key,value)
        if options.get('bars') in (32,64):options['bars']=16
        if options['source']=='INTERNAL':options['monitor']=False
        return options

    def capture_fields(self):
        if getattr(self,'capture_section',0) and self.capture_options()['source']!='INTERNAL':return ('monitor',)
        return ('source','input','mode','bars' if self.capture_options()['mode'] in ('SYNC','LOOP') else 'threshold')

    def capture_inputs(self):
        source=self.capture_options()['source']
        channels=self.audio.input_channels if self.audio and self.audio.capture else 2
        if source=='INTERNAL':return tuple(f'GROUP {i}' for i in range(len(self.project['groups'])))+('MASTER',)+tuple(f'SOUND {g} {p}' for g in range(len(self.project['groups'])) for p in range(16))
        if source=='EXT MONO':return (('IN 1 L',) if channels==1 else ('IN 1 L','IN 1 R'))+tuple(f'IN {i+1}' for i in range(2,channels))
        return ('IN 1',)+tuple(f'IN {i+1}/{i+2}' for i in range(2,channels-1,2))

    def capture_source_label(self):
        options=self.capture_options();value=options['input']
        if value.startswith('SOUND '):
            _,g,p=value.split();return f'SOUND {self.group_name(int(g))}:{int(p)+1:02}'
        return 'GROUP '+chr(65+int(value.split()[1])%8)+(str(int(value.split()[1])//8+1) if int(value.split()[1])>=8 else '') if value.startswith('GROUP ') else value


    def wave_view(self):
        if self.page not in ('SAMPLE EDIT','CHOP'):
            self.wave_view_active=False
        return self.wave_view_active

    def wave_bounds(self, frames):
        if self.wave_sample != self.track()['sample']:
            self.wave_sample=self.track()['sample'];self.wave_zoom=self.wave_offset=0
        focus=getattr(self,'slice_wave_focus',None)
        if focus is not None:
            self.slice_wave_focus=None
            group,pad,path,index=focus
            if self.page=='CHOP' and self.slice_edit and (group,pad,path)==(self.group,self.pad,self.track()['sample']):
                ranges=self.slice_ranges()
                if 0<=index<len(ranges):
                    start,end=ranges[index]
                    size=max(min(120,frames),frames>>self.wave_zoom)
                    # At close zoom keep the chosen cut in view with context
                    # on both sides; at overview zoom retain the whole slice.
                    anchor=(end if self.slice_focus_end else start) if end-start>=size else (start+end)//2
                    self.wave_offset=anchor-size//2
        size=max(min(120,frames),frames >> self.wave_zoom)
        self.wave_offset=max(0,min(max(0,frames-size),self.wave_offset))
        return self.wave_offset,self.wave_offset+size

    def wave_control(self, slot):
        if not self.wave_selected:return
        if not self.track()['sample']:self.message='NO SAMPLE';return
        with wave.open(self.track()['sample'],'rb') as wav:frames=wav.getnframes()
        first,last=self.wave_bounds(frames);size=last-first
        if slot in (1,5):
            old_zoom=self.wave_zoom
            self.wave_zoom=max(0,min(16,self.wave_zoom+(1 if slot==5 else -1)))
            new_size=max(min(120,frames),frames >> self.wave_zoom)
            if new_size==size:self.wave_zoom=old_zoom;return
            track=self.track()
            if self.page=='CHOP':
                ranges=self.slice_ranges();a,b=ranges[min(self.slice_index,len(ranges)-1)]
                anchor=(a+b)//2
            else:
                key=('selection_' if self.range_page else '')+('start' if self.sample_field==0 else 'end')
                anchor=track.get(key,track['start' if self.sample_field==0 else 'end'])
            if not first<=anchor<=last:anchor=(first+last)//2
            self.wave_offset=max(0,min(frames-new_size,anchor-new_size//2))
        elif slot in (0,2):
            self.wave_offset+=(-1 if slot==0 else 1)*max(1,size//4)
        self.wave_bounds(frames)

    def sampling_button(self, name, pressed):
        if self.audio_tool_button(name,pressed):return True
        if self.page=='SAMPLING' and pressed and name in ('NAV LEFT','NAV RIGHT'):
            self.capture_field=max(0,min(len(self.capture_fields())-1,self.capture_field+(-1 if name=='NAV LEFT' else 1)));return True

        if name=='VIEW' and self.page in ('SAMPLE EDIT','CHOP') and not self.shift:
            if pressed:
                if self.wave_view_active and self.wave_view_pinned:
                    self.wave_view_active=False
                else:
                    self.wave_view_active=True
                    self.wave_view_pinned='VIEW' in self.pinned_modes
            elif not self.wave_view_pinned:self.wave_view_active=False
            return True
        if self.wave_view():
            if pressed and name=='MAIN' and 'VIEW' in self.held_buttons:
                self.pin_view();self.wave_view_pinned='VIEW' in self.pinned_modes;return True
            if pressed and name=='F2':self.wave_selected=True;return True
            if pressed and name in ('NAV LEFT','NAV RIGHT'):
                self.view_field=int(name=='NAV RIGHT');return True
            if name in ('F1','F3'):return True
            if pressed and name in ('NAV','SAMPLING','BROWSE','MAIN'):
                self.wave_view_active=self.wave_view_pinned=False

        if name == 'NAV' and self.page in PAGES+('SAMPLING NAV',):
            if pressed:
                if self.page in PAGES:self.sampling_nav_origin=self.page
                self.sampling_nav = PAGES.index(self.page) if self.page in PAGES else self.sampling_nav
                self.page = 'SAMPLING NAV'
            elif self.page == 'SAMPLING NAV':
                self.commit_sampling_nav()
            return True
        if self.auto_ui_button(name,pressed):return True
        if not pressed:return False
        if self.page=='SAMPLING' and self.capture_started is None and not self.capture_armed and not self.shift and name in ('F2','F3'):
            history=self.record_history.get((self.group,self.pad),[])
            if history:
                index=max(0,min(len(history)-1,self.record_cursor.get((self.group,self.pad),len(history)-1)+(-1 if name=='F2' else 1)))
                self.record_cursor[(self.group,self.pad)]=index;self.remember()
                for key in ('slices','slice_source','slice_mode','slice_committed','slice_manual'):self.track().pop(key,None)
                self.track().update(copy.deepcopy(history[index]));self.actions.append(('load',(self.group,self.pad,copy.deepcopy(self.track()))))
            return True
        if self.page=='SAMPLING' and self.capture_armed and name in ('F1','F2'):
            if name=='F1' and (self.capture_job or {}).get('options',self.capture_options())['mode']=='DETECT':self.actions.append(('capture_trigger',None))
            elif name=='F2':self.actions.append(('capture_cancel',None));self.capture_armed=False
            return True
        if self.page=='STRETCH':
            if name in ('NAV LEFT','NAV RIGHT'):self.sample_field=int(name=='NAV RIGHT');return True
            if name=='F2':self.actions.extend([('preview_stop',None),('process','STRETCH')]);self.page='SAMPLE EDIT';return True
            if name=='F3':self.actions.append(('preview_stop',None));self.page='SAMPLE EDIT';return True
            return name in ('F1','ENTER')
        if self.page == 'SAMPLING NAV':
            if name in ('F1','F2','F3'):
                self.sampling_nav=int(name[1])-1
            elif name in ('NAV LEFT','NAV RIGHT'):
                if self.sampling_nav==0:
                    self.capture_section=int(name=='NAV RIGHT' and self.capture_options()['source']!='INTERNAL');self.capture_field=0
                elif self.sampling_nav==2:
                    self.slice_section=int(name=='NAV RIGHT' and self.slice_mode=='DETECT');self.slice_field=0
                elif self.sampling_nav==3:
                    self.zone_page=max(0,min(4,self.zone_page+(-1 if name=='NAV LEFT' else 1)));self.zone_field=0
                elif self.sampling_nav==4:
                    self.auto_setup();self.auto_field=max(0,min(23,self.auto_field+(-8 if name=='NAV LEFT' else 8)))
                else:self.range_page=int(name=='NAV RIGHT')
            elif name in ('ENTER','ENCODER PUSH'):
                self.commit_sampling_nav()
            elif name == 'SAMPLING':self.page=self.control_home()
            return True
        if self.page in ('SAMPLING','SAMPLE EDIT') and self.shift and name=='F3':
            if self.capture_started is not None or self.capture_armed:
                self.message='STOP RECORDING FIRST'
            elif self.track()['sample']:
                self.sample_delete_index=0;self.sample_delete_origin=self.page;self.page='SAMPLE DELETE'
            else:self.message='NO SAMPLE'
            return True
        if self.page == 'SAMPLE DELETE':
            if name=='F1':self.page=self.sample_delete_origin
            elif name in ('F2','ENTER','ENCODER PUSH'):
                delete_file=self.sample_delete_index==1
                self.confirm('DELETE SAMPLE FILE?' if delete_file else 'REMOVE FROM PAD?',
                             lambda:self.remove_sample(delete_file),origin=self.sample_delete_origin)
            elif name in ('NAV LEFT','NAV RIGHT'):
                self.sample_delete_index=int(name=='NAV RIGHT')
            return True
        return False

    def sampling_rotate(self, delta):
        if self.audio_tool_rotate(delta):return True
        if self.page=='SAMPLING':
            if self.capture_started is not None or self.capture_armed:self.message='STOP RECORDING FIRST';return True
            options=self.capture_options();key=self.capture_fields()[self.capture_field];self.remember()
            choices={'source':('EXT STEREO','EXT MONO','INTERNAL'),'input':self.capture_inputs(),'mode':('DETECT','SYNC','LOOP'),'bars':(1,2,4,8,16,'FREE')}
            if key in choices:
                values=choices[key];index=values.index(options[key]) if options[key] in values else 0;options[key]=values[max(0,min(len(values)-1,index+delta))]
            elif key=='threshold':options[key]=max(-60,min(0,options[key]+delta))
            else:options[key]=delta>0
            if key=='source':
                options['input']=self.capture_inputs()[0];options['monitor']=False;self.capture_section=0
            return True

        if self.page=='STRETCH':
            self.remember();key='stretch_ratio' if self.sample_field==0 else 'stretch_pitch';self.track()[key]=max(10 if self.sample_field==0 else -48,min(1000 if self.sample_field==0 else 48,self.track().get(key,100 if self.sample_field==0 else 0)+delta));return True
        if self.wave_view():
            if self.wave_selected:
                slot=(5 if delta>0 else 1) if self.view_field==0 else (2 if delta>0 else 0)
                for _ in range(min(128,abs(delta))):self.wave_control(slot)
            return True
        if self.page=='AUTOSAMPLER':
            self.auto_setup();self.auto_adjust(self.auto_field,delta);return True
        if self.page=='SAMPLING NAV':
            self.sampling_nav=max(0,min(len(PAGES)-1,self.sampling_nav+delta));return True
        if self.page=='SAMPLE DELETE':
            self.sample_delete_index=max(0,min(1,self.sample_delete_index+delta));return True
        return False

    def sampling_pad(self, slot,velocity=100):
        if self.page in ('SAMPLE EDIT','ZONE') and self.keyboard_enabled and not self.shift and not self.wave_view():
            for note in self.performance_notes(slot):
                for z in self.track().get('zones',[]):
                    if z['key_lo']<=note<=z['key_hi']:
                        preview=copy.deepcopy(self.track());preview.update(z);preview.pop('zones',None)
                        preview['_preview_velocity']=velocity
                        self.actions.append(('slice_play',preview))
            return True
        if self.wave_view():
            self.wave_control(slot);return True
        if self.page=='SAMPLING NAV':
            if slot in (12,13,14,15,8):
                self.sampling_nav=(12,13,14,15,8).index(slot)
            return True
        return False

    def sample_process_request(self,operation):
        old=copy.deepcopy(self.track());old['_generation']=self.project_generation;old['_zone_index']=self.zone_index
        processing=copy.deepcopy(old)
        if operation=='NORMALIZE':
            source=copy.deepcopy(old.get('slice_source') or {key:old[key] for key in ('sample','start','end')})
            processing.update(source,selection_start=source['start'],selection_end=source['end'])
            if old.get('slices') or old.get('slice_source'):old['_normalize_slice_source']=source
        return old,processing

    def finish_sample_process(self,track,old,operation,path,frames):
        if operation=='NORMALIZE' and '_normalize_slice_source' in old:
            source=old['_normalize_slice_source'];items=track.get('zones',[])
            if any(track.get(key)!=old.get(key) for key in ('zones','slices','slice_source')):
                self.message='SLICES CHANGED: COPY KEPT';return False
            if source['end']>frames or any(not 0<=z['start']<z['end']<=frames for z in items):
                self.message='SLICE RANGE: COPY KEPT';return False
            self.remember();path=str(path)
            for z in items:z['sample']=path
            if track.get('slice_source'):track['slice_source']['sample']=path
            track['sample']=path
            self.message='SAMPLE NORMALIZED';return True
        index=old.get('_zone_index',0);items=track.get('zones',[]);old_items=old.get('zones',[])
        if items and (index>=len(items) or index>=len(old_items) or items[index]!=old_items[index]):
            self.message='ZONE CHANGED: COPY KEPT';return False
        first,last=old['start'],old['end']
        if operation=='TRUNCATE':first,last=0,frames
        elif operation in ('CUT','PASTE','DUPLICATE','STRETCH'):
            with wave.open(old['sample'],'rb') as wav:delta=frames-wav.getnframes()
            last+=delta
        if not 0<=first<last<=frames:self.message='EMPTY SLICE: COPY KEPT';return False
        self.remember();track.update(sample=str(path),start=first,end=last,selection_start=first,selection_end=last)
        if items:
            z=items[index];z.update(sample=str(path),start=first,end=last)
            z['loop_start']=max(first,min(last-1,z['loop_start']));z['loop_end']=max(z['loop_start']+1,min(last,z['loop_end']));z['xfade']=min(z.get('xfade',0),last-first)
        if not track.get('slice_source'):
            for key in ('slices','slice_mode','slice_committed','slice_manual'):track.pop(key,None)
        self.message=operation+' SAVED AS COPY';return True

    def remove_sample(self, delete_file=False):
        track=self.track()
        if not track['sample']:self.message='NO SAMPLE';return
        path=Path(track['sample']).resolve()
        if delete_file:
            if not path.is_relative_to(self.samples.resolve()):
                self.message='EXTERNAL: REMOVE ONLY';return
            current_ids={id(track),id(track.get('slice_source'))}|{id(z) for z in track.get('zones',[])}
            if any(id(obj) not in current_ids and Path(obj[key]).resolve()==path for obj,key in sample_references(self.project)):
                self.message='SAMPLE IN USE';return
            ignored={self.project_path,self.active_project_file()}
            for file in (self.root/'projects').glob('*.json'):
                if file in ignored:continue
                project=resolve_assets(json.loads(file.read_text()),file.parent)
                if any(Path(obj[key]).resolve()==path for obj,key in sample_references(project)):
                    self.message='OTHER PROJECT USES IT';return
            trash=self.samples/'.trash';trash.mkdir(exist_ok=True)
            if path.exists():path.rename(trash/f'{time.time_ns()}-{path.name}')
        self.remember()
        track.update(sample=None,start=0,end=0,selection_start=0,selection_end=0,zones=[])
        track.pop('slices',None);track.pop('slice_source',None);track.pop('slice_mode',None);track.pop('slice_committed',None);track.pop('slice_manual',None)
        self.actions.extend([('panic',None),('load',(self.group,self.pad,copy.deepcopy(track)))])
        if delete_file:
            for target,history in self.record_history.items():
                self.record_history[target]=[t for t in history if t['sample'] and Path(t['sample']).resolve()!=path]
            self.undo.clear();self.redo.clear();self.save()
        self.message='FILE MOVED TO TRASH' if delete_file else 'SAMPLE REMOVED'
