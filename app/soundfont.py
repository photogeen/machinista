"""Bounded, read-only SF2 parser and native-sampler conversion plan.

No shared library, synthesizer, subprocess or live engine access. PCM stays mapped
read-only until a selected preset is extracted by the background import worker.
"""
import math,mmap,struct,wave
from pathlib import Path
MAX_FILE=512*1024**2
SIZES={'phdr':38,'pbag':4,'pmod':10,'pgen':4,'inst':22,'ibag':4,'imod':10,'igen':4,'shdr':46}
DEFAULT={8:13500,9:0,15:0,16:0,17:0,21:-12000,22:-12000,23:-12000,24:-12000,25:0,26:-12000,27:0,28:0,29:0,30:0,33:-12000,34:-12000,35:-12000,36:-12000,37:0,38:-12000,39:0,40:0,48:0,51:0,52:0,54:0,56:100,57:0}
SUPPORTED={0,1,2,3,4,8,9,12,17,33,34,35,36,37,38,41,43,44,45,48,50,51,52,53,54,56,57,58}
LABELS={5:'Modulation LFO → pitch',6:'Vibrato LFO → pitch',7:'Modulation envelope → pitch',10:'Modulation LFO → filter',11:'Modulation envelope → filter',13:'Modulation LFO → volume',15:'Chorus send',16:'Reverb send',21:'Modulation LFO delay',22:'Modulation LFO frequency',23:'Vibrato delay',24:'Vibrato frequency',25:'Modulation envelope delay',26:'Modulation envelope attack',27:'Modulation envelope hold',28:'Modulation envelope decay',29:'Modulation envelope sustain',30:'Modulation envelope release',31:'Key-dependent modulation hold',32:'Key-dependent modulation decay',39:'Key-dependent amplitude hold',40:'Key-dependent amplitude decay',46:'Fixed key',47:'Fixed velocity',57:'Exclusive group'}

def text(raw):return raw.split(b'\0',1)[0].decode('latin1').strip() or 'Untitled'
def tc(value):return 0 if value<=-32768 else 1000*2**(max(-16000,min(16000,value))/1200)

class Font:
 def __init__(self,path):
  self.file=Path(path).open('rb');self.data=None
  try:
   size=self.file.seek(0,2)
   if not 12<=size<=MAX_FILE:raise ValueError('SoundFont must be between 12 bytes and 512 MiB.')
   self.data=mmap.mmap(self.file.fileno(),0,access=mmap.ACCESS_READ);d=self.data
   if d[:4]!=b'RIFF' or d[8:12]!=b'sfbk' or struct.unpack_from('<I',d,4)[0]+8!=size:raise ValueError('Invalid or truncated SF2 RIFF file.')
   self.chunks={};self.info={}
   for tag,start,length in self.chunks_at(12,size):
    if tag!=b'LIST' or length<4:continue
    kind=d[start:start+4]
    for key,off,n in self.chunks_at(start+4,start+length):
     name=key.decode('ascii','replace')
     if kind==b'INFO':self.info[name]=bytes(d[off:off+min(n,4096)])
     elif kind in (b'sdta',b'pdta'):
      if name in self.chunks:raise ValueError('Duplicate SoundFont chunk: '+name)
      self.chunks[name]=(off,n)
   version=self.info.get('ifil',b'')
   if len(version)<4 or struct.unpack_from('<H',version)[0]!=2:raise ValueError('Only uncompressed SoundFont 2 (.sf2) is supported; not SF3.')
   if 'smpl' not in self.chunks or self.chunks['smpl'][1]%2:raise ValueError('Missing or invalid PCM sample data.')
   self.samples=self.chunks['smpl'][1]//2
   if 'sm24' in self.chunks and self.chunks['sm24'][1]<self.samples:raise ValueError('Truncated 24-bit SoundFont samples.')
   self.tables={}
   for key,width in SIZES.items():
    if key not in self.chunks:raise ValueError('Missing SoundFont table: '+key)
    off,n=self.chunks[key]
    if n%width or n>8*1024**2 or n<width:raise ValueError('Invalid SoundFont table: '+key)
    self.tables[key]=(off,n//width)
   if not 2<=self.count('phdr')<=2049 or self.count('shdr')>8193:raise ValueError('SoundFont has too many presets or samples.')
   self.presets=[]
   for i in range(self.count('phdr')-1):
    row=self.record('phdr',i);name,program,bank,bag=struct.unpack_from('<20sHHH',row)
    self.presets.append(dict(index=i,name=text(name),program=program,bank=bank))
   # Verify every header and bag reference before exposing the catalog.
   for header,bags,gens,mods in [('phdr','pbag','pgen','pmod'),('inst','ibag','igen','imod')]:
    field=24 if header=='phdr' else 20;indices=[struct.unpack_from('<H',self.record(header,i),field)[0] for i in range(self.count(header))]
    if indices!=sorted(indices) or any(v>=self.count(bags) for v in indices):raise ValueError('Invalid SoundFont bag references.')
    pairs=[struct.unpack('<HH',self.record(bags,i)) for i in range(self.count(bags))]
    if any(g>=self.count(gens) or m>=self.count(mods) for g,m in pairs) or pairs!=sorted(pairs) or any(pairs[i][1]>pairs[i+1][1] for i in range(len(pairs)-1)):raise ValueError('Invalid SoundFont generator/modulator references.')
  except BaseException:self.close();raise
 def close(self):
  if self.data is not None:self.data.close();self.data=None
  self.file.close()
 def __enter__(self):return self
 def __exit__(self,*args):self.close()
 def chunks_at(self,start,end):
  while start<end:
   if start+8>end:raise ValueError('Truncated SoundFont chunk header.')
   tag,n=struct.unpack_from('<4sI',self.data,start);off=start+8
   if off+n>end:raise ValueError('SoundFont chunk exceeds its container.')
   yield tag,off,n
   start=off+n+(n&1)
  if start!=end:raise ValueError('Invalid SoundFont chunk padding.')
 def count(self,key):return self.tables[key][1]
 def record(self,key,index):
  off,count=self.tables[key]
  if not 0<=index<count:raise ValueError('SoundFont table index out of range.')
  size=SIZES[key];return self.data[off+index*size:off+(index+1)*size]
 def bags(self,header,index):
  table='pbag' if header=='phdr' else 'ibag';gen='pgen' if header=='phdr' else 'igen';mod='pmod' if header=='phdr' else 'imod';field=24 if header=='phdr' else 20
  if not 0<=index<self.count(header)-1:raise ValueError('Invalid preset/instrument reference.')
  lo=struct.unpack_from('<H',self.record(header,index),field)[0];hi=struct.unpack_from('<H',self.record(header,index+1),field)[0];result=[]
  for i in range(lo,hi):
   start,ms=struct.unpack('<HH',self.record(table,i));end,me=struct.unpack('<HH',self.record(table,i+1));values={}
   for j in range(start,end):
    op,raw=struct.unpack('<HH',self.record(gen,j))
    if op>60 or op in values:raise ValueError('Invalid/duplicate SoundFont generator.')
    values[op]=raw if op in (41,43,44,53,54,57,58) else struct.unpack('<h',struct.pack('<H',raw))[0]
   custom=any(self.record(mod,j)!=bytes(10) for j in range(ms,me));result.append((values,custom))
  return result
 @staticmethod
 def global_zones(rows,selector):
  global_values={};global_mod=False;result=[]
  for i,(v,mod) in enumerate(rows):
   if selector not in v:
    if i!=0:raise ValueError('Global SoundFont zone must be first.')
    global_values=v;global_mod=mod
   else:result.append((global_values|v,global_mod or mod))
  return result
 def plan(self,index):
  if type(index) is not int or not 0<=index<len(self.presets):raise ValueError('Choose a SoundFont preset.')
  warnings={'Native velocity and envelope curves may differ from reference SF2 playback.'};zones=[];shapes=[];blockers=[]
  prows=self.global_zones(self.bags('phdr',index),41);attempts=0
  for pg,pm in prows:
   for ig,im in self.global_zones(self.bags('inst',pg[41]),53):
    attempts+=1
    if attempts>2048:raise ValueError('Preset has more than 2048 zone combinations.')
    values=dict(DEFAULT);values.update(ig)
    for k,v in pg.items():
     if k not in (41,43,44,53,54,58):values[k]=values.get(k,0)+v
    ranges=[]
    for op in (43,44):
     limits=[(g.get(op,0x7f00)&255,g.get(op,0x7f00)>>8) for g in (pg,ig)]
     if any(not 0<=a<=b<=127 for a,b in limits):raise ValueError('Invalid SoundFont key/velocity range.')
     ranges.append((max(x[0] for x in limits),min(x[1] for x in limits)))
    (kl,kh),(vl,vh)=ranges;vl=max(1,vl)
    if kl>kh or vl>vh:continue
    sid=ig[53]
    if sid>=self.count('shdr')-1:raise ValueError('Invalid SoundFont sample reference.')
    raw=self.record('shdr',sid);label,start,end,ls,le,rate,root,correction,link,kind=struct.unpack('<20sIIIIIBbHH',raw)
    if kind&0x8000 or kind&0x10 or kind not in (1,2,4):blockers.append('ROM, compressed or unsupported linked sample: '+text(label));continue
    start+=values.get(0,0)+32768*values.get(4,0);end+=values.get(1,0)+32768*values.get(12,0);ls+=values.get(2,0)+32768*values.get(45,0);le+=values.get(3,0)+32768*values.get(50,0)
    if not 0<=start<end<=self.samples or not 8000<=rate<=192000:raise ValueError('Invalid SoundFont sample boundaries/rate.')
    mode=values.get(54,0)
    if mode not in (0,1,3):blockers.append('Unsupported loop mode: '+str(mode));continue
    if mode and ls==le and start<=ls<=end:
     ls,le=start,end;warnings.add('Empty loop markers use the full sample range.')
    if mode and not start<=ls<le<=end:raise ValueError('Invalid SoundFont sample loop.')
    if mode==1:warnings.add('Continuous loops become sustain loops and stop looping on key release.')
    if kind in (2,4):warnings.add('Stereo members are imported as separate mono zones; only explicit zone panning is retained.')
    if pm or im:warnings.add('Custom SF2 modulators are not imported.')
    for k,v in values.items():
     if k not in SUPPORTED and k not in (41,43,44,53) and v!=DEFAULT.get(k,0):warnings.add(LABELS.get(k,'Generator '+str(k))+' is not imported.')
    for key in (46,47):
     if key in values:warnings.add(LABELS[key]+' is not imported.')
    if values.get(57,0):warnings.add('Per-zone exclusive/choke groups are not imported.')
    if values.get(56,100)!=100:warnings.add('Nonstandard key scaling is not imported.')
    if values.get(9,0):warnings.add('SF2 filter resonance is not imported.')
    if tc(values[33])>1:warnings.add('Amplitude envelope delay is not imported.')
    if tc(values[35])>1:warnings.add('Amplitude envelope hold is not imported.')
    if 58 in ig:root=ig[58]
    if not 0<=root<=127:root=60;warnings.add('Unpitched/invalid root note uses C3 (MIDI 60).')
    tune=values.get(51,0)+(values.get(52,0)+correction)/100
    gain=100*10**(-max(-960,min(1440,values.get(48,0)))/200)
    if abs(values.get(17,0))>500:warnings.add('Out-of-range panning is clamped.')
    if not -48<=tune<=48 or gain>200:warnings.add('Out-of-range tuning/gain is clamped to the native sampler limits.')
    zone=dict(sample_id=sid,label=text(label),start=start,end=end,rate=rate,root=root,key_lo=kl,key_hi=kh,vel_lo=vl,vel_hi=vh,tune=max(-48,min(48,tune)),gain=min(200,gain),pan=max(-100,min(100,values.get(17,0)/5)),loop=bool(mode),loop_start=ls-start if mode else 0,loop_end=le-start if mode else end-start,xfade=0)
    zones.append(zone);shapes.append((values[34],values[36],values[37],values[38],values[8]))
  if not zones:blockers.append('Preset has no playable PCM sample zones.')
  if len(zones)>128:blockers.append('Preset exceeds the native limit of 128 zones.')
  decoded={(z['sample_id'],z['start'],z['end']):(z['end']-z['start'])*8 for z in zones}
  if any(n>64*1024**2 for n in decoded.values()):blockers.append('A zone exceeds the 64 MiB decoded sample limit.')
  if sum(decoded.values())>256*1024**2:blockers.append('Preset exceeds the 256 MiB decoded-memory import limit.')
  if len(set(shapes))>1:warnings.add('Per-zone envelopes/filter settings differ; the first zone supplies shared settings.')
  sampler={'type':'ADSR','polyphony':32}
  if shapes:
   attack,decay,sustain,release,cutoff=shapes[0]
   for key,value,low in [('attack',tc(attack),0),('decay',tc(decay),1),('release',tc(release),1)]:
    if value>10000:warnings.add('Envelope times above 10 seconds are clamped.')
    sampler[key]=max(low,min(10000,value))
   sampler['sustain']=max(0,min(100,100*10**(-max(0,sustain)/200)))
   if cutoff!=13500:sampler.update(filter='LP2',cutoff=max(20,min(20000,8.176*2**(max(1500,min(13500,cutoff))/1200))))
  return dict(preset=self.presets[index],zones=zones,sampler=sampler,warnings=sorted(warnings),blockers=sorted(set(blockers)),zone_count=len(zones))
 def extract(self,zone,path):
  start,end=zone['start'],zone['end'];n=end-start;off=self.chunks['smpl'][0];lo=self.chunks.get('sm24');width=3 if lo else 2
  if n*max(8,width)>64*1024**2:raise ValueError('A SoundFont zone exceeds the 64 MiB decoded sample limit.')
  with wave.open(str(path),'wb') as w:
   w.setnchannels(1);w.setsampwidth(width);w.setframerate(zone['rate'])
   for a in range(start,end,32768):
    b=min(end,a+32768);pcm=self.data[off+a*2:off+b*2]
    if lo:
     low=self.data[lo[0]+a:lo[0]+b];out=bytearray((b-a)*3);out[0::3]=low;out[1::3]=pcm[0::2];out[2::3]=pcm[1::2];pcm=out
    w.writeframesraw(pcm)
