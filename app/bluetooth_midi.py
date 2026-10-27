"""Nonblocking controller UI/client for the isolated BLE-MIDI service."""
from concurrent.futures import ThreadPoolExecutor
import json
import socket
from app.storage import save_json

SOCKET='/run/maschineos-bluetooth/control.sock'
MIDI_UUID='03b80e5a-ede8-4b33-a751-6ce34ec4c700'

def request(command):
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as connection:
        connection.settimeout(.5);connection.connect(SOCKET)
        connection.sendall(json.dumps(command).encode()+b'\n');data=b''
        while b'\n' not in data:
            chunk=connection.recv(16384)
            if not chunk:raise OSError('Bluetooth service closed')
            data+=chunk
            if len(data)>65536:raise OSError('Bluetooth status oversized')
        return json.loads(data.split(b'\n',1)[0])

class BluetoothMidi:
    def __init__(self,call=request):
        self.call=call;self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='bluetooth-control')
        self.future=None;self.queue=[];self.next_poll=0;self.current=None;self.retry_at=0
    def submit(self,operation,address=None):
        command={'op':operation}
        if address:command['address']=address
        if operation in ('on','off'):self.queue=[c for c in self.queue if c['op'] not in ('on','off')]
        if command not in self.queue and len(self.queue)<8:self.queue.append(command)
    def poll(self,now):
        result=None
        if self.future is not None and self.future.done():
            try:result=self.future.result()
            except (OSError,ValueError):
                result={'enabled':False,'error':'BLUETOOTH UNAVAILABLE','devices':[]}
                # Preserve the saved enable preference if the service starts
                # after the UI, without blocking input or flooding its socket.
                if self.current['op'] in ('on','off') and not any(c['op'] in ('on','off') for c in self.queue):
                    self.queue.insert(0,self.current);self.retry_at=now+.5
            self.future=None
        if self.future is None and now>=self.retry_at and (self.queue or now>=self.next_poll):
            command=self.queue.pop(0) if self.queue else {'op':'status'}
            self.current=command;self.future=self.pool.submit(self.call,command);self.next_poll=now+.5
        return result
    def close(self):self.pool.shutdown(wait=False,cancel_futures=True)

def devices(app):return app.bluetooth_status.get('devices',[])

def command(app,operation):
    if operation in ('on','off'):
        app.settings['ble_midi']=operation=='on';save_json(app.settings_path,app.settings)
    if operation in ('connect','disconnect'):
        rows=devices(app)
        if not rows:app.message='NO BLE MIDI DEVICE';return
        address=rows[min(app.bluetooth_index,len(rows)-1)]['address']
    else:address=None
    app.actions.append(('bluetooth',(operation,address)));app.message=''

def button(app,name,pressed):
    if app.page!='BLUETOOTH MIDI':return False
    if not pressed:return name in ('F1','F2','F3','MAIN','ENTER','ENCODER PUSH','NAV LEFT','NAV RIGHT')
    if name=='F1':command(app,'off' if app.bluetooth_status.get('enabled') else 'on')
    elif name=='F2':command(app,'pair' if app.shift else 'scan')
    elif name in ('F3','MAIN'):app.open_settings('MIDI')
    elif name in ('ENTER','ENCODER PUSH'):
        rows=devices(app);row=rows[min(app.bluetooth_index,len(rows)-1)] if rows else {}
        command(app,'disconnect' if row.get('connected') else 'connect')
    else:return name in ('NAV LEFT','NAV RIGHT')
    return True

def display(app):
    state=app.bluetooth_status;rows=devices(app);index=min(app.bluetooth_index,max(0,len(rows)-1))
    status=state.get('error') or ('STARTING' if state.get('starting') else 'PAIRING '+str(state.get('pair_seconds',0))+'S' if state.get('pair_seconds') else 'SCANNING' if state.get('scanning') else 'ON' if state.get('enabled') else 'OFF')
    first=max(0,index-1)
    body=[('>' if n==index else ' ')+row['name']+(' [ON]' if row.get('connected') else '') for n,row in enumerate(rows) if first<=n<first+3]
    if not body:body=['NO BLE MIDI DEVICES','IPAD: CONNECT TO','Machinista']
    return 'BLE MIDI: '+status,body,'ENC SELECT / ENTER CONNECT'
