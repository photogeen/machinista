"""Export-only audio container validation; no playback/import behavior changes."""
import math
from pathlib import Path
import struct

FORMATS=('WAV','AIFF')
DEPTHS=(16,24,32)


def export_format(request):
    format=request.get('format','WAV');bits=request.get('bits',16)
    if format not in FORMATS or type(bits) is not int or bits not in DEPTHS:raise ValueError('INVALID EXPORT FORMAT')
    return format,bits


def verify_audio_export(path,format,bits,rate,frames):
    """Bounded chunk reader, checks physical data and exact metadata, including float."""
    size=Path(path).stat().st_size;big=format=='AIFF';order='big' if big else 'little'
    with Path(path).open('rb') as stream:
        header=stream.read(12)
        if len(header)!=12 or header[:4]!=(b'FORM' if big else b'RIFF') or int.from_bytes(header[4:8],order)+8!=size:raise ValueError('INVALID EXPORT CONTAINER')
        expected=b'AIFC' if bits==32 else b'AIFF'
        if header[8:12]!=(expected if big else b'WAVE'):raise ValueError('INVALID EXPORT TYPE')
        info=None;payload=None;fact=None;version=None
        while stream.tell()<size:
            chunk=stream.read(8)
            if len(chunk)!=8:raise ValueError('TRUNCATED EXPORT CHUNK')
            kind=chunk[:4];length=int.from_bytes(chunk[4:],order);position=stream.tell()
            if position+length+(length&1)>size:raise ValueError('TRUNCATED EXPORT DATA')
            if kind==b'fmt ' and not big:
                data=stream.read(min(length,16))
                if len(data)!=16:raise ValueError('INVALID WAV FORMAT')
                code,channels,hz,byte_rate,align,depth=struct.unpack('<HHIIHH',data)
                info=(channels,hz,depth)
                if code!=(3 if bits==32 else 1) or align!=2*(bits//8) or byte_rate!=rate*align:raise ValueError('INVALID WAV ENCODING')
            elif kind==b'COMM' and big:
                data=stream.read(min(length,28))
                if len(data)<18:raise ValueError('INVALID AIFF FORMAT')
                channels,count,depth,exponent,mantissa=struct.unpack('>HIHHQ',data[:18])
                hz=math.ldexp(mantissa,exponent-16383-63) if exponent else 0
                info=(channels,hz,depth)
                if count!=frames or (bits==32 and (len(data)<24 or data[18:22]!=b'fl32')):raise ValueError('INVALID AIFF ENCODING')
            elif kind==b'fact' and not big:fact=int.from_bytes(stream.read(min(length,4)),'little')
            elif kind==b'FVER' and big:version=stream.read(min(length,4))
            elif kind==(b'SSND' if big else b'data'):
                if big:
                    if length<8 or stream.read(8)!=b'\0'*8:raise ValueError('INVALID AIFF SOUND DATA')
                    payload=(position+8,length-8)
                else:payload=(position,length)
            stream.seek(position+length+(length&1))
        if info!=(2,rate,bits) or payload is None or payload[1]!=frames*2*(bits//8):raise ValueError('INVALID EXPORT AUDIO')
        if bits==32 and (version!=b'\xa2\x80\x51\x40' if big else fact!=frames):raise ValueError('INVALID FLOAT EXPORT')
        stream.seek(payload[0]+payload[1]-2*(bits//8))
        if len(stream.read(2*(bits//8)))!=2*(bits//8):raise ValueError('TRUNCATED EXPORT')
    return payload[0]
