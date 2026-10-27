"""Validate uploaded PCM WAVs, repairing only provably undersized RIFF headers.

Legacy samplers sometimes omit metadata bytes from the RIFF size while keeping
complete fmt/data chunks. Never infer or extend missing audio, change data sizes,
remove metadata, or convert sample data.
"""
import struct
import wave
import math


def _convert_float32(stream,details):
    """Convert IEEE float to signed PCM32 in place, retaining all RIFF chunks.

    Both encodings use four bytes per sample, so cue/loop metadata and chunk
    offsets stay intact. This operates only on the private upload temporary.
    """
    stream.seek(0,2);size=stream.tell();stream.seek(0);header=stream.read(12)
    if len(header)!=12 or header[:4]!=b'RIFF' or header[8:]!=b'WAVE':return False
    pos=12;fmt=None;audio=None;count=0
    while pos+8<=size:
        count+=1
        if count>4096:raise ValueError('Too many WAV chunks.')
        stream.seek(pos);kind,length=struct.unpack('<4sI',stream.read(8));end=pos+8+length
        if end>size:raise ValueError('The WAV file is incomplete.')
        if kind==b'fmt ':
            if fmt is not None:raise ValueError('Multiple WAV format chunks.')
            if length<16:raise ValueError('Invalid WAV format chunk.')
            fmt=(pos+8,struct.unpack('<HHIIHH',stream.read(16)))
        if kind==b'data':
            if audio is not None:raise ValueError('Multiple WAV audio chunks.')
            audio=(pos+8,length)
        pos=end if end==size else end+(length&1)
    if fmt is None or fmt[1][0]!=3:return False
    encoding,channels,rate,byte_rate,alignment,bits=fmt[1]
    if bits!=32:raise ValueError('Only 32-bit floating-point WAV is supported.')
    if not 1<=channels<=32 or not 8000<=rate<=384000 or alignment!=channels*4 or byte_rate!=rate*alignment:
        raise ValueError('Invalid floating-point WAV format.')
    if pos!=size or audio is None or not audio[1] or audio[1]%alignment:
        raise ValueError('The floating-point WAV audio is incomplete.')
    start,length=audio
    peak=1.0
    for offset in range(start,start+length,65536):
        stream.seek(offset);raw=stream.read(min(65536,start+length-offset))
        for (value,) in struct.iter_unpack('<f',raw):
            if not math.isfinite(value):raise ValueError('WAV contains non-finite audio samples.')
            peak=max(peak,abs(value))
    gain=1.0/peak
    for offset in range(start,start+length,65536):
        stream.seek(offset);raw=stream.read(min(65536,start+length-offset));values=[]
        for (value,) in struct.iter_unpack('<f',raw):
            if not math.isfinite(value):raise ValueError('WAV contains non-finite audio samples.')
            values.append(max(-2147483648,min(2147483647,round(value*gain*2147483648))))
        stream.seek(offset);stream.write(struct.pack('<'+'i'*len(values),*values))
    stream.seek(fmt[0]);stream.write(struct.pack('<H',1))
    stream.seek(4);stream.write(struct.pack('<I',size-8));stream.flush()
    details.update(converted='32-bit PCM',gain_db=20*math.log10(gain))
    return True


def _check_pcm(stream):
    stream.seek(0)
    try:
        with wave.open(stream,'rb') as wav:
            frames=wav.getnframes();width=wav.getsampwidth();channels=wav.getnchannels()
            if frames<1 or width not in (1,2,3,4) or not 1<=channels<=32 or not 8000<=wav.getframerate()<=384000:
                raise ValueError('Unsupported WAV format.')
            wav.setpos(frames-1)
            if len(wav.readframes(1))!=width*channels:raise ValueError('The WAV file is incomplete.')
    except (wave.Error,EOFError,RuntimeError,struct.error) as error:
        # Preserve the parser's actual reason: a generic message hid encoding
        # differences (e.g. IEEE float versus integer PCM) and broken chunks.
        detail=' '.join(str(error).split())[:160]
        if not detail:
            detail='unexpected end of file' if isinstance(error,EOFError) else 'invalid WAV chunk boundary'
        raise ValueError('Invalid or unsupported PCM WAV structure: '+detail+'.') from error


def validate_pcm(stream,details=None):
    if details is None:details={}
    # A valid WAV can have trailing non-RIFF tags. Keep already readable files
    # byte-exact rather than interpreting such tags as broken chunk headers.
    try:_check_pcm(stream);return False
    except ValueError:
        if _convert_float32(stream,details):
            _check_pcm(stream)
            return True
        stream.seek(0,2);size=stream.tell();stream.seek(0);header=stream.read(12)
        if len(header)!=12 or header[:4]!=b'RIFF' or header[8:]!=b'WAVE':raise
        if struct.unpack_from('<I',header,4)[0]+8>=size:raise
    # Walk actual chunk boundaries before trusting a larger RIFF size. The walk
    # reads only headers, independently of audio/sample length.
    pos=12;data_count=0;fmt_seen=False;count=0
    while pos<size:
        count+=1
        if count>4096 or size-pos<8:raise ValueError('Invalid WAV chunk sizes.')
        stream.seek(pos);kind,length=struct.unpack('<4sI',stream.read(8))
        end=pos+8+length
        if end>size:raise ValueError('The WAV file is incomplete.')
        if kind==b'fmt ':fmt_seen=True
        if kind==b'data':
            if not fmt_seen:raise ValueError('WAV format must precede audio data.')
            data_count+=1
        # Accept a final unpadded odd-size chunk, as Python wave does.
        pos=end if end==size else end+(length&1)
    if pos!=size or data_count!=1 or not fmt_seen:raise ValueError('Invalid WAV chunk sizes.')
    stream.seek(4);stream.write(struct.pack('<I',size-8));stream.flush()
    _check_pcm(stream)
    return True
