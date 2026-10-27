"""Persisted slice boundaries and non-destructive live chopping."""
import array
import copy
import math
import sys
import time
import wave

MODES=('SPLIT','GRID','DETECT','MANUAL')


def detect_slices(track,sensitivity=50,zero_crossing=True):
    with wave.open(track['sample'],'rb') as wav:
        channels,width,rate=wav.getnchannels(),wav.getsampwidth(),wav.getframerate()
        wav.setpos(track['start']);raw=wav.readframes(track['end']-track['start'])
    if len(raw)>32*1024*1024:raise ValueError('sample too large for detection')
    mono=[]
    for i in range(0,len(raw),channels*width):
        frame=raw[i:i+channels*width]
        mono.append(sum((frame[c*width]-128)/128 if width==1 else int.from_bytes(frame[c*width:(c+1)*width],'little',signed=True)/(1<<(width*8-1)) for c in range(channels))/channels)
    hop=max(1,rate//200);window=max(1,rate//100);previous=0;positions=[track['start']]
    threshold=0.005+(100-sensitivity)/100*0.12
    for i in range(0,len(mono),hop):
        energy=sum(abs(v) for v in mono[i:i+window])/max(1,len(mono[i:i+window]))
        if energy-previous>threshold and track['start']+i-positions[-1]>rate//20:
            pos=i
            if zero_crossing:
                candidates=[j for j in range(max(1,i-hop),min(len(mono),i+hop)) if mono[j-1]*mono[j]<=0]
                if candidates:pos=min(candidates,key=lambda j:abs(j-i))
            positions.append(track['start']+pos)
            if len(positions)>=128:break
        previous=energy
    return [[first,last] for first,last in zip(positions,positions[1:]+[track['end']]) if first<last]


class Slicing:
    def init_slicing(self):
        self.slice_mode='SPLIT';self.slice_grid=16;self.slice_sensitivity=50;self.slice_zero=True
        self.slice_bank=0;self.slice_boundary=0;self.live_chop_started=None
        self.slice_focus_end=False
        self.slice_auto_snap=False;self.slice_transients={}
        self.live_chop_anchor=0;self.live_chop_rate=1;self.live_chop_limit=0;self.live_chop_token=0;self.live_chop_key=None
        self.slice_target_group=self.group;self.slice_target_sound=None;self.slice_pattern='CREATE';self.slice_single_apply=False;self.slice_target_field=0

    def focus_slice_boundary(self,end):
        self.slice_focus_end=bool(end);self.slice_field=2 if end else 1
        self.slice_wave_focus=(self.group,self.pad,self.track()['sample'],self.slice_index)

    def slice_options(self):
        return self.track().get('slice_options',{'bpm_mode':'AUTO','auto_bpm':self.project['tempo'],'manual_bpm':self.project['tempo'],'adjust':1.,'mono':True})

    def slice_bpm(self,track=None):
        cfg=(track or self.track()).get('slice_options',{})
        return cfg.get('manual_bpm',self.project['tempo']) if cfg.get('bpm_mode','AUTO')=='MANUAL' else cfg.get('auto_bpm',self.project['tempo'])*cfg.get('adjust',1.)

    def slice_parameters(self):
        if self.slice_section and self.slice_mode=='DETECT':return ('ZERO-X',),('ON' if self.slice_zero else 'OFF',)
        cfg=self.slice_options()
        second=('SENSITIVITY',self.slice_sensitivity) if self.slice_mode=='DETECT' else ('AUTO-SNAP','ON' if self.slice_auto_snap else 'OFF') if self.slice_mode=='MANUAL' else ('SLICES',f'1/{self.slice_grid}' if self.slice_mode=='GRID' else len(self.slice_ranges()))
        return ('MODE',second[0],'BPM','ADJUST','MONO'),(self.slice_mode,second[1],cfg['bpm_mode'],f'{self.slice_bpm():.2f}', 'ON' if cfg['mono'] else 'OFF')

    def apply_single_slice(self,group,sound=None):
        ranges=self.slice_ranges()
        if not ranges:self.message='NO SLICES';return
        if not 0<=group<len(self.project['groups']):self.message='INVALID GROUP';return
        sound=0 if sound is None else sound
        if not 0<=sound<16:self.message='INVALID SOUND';return
        source=self.slice_source_track();first,last=ranges[min(self.slice_index,len(ranges)-1)]
        from app.sampler import default_zone
        self.stop_live_chop();self.remember()
        for key in ('slices','slice_source','slice_mode','slice_committed','slice_manual','zones'):source.pop(key,None)
        source.update(start=first,end=last,selection_start=first,selection_end=last,note=36+sound,source='SAMPLE')
        source['zones']=[default_zone(source)];source['sampler']=dict(source.get('sampler',{}),type='ONESHOT')
        self.project['groups'][group]['pads'][sound]=source
        self.actions.append(('load',(group,sound,copy.deepcopy(source))))
        self.group=group;self.group_bank=group//8;self.pad=sound;self.selected_pads={sound};self.zone_index=0;self.keyboard_enabled=False
        self.velocities16=False;self.performance_lights.clear();self.flash_until.clear()
        self.slice_single_apply=False;self.page=self.control_home();self.message='SINGLE SLICE APPLIED'

    def slice_source_track(self):
        track=copy.deepcopy(self.track())
        if track.get('slice_source'):track.update(track['slice_source'])
        return track

    def prepare_slice_editor(self):
        track=self.track();self.slice_single_apply=False
        # Migrate existing applied slices before a focused zone narrows the view.
        if not track.get('slice_source') and track.get('slices') and len(track.get('zones',[]))>1:
            if all(z['sample']==track['sample'] and z['key_lo']==z['key_hi']==i for i,z in enumerate(track['zones'])):
                track['slice_source']={'sample':track['sample'],'start':min(a for a,b in track['slices']),'end':max(b for a,b in track['slices'])}
        if track.get('slice_source'):
            track.setdefault('slice_committed',copy.deepcopy(track.get('slices',[])));track.update(track['slice_source'])
        if track.get('sample'):
            with wave.open(track['sample'],'rb') as wav:duration=(track['end']-track['start'])/wav.getframerate()
            cfg=dict(self.slice_options())
            if cfg.get('auto_duration')!=duration:
                beats=2**round(math.log2(max(.125,duration*self.project['tempo']/60)))
                cfg['auto_bpm']=max(20,min(999,beats*60/max(.001,duration)));cfg['auto_duration']=duration
                track['slice_options']=cfg
        self.slice_mode=track.get('slice_mode','MANUAL' if track.get('slices') else self.slice_mode)
        if self.slice_mode=='MANUAL' and track.get('slices') and not track.get('slice_manual'):
            track['slice_manual']=copy.deepcopy(track['slices'])
        ranges=self.slice_ranges();self.slice_count=max(1,len(ranges))
        self.slice_index=min(self.slice_index,max(0,len(ranges)-1));self.slice_bank=self.slice_index//16

    def stop_live_chop(self,stop_audio=True):
        self.live_chop_started=None;self.live_chop_token+=1;self.live_chop_key=None
        if stop_audio:self.actions.append(('preview_stop',None))

    def live_chop_position(self,now=None):
        if self.live_chop_started is None:return None
        track=self.track()
        if self.live_chop_key!=(track.get('sample'),track['start'],track['end']):self.stop_live_chop();return None
        now=time.monotonic() if now is None else now
        point=self.live_chop_anchor+round(max(0,now-self.live_chop_started)*self.live_chop_rate)
        if point>=self.live_chop_limit:self.live_chop_started=None;return None
        return point

    def live_chop_event(self,event):
        if event['token']!=self.live_chop_token or self.live_chop_key is None:return
        if event['status']=='playing':
            self.live_chop_anchor=event['frame'];self.live_chop_started=time.monotonic()
        else:self.live_chop_started=None

    def start_live_chop(self,index,ranges,velocity=100):
        track=copy.deepcopy(self.track());track['start']=ranges[index][0];track.pop('zones',None)
        track['_preview_velocity']=velocity
        with wave.open(track['sample'],'rb') as w:self.live_chop_rate=w.getframerate()
        self.live_chop_anchor=track['start'];self.live_chop_limit=track['end'];self.live_chop_started=time.monotonic()
        self.live_chop_token+=1;self.live_chop_key=(self.track()['sample'],self.track()['start'],self.track()['end'])
        self.slice_index=index;self.slice_bank=index//16
        self.actions.append(('slice_live_play',(track,self.live_chop_token)))

    def transient_key(self):
        t=self.track();return (t.get('sample'),t['start'],t['end'],self.slice_sensitivity,self.slice_zero)

    def request_transients(self):
        if self.track().get('sample') and self.transient_key() not in self.slice_transients:
            self.actions.append(('analyze_slices',(self.group,self.pad,copy.deepcopy(self.track()),self.slice_sensitivity,self.slice_zero)))

    def slice_ranges(self):
        current=self.track();track=current.get('slice_source',current);ranges=current.get('slices')
        if ranges and all(track['start']<=a<b<=track['end'] for a,b in ranges):return ranges
        if not track['sample'] or track['start']>=track['end']:return []
        count=1 if self.slice_mode=='MANUAL' else min(self.slice_count,track['end']-track['start']);size=track['end']-track['start']
        return [[track['start']+size*i//count,track['start']+size*(i+1)//count] for i in range(count)]

    def build_slices(self,remember=True):
        if not self.track()['sample']:self.message='NO SAMPLE';return
        if remember:self.remember()
        track=self.track();track['slice_mode']=self.slice_mode
        if track.get('slice_source'):track.update(track['slice_source'])
        if self.slice_mode=='DETECT':
            self.actions.append(('detect_slices',(self.group,self.pad,copy.deepcopy(track),self.slice_sensitivity,self.slice_zero)));return
        if self.slice_mode=='MANUAL':
            self.stop_live_chop()
            saved=track.get('slice_manual',track.get('slices',[]))
            track['slices']=[[max(a,track['start']),min(b,track['end'])] for a,b in saved if max(a,track['start'])<min(b,track['end'])] or [[track['start'],track['end']]]
            track['slice_manual']=copy.deepcopy(track['slices'])
            if self.slice_auto_snap:self.request_transients()
        else:
            size=track['end']-track['start']
            if self.slice_mode=='GRID':
                with wave.open(track['sample'],'rb') as w:rate=w.getframerate()
                distance=max(1,round(rate*60/self.slice_bpm()*4/self.slice_grid))
                cuts=list(range(track['start'],track['end'],distance))[:128]+[track['end']]
                track['slices']=[[a,b] for a,b in zip(cuts,cuts[1:])]
            else:
                track.pop('slices',None);track['slices']=self.slice_ranges()
        self.slice_count=len(track['slices']);self.slice_index=min(self.slice_index,self.slice_count-1)

    def save_manual_slices(self):
        if self.slice_mode=='MANUAL':self.track()['slice_manual']=copy.deepcopy(self.track().get('slices',[]))

    def slicing_button(self,name,pressed):
        if not pressed:return False
        if self.page=='SLICE TARGET':
            if name=='F2':self.page='CHOP';self.slice_single_apply=False
            elif name in ('F3','ENTER','ENCODER PUSH'):self.confirm('APPLY SLICES?',lambda:self.apply_slices(self.slice_target_group,self.slice_target_sound,self.slice_pattern),origin='CHOP')
            elif name=='F1':self.slice_single_apply=True;self.slice_edit=True;self.slice_field=0;self.page='CHOP'
            elif name in ('NAV LEFT','NAV RIGHT'):
                if 'GROUP' in self.held_buttons and self.shift:
                    bank=self.slice_target_group//8+(-1 if name=='NAV LEFT' else 1)
                    bank=max(0,min((len(self.project['groups'])-1)//8,bank))
                    self.slice_target_group=bank*8+self.slice_target_group%8;self.slice_target_sound=None
                else:self.slice_target_field=int(name=='NAV RIGHT')
            elif name=='GROUP':self.slice_target_sound=None
            return True
        if self.page!='CHOP' or self.wave_view():return False
        if name=='F2' and self.slice_single_apply:
            self.slice_single_apply=False;self.slice_edit=False;self.page='SLICE TARGET';return True
        if name=='F3' and self.slice_single_apply:
            self.confirm('APPLY SINGLE SLICE?',lambda:self.apply_single_slice(self.slice_target_group,self.slice_target_sound),origin='CHOP');return True
        if name=='F1':
            if not self.slice_edit and self.live_chop_started is not None:self.stop_live_chop()
            self.slice_edit=not self.slice_edit;self.slice_field=0
            if self.slice_edit:self.focus_slice_boundary(False)
            return True
        if name=='F2':
            if self.slice_edit:
                ranges=self.slice_ranges()
                if not ranges or len(ranges)>=128:return True
                a,b=ranges[self.slice_index];middle=(a+b)//2
                if middle>a:self.remember();self.slice_mode='MANUAL';self.track()['slice_mode']='MANUAL';self.track()['slices']=ranges[:self.slice_index]+[[a,middle],[middle,b]]+ranges[self.slice_index+1:];self.save_manual_slices();self.slice_count=len(self.track()['slices'])
            else:self.slice_target_group=self.group;self.slice_target_sound=None;self.slice_target_field=0;self.slice_single_apply=False;self.page='SLICE TARGET'
            return True
        if name=='F3':
            if self.slice_edit:
                ranges=self.slice_ranges()
                if self.shift:
                    if not self.track()['sample'] or self.track()['start']>=self.track()['end']:self.message='NO SAMPLE';return True
                    self.remember();self.stop_live_chop();self.track()['slices']=[[self.track()['start'],self.track()['end']]]
                    self.track()['slice_manual']=copy.deepcopy(self.track()['slices'])
                    self.slice_mode='MANUAL';self.track()['slice_mode']='MANUAL';self.slice_count=1;self.slice_index=self.slice_bank=0;return True
                if len(ranges)>1 and self.slice_index:
                    self.remember();idx=self.slice_index
                    ranges[idx-1][1]=ranges[idx][1];ranges.pop(idx)
                    self.track()['slices']=ranges;self.track()['slice_mode']='MANUAL';self.slice_mode='MANUAL'
                    self.save_manual_slices()
                    self.slice_count=len(ranges);self.slice_index=idx-1;self.slice_bank=self.slice_index//16
            else:self.confirm('APPLY TO SOUND?',lambda:self.apply_slices(self.group,self.pad,'NONE'))
            return True
        if name in ('NAV LEFT','NAV RIGHT'):
            if self.shift:
                self.slice_bank=max(0,min((len(self.slice_ranges())-1)//16,self.slice_bank+(-1 if name=='NAV LEFT' else 1)))
            elif self.slice_edit:self.focus_slice_boundary(name=='NAV RIGHT')
            else:self.slice_field=max(0,min(2 if self.slice_edit else len(self.slice_parameters()[0])-1,self.slice_field+(-1 if name=='NAV LEFT' else 1)))
            return True
        return False

    def slicing_rotate(self,delta):
        if self.page=='SLICE TARGET':
            if 'GROUP' in self.held_buttons:
                self.slice_target_group=max(0,min(len(self.project['groups'])-1,self.slice_target_group+delta));self.slice_target_sound=None
                return True
            if self.slice_target_field==0:
                modes=('CREATE','REPLACE','NONE');self.slice_pattern=modes[max(0,min(2,modes.index(self.slice_pattern)+delta))]
            else:
                self.remember();cfg=dict(self.slice_options());cfg['mono']=delta>0;self.track()['slice_options']=cfg
            return True
        if self.page!='CHOP' or self.wave_view():return False
        if self.slice_edit:
            ranges=copy.deepcopy(self.slice_ranges())
            if not ranges:return True
            if self.slice_field==0:self.slice_index=max(0,min(len(ranges)-1,self.slice_index+delta));self.slice_bank=self.slice_index//16
            else:
                self.remember();self.track()['slice_manual']=copy.deepcopy(self.track().get('slices',[]));self.slice_mode='MANUAL';self.track()['slice_mode']='MANUAL';idx=self.slice_index;a,b=ranges[idx];increment=max(1,(b-a)//(120 if self.encoder_held or self.shift else 30))
                if self.slice_field==1:
                    joined=idx>0 and ranges[idx-1][1]==a
                    lower=ranges[idx-1][0]+1 if joined else self.track()['start']
                    ranges[idx][0]=max(lower,min(b-1,a+delta*increment))
                    if joined:ranges[idx-1][1]=ranges[idx][0]
                else:ranges[idx][1]=max(a+1,min(self.track()['end'],b+delta*increment))
                self.track()['slices']=ranges
                self.save_manual_slices()
        elif not self.slice_section and self.slice_field>=2:
            self.remember();cfg=dict(self.slice_options())
            if self.slice_field==2:cfg['bpm_mode']='MANUAL' if delta>0 else 'AUTO'
            elif self.slice_field==3:
                if cfg['bpm_mode']=='MANUAL':cfg['manual_bpm']=round(max(20,min(999,cfg['manual_bpm']+delta*(.01 if self.shift or self.encoder_held else 1))),2)
                else:
                    choices=(.5,1.,2.);cfg['adjust']=choices[max(0,min(2,choices.index(cfg['adjust'])+delta))]
            else:cfg['mono']=delta>0
            self.track()['slice_options']=cfg
            if self.slice_mode=='GRID' and self.slice_field in (2,3):self.build_slices(remember=False)
        elif self.slice_section and self.slice_mode=='DETECT':
            self.slice_zero=delta>0;self.build_slices()
        elif self.slice_field==0:
            mode=MODES[max(0,min(3,MODES.index(self.slice_mode)+delta))]
            if mode!=self.slice_mode:
                self.remember()
                track=self.track()
                if self.slice_mode=='MANUAL':track['slice_manual']=copy.deepcopy(track.get('slices',[]))
                if mode=='MANUAL' and not track.get('slice_manual'):
                    source=track.get('slice_source',track)
                    track['slice_manual']=[[source['start'],source['end']]]
                self.stop_live_chop();self.slice_section=0;self.slice_mode=mode;self.build_slices(remember=False)
        elif self.slice_mode=='SPLIT':
            counts=(4,8,16,32);old=min(counts,key=lambda v:abs(v-self.slice_count));self.slice_count=counts[max(0,min(3,counts.index(old)+delta))];self.build_slices()
        elif self.slice_mode=='GRID':
            grids=(4,8,16,32);self.slice_grid=grids[max(0,min(3,grids.index(self.slice_grid)+delta))];self.build_slices()
        elif self.slice_mode=='DETECT':
            if self.slice_field==2:self.slice_zero=delta>0
            else:self.slice_sensitivity=max(0,min(100,self.slice_sensitivity+delta))
            self.build_slices()
        elif self.slice_mode=='MANUAL':
            self.slice_auto_snap=delta>0
            if self.slice_auto_snap:self.request_transients()
        return True

    def slicing_pad(self,slot,velocity):
        if self.page=='SLICE TARGET':
            groups=(12,13,14,15,8,9,10,11)
            if 'GROUP' in self.held_buttons:
                if slot in groups:
                    self.slice_target_group=(self.slice_target_group//8)*8+groups.index(slot);self.slice_target_sound=None
            else:self.slice_target_sound=slot
            return True
        if self.page!='CHOP' or self.wave_view():return False
        if not self.track()['sample']:return True
        idx=self.slice_bank*16+slot
        if self.slice_mode=='MANUAL' and not self.slice_edit:
            if not self.track().get('slices'):
                if idx!=0:self.message='PRESS PAD 1';return True
                self.remember();self.track()['slices']=[[self.track()['start'],self.track()['end']]];self.slice_count=1
                self.track()['slice_manual']=copy.deepcopy(self.track()['slices'])
            ranges=copy.deepcopy(self.slice_ranges());self.slice_count=len(ranges)
            if idx<len(ranges):
                if self.slice_auto_snap and self.transient_key() not in self.slice_transients:
                    self.request_transients();self.message='ANALYZING: WAIT';return True
                self.start_live_chop(idx,ranges,velocity);return True
            if idx!=len(ranges) or len(ranges)>=128:return True
            point=self.live_chop_position()
            if point is None:self.message='PLAY A SLICE FIRST';return True
            if self.slice_auto_snap:
                candidates=self.slice_transients.get(self.transient_key(),[])
                if not candidates:self.request_transients();self.message='ANALYZING: WAIT';return True
                point=min(candidates,key=lambda p:abs(p-point))
            if point in [a for a,b in ranges]:self.message='SLICE EXISTS';return True
            for index,(a,b) in enumerate(ranges):
                if a<point<b:
                    self.remember();ranges[index:index+1]=[[a,point],[point,b]]
                    self.track()['slices']=ranges;self.slice_count=len(ranges);self.slice_index=index+1
                    self.save_manual_slices()
                    self.slice_bank=self.slice_index//16;return True
            return True
        ranges=self.slice_ranges()
        if idx<len(ranges):
            self.slice_index=idx;track=copy.deepcopy(self.track());track['start'],track['end']=ranges[idx];track.pop('zones',None)
            if self.slice_edit:self.slice_wave_focus=(self.group,self.pad,self.track()['sample'],idx)
            track['_preview_velocity']=velocity
            self.actions.append(('slice_play',track))
        return True

    def apply_slices(self,group,sound=None,pattern='NONE'):
        source=self.slice_source_track();ranges=self.slice_ranges()
        if not source['sample'] or not ranges:self.message='NO SLICES';return
        if not 0<=group<len(self.project['groups']) or sound is not None and not 0<=sound<16:self.message='INVALID TARGET';return
        if sound is None and len(ranges)>16:self.message='OVER 16: APPLY TO SOUND';return
        tempo=self.slice_bpm(source);mono=source.get('slice_options',{}).get('mono',True)
        self.stop_live_chop();self.remember();previous_zones=copy.deepcopy(source.pop('zones',[]))
        self.velocities16=False;self.chord=0;self.chord_focus=0;self.pad_field=0;self.performance_lights.clear();self.flash_until.clear()
        from app.sampler import default_zone
        if sound is not None:
            mapped=[];previous=source.get('slice_committed',[])
            for index,(a,b) in enumerate(ranges):
                z=default_zone(dict(source,start=a,end=b,note=index));z.update(key_lo=index,key_hi=index,root=index)
                if index<len(previous) and list(previous[index])==list(ranges[index]):
                    existing=next((old for old in previous_zones if old['key_lo']==old['key_hi']==index),None)
                    if existing:z=existing
                mapped.append(z)
            source['slices']=copy.deepcopy(ranges)
            source['slice_source']={k:source[k] for k in ('sample','start','end')};source['slice_mode']=self.slice_mode;source['slice_committed']=copy.deepcopy(ranges)
            source['note']=0;source['source']='SAMPLE';self.zone_index=0
            source['zones']=mapped;source['sampler']=dict(source.get('sampler',{}),type='ONESHOT')
            self.project['groups'][group]['pads'][sound]=source
            self.actions.append(('load',(group,sound,copy.deepcopy(source))));self.pad=sound;self.keyboard_root=0;self.keyboard_enabled=True
        else:
            for slot,(a,b) in enumerate(ranges):
                track=copy.deepcopy(source)
                for key in ('slices','slice_source','slice_mode','slice_committed','slice_manual'):track.pop(key,None)
                track.update(start=a,end=b,note=36+slot)
                track['zones']=[default_zone(track)];track['sampler']=dict(track.get('sampler',{}),type='ONESHOT')
                if mono:track.update(choke_group=1,choke_mode='MASTER');track['sampler']['polyphony']=1
                self.project['groups'][group]['pads'][slot]=track;self.actions.append(('load',(group,slot,copy.deepcopy(track))))
            self.pad=0;self.keyboard_enabled=False
        if pattern!='NONE':
            bank=self.project['groups'][group]
            if pattern=='CREATE':
                free=next((i for i in range(len(bank['patterns'])) if i not in bank['pattern_created']),None)
                if free is None:
                    free=len(bank['patterns'])
                    bank['patterns'].extend([[[False]*16 for _ in range(16)] for _ in range(16)])
                self.pattern=free;bank['pattern_created'].append(free)
            if pattern=='REPLACE':
                bank['patterns'][self.pattern]=[[False]*len(bank['patterns'][self.pattern][0]) for _ in range(16)]
                for name in ('events','extra_events'):
                    bank[name]={k:v for k,v in bank[name].items() if not k.startswith(f'{self.pattern}:')}
            with wave.open(source['sample'],'rb') as w:rate=w.getframerate()
            applied=ranges
            duration=round((applied[-1][1]-source['start'])/rate*tempo/60*96)
            length=max(16,min(4096,((duration+383)//384)*16))
            for lane in bank['patterns'][self.pattern]:
                lane.extend([False]*max(0,length-len(lane)))
            bank['pattern_lengths'][str(self.pattern)]=length
            self.project['scenes'][self.scene][group]=self.pattern
            self.active_patterns[group]=self.pattern;self.active_clips[group]=True;self.pattern_bank=self.pattern//16
            for index,(a,b) in enumerate(applied):
                tick=round((a-source['start'])/rate*tempo/60*96)
                if tick<length*24:self.put_note(index if sound is None else sound,tick,{'velocity':100,'probability':100,'length':max(1,round((b-a)/rate*tempo/60*96)),'note':index if sound is not None else 36+index},group,self.pattern)
        self.group=group;self.group_bank=group//8;self.selected_pads={self.pad};self.page=self.control_home();self.live_chop_started=None;self.message=f'{len(ranges)} SLICES APPLIED'
