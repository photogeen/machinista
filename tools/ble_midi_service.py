#!/usr/bin/env python3
"""Privileged BLE-MIDI service; all MIDI traffic uses ALSA, never this socket.

The audio-group control socket accepts only fixed operations and BlueZ-known
BLE-MIDI device addresses. Pairing is explicitly opened for 120 seconds.
"""
from pathlib import Path
import grp
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
from app.bluetooth_midi import MIDI_UUID
from app.ble_midi_bridge import parse_ports,parse_connections,raw_card

ROOT=Path(__file__).resolve().parents[1]
RUN=Path('/run/maschineos-bluetooth')
STATE=Path('/var/lib/maschineos-bluetooth')
PROPS='org.freedesktop.DBus.Properties'

class Rejected(dbus.DBusException):_dbus_error_name='org.bluez.Error.Rejected'

class Agent(dbus.service.Object):
    def __init__(self,owner):
        self.owner=owner;super().__init__(owner.bus,'/maschineos/agent')
    def allow(self,device):
        if time.monotonic()>=self.owner.pair_until:raise Rejected('Open pairing on Machinista first')
    @dbus.service.method('org.bluez.Agent1',in_signature='',out_signature='')
    def Release(self):pass
    @dbus.service.method('org.bluez.Agent1',in_signature='o',out_signature='')
    def RequestAuthorization(self,device):self.allow(device)
    @dbus.service.method('org.bluez.Agent1',in_signature='ou',out_signature='')
    def RequestConfirmation(self,device,passkey):self.allow(device)
    @dbus.service.method('org.bluez.Agent1',in_signature='os',out_signature='')
    def AuthorizeService(self,device,uuid):
        if str(uuid).lower()!=MIDI_UUID:raise Rejected('MIDI only')
        if not self.owner.props(device).get('Trusted'):self.allow(device)
    @dbus.service.method('org.bluez.Agent1',in_signature='o',out_signature='s')
    def RequestPinCode(self,device):raise Rejected('PIN entry unsupported')
    @dbus.service.method('org.bluez.Agent1',in_signature='o',out_signature='u')
    def RequestPasskey(self,device):raise Rejected('Passkey entry unsupported')
    @dbus.service.method('org.bluez.Agent1',in_signature='os',out_signature='')
    def DisplayPinCode(self,device,pincode):self.owner.error='PIN '+str(pincode)
    @dbus.service.method('org.bluez.Agent1',in_signature='ouq',out_signature='')
    def DisplayPasskey(self,device,passkey,entered):self.owner.error=f'PASSKEY {passkey:06}'
    @dbus.service.method('org.bluez.Agent1',in_signature='',out_signature='')
    def Cancel(self):pass

class Service:
    def __init__(self):
        self.bus=dbus.SystemBus();self.loop=GLib.MainLoop()
        self.enabled=False;self.error='';self.pair_until=self.scan_until=self.start_until=0
        self.child=None;self.adapter=None;self.pending=set();self.suppressed=set();self.next_reconnect=0
        self.rows=[];self.connections=set();self.manifest=[]
        try:self.slots=json.loads((STATE/'slots.json').read_text())
        except (OSError,ValueError):self.slots={}
        self.agent=Agent(self)
        manager=dbus.Interface(self.bus.get_object('org.bluez','/org/bluez'),'org.bluez.AgentManager1')
        manager.RegisterAgent('/maschineos/agent','NoInputNoOutput');manager.RequestDefaultAgent('/maschineos/agent')
        RUN.mkdir(parents=True,exist_ok=True);STATE.mkdir(parents=True,exist_ok=True)
        self.server=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        path=RUN/'control.sock';path.unlink(missing_ok=True);self.server.bind(str(path))
        os.chown(path,0,grp.getgrnam('audio').gr_gid);os.chmod(path,0o660)
        self.server.listen(8);self.server.setblocking(False)
        GLib.io_add_watch(self.server,GLib.IO_IN,self.accept)
        GLib.timeout_add(1000,self.tick)
        self.publish([])

    def objects(self):return dbus.Interface(self.bus.get_object('org.bluez','/'),'org.freedesktop.DBus.ObjectManager').GetManagedObjects()
    def props(self,path):return dbus.Interface(self.bus.get_object('org.bluez',path),PROPS).GetAll('org.bluez.Device1')
    def adapter_props(self):return dbus.Interface(self.bus.get_object('org.bluez',self.adapter),PROPS)
    def adapter_call(self):return dbus.Interface(self.bus.get_object('org.bluez',self.adapter),'org.bluez.Adapter1')
    def fail(self,error):
        name=error.get_dbus_name() if isinstance(error,dbus.DBusException) else ''
        self.error={
            'org.bluez.Error.InProgress':'CONNECTION BUSY',
            'org.freedesktop.DBus.Error.NoReply':'CONNECTION TIMEOUT',
            'org.freedesktop.DBus.Error.Timeout':'CONNECTION TIMEOUT',
            'org.bluez.Error.AuthenticationRejected':'PAIRING REJECTED',
            'org.bluez.Error.AuthenticationFailed':'PAIRING FAILED',
            'org.freedesktop.DBus.Error.UnknownObject':'DEVICE OFFLINE',
        }.get(name,str(error)[-120:])
        print(str(error),flush=True)

    def power(self,on):
        if on==self.enabled and (not on or self.start_until or self.child and self.child.poll() is None):return
        self.error='';self.pair_until=self.scan_until=0
        if not on:
            self.start_until=0
            if self.adapter:
                try:self.adapter_call().StopDiscovery()
                except dbus.DBusException:pass
                self.adapter_props().Set('org.bluez.Adapter1','Pairable',False)
            if self.child:
                self.child.terminate()
                try:self.child.wait(timeout=2)
                except subprocess.TimeoutExpired:self.child.kill();self.child.wait()
                self.child=None
            for path,interfaces in self.objects().items():
                p=interfaces.get('org.bluez.Device1',{})
                if MIDI_UUID in [str(u).lower() for u in p.get('UUIDs',[])] and p.get('Connected'):
                    dbus.Interface(self.bus.get_object('org.bluez',path),'org.bluez.Device1').Disconnect(reply_handler=lambda:None,error_handler=self.fail)
            self.enabled=False;self.publish([]);return
        subprocess.run(['/usr/sbin/rfkill','unblock','bluetooth'],check=True,timeout=3)
        self.adapter=next((str(p) for p,i in self.objects().items() if 'org.bluez.Adapter1' in i),None)
        if not self.adapter:raise ValueError('NO BLUETOOTH ADAPTER')
        self.adapter_props().Set('org.bluez.Adapter1','Alias','Machinista')
        subprocess.run(['/usr/sbin/modprobe','snd-virmidi','id=maschineBLE','midi_devs=4'],check=True,timeout=3)
        if raw_card() is None:raise ValueError('BLE MIDI CARD UNAVAILABLE')
        self.enabled=True;self.start_until=time.monotonic()+10;self.suppressed.clear()
        self.start()

    def start(self):
        props=self.adapter_props()
        if not props.Get('org.bluez.Adapter1','Powered'):
            try:props.Set('org.bluez.Adapter1','Powered',True)
            except dbus.DBusException as error:
                if error.get_dbus_name() not in ('org.bluez.Error.Busy','org.bluez.Error.InProgress'):raise
            return
        props.Set('org.bluez.Adapter1','Pairable',False)
        self.child=subprocess.Popen(['/usr/bin/bluealsa','-p','midi','--midi-advertisement'],stdout=subprocess.DEVNULL)
        self.start_until=0

    def pair(self):
        if not self.enabled:raise ValueError('TURN BLUETOOTH ON FIRST')
        self.pair_until=time.monotonic()+120;self.error=''
        self.adapter_props().Set('org.bluez.Adapter1','Pairable',True)

    def scan(self):
        if not self.enabled:raise ValueError('TURN BLUETOOTH ON FIRST')
        self.adapter_call().SetDiscoveryFilter({'Transport':'le','UUIDs':dbus.Array([MIDI_UUID],signature='s')})
        try:self.adapter_call().StartDiscovery()
        except dbus.DBusException as error:
            if error.get_dbus_name()!='org.bluez.Error.InProgress':raise
        self.scan_until=time.monotonic()+20;self.error=''

    def stop_scan(self):
        self.scan_until=0
        try:self.adapter_call().StopDiscovery()
        except dbus.DBusException as error:
            if not (error.get_dbus_name()=='org.bluez.Error.Failed' and 'No discovery started' in str(error)):raise

    def connect(self,address):
        if not self.enabled:raise ValueError('TURN BLUETOOTH ON FIRST')
        if address in self.pending:return
        row=next((r for r in self.rows if r['address']==address),None)
        if not row:raise ValueError('UNKNOWN BLE MIDI DEVICE')
        self.pending.add(address);self.suppressed.discard(address)
        obj=self.bus.get_object('org.bluez',row['path']);dev=dbus.Interface(obj,'org.bluez.Device1')
        def failed(e):
            name=e.get_dbus_name() if isinstance(e,dbus.DBusException) else ''
            if name in ('org.freedesktop.DBus.Error.NoReply','org.freedesktop.DBus.Error.Timeout','org.bluez.Error.InProgress'):
                # A D-Bus timeout does not cancel BlueZ's pending pairing.
                # Release only this device's attempt so the next retry works.
                dev.CancelPairing(reply_handler=lambda:None,error_handler=lambda _:None)
            self.pending.discard(address);self.fail(e)
        def connected():self.pending.discard(address);self.error='';dbus.Interface(obj,PROPS).Set('org.bluez.Device1','Trusted',True)
        def connect_now():dev.Connect(reply_handler=connected,error_handler=failed,timeout=15)
        if row['paired']:connect_now()
        else:
            self.pair();dev.Pair(reply_handler=connect_now,error_handler=failed,timeout=30)

    def operation(self,command):
        op=command.get('op')
        if op=='on':self.power(True)
        elif op=='off':self.power(False)
        elif op=='pair':self.pair()
        elif op=='scan':self.scan()
        elif op in ('connect','disconnect'):
            address=command.get('address','')
            if not isinstance(address,str) or not re.fullmatch(r'(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}',address):raise ValueError('INVALID DEVICE')
            if op=='connect':self.connect(address)
            else:
                row=next((r for r in self.rows if r['address']==address),None)
                if not row:raise ValueError('UNKNOWN BLE MIDI DEVICE')
                self.suppressed.add(address)
                dbus.Interface(self.bus.get_object('org.bluez',row['path']),'org.bluez.Device1').Disconnect(reply_handler=lambda:None,error_handler=self.fail)
        elif op!='status':raise ValueError('UNKNOWN OPERATION')

    def accept(self,*_):
        connection,_=self.server.accept()
        try:
            connection.settimeout(.05);data=connection.recv(8192)
            command=json.loads(data.split(b'\n',1)[0]);self.operation(command)
        except Exception as error:self.fail(error)
        try:
            state=dict(enabled=self.enabled,starting=bool(self.start_until),error=self.error,devices=[{k:v for k,v in row.items() if k!='path'} for row in self.rows],
                       pair_seconds=max(0,int(self.pair_until-time.monotonic())),scanning=self.scan_until>time.monotonic(),ports=self.manifest)
            connection.sendall(json.dumps(state).encode()+b'\n')
        except OSError:pass
        finally:connection.close()
        return True

    def publish(self,rows):
        self.manifest=rows;temp=RUN/'ports.tmp';temp.write_text(json.dumps(rows));os.chmod(temp,0o644);temp.replace(RUN/'ports.json')

    def bridge(self):
        listing=subprocess.run(['aconnect','-l'],capture_output=True,text=True,check=True,timeout=2).stdout
        ports=parse_ports(listing);actual=parse_connections(listing)
        card=raw_card();raw={}
        for client,port,_,name in ports:
            match=re.fullmatch(rf'(?:Virtual Raw MIDI|VirMIDI) {card}-(\d+)',name)
            if match:raw[int(match[1])]=(client,port)
        targets=[]
        for client,port,client_name,name in ports:
            if client_name=='BlueALSA' and name=='BLE MIDI Server':targets.append((0,'ble:server','Machinista',(client,port)))
            elif name.endswith(' Bluetooth'):
                matches=[r for r in self.rows if r['connected'] and client_name in (r['name'],r['original_name'],r['address'])]
                if len(matches)>1:self.error='AMBIGUOUS BLE DEVICE NAME'
                if len(matches)!=1:continue
                row=matches[0];address=row['address'];slot=self.slots.get(address)
                if type(slot) is not int or not 1<=slot<4:
                    slot=next((i for i in range(1,4) if i not in self.slots.values()),None)
                    if slot is None:
                        connected={r['address'] for r in self.rows if r['connected']}
                        old=next((a for a in self.slots if a not in connected),None)
                        if old is not None:slot=self.slots.pop(old)
                    if slot is None:self.error='MAX 3 BLE CONTROLLERS';continue
                    self.slots[address]=slot;(STATE/'slots.json').write_text(json.dumps(self.slots))
                targets.append((slot,'ble:'+address,row['name'],(client,port)))
        wanted=set();rows=[]
        for slot,key,name,remote in targets:
            if slot not in raw:continue
            wanted.update(((raw[slot],remote),(remote,raw[slot])))
            rows.append(dict(slot=slot,key=key,name=name))
        for source,target in self.connections-wanted:
            subprocess.run(['aconnect','-d',f'{source[0]}:{source[1]}',f'{target[0]}:{target[1]}'],capture_output=True,timeout=2)
        ready=set()
        for source,target in wanted:
            if (source,target) in actual:ready.add((source,target));continue
            result=subprocess.run(['aconnect',f'{source[0]}:{source[1]}',f'{target[0]}:{target[1]}'],capture_output=True,timeout=2)
            if result.returncode==0:ready.add((source,target))
        self.connections=ready
        self.publish([row for row in rows if any(source==raw[row['slot']] for source,target in ready) and any(target==raw[row['slot']] for source,target in ready)])

    def tick(self):
        try:
            now=time.monotonic()
            if self.start_until:
                if now>=self.start_until:self.start_until=0;self.enabled=False;raise ValueError('BLUETOOTH START TIMEOUT')
                self.start()
            if self.pair_until and now>=self.pair_until:
                self.pair_until=0;self.adapter_props().Set('org.bluez.Adapter1','Pairable',False)
            if self.scan_until and now>=self.scan_until:
                self.stop_scan()
            self.rows=[]
            for path,interfaces in self.objects().items():
                p=interfaces.get('org.bluez.Device1',{})
                if MIDI_UUID not in [str(u).lower() for u in p.get('UUIDs',[])]:continue
                self.rows.append(dict(path=str(path),address=str(p['Address']),name=str(p.get('Alias',p.get('Name',p['Address']))),original_name=str(p.get('Name','')),
                                      connected=bool(p.get('Connected')),paired=bool(p.get('Paired')),trusted=bool(p.get('Trusted'))))
            self.rows.sort(key=lambda r:(not r['connected'],r['name'],r['address']))
            if self.enabled:
                if self.start_until:return True
                if not self.child or self.child.poll() is not None:raise ValueError('BLE MIDI SERVICE STOPPED')
                self.bridge()
                if now>=self.next_reconnect:
                    self.next_reconnect=now+10
                    for row in self.rows:
                        if row['trusted'] and row['paired'] and not row['connected'] and row['address'] not in self.suppressed:self.connect(row['address'])
        except Exception as error:self.fail(error)
        return True

    def close(self):
        self.power(False);self.loop.quit()

if __name__=='__main__':
    DBusGMainLoop(set_as_default=True);service=Service()
    for sig in (signal.SIGTERM,signal.SIGINT):GLib.unix_signal_add(GLib.PRIORITY_DEFAULT,sig,lambda:service.close())
    service.loop.run()
