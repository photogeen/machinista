"""Portable user chord maps and independent strum/humanization planning."""
import json
import random
import xml.etree.ElementTree as ET
from pathlib import Path

MAX_BYTES=1024*1024
DIRECTIONS=('UP','DOWN','UP ALT','DOWN ALT')
PLAY_DEFAULTS={'strum':0,'direction':'UP','human_time':0,'velocity_spread':0,'velocity_direction':'UP','human_velocity':0}


def integer(value,lo,hi):
    if type(value) is not int or not lo<=value<=hi:raise ValueError(f'Expected an integer from {lo} to {hi}.')
    return value



def chord_voicing(base,step):
    """Rebuild a reversible inversion from its original (possibly open) voicing."""
    notes=sorted(base)
    for _ in range(abs(step)):
        moved=notes.pop(0 if step>0 else -1)+(12 if step>0 else -12)
        while moved in notes:moved+=12 if step>0 else -12
        if not 0<=moved<=127:raise ValueError('MIDI NOTE LIMIT')
        notes.append(moved);notes.sort()
    return notes

def invert_chord(row,up):
    notes=row['notes'];base=row.get('inversion_base',notes);step=row.get('inversion_step',0)
    # Direct voice edits establish a new voicing, never restore stale notes.
    if chord_voicing(base,step)!=sorted(notes):base=notes;step=0
    step+=1 if up else -1
    result=dict(row,notes=chord_voicing(base,step))
    if step:
        result.update(inversion_base=list(base),inversion_step=step)
    else:
        result['notes']=list(base)
        result.pop('inversion_base',None);result.pop('inversion_step',None)
    return result

def normalize(value):
    if not isinstance(value,dict):raise ValueError('Invalid chord preset.')
    name=value.get('name','Untitled')
    if not isinstance(name,str) or not name.strip() or len(name)>80 or any(ord(c)<32 for c in name):raise ValueError('Invalid preset name.')
    rows=value.get('chords');result=[];seen=set()
    if not isinstance(rows,list) or not 1<=len(rows)<=128:raise ValueError('A preset needs 1–128 chord mappings.')
    for row in rows:
        if not isinstance(row,dict):raise ValueError('Invalid chord mapping.')
        key=integer(row.get('input'),0,127);notes=row.get('notes');label=row.get('name','')
        if key in seen:raise ValueError('Each input key can only appear once.')
        if not isinstance(notes,list) or not 1<=len(notes)<=32:raise ValueError('Each chord needs 1–32 notes.')
        if not isinstance(label,str) or len(label)>80 or any(ord(c)<32 for c in label):raise ValueError('Invalid chord name.')
        notes=list(dict.fromkeys(integer(n,0,127) for n in notes))
        item={'input':key,'name':label,'notes':notes}
        if 'inversion_base' in row and 'inversion_step' in row:
            base=row['inversion_base'];step=integer(row['inversion_step'],-512,512)
            if not isinstance(base,list) or not 1<=len(base)<=32:raise ValueError('Invalid inversion voicing.')
            base=list(dict.fromkeys(integer(n,0,127) for n in base))
            if step and chord_voicing(base,step)==sorted(notes):
                item.update(inversion_base=base,inversion_step=step)
        seen.add(key);result.append(item)
    return {'version':1,'name':name.strip(),'root':integer(value.get('root',60),0,127),'chords':result}


def parse(data,filename):
    if not 0<len(data)<=MAX_BYTES:raise ValueError('Chord presets must be 1 byte to 1 MiB.')
    suffix=Path(filename).suffix.lower();name=Path(filename).stem
    if suffix=='.rpc':
        try:text=data.decode('utf-8-sig')
        except UnicodeError as exc:raise ValueError('Ripchord presets must use UTF-8 XML.') from exc
        if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():raise ValueError('XML declarations/entities are not supported.')
        try:
            root=ET.fromstring(text)
            if root.tag!='ripchord':raise ValueError('Not a Ripchord preset.')
            rows=[]
            for item in root.findall('./preset/input'):
                chord=item.find('chord')
                if chord is not None:
                    rows.append({'input':int(item.attrib['note']),'name':chord.get('name',''),
                                 'notes':[int(n) for n in chord.get('notes','').split(';') if n.strip()]})
            return normalize({'name':name,'chords':rows})
        except (ET.ParseError,KeyError,TypeError) as exc:raise ValueError('Invalid Ripchord preset.') from exc
    if suffix not in ('.progression','.json'):raise ValueError('Choose .rpc, .progression or Machinista chord JSON.')
    try:value=json.loads(data)
    except (ValueError,UnicodeError,RecursionError) as exc:raise ValueError('Invalid chord JSON.') from exc
    if suffix=='.progression':
        try:
            rows=value['progression']['chords'];start=60 if len(rows)<=68 else 0
            value={'name':name,'chords':[dict(input=start+i,name=row.get('name',''),notes=row['notes']) for i,row in enumerate(rows)]}
        except (KeyError,TypeError,AttributeError) as exc:raise ValueError('Invalid MPC progression.') from exc
    return normalize(value)


def validate_play(value):
    if not isinstance(value,dict):raise ValueError('Invalid chord performance.')
    result=dict(PLAY_DEFAULTS,**value)
    for key,hi in (('strum',500),('human_time',100),('velocity_spread',127),('human_velocity',64)):integer(result[key],0,hi)
    for key in ('direction','velocity_direction'):
        if result[key] not in DIRECTIONS:raise ValueError('Invalid strum direction.')
    return {key:result[key] for key in PLAY_DEFAULTS}


def plan(notes,velocity,settings,stroke=0,rng=None):
    """Return (delay seconds, pitch, velocity), first/last span = strum ms.

    All randomness is resolved once at attack; recording uses the same result.
    """
    p=validate_play(settings);rng=rng or random;ordered=sorted(set(notes));count=len(ordered)
    def reverse(direction):return direction.startswith('DOWN') ^ (direction.endswith('ALT') and bool(stroke%2))
    if reverse(p['direction']):ordered.reverse()
    result=[]
    for i,note in enumerate(ordered):
        position=i/max(1,count-1)
        # Velocity contour follows pitch direction independently of time direction.
        rank=sorted(ordered).index(note)/max(1,count-1)
        if reverse(p['velocity_direction']):rank=1-rank
        level=velocity+(rank-.5)*p['velocity_spread'] if count>1 else velocity
        level+=rng.uniform(-p['human_velocity'],p['human_velocity']) if p['human_velocity'] else 0
        delay=position*p['strum']+(rng.uniform(0,p['human_time']) if p['human_time'] else 0)
        result.append((delay/1000,note,max(1,min(127,round(level)))))
    return sorted(result,key=lambda item:item[0])
