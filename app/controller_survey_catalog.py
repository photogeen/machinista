"""Front-panel checklists derived from NI hardware manuals, not guessed HID maps.

USB IDs for existing devices are cross-checked against our own drivers and the
public references listed in docs/CONTROLLER_SURVEY.md. Layout selection is not
an assertion that an untested controller already works in Machinista.
"""
import re
NI='https://www.native-instruments.com/fileadmin/ni_media/downloads/manuals/'
SOURCES={
 'studio':NI+'maschine_276/MASCHINE_2.0_STUDIO_2.7.6_0518_Manual_English.pdf',
 'jam':NI+'maschine_278/MASCHINE_JAM_Manual_English_2_7_8.pdf',
 'mikro3':NI+'maschine_2_8/MASCHINE_2.0_MIKRO_MK3_Manual_English_2_8.pdf',
 's1':NI+'komplete_kontrol/KOMPLETE_KONTROL_S-Series_MK1_1.9.2_1217_Manual_English.pdf',
 's2':NI+'komplete_kontrol/KOMPLETE_KONTROL_S-Series_MK2_202_Manual_English.pdf',
 's3':'https://docs.native-instruments.com/online-guides/kontrol-s-mk3-manual/en/keyboard-overview.html',
 'a':NI+'komplete_kontrol/KOMPLETE_KONTROL_A-Series_Manual_English_04_2022.pdf',
 'm':NI+'komplete_kontrol/KOMPLETE_KONTROL_M32_Manual_English_28_10_2021.pdf',
 'maschine':'https://www.native-instruments.com/pages/maschine-downloads',
}
PROFILES={}
def add(identity,name,pids,buttons,encoders=(),touches=(),pads=0,strips=(),keys=0,pressure=None,pedals=(),source='maschine',family='Maschine'):
 PROFILES[identity]=dict(id=identity,name=name,product_ids=list(pids),family=family,buttons=list(buttons),encoders=list(encoders),touches=list(touches),pads=pads,strips=list(strips),keys=keys,pressure=pressure,pedals=list(pedals),sources=[SOURCES[source]],inventory_revision='2026-11-05',identity_note='' if pids else 'USB product ID must be recorded and reviewed; no unverified ID is guessed.')
GROUPS=tuple('GROUP '+c for c in 'ABCDEFGH');TOP=tuple('DISPLAY '+str(n) for n in range(1,9));KNOBS=tuple('KNOB '+str(n) for n in range(1,9))
STUDIO_BUTTONS=('CHANNEL','PLUG-IN','ARRANGE','MIX','BROWSE','SAMPLING','ALL','AUTO','IN 1','IN 2','IN 3','IN 4','MASTER','GROUP','SOUND','CUE',*TOP,*GROUPS,'COPY','PASTE','NOTE','NUDGE','UNDO','REDO','QUANTIZE','CLEAR','JOG PUSH','BACK','JOG LEFT','JOG RIGHT','ENTER','LOOP','METRO','SELECT','GRID','PLAY','REC','ERASE','TAP','SNAP','MACRO','NOTE REPEAT','SHIFT','SCENE','PATTERN','PAD MODE','NAVIGATE','DUPLICATE','PAD SELECT','SOLO','MUTE')
add('maschine_studio','Maschine Studio',[0x1300],STUDIO_BUTTONS,(*KNOBS,'LEVEL','JOG WHEEL'),KNOBS,16,source='studio')
JAM_BUTTONS=('SONG',*('SCENE '+str(n) for n in range(1,9)),'STEP','PAD MODE','CLEAR','DUPLICATE','DPAD UP','DPAD LEFT','DPAD RIGHT','DPAD DOWN','NOTE REPEAT',*GROUPS,'MST','GRP','IN1','CUE','BROWSE','MACRO','LEVEL','AUX','CONTROL','AUTO','PERFORM','NOTES','LOCK','TUNE','SWING','SHIFT','PLAY','REC','PAGE LEFT','PAGE RIGHT','TEMPO','GRID','SOLO','MUTE','SELECT','ENCODER PUSH',*('MATRIX ROW '+str(r)+' COLUMN '+str(c) for r in range(1,9) for c in range(1,9)))
add('maschine_jam','Maschine Jam',[0x1500],JAM_BUTTONS,('ENCODER',),('ENCODER',*('SMART STRIP '+str(i) for i in range(1,9))),strips=tuple('SMART STRIP '+str(i)+' / '+f for i in range(1,9) for f in ('one finger','two fingers')),pedals=('FOOTSWITCH',),source='jam')
PROFILES['maschine_jam']['sources'].append('https://github.com/styyle14/maschine-jam-linux#debugging-details')
MIKRO3_BUTTONS=('PROJECT','FAVORITES','BROWSE','VOLUME','SWING','TEMPO','PLUG-IN','SAMPLING','ENCODER PUSH','PAGE LEFT','PAGE RIGHT','PITCH','MOD','PERFORM','NOTES','GROUP','AUTO','LOCK','NOTE REPEAT','RESTART','ERASE','TAP','FOLLOW','PLAY','REC','STOP','SHIFT','FIXED VEL','PAD MODE','KEYBOARD','CHORDS','STEP','SCENE','PATTERN','EVENTS','VARIATION','DUPLICATE','SELECT','SOLO','MUTE')
add('maschine_mikro_mk3','Maschine Mikro MK3',[0x1700],MIKRO3_BUTTONS,('ENCODER',),('SMART STRIP',),16,('SMART STRIP',),source='mikro3')
MK2_BUTTONS=(*TOP,'CONTROL','STEP','BROWSE','SAMPLING','PAGE LEFT','PAGE RIGHT','ALL','AUTO','VOLUME','SWING','TEMPO','MASTER LEFT','MASTER RIGHT','ENTER','NOTE REPEAT','MASTER PUSH',*GROUPS,'RESTART','TRANSPORT LEFT','TRANSPORT RIGHT','GRID','PLAY','REC','ERASE','SHIFT','SCENE','PATTERN','PAD MODE','NAVIGATE','DUPLICATE','SELECT','SOLO','MUTE')
add('maschine_mk2','Maschine MK2',[0x1140],MK2_BUTTONS,(*KNOBS,'MASTER'),pads=16)
add('maschine_mk1','Maschine MK1',[0x0808],tuple(n for n in MK2_BUTTONS if n not in ('MASTER PUSH','MASTER LEFT','MASTER RIGHT','ENTER','VOLUME','SWING','TEMPO')),(*KNOBS,'VOLUME','TEMPO','SWING'),pads=16)
MIKRO_BUTTONS=('F1','F2','F3','CONTROL','BROWSE','SAMPLING','NOTE REPEAT','ENCODER PUSH','NAV','PAGE LEFT','PAGE RIGHT','MAIN','GROUP','PLAY','REC','ERASE','RESTART','SCENE','PATTERN','PAD MODE','VIEW','DUPLICATE','SELECT','SOLO','MUTE','GRID','SHIFT')
for generation,pid in ((1,0x1110),(2,0x1200)):add('maschine_mikro_mk'+str(generation),'Maschine Mikro MK'+str(generation),[pid],MIKRO_BUTTONS,('ENCODER',),pads=16)
MK3_BUTTONS=(*TOP,'CHANNEL','PLUG-IN','ARRANGER','MIXER','BROWSER','SAMPLING','FILE','SETTINGS','AUTO','MACRO','VOLUME','SWING','TEMPO','NOTE REPEAT','LOCK',*GROUPS,'RESTART','ERASE','TAP','FOLLOW','PLAY','REC','STOP','SHIFT','FIXED VEL','PAD MODE','KEYBOARD','CHORDS','STEP','SCENE','PATTERN','EVENTS','VARIATION','DUPLICATE','SELECT','SOLO','MUTE','PITCH','MOD','PERFORM','NOTES','4D PUSH','4D UP','4D DOWN','4D LEFT','4D RIGHT','PAGE LEFT','PAGE RIGHT')
add('maschine_mk3','Maschine MK3',[0x1600],MK3_BUTTONS,(*KNOBS,'4D'),(*KNOBS,'4D','SMART STRIP'),16,('SMART STRIP',),pedals=('FOOTSWITCH',))
add('maschine_plus','Maschine+ / Controller Mode',[0x1820],MK3_BUTTONS,(*KNOBS,'4D'),(*KNOBS,'4D','SMART STRIP'),16,('SMART STRIP',),pedals=('FOOTSWITCH',))
FOUR_D=('4D PUSH','4D UP','4D DOWN','4D LEFT','4D RIGHT')
S1_BUTTONS=('SHIFT','SCALE','ARP','LOOP','RWD','FFW','PLAY','REC','STOP','PAGE LEFT','PAGE RIGHT','BROWSE','INSTANCE','BACK','NAV LEFT','NAV RIGHT','NAV UP','NAV DOWN','PRESET UP','PRESET DOWN','ENTER','CONTROL ENCODER PUSH','OCT -','OCT +')
for size,pid in ((25,0x1340),(49,0x1350),(61,0x1360),(88,0x1410)):
 add('kk_s'+str(size)+'_mk1','Komplete Kontrol S'+str(size)+' MK1',[pid],S1_BUTTONS,(*KNOBS,'CONTROL ENCODER'),KNOBS,strips=('PITCH STRIP','MOD STRIP'),keys=size,pressure='channel',pedals=('SUSTAIN PEDAL','EXPRESSION PEDAL'),source='s1',family='Komplete Kontrol')
S2_BUTTONS=(*TOP,'MUTE','SOLO','SCENE','PATTERN','TRACK','KEY MODE','CLEAR','FIXED VEL','SHIFT','SCALE','ARP','UNDO','QUANTIZE','LOOP','METRO','TEMPO','PLAY','REC','STOP','PRESET UP','PRESET DOWN','PAGE LEFT','PAGE RIGHT','BROWSER','PLUG-IN','MIXER','INSTANCE','MIDI','SETUP','OCT -','OCT +',*FOUR_D)
for size,pid in ((49,0x1610),(61,0x1620),(88,0x1630)):
 add('kk_s'+str(size)+'_mk2','Komplete Kontrol S'+str(size)+' MK2',[pid],S2_BUTTONS,(*KNOBS,'4D'),KNOBS,strips=('PITCH WHEEL','MOD WHEEL','TOUCH STRIP'),keys=size,pressure='channel',pedals=('PEDAL A','PEDAL B'),source='s2',family='Komplete Kontrol')
S3_BUTTONS=(*TOP,'SHIFT','UNDO','QUANTIZE','PAGE LEFT','PAGE RIGHT','PLAY ASSIST','SETTINGS','BROWSER','PLUG IN','DAW','LOOP','METRO / TEMPO','PLAY','REC','STOP','PREVIOUS','NEXT','FIXED VEL','OCT -','OCT +',*FOUR_D)
for size,pid in ((49,0x2100),(61,0x2110),(88,0x2120)):
 add('kk_s'+str(size)+'_mk3','Kontrol S'+str(size)+' MK3',[pid],S3_BUTTONS,(*KNOBS,'4D'),KNOBS,strips=('PITCH WHEEL','MOD WHEEL','TOUCH STRIP'),keys=size,pressure='poly',pedals=('SUSTAIN PEDAL','EXPRESSION PEDAL','ASSIGN 1 PEDAL','ASSIGN 2 PEDAL'),source='s3',family='Komplete Kontrol')
AM_BUTTONS=('MUTE','SOLO','SHIFT','SCALE','ARP','IDEAS / AUTO','QUANTIZE','UNDO','LOOP','METRO','TEMPO','PLAY','REC','STOP','BROWSER','PLUG-IN','TRACK','PAGE LEFT','PAGE RIGHT','PRESET UP','PRESET DOWN','OCT -','OCT +',*FOUR_D)
for size in (25,49,61):add('kk_a'+str(size),'Komplete Kontrol A'+str(size),[],AM_BUTTONS,(*KNOBS,'4D'),KNOBS,strips=('PITCH WHEEL','MOD WHEEL'),keys=size,pedals=('SUSTAIN PEDAL',),source='a',family='Komplete Kontrol')
add('kk_m32','Komplete Kontrol M32',[],AM_BUTTONS,(*KNOBS,'4D'),KNOBS,strips=('PITCH STRIP','MOD STRIP'),keys=32,pedals=('SUSTAIN PEDAL',),source='m',family='Komplete Kontrol')

# Keep historical inventories importable, but do not ask testers to re-map
# controllers already supported by Machinista.
SUPPORTED_PROFILES={'maschine_jam','maschine_mk1','maschine_mk2','maschine_mk3','maschine_plus','maschine_mikro_mk1','maschine_mikro_mk2'}
for identity,profile in PROFILES.items():profile['survey_required']=identity not in SUPPORTED_PROFILES


def display_inventory(identity):
 def mono(count,protocol):
  return [dict(id='display_'+str(i+1),name='Display' if count==1 else 'Display '+str(i+1)+' (left to right)',index=i,width=128,height=32,color=False,protocol=protocol) for i in range(count)]
 if identity=='maschine_mk2':return [dict(id='display_'+str(i+1),name='Right display' if i else 'Left display',index=i,width=256,height=64,color=False,protocol='mono-mk2') for i in range(2)]
 if identity=='maschine_mikro_mk3':return mono(1,'mono-pages')
 if re.fullmatch(r'kk_s\d+_mk1',identity):return mono(8,'mono-oled')
 if re.match(r'kk_[am]',identity):return mono(1,'mono-pages')
 if identity=='maschine_studio' or re.fullmatch(r'kk_s\d+_mk2',identity):
  return [dict(id='display_'+str(i+1),name='Right display' if i else 'Left display',index=i,width=480,height=272,color=True,protocol='ni-color',usbInterface=1 if identity=='maschine_studio' else 3,endpoint=2 if identity=='maschine_studio' else 3) for i in range(2)]
 if re.fullmatch(r'kk_s\d+_mk3',identity):return [dict(id='display_1',name='Wide color display',index=0,width=1280,height=480,color=True,protocol='pending-odr',reason='Kontrol S-MK3 uses ODR rather than the Studio/S-MK2 bulk format. Browser rendering is not implemented; record this as blocked, not passed.')]
 return []
from app.controller_survey_outputs import output_inventory
for identity,profile in PROFILES.items():
 profile['displays']=display_inventory(identity)
 profile['led_banks'],profile['led_tests']=output_inventory(identity,profile)

def checklist(profile_id,extras=(),version=3,keyboard_test="quick"):
 if profile_id not in PROFILES:raise ValueError('Choose a controller model first.')
 p=PROFILES[profile_id];result=[]
 def step(kind,name,instruction,optional=False,**more):
  identity=kind+'_'+re.sub('[^a-z0-9]+','_',name.lower().replace('+',' plus ').replace('-',' minus ')).strip('_');result.append(dict(id=identity,name=name,kind=kind,instruction=instruction,optional=optional,**more))
 for name in p['buttons']:step('button',name,'Press and release this physical button three times. Do not hold SHIFT unless SHIFT itself is being tested.')
 for name in p['encoders']:
  if version==1:
   for direction in ('clockwise','counterclockwise'):step('encoder',name+' / '+direction,'Turn slowly '+direction+' through several steps. Do not press it.',direction=direction)
  else:step('encoder',name,'Turn slowly clockwise through a few steps, then stop. Do not press it.',direction='clockwise')
 for name in p['touches']:step('touch',name+' TOUCH','Touch and release three times without turning or moving the control.')
 for i in range(1,p['pads']+1):step('pad','PAD '+str(i),'Play this pad soft, medium and firm; release between hits. Pad 1 is bottom left, pad 16 top right.')
 for name in p['strips']:step('slider',name,'Move over the whole range slowly and return to rest. For two-finger strips move two fingers apart and together.')
 key_numbers=([1,p['keys'],2] if p['keys'] and version>=3 and keyboard_test=='quick' else range(1,p['keys']+1))
 for i in key_numbers:step('key','KEY '+str(i)+' FROM LEFT',('Play the first black key from the left (second physical key), then release.' if version>=3 and keyboard_test=='quick' and i==2 else 'Play this physical key, then release. Keep octave and transpose settings unchanged.'))
 if p['pressure']:
  for i in (1,(p['keys']+1)//2,p['keys']):step('pressure','AFTERTOUCH KEY '+str(i)+' FROM LEFT','Hold the indicated key, press firmly to vary aftertouch, then release. Do not force the mechanism.')
 for name in p['pedals']:step('pedal',name,'Connect a compatible pedal to this socket, operate it and release. Skip explicitly if no pedal is available.',True)
 for item in extras:
  if not isinstance(item,dict) or set(item)!=set(('name','kind')) or item['kind'] not in ('button','encoder','touch','pad','slider','key','pressure','pedal') or not isinstance(item['name'],str) or not 1<=len(item['name'])<=60:raise ValueError('Invalid additional control.')
  step(item['kind'],'EXTRA '+item['name'],'Operate only this additional physical control several times, then release. Encoder: test both directions separately if needed.')
 ids=[s['id'] for s in result]
 if len(ids)!=len(set(ids)):raise ValueError('Duplicate control in the checklist.')
 return result
