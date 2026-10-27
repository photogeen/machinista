"""ALSA sequencer/virtual-raw-MIDI bridge mapping, independent of card IDs."""
from pathlib import Path
import json
import re
from app.devices import MidiDevice

def parse_ports(text):
    result=[];client=None;name=None
    for line in text.splitlines():
        match=re.match(r"client (\d+): '(.*)' \[",line)
        if match:client=int(match[1]);name=match[2];continue
        match=re.match(r"\s+(\d+) '(.*)'\s*$",line)
        if match and client is not None:result.append((client,int(match[1]),name,match[2].strip()))
    return result

def parse_connections(text):
    result=set();client=port=None
    for line in text.splitlines():
        match=re.match(r"client (\d+):",line)
        if match:client=int(match[1]);port=None;continue
        match=re.match(r"\s+(\d+) '",line)
        if match:port=int(match[1]);continue
        if client is not None and port is not None and 'Connecting To:' in line:
            for target in re.findall(r'(\d+):(\d+)',line.split('Connecting To:',1)[1]):result.add(((client,port),tuple(map(int,target))))
    return result

def raw_card(proc=Path('/proc/asound')):
    for card in proc.glob('card*'):
        try:
            if (card/'id').read_text().strip()=='maschineBLE':return int(card.name[4:])
        except (OSError,ValueError):pass
    return None

def discover_ble(proc=Path('/proc/asound'),dev=Path('/dev/snd'),manifest=Path('/run/maschineos-bluetooth/ports.json')):
    card=raw_card(proc)
    if card is None:return []
    try:rows=json.loads(manifest.read_text())
    except (OSError,ValueError):return []
    result=[]
    if not isinstance(rows,list):return []
    for row in rows[:8]:
        if not isinstance(row,dict):continue
        slot=row.get('slot');key=row.get('key');name=row.get('name')
        if type(slot) is not int or not 0<=slot<8 or not isinstance(key,str) or not isinstance(name,str):continue
        if not re.fullmatch(r'ble:(server|[0-9A-Fa-f:]{17})',key):continue
        path=dev/f'midiC{card}D{slot}'
        if path.exists():result.append(MidiDevice(key,'BT '+name[:60],str(path)))
    return result
