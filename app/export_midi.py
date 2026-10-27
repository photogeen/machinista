"""Editable Standard MIDI File export, isolated from the live project and audio host."""
import os
import errno
from pathlib import Path
import shutil
import struct
import tempfile
import uuid
from app.export_destination import ExportLocation
from app.export_audio import check_cancel,export_spans
from app.storage import save_json


def vlq(value):
    if not 0<=value<=0x0fffffff:raise ValueError('MIDI TIME LIMIT')
    result=bytearray([value&127]);value>>=7
    while value:result.insert(0,128|(value&127));value>>=7
    return bytes(result)


def meta(kind,data):return bytes((255,kind))+vlq(len(data))+data


def midi_track(events,end):
    data=bytearray();previous=0
    for tick,priority,message in sorted(events,key=lambda e:(e[0],e[1])):
        data+=vlq(tick-previous)+message;previous=tick
    data+=vlq(max(0,end-previous))+b'\xff\x2f\x00'
    return b'MTrk'+struct.pack('>I',len(data))+data


def compile_midi(app,request,cancel=None):
    """Stored notes, not a probabilistic performance: retain muted and empty Sounds."""
    spans=export_spans(app,request);end=sum(length for _,length in spans)
    if end*60/(app.project['tempo']*96)>3600:raise ValueError('EXPORT LIMIT 60 MIN')
    groups=range(len(app.project['groups'])) if request['source']=='ALL GROUPS' else [request['group']]
    selected=[(g,p) for g in groups for p in (range(16) if request['source']!='SOUND' else [request['pad']])]
    events={key:[] for key in selected};offset=0;count=0
    for clips,duration in spans:
        check_cancel(cancel)
        for group,pad in selected:
            pattern=clips[group] if group<len(clips) else None
            if pattern is None:continue
            track=app.project['groups'][group]['pads'][pad];channel=track['channel']-1
            length=app.pattern_ticks(group,pattern)
            for identity,event in app.event_notes(group,pattern).items():
                if identity[0]!=pad:continue
                tick=identity[1]
                if request.get('groove'):tick=app.groove_position(group,pad,tick,length)
                if request['mode']=='SONG' and request.get('scene_retrigger','ON')!='ON':tick=(tick-offset)%length
                for cycle in range(0,duration,length):
                    at=cycle+tick
                    if at>=duration:continue
                    boundary=end-offset-at if request['mode']=='SONG' and request.get('scene_retrigger','ON')!='ON' else duration-at
                    gate=max(1,min(boundary,event.get('length',app.grid_ticks())))
                    for note in event.get('chord') or [event.get('note',track['note'])]:
                        events[group,pad].extend(((offset+at,2,bytes((0x90|channel,note,event['velocity']))),(offset+at+gate,1,bytes((0x80|channel,note,0)))))
                        count+=1
                        if count>100000:raise ValueError('MIDI NOTE LIMIT')
                        if count%512==0:check_cancel(cancel)
        offset+=duration
    tempo=round(60000000/app.project['tempo'])
    tracks=[midi_track([(0,0,meta(3,b'Machinista Tempo')),(0,0,meta(0x51,tempo.to_bytes(3,'big'))),(0,0,meta(0x58,b'\x04\x02\x18\x08'))],end)]
    for group,pad in selected:
        check_cancel(cancel)
        track=app.project['groups'][group]['pads'][pad]
        name=f'{chr(65+group%8)}{group//8+1}:{pad+1:02} '+track.get('name','Sound')
        tracks.append(midi_track([(0,0,meta(3,name.encode('utf-8'))),*events[group,pad]],end))
    return b'MThd'+struct.pack('>IHHH',6,1,len(tracks),96)+b''.join(tracks),end,count


def render_midi_export(request,root,cancel=None,progress=None):
    check_cancel(cancel)
    location=None
    try:
        location=ExportLocation(root,request)
        return _render_midi_export(request,root,cancel,progress,location)
    except OSError as error:
        if error.errno in (errno.EACCES,errno.EPERM,errno.EROFS):raise ValueError('DESTINATION NOT WRITABLE') from error
        if error.errno==errno.ENOSPC:raise ValueError('DESTINATION FULL') from error
        raise
    finally:
        if location is not None:location.close()


def _render_midi_export(request,root,cancel,progress,location):
    from app.model import Application
    root=Path(root);base=location.base
    temporary=base/('.midi-'+uuid.uuid4().hex);temporary.mkdir()
    try:
        check_cancel(cancel)
        if progress is not None:progress.put('WRITING MIDI')
        (root/'cache').mkdir(exist_ok=True)
        if request.get('destination') and shutil.disk_usage(root).free<1024*1024:raise ValueError('SD CACHE FULL')
        with tempfile.TemporaryDirectory(prefix='midi-',dir=root/'cache') as job:
            save_json(Path(job)/'projects'/'current.json',request['project'])
            app=Application(Path(job));data,ticks,notes=compile_midi(app,request,cancel)
        if shutil.disk_usage(base).free<len(data)+1024*1024:raise ValueError('DESTINATION FULL')
        with (temporary/'Notes.mid').open('wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
        save_json(temporary/'Export.json',dict(format='Machinista-MIDI-export',version=1,project=request['project']['name'],mode=request['mode'],source=request['source'],ppq=96,ticks=ticks,notes=notes,timing='GROOVE' if request.get('groove') else 'GRID',policy='All stored notes; mute, solo, probability, links, effects and automation are not baked in.'))
        check_cancel(cancel);location.verify()
        # Model validation restricts project names; retain a safe filename even for direct callers.
        name=''.join(c for c in app.project['name'] if c.isalnum() or c in ' _-').strip() or 'Project'
        for number in range(1,10000):
            destination=base/f'{name}-MIDI-{request["mode"].title()}-{number:03}'
            if not destination.exists():
                temporary.rename(destination);fd=os.open(base,os.O_RDONLY)
                try:os.fsync(fd)
                finally:os.close(fd)
                return location.result(destination.name)
        raise ValueError('EXPORT FOLDER LIMIT')
    finally:
        if temporary.exists():shutil.rmtree(temporary)
