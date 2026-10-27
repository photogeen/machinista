"""Controller setup for the shared nonblocking autosampler runtime."""
import copy

FIELDS=('source','low','high','step','layers','hold','tail','gap',
        'name','folder','midi_out','channel','input','trim',None,None)+tuple('velocity'+str(i) for i in range(8))
LABELS=('SOURCE','LOW NOTE','HIGH NOTE','INTERVAL','LAYERS','HOLD','TAIL','GAP',
        'SOUND NAME','FOLDER','MIDI OUT','CHANNEL','AUDIO IN','TRIM', '', '')+tuple('VELOCITY '+str(i+1) for i in range(8))

class AutosamplerUI:
    def auto_setup(self):
        if not hasattr(self,'auto_config'):
            self.auto_config=dict(name='',folder='Autosampled',tags=['autosampled'],source='LV2',low=48,high=84,step=12,
                                  velocities=[100],hold=2.,tail=1.,gap=.2,channel=1,input='IN 1/2',trim=True,midi_out='')
            self.auto_field=0;self.auto_status={'state':'IDLE'};self.auto_command=None
        return self.auto_config

    def auto_rows(self):
        v=self.auto_setup();rows=[]
        for key,label in zip(FIELDS,LABELS):
            if key is None:rows.append(('', ''));continue
            if key=='layers':value=str(len(v['velocities']))
            elif key.startswith('velocity'):
                i=int(key[8:]);value=str(v['velocities'][i]) if i<len(v['velocities']) else '--'
            elif key in ('low','high'):
                n=v[key];value=('C','C#','D','D#','E','F','F#','G','G#','A','A#','B')[n%12]+str(n//12-1)
            elif key=='midi_out':value=next((d.name for d in self.midi_devices if d.key==v[key]),'NONE')
            elif key=='trim':value='ON' if v[key] else 'OFF'
            elif key in ('hold','tail','gap'):value=f'{v[key]:.2f} S'
            else:value=str(v[key]) or 'ENTER NAME'
            rows.append((label,value))
        return rows

    def auto_adjust(self,index,delta):
        v=self.auto_setup();self.auto_field=index;key=FIELDS[index]
        if self.auto_status.get('state') in ('RECORDING','SAVING','CANCELLING') or self.auto_command:return
        if key in ('name','folder'):
            self.auto_name(key);return
        if key is None:return
        if key=='source':v[key]=('LV2','EXTERNAL')[max(0,min(1,('LV2','EXTERNAL').index(v[key])+delta))]
        elif key=='layers':
            count=max(1,min(8,len(v['velocities'])+delta))
            if count!=len(v['velocities']):v['velocities']=[100] if count==1 else [round(1+i*126/(count-1)) for i in range(count)]
        elif key.startswith('velocity'):
            i=int(key[8:]);values=v['velocities']
            if i<len(values):values[i]=max(values[i-1]+1 if i else 1,min(values[i+1]-1 if i+1<len(values) else 127,values[i]+delta))
        elif key=='midi_out':
            choices=['']+[d.key for d in self.midi_devices]
            v[key]=choices[max(0,min(len(choices)-1,(choices.index(v[key]) if v[key] in choices else 0)+delta))]
        elif key=='input':
            count=self.audio.input_channels if self.audio else 0
            choices=[f'IN {i+1}' for i in range(count)]+[f'IN {i+1}/{i+2}' for i in range(0,count-1,2)]
            if choices:v[key]=choices[max(0,min(len(choices)-1,(choices.index(v[key]) if v[key] in choices else 0)+delta))]
        elif key=='trim':v[key]=delta>0
        else:
            lo,hi,step={'low':(0,v['high'],1),'high':(v['low'],127,1),'step':(1,24,1),'channel':(1,16,1),
                        'hold':(.05,30,.01 if self.shift else .1),'tail':(0,10,.01 if self.shift else .1),'gap':(.05,5,.01 if self.shift else .05)}[key]
            value=max(lo,min(hi,round(v[key]+delta*step,2)));v[key]=int(value) if step==1 else value

    def auto_name(self,key):
        v=self.auto_setup()
        if self.auto_status.get('state') in ('RECORDING','SAVING','CANCELLING'):return
        self.open_name_dialog('AUTO '+key.upper());self.name_value=v[key];self.name_cursor=0

    def auto_start(self):
        from app.autosampler import configuration
        v=self.auto_setup()
        if self.auto_command or self.auto_status.get('state') in ('RECORDING','SAVING','CANCELLING'):return
        if not v['name']:
            self.auto_name('name');return
        try:configuration(v)
        except ValueError as e:self.message=str(e);return
        self.auto_command=('start',copy.deepcopy(v))

    def auto_ui_button(self,name,pressed):
        if self.page!='AUTOSAMPLER' or not pressed:return False
        self.auto_setup()
        if name in ('NAV LEFT','NAV RIGHT'):
            step=-1 if name=='NAV LEFT' else 1
            i=self.auto_field
            while 0<=i+step<len(FIELDS):
                i+=step
                if FIELDS[i] is not None:break
            self.auto_field=i;return True
        if name=='F1':self.page='SAMPLING';return True
        if name=='F2':self.auto_start();return True
        if name=='F3':self.auto_command=('cancel',None);return True
        if name in ('ENTER','ENCODER PUSH'):
            key=FIELDS[self.auto_field]
            if key in ('name','folder'):self.auto_name(key)
            return True
        return False
