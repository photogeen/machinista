"""Voice parameters and layered sample zones shared by UI, storage and audio."""
import copy
import math
import wave

# key, label, default, bounds or choices; six pages as on Mikro.
SAMPLER_PAGES = (
 ('VOICE', (('polyphony','POLYPHONY',8,(1,2,4,8,16,32,64,'LEGATO')),('glide','GLIDE',0,(0,2000)),('bend','PITCHBEND',2,(0,24)))),
 ('PITCH/ENV', (('tune','TUNE',0,(-48,48)),('reverse','REVERSE',False,(False,True)),('type','TYPE','ONESHOT',('ONESHOT','AHD','ADSR')),('attack','ATTACK',0,(0,10000)),('hold','HOLD',0,(0,10000)),('decay','DECAY',250,(1,10000)),('sustain','SUSTAIN',100,(0,100)),('release','RELEASE',100,(1,10000)))),
 ('FX/FILTER', (('comp','COMP',0,(0,100)),('drive','DRIVE',0,(0,100)),('sr','SR',100,(1,100)),('bits','BITS',16,(4,16)),('filter','FILTER','OFF',('OFF','LP2','BP2','HP2','EQ')),('cutoff','CUTOFF',18000,(20,20000)),('resonance','RESONANCE',0,(0,95)),('eq_gain','EQ GAIN',0,(-24,24)),('eq_width','EQ WIDTH',1,(0.1,4)))),
 ('MOD ENV', (('mod_attack','ATTACK',0,(0,10000)),('mod_decay','DECAY',250,(1,10000)),('mod_pitch','PITCH',0,(-24,24)),('mod_cutoff','CUTOFF',0,(-100,100)),('mod_pan','PAN',0,(-100,100)))),
 ('LFO', (('lfo_shape','SHAPE','SINE',('SINE','TRI','RECT','SAW','RANDOM')),('lfo_rate','SPEED',1,(0.1,30)),('lfo_sync','SYNC','FREE',('FREE','1/1','1/2','1/4','1/8','1/16','1/32','1/8T','1/16T')),('lfo_phase','PHASE',0,(0,360)),('lfo_pitch','PITCH',0,(0,24)),('lfo_cutoff','CUTOFF',0,(0,100)),('lfo_pan','PAN',0,(0,100)))),
 ('VEL/MOD', (('vel_volume','VEL VOLUME',100,(0,100)),('vel_cutoff','VEL CUTOFF',0,(-100,100)),('vel_start','VEL START',0,(0,100)),('pan','PAN',0,(-100,100)),('wheel_pitch','MW PITCH',0,(-24,24)),('wheel_cutoff','MW CUTOFF',0,(-100,100)),('wheel_pan','MW PAN',0,(-100,100))))
)
DEFAULTS={key:default for _,fields in SAMPLER_PAGES for key,_,default,_ in fields}
ZONE_PAGES=(('PLAY',('start','end')),('LOOP',('loop','loop_start','loop_end','xfade')),('TUNE',('tune','gain','pan','root')),('ENVELOPE',('attack','decay')),('MAP',('key_lo','key_hi','vel_lo','vel_hi')))


def adjust_cutoff(value,delta,fine=False):
    """Equal encoder travel per octave; fine mode quarters each musical step."""
    import math
    low,high=20.,20000.
    log_value=math.log2(max(low,min(high,float(value))))
    position=max(math.log2(low),min(math.log2(high),log_value+delta/(128 if fine else 32)))
    return round(2**position,3)


def cutoff_position(value):
    """Fixed logarithmic axis shared by filter feedback on all displays."""
    import math
    return math.log(max(20.,min(20000.,float(value)))/20.)/math.log(1000.)


def default_zone(track):
    return {'sample':track['sample'],'start':track['start'],'end':track['end'],
            'loop':False,'loop_start':track['start'],'loop_end':track['end'],'xfade':0,
            'tune':0,'gain':100,'pan':0,'root':track.get('note',36),'attack':0,'decay':0,
            'key_lo':0,'key_hi':127,'vel_lo':1,'vel_hi':127}


def zones(track):
    return track.get('zones') or ([default_zone(track)] if track.get('sample') else [])


def validate_sampler(track):
    from app.audio_loop import validate_audio_loop
    validate_audio_loop(track)
    if not isinstance(track.get('slices',[]),list) or len(track.get('slices',[]))>128:raise ValueError('invalid slice count')
    for pair in track.get('slices',[]):
        if not isinstance(pair,list) or len(pair)!=2 or any(type(v) is not int for v in pair) or not 0<=pair[0]<pair[1]:raise ValueError('invalid slice range')
    if 'slice_source' in track:
        source=track['slice_source']
        if not isinstance(source,dict) or not isinstance(source.get('sample'),str) or type(source.get('start')) is not int or type(source.get('end')) is not int or not 0<=source['start']<source['end']:raise ValueError('invalid slice source')
    if track.get('slice_mode','MANUAL') not in ('MANUAL','SPLIT','GRID','DETECT'):raise ValueError('invalid slice mode')
    if 'slice_options' in track:
        cfg=track['slice_options']
        if not isinstance(cfg,dict) or cfg.get('bpm_mode') not in ('AUTO','MANUAL') or type(cfg.get('mono')) is not bool or cfg.get('adjust') not in (.5,1.,2.):raise ValueError('invalid slice options')
        for key in ('auto_bpm','manual_bpm'):
            value=cfg.get(key)
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 20<=value<=999:raise ValueError('invalid slice tempo')
    for key in ('slice_committed','slice_manual'):
        values=track.get(key,[])
        if not isinstance(values,list) or len(values)>128:raise ValueError('invalid '+key)
        for pair in values:
            if not isinstance(pair,(list,tuple)) or len(pair)!=2 or any(type(v) is not int for v in pair) or not 0<=pair[0]<pair[1]:raise ValueError('invalid '+key)
    values=track.get('sampler',{})
    if not isinstance(values,dict):raise ValueError('invalid sampler')
    for _,fields in SAMPLER_PAGES:
        for key,_,default,bounds in fields:
            value=values.get(key,default)
            if isinstance(default,str) or type(default) is bool or key=='polyphony':
                if value not in bounds:raise ValueError('invalid sampler '+key)
            elif isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not bounds[0]<=value<=bounds[1]:raise ValueError('invalid sampler '+key)
    if not isinstance(track.get('zones',[]),list) or len(track.get('zones',[]))>128:raise ValueError('invalid zones')
    for zone in track.get('zones',[]):
        if not isinstance(zone,dict) or not isinstance(zone.get('sample'),str):raise ValueError('invalid zone asset')
        base=default_zone(dict(track,sample=zone['sample']));base.update(zone)
        if any(type(base[k]) is not int for k in ('start','end','loop_start','loop_end','key_lo','key_hi','vel_lo','vel_hi','root')):raise ValueError('invalid zone range')
        if not 0<=base['start']<base['end'] or not base['start']<=base['loop_start']<base['loop_end']<=base['end']:raise ValueError('invalid zone loop')
        if not 0<=base['key_lo']<=base['key_hi']<=127 or not 1<=base['vel_lo']<=base['vel_hi']<=127 or not 0<=base['root']<=127:raise ValueError('invalid zone mapping')
        if type(base['loop']) is not bool:raise ValueError('invalid zone loop switch')
        for k,lo,hi in (('gain',0,200),('pan',-100,100),('tune',-48,48),('attack',0,10000),('decay',0,10000),('xfade',0,base['end']-base['start'])):
            if not isinstance(base[k],(int,float)) or not math.isfinite(base[k]) or not lo<=base[k]<=hi:raise ValueError('invalid zone '+k)


class Sampler:
    def init_sampler(self):
        self.sampler_page=self.sampler_field=self.zone_page=self.zone_field=self.zone_index=0
        self.zone_browse=False;self.capture_field=0;self.capture_section=0;self.slice_section=0;self.capture_peak=0;self.capture_stereo_peak=(0.,0.)
        self.live_notes={};self.capture_armed=False;self.record_history={};self.record_cursor={}

    def sampler_fields(self):
        fields=SAMPLER_PAGES[self.sampler_page][1];values=self.track().get('sampler',{})
        if self.sampler_page==0 and values.get('polyphony',DEFAULTS['polyphony'])!='LEGATO':
            fields=tuple(field for field in fields if field[0]!='glide')
        if self.sampler_page==1:
            kind=values.get('type',DEFAULTS['type'])
            hidden={'attack','hold','decay','sustain','release'} if kind=='ONESHOT' else {'sustain','release'} if kind=='AHD' else {'hold'}
            fields=tuple(field for field in fields if field[0] not in hidden)
        self.sampler_field=min(self.sampler_field,len(fields)-1)
        return fields
    def sampler_parameter(self):
        fields=self.sampler_fields();return fields[self.sampler_field]
    def zone(self):
        items=zones(self.track());self.zone_index=min(self.zone_index,max(0,len(items)-1))
        return items[self.zone_index] if items else None

    def sync_zone(self):
        zone=self.zone()
        if zone:
            self.track().update(sample=zone['sample'],start=zone['start'],end=zone['end'],selection_start=zone['start'],selection_end=zone['end'])
            self.actions.append(('load',(self.group,self.pad,copy.deepcopy(self.track()))))

    def sampler_button(self,name,pressed):
        if name=='SHIFT' or not pressed:return False
        if self.page not in ('SAMPLER','ZONE'):return False
        if name=='ENCODER PUSH':self.encoder_held=True;return True
        if name in ('NAV LEFT','NAV RIGHT'):
            delta=-1 if name=='NAV LEFT' else 1
            page_attr,field_attr,total=('sampler_page','sampler_field',len(SAMPLER_PAGES)) if self.page=='SAMPLER' else ('zone_page','zone_field',len(ZONE_PAGES))
            if 'NAV' in self.held_buttons:
                setattr(self,page_attr,max(0,min(total-1,getattr(self,page_attr)+delta)));setattr(self,field_attr,0)
            else:
                fields=self.sampler_fields() if self.page=='SAMPLER' else ZONE_PAGES[self.zone_page][1]
                setattr(self,field_attr,max(0,min(len(fields)-1,getattr(self,field_attr)+delta)))
            return True
        if self.page=='ZONE' and name in ('F1','F2','F3'):
            if name=='F3':
                if self.shift:
                    items=zones(self.track())
                    if items:
                        self.remember();self.track()['zones']=copy.deepcopy(items);self.track()['zones'].pop(self.zone_index)
                        if not self.track()['zones']:
                            self.track().update(sample=None,start=0,end=0,selection_start=0,selection_end=0)
                            for key in ('slices','slice_source','slice_mode','slice_committed','slice_manual'):self.track().pop(key,None)
                        self.sync_zone();self.actions.append(('reload',None))
                else:self.zone_browse=True;self.page='BROWSE'
            else:self.zone_index=max(0,min(len(zones(self.track()))-1,self.zone_index+(-1 if name=='F1' else 1)));self.sync_zone()
            return True
        return False

    def sampler_rotate(self,delta):
        if self.page=='SAMPLER':
            key,_,default,bounds=self.sampler_parameter();self.remember()
            values=self.track().setdefault('sampler',{})
            old=values.get(key,default)
            if isinstance(default,str) or type(default) is bool or key=='polyphony':values[key]=bounds[max(0,min(len(bounds)-1,bounds.index(old)+delta))]
            elif key=='cutoff':values[key]=adjust_cutoff(old,delta,self.encoder_held or self.shift)
            else:
                step=0.1 if key in ('lfo_rate','eq_width') else 1 if self.encoder_held else 10 if key in ('attack','hold','decay','release','mod_attack','mod_decay') else 1
                values[key]=max(bounds[0],min(bounds[1],round(old+delta*step,3)))
            self.actions.append(('load',(self.group,self.pad,copy.deepcopy(self.track()))));return True
        if self.page!='ZONE':return False
        items=zones(self.track())
        if not items:return True
        self.remember();self.track()['zones']=copy.deepcopy(items);z=self.zone()
        key=ZONE_PAGES[self.zone_page][1][self.zone_field]
        if key=='loop':z[key]=delta>0
        else:
            hi=127 if key in ('key_lo','key_hi','root','vel_lo','vel_hi') else 200 if key=='gain' else 100 if key=='pan' else 48 if key=='tune' else 10000 if key in ('attack','decay') else z['end']
            lo=1 if key.startswith('vel_') else -100 if key=='pan' else -48 if key=='tune' else 0
            if key in ('start','end','loop_start','loop_end','xfade'):
                with wave.open(z['sample'],'rb') as wav:hi=wav.getnframes()
                increment=max(1,(self.wave_bounds(hi)[1]-self.wave_bounds(hi)[0])//(120 if self.encoder_held else 30))
            else:increment=1
            z[key]=max(lo,min(hi,z[key]+delta*increment))
            for first,last in (('key_lo','key_hi'),('vel_lo','vel_hi')):
                if z[first]>z[last]:z[last if key==first else first]=z[key]
            z['start']=min(z['start'],z['end']-1);z['loop_start']=max(z['start'],min(z['end']-1,z['loop_start']));z['loop_end']=max(z['loop_start']+1,min(z['end'],z['loop_end']))
        self.sync_zone();return True
