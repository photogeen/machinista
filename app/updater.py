"""Asynchronous update UI adapter. All I/O runs on a single low-priority worker."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json,os,socket,time
from app.branding import VERSION

def enabled(root):
    # One distribution for everyone, including installations with legacy markers.
    # The privileged broker still requires its own root-owned trusted config/key.
    return True

def initial(root):return dict(enabled=enabled(root),configured=False,current=VERSION,latest=None,channel='release',state='OFFLINE',progress=0,busy=False,available=False,message='Update service unavailable',error='',os_included=True)

def request(value,runtime=Path('/run/machinista-updater')):
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(2);connection.connect(str(Path(runtime)/'control.sock'));connection.sendall(json.dumps(value).encode()+b'\n');raw=b''
        while b'\n' not in raw:
            part=connection.recv(4096)
            if not part or len(raw)+len(part)>16384:raise OSError('Update service unavailable.')
            raw+=part
    state=json.loads(raw.split(b'\n',1)[0])
    if state.get('error') and 'state' not in state:raise ValueError(state['error'])
    return state

class Control:
    def __init__(self,root,runtime=Path('/run/machinista-updater'),call=request):
        self.root=Path(root);self.runtime=Path(runtime);self.call=call;self.active=enabled(root);self.future=None;self.queue=[];self.next=0
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='update-control')
    def submit(self,value):
        if self.active and value not in self.queue and len(self.queue)<3:self.queue.append(value)
    def exchange(self,value,pulse):
        try:
            directory=self.runtime/'app';tmp=directory/'status.json.pending'
            tmp.write_text(json.dumps(pulse));os.replace(tmp,directory/'status.json')
        except OSError:pass
        return self.call(value,self.runtime)
    def poll(self,app,now,busy):
        if not self.active:return
        if self.future is not None and self.future.done():
            try:app.update_status=self.future.result()
            except (OSError,ValueError) as error:
                app.update_status=dict(app.update_status,state='OFFLINE',busy=False,error=str(error),message=str(error))
            self.future=None
        if self.future is None and (self.queue or now>=self.next):
            self.next=now+1;value=self.queue.pop(0) if self.queue else {'op':'status'}
            pulse=dict(updated=time.time(),pid=os.getpid(),busy=bool(busy),playing=app.playing)
            self.future=self.pool.submit(self.exchange,value,pulse)
    def close(self):self.pool.shutdown(wait=False,cancel_futures=True)

def command(app,op,channel=None):
    state=app.update_status
    if not state.get('enabled'):app.message='UPDATER NOT ENABLED';return
    if state.get('busy'):app.message='UPDATE IN PROGRESS';return
    value={'op':op}
    if op=='channel':value['channel']=channel
    if op=='install':
        if app.playing or app.recording or app.capture_armed or app.capture_started is not None or app.export_busy:
            app.message='STOP PLAY/REC FIRST';return
        if not state.get('available'):app.message='CHECK FOR UPDATES FIRST';return
        value.update(expected=state['latest'],channel=state['channel'])
        app.confirm('SAVE AND UPDATE?',lambda:app.actions.append(('update',value)));return
    app.actions.append(('update',value))

def button(app,name,pressed):
    if app.page!='UPDATE':return False
    if not pressed:return name in ('F1','F2','F3','MAIN','ENTER','ENCODER PUSH','NAV LEFT','NAV RIGHT')
    if name=='F1':command(app,'channel','beta' if app.update_status.get('channel')=='release' else 'release')
    elif name=='F2':command(app,'install' if app.update_status.get('available') else 'check')
    elif name in ('F3','MAIN','NAV LEFT'):app.open_settings('SYSTEM')
    elif name in ('ENTER','ENCODER PUSH'):command(app,'install')
    else:return name=='NAV RIGHT'
    return True

def display(app):
    s=app.update_status;body=['NOW '+s.get('current',VERSION),'NEW '+(s.get('latest') or '--'),s.get('state','OFFLINE')]
    if not s.get('configured'):body[-1]='NOT CONFIGURED'
    if s.get('busy'):body[-1]=s['state']+' '+str(s.get('progress',0))+'%'
    if s.get('error'):body[-1]=s['error']
    return 'UPDATE / '+s.get('channel','release').upper(),body,'OS UPDATES INCLUDED'


def prepare(app,busy,now):
    if busy or app.playing or app.recording or app.capture_armed or app.capture_started is not None:
        raise ValueError('Stop playback/recording and finish processing first.')
    app.update_lock_until=now+10;app.message='UPDATING...'
    return {'ok':True}
