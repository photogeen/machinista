"""Generate controller-only profiles and original example banks for Calf Color."""
import copy,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.plugin_profiles import validate_bank
from app.plugin_bank_import import import_bank
catalog=json.loads((ROOT/'output/calf-audit/catalog-arm64.json').read_text())
PAGES={
'TapeSimulator':[('TAPE',['mix','lowpass','speed','mechanical','noise','level_out']),('TAPE TONE',['level_in','magnetical','post','bypass','mix','lowpass','speed','level_out'])],
'BassEnhancer':[('BASS',['amount','freq','drive','blend','floor','level_out']),('BASS RANGE',['floor_active','listen','level_in','bypass','freq','floor','amount','level_out'])],
'Vinyl':[('VINYL',['drone','aging','freq','speed','level_in','level_out']),('NOISE BED',['active0','gain0','active1','gain1','active2','gain2','active3','gain3']),('SURFACE',['active4','gain4','active5','gain5','active6','gain6','bypass','aging']),('NOISE TUNE',['pitch0','pitch1','pitch2','pitch3','pitch4','pitch5','pitch6','bypass'])]}
PRESETS={
'TapeSimulator':[('Clean Warmth',dict(mix=.35,lowpass=14000,speed=1,noise=0,mechanical=0,magnetical=1,level_out=1.6)),('Soft Cassette',dict(mix=.6,lowpass=9000,speed=0,noise=.015,mechanical=.08,magnetical=1,post=1,level_out=1.2)),('Worn Reel',dict(mix=.65,lowpass=7000,speed=0,noise=.04,mechanical=.18,magnetical=1,post=1,level_in=.7,level_out=1.2))],
'BassEnhancer':[('Gentle Weight',dict(amount=.35,freq=120,drive=3,blend=0,floor_active=1,floor=30,level_out=.9)),('Deep Foundation',dict(amount=.7,freq=85,drive=5.5,blend=-3,floor_active=1,floor=25,level_out=.85)),('Warm Harmonics',dict(amount=.45,freq=180,drive=6,blend=3,floor_active=1,floor=45,level_out=.9))],
'Vinyl':[('Light Dust',dict(aging=.08,freq=1200,drone=0,speed=33,active5=1,gain5=.035,active3=1,gain3=.003)),('Warm Record',dict(aging=.2,freq=1000,drone=.01,speed=33,active5=1,gain5=.07,active3=1,gain3=.006)),('Old Gramophone',dict(aging=.5,freq=1100,drone=.02,speed=78,active0=1,gain0=.004,active5=1,gain5=.08,active6=1,gain6=.025,level_out=1.25))]}
LABELS={'level_in':'INPUT','level_out':'OUTPUT','mix':'MIX','lowpass':'FILTER','speed':'SPEED','noise':'NOISE','mechanical':'MECHANICAL','magnetical':'MAGNETIC','post':'MUFFLE','amount':'HARM LEVEL','freq':'SCOPE','drive':'HARMONICS','blend':'COLOR','floor_active':'FLOOR ON','floor':'FLOOR','listen':'LISTEN','drone':'WOW','aging':'AGING'}
NOISES=['HUM','MOTOR','STATIC','HISS','RUMBLE','CRACKLE','CRINKLE']
def main():
 for effect,pages in PAGES.items():
  meta=next(p for p in catalog if p['uri'].endswith('/'+effect));ttl=(ROOT/'output/calf-effects/source-metadata'/(effect+'.ttl')).read_text();params=[];overrides={}
  for spec in meta['ports']:
   v=copy.deepcopy(spec);s=v['symbol'];o={};o['name']=LABELS.get(s,v['name'].upper())
   if s=='freq' and effect=='Vinyl':o['name']='COLOR FREQ'
   if s in ('level_in','level_out','amount') or s.startswith('gain'):o.update(unit='amplitude_db',log=True)
   if s in ('lowpass','freq','floor'):o['unit']='hz'
   if s in ('mix','noise','mechanical','drone','aging'):o['unit']='percent'
   if s=='speed':o.update(choices=[[0,'SLOW'],[1,'FAST']] if effect=='TapeSimulator' else [[33,'33 RPM'],[45,'45 RPM'],[78,'78 RPM']],choice=True)
   for i,name in enumerate(NOISES):
    if s=='gain'+str(i):o['name']=name+' LEVEL'
    if s=='active'+str(i):o['name']=name+' ON'
    if s=='pitch'+str(i):o.update(name=name+' TUNE',unit='cents',display_scale=1200)
   v.update(o);params.append(v);overrides[s]=o
  sections=[dict(title=title,controls=(['@bank','@patch'] if i==0 else [])+symbols) for i,(title,symbols) in enumerate(pages)]
  assert all(len(p['controls'])==8 for p in sections)
  assert {v['symbol'] for v in params}=={s for p in sections for s in p['controls'] if not s.startswith('@')}
  profile=dict(schema=1,id='calf-'+effect.lower(),uri=meta['uri'],title=meta['name'],provider='parameter-bank',bank_format='json',extensions=['.json'],parameters=params,pages=sections,overrides=overrides,quirks=['Calf Color optional ARM64 bundle. Original LV2 values retained.','Vinyl includes original Calf noise SoundFonts; no audio driver or external synth required.'])
  (ROOT/'app/plugin_profiles_data'/('calf-'+effect.lower()+'.json')).write_text(json.dumps(profile,indent=2)+'\n')
  patches=[]
  for name,values in PRESETS[effect]:
   c={v['symbol']:v['default'] for v in params};c.update(values);patches.append(dict(name=name,controls=c))
  bank=dict(schema=1,uri=meta['uri'],name='Calf Color',patches=patches);validate_bank(bank,profile)
  # Native values are also the WebUI JSON patch-bank format.
  import hashlib
  raw=json.dumps(bank,ensure_ascii=False).encode();identifier=hashlib.sha256(raw).hexdigest()[:24]
  f=ROOT/'presets/plugin-banks'/profile['id'];f.mkdir(parents=True,exist_ok=True);(f/(identifier+'.json')).write_bytes(raw)
  print(profile['title'],len(params),'controls',len(sections),'pages')
if __name__=='__main__':main()
