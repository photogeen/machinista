"""Import OB-Xd, DX7/Dexed or RaffoSynth parameter banks without loading executable code."""
import hashlib
import json
import math
import re
import struct
import xml.etree.ElementTree as ET
from app.plugin_profiles import profiles,validate_bank,bank_folder,_cache

MAX_SIZE=8*1024**2

def decode_obxd(data,p,name):
    specs=p['parameters'];defaults={v['symbol']:v['default'] for v in specs}
    def patch(label,values):
        result=dict(defaults)
        for v in specs:
            if v['engineIndex'] in values:
                value=float(values[v['engineIndex']])
                if not math.isfinite(value) or not 0<=value<=1:raise ValueError('Invalid OB-Xd parameter')
                result[v['symbol']]=value
        return dict(name=(label.strip() or 'Untitled')[:128],controls=result)
    def u32(b,offset):
        if len(b)<offset+4:raise ValueError('Truncated preset file')
        return struct.unpack_from('>I',b,offset)[0]
    def record(b):
        if len(b)<28 or b[:4]!=b'CcnK' or b[16:20]!=b'Obxd':raise ValueError('Not a legacy OB-Xd bank')
        size=u32(b,4)
        if size and size+8!=len(b):raise ValueError('Invalid VST bank size')
        kind=b[8:12];count=u32(b,24)
        if kind in (b'FBCh',b'FPCh'):
            offset=160 if kind==b'FBCh' else 60;n=u32(b,offset-4)
            if not n or offset+n!=len(b):raise ValueError('Truncated OB-Xd bank chunk')
            return xml(b[offset:])
        if kind==b'FxCk':
            if count>256 or len(b)!=56+count*4:raise ValueError('Invalid parameter program')
            return [patch(b[28:56].split(b'\0')[0].decode('utf-8','replace'),dict(enumerate(struct.unpack_from('>'+str(count)+'f',b,56))))]
        if kind==b'FxBk':
            if not 1<=count<=256:raise ValueError('Invalid program count')
            offset=156;result=[]
            for _ in range(count):
                n=u32(b,offset+4)+8
                if n<56 or offset+n>len(b):raise ValueError('Invalid program size')
                result+=record(b[offset:offset+n]);offset+=n
            if offset!=len(b):raise ValueError('Trailing bank data')
            return result
        raise ValueError('Unsupported OB-Xd bank version')
    def xml(chunk):
        if chunk.startswith(b'VC2!'):
            if len(chunk)<8:raise ValueError('Truncated XML chunk')
            n=struct.unpack_from('<I',chunk,4)[0]
            if not n or n>len(chunk)-8:raise ValueError('Invalid XML chunk size')
            chunk=chunk[8:8+n]
        text=chunk.rstrip(b'\0').decode('utf-8')
        if re.search(r'<!\s*(DOCTYPE|ENTITY)',text,re.I):raise ValueError('XML declarations not allowed')
        # JUCE's legacy serializer permits numeric attribute names. Repair only
        # attribute tokens outside quoted strings, never preset-name contents.
        text=re.sub(r'''("[^"]*"|'[^']*')|(?<=\s)(\d+)(?=\s*=)''',lambda m:m[1] if m[1] else 'p_'+m[2],text)
        root=ET.fromstring(text)
        if root.tag!='Datsounds':raise ValueError('Not a legacy OB-Xd XML bank')
        nodes=root.findall('./programs/program') or [root]
        if len(nodes)>256:raise ValueError('Too many patches')
        result=[]
        for node in nodes:
            values={int(k[2:]):v for k,v in node.attrib.items() if re.fullmatch(r'p_\d+',k)}
            if not values:raise ValueError('Missing OB-Xd parameters')
            result.append(patch(node.get('programName','Untitled'),values))
        return result
    patches=record(data) if data.startswith(b'CcnK') else xml(data)
    return validate_bank(dict(schema=1,uri=p['uri'],name=name[:128],patches=patches),p)

def import_bank(root,profile_id,name,data):
    p=next((v for v in profiles() if v['id']==profile_id and v['provider']=='parameter-bank'),None)
    if not p:raise ValueError('Unsupported plugin profile')
    if not isinstance(data,bytes) or not 0<len(data)<=MAX_SIZE:raise ValueError('Bank must be between 1 byte and 8 MiB')
    from pathlib import Path
    title=Path(name).stem
    try:
        if name.lower().endswith('.json'):bank=validate_bank(json.loads(data),p)
        elif p['bank_format']=='dx7-sysex':
            from app.dexed_banks import decode_sysex
            bank=decode_sysex(data,p,title)
        elif p['bank_format']=='raffo-dat':
            from app.raffosynth_banks import decode_dat
            bank=decode_dat(data,p,title)
        else:bank=decode_obxd(data,p,title)
    except (ET.ParseError,UnicodeError,struct.error,TypeError,KeyError,OverflowError) as e:raise ValueError('Invalid preset bank') from e
    encoded=(json.dumps(bank,ensure_ascii=True,sort_keys=True,indent=2)+'\n').encode()
    bank_id=hashlib.sha256(encoded).hexdigest()[:24];folder=bank_folder(root,p);folder.mkdir(parents=True,exist_ok=True)
    destination=folder/(bank_id+'.json')
    if folder.is_symlink() or destination.is_symlink():raise ValueError('Unsafe bank path')
    import os,tempfile
    fd,tmp=tempfile.mkstemp(prefix='.import-',dir=folder)
    try:
        with os.fdopen(fd,'wb') as f:f.write(encoded)
        os.replace(tmp,destination)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    _cache.clear();return dict(id=bank_id,name=bank['name'],patches=len(bank['patches']),path=str(destination))
