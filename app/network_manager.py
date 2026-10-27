"""Independent NetworkManager Wi-Fi fallback; never imports the audio engine."""
import configparser
import grp
import json
import os
from pathlib import Path
import queue
import re
import socketserver
import subprocess
import threading
import time
import uuid

AP_ID='machinista-hotspot'
CLIENT_ID='machinista-home'
ADDRESS='10.42.0.1/24'

def fields(line):
    result=[];word='';escaped=False
    for char in line:
        if escaped:word+=char;escaped=False
        elif char=='\\':escaped=True
        elif char==':':result.append(word);word=''
        else:word+=char
    result.append(word)
    return result

def hotspot_name(mac):
    compact=mac.replace(':','').upper()
    if not re.fullmatch('[0-9A-F]{12}',compact):raise ValueError('Invalid MAC address')
    return 'Machinista-'+compact[-4:]

def credentials(ssid,password):
    if not isinstance(ssid,str) or not 1<=len(ssid.encode())<=32 or any(ord(c)<32 for c in ssid):raise ValueError('Invalid SSID.')
    if not isinstance(password,str) or password and not (8<=len(password.encode())<=63 or re.fullmatch('[0-9a-fA-F]{64}',password)):raise ValueError('Wi-Fi password: 8–63 characters (or 64 hexadecimal digits).')
    if any(ord(c)<32 for c in password):raise ValueError('Invalid Wi-Fi password.')
    return ssid,password

def keyvalue(value):return value.replace('\\','\\\\').replace(' ','\\s')

class Manager:
    def __init__(self,interface='wlan0',profiles=Path('/etc/NetworkManager/system-connections')):
        self.interface=interface;self.profiles=Path(profiles);self.jobs=queue.Queue(maxsize=1)
        self.lock=threading.Lock();self.busy=False;self.message='';self.last_try=0;self.down_since=None
        # The PHY address remains permanent even when NM randomizes scan MACs.
        base=Path('/sys/class/net')/interface
        mac=base/'phy80211/macaddress'
        if not mac.exists():mac=base/'address'
        self.ssid=hotspot_name(mac.read_text().strip());self.ap_uuid=None
    def nm(self,*args,timeout=15):
        result=subprocess.run(['nmcli',*args],capture_output=True,text=True,timeout=timeout,env={**os.environ,'LC_ALL':'C'})
        if result.returncode:raise OSError('Wi-Fi operation failed.')
        return result.stdout.strip()
    def profile(self,kind,ssid,password):
        identity=AP_ID if kind=='ap' else CLIENT_ID
        path=self.profiles/(identity+'.nmconnection');identifier=str(uuid.uuid5(uuid.NAMESPACE_DNS,identity))
        cfg=configparser.ConfigParser(interpolation=None)
        cfg['connection']={'id':identity,'uuid':identifier,'type':'wifi','interface-name':self.interface,'autoconnect':'false' if kind=='ap' else 'true','autoconnect-retries':'1','auth-retries':'1'}
        cfg['wifi']={'mode':kind,'ssid':';'.join(str(b) for b in ssid.encode())+';','cloned-mac-address':'permanent'}
        if kind=='ap':cfg['wifi'].update({'band':'bg','channel':'6'})
        if password:cfg['wifi-security']={'key-mgmt':'wpa-psk','psk':keyvalue(password),'psk-flags':'0'}
        cfg['ipv4']={'method':'shared','address1':ADDRESS,'never-default':'true'} if kind=='ap' else {'method':'auto'}
        cfg['ipv6']={'method':'disabled' if kind=='ap' else 'auto'}
        self.profiles.mkdir(parents=True,exist_ok=True)
        temporary=path.with_suffix('.tmp')
        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,'w') as out:cfg.write(out,space_around_delimiters=False)
        os.chmod(temporary,0o600);os.replace(temporary,path)
        self.nm('connection','load',str(path))
        return identifier
    def active(self):
        rows=[fields(line) for line in self.nm('-t','-f','UUID,TYPE,DEVICE','connection','show','--active').splitlines()]
        return next((row[0] for row in rows if len(row)==3 and row[1]=='802-11-wireless' and row[2]==self.interface),None)
    def status(self):
        active=self.active();mode='hotspot' if active==self.ap_uuid else 'wifi' if active else 'offline'
        address=self.nm('-g','IP4.ADDRESS','device','show',self.interface).splitlines()
        ssid=self.ssid if mode=='hotspot' else self.nm('-g','802-11-wireless.ssid','connection','show',active) if active else ''
        return dict(mode=mode,ssid=ssid,address=address[0].split('/')[0] if address else '',hotspot=self.ssid,busy=self.busy,message=self.message)
    def scan(self):
        rows=[]
        for line in self.nm('-t','--escape','yes','-f','SSID,SIGNAL,SECURITY','device','wifi','list','ifname',self.interface,'--rescan','yes').splitlines():
            parts=fields(line)
            if len(parts)!=3 or not parts[0] or parts[0]==self.ssid:continue
            if not any(r['ssid']==parts[0] for r in rows):rows.append(dict(ssid=parts[0],signal=int(parts[1] or 0),security=parts[2]))
        return dict(networks=sorted(rows,key=lambda r:-r['signal']))
    def clients(self):
        result=[]
        for line in self.nm('-t','-f','UUID,TYPE','connection','show').splitlines():
            parts=fields(line)
            if len(parts)==2 and parts[1]=='802-11-wireless' and parts[0]!=self.ap_uuid:
                mode=self.nm('-g','802-11-wireless.mode','connection','show',parts[0])
                if mode!='ap':result.append((parts[0],self.nm('-g','802-11-wireless.ssid','connection','show',parts[0])))
        return result
    def refresh_smb(self,identifier):
        if getattr(self,'smb_connection',None)==identifier:return
        # Samba keeps its explicit interface restriction. Rebind when the
        # single Wi-Fi radio changes its address between client and AP mode.
        subprocess.run(['systemctl','try-restart','smbd.service'],check=False,timeout=10,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        self.smb_connection=identifier
    def activate(self,identifier):
        self.nm('--wait','20','connection','up','uuid',identifier,'ifname',self.interface,timeout=25)
        self.refresh_smb(identifier)
    def fallback(self):
        if self.active()!=self.ap_uuid:self.activate(self.ap_uuid)
    def submit(self,ssid,password):
        ssid,password=credentials(ssid,password)
        with self.lock:
            if self.busy:raise ValueError('A Wi-Fi connection is already being configured.')
            self.busy=True;self.message='Connecting.'
        self.jobs.put((ssid,password));return dict(ok=True,hotspot=self.ssid,address='10.42.0.1')
    def tick(self,now):
        try:ssid,password=self.jobs.get_nowait()
        except queue.Empty:pass
        else:
            # Return the HTTP response before the hotspot disappears.
            time.sleep(2)
            try:self.activate(self.profile('infrastructure',ssid,password));self.message='Connected to Wi-Fi.'
            except (OSError,subprocess.TimeoutExpired):
                self.message='Wi-Fi connection failed. The hotspot is active again.';self.fallback()
            finally:self.busy=False;self.last_try=now
            return
        active=self.active()
        if active:self.refresh_smb(active)
        if active and active!=self.ap_uuid:
            self.down_since=None;self.message='Connected to Wi-Fi.';return
        if not active:
            if self.down_since is None:self.down_since=now
            if now-self.down_since<15:return
        if now-self.last_try>=60:
            self.last_try=now
            try:visible={r['ssid'] for r in self.scan()['networks']}
            except (OSError,subprocess.TimeoutExpired):visible=set()
            for identifier,ssid in self.clients():
                if ssid in visible:
                    try:self.activate(identifier);self.down_since=None;return
                    except (OSError,subprocess.TimeoutExpired):pass
        self.fallback()
    def run(self):
        while True:
            try:self.tick(time.monotonic())
            except (OSError,ValueError,subprocess.TimeoutExpired):self.message='Checking Wi-Fi again.'
            time.sleep(4)

class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(5)
        try:
            raw=self.rfile.readline(4097)
            if len(raw)>4096:raise ValueError('Request too large.')
            request=json.loads(raw);manager=self.server.manager;action=request.get('action')
            if action=='status':result=manager.status()
            elif action=='scan':result=manager.scan()
            elif action=='connect':result=manager.submit(request.get('ssid'),request.get('password'))
            else:raise ValueError('Unknown Wi-Fi operation.')
        except Exception as error:result={'error':str(error) if isinstance(error,ValueError) else 'Wi-Fi service unavailable.'}
        self.wfile.write(json.dumps(result).encode()+b'\n')

def main():
    path=Path('/run/machinista-network/control.sock');path.parent.mkdir(exist_ok=True)
    path.unlink(missing_ok=True)
    manager=Manager(os.environ.get('MACHINISTA_WIFI_INTERFACE','wlan0'))
    manager.nm('radio','wifi','on');manager.ap_uuid=manager.profile('ap',manager.ssid,'machinista')
    with socketserver.ThreadingUnixStreamServer(str(path),Handler) as server:
        server.manager=manager;os.chown(path,0,grp.getgrnam(os.environ.get('MACHINISTA_NETWORK_GROUP','machinista')).gr_gid);os.chmod(path,0o660)
        threading.Thread(target=manager.run,daemon=True).start();server.serve_forever()
