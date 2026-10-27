"""Read-only LCD audit: render current layouts against all extracted Mikro references."""
import copy, hashlib, html, json, math, shutil, sys, tempfile, wave
from pathlib import Path
from types import SimpleNamespace
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from app.model import Application
from app.ni_display import frame
from app.sampler import default_zone
from app.waveform import read_envelope
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'outputs/display-audit-2026-10-04'
if hashlib.sha256((ROOT/'app/ni_display.py').read_bytes()).hexdigest()!='6eaadeceedf8ef29be0ffbfc867b403db5e751c9dd505932f85faf5ca66eb4b8':
    raise SystemExit('Dieser historische Vergleich benötigt den Displaycode vor dem NI-Layoutumbau; gespeicherte Auditbilder bleiben unverändert.')
REF=Path('/private/tmp/maschine-lcd-review')
MANUAL='https://docs.native-instruments.com/pdf-guides/maschine/MASCHINE_2_5_5_MIKRO_MK2_Manual_English_161213.pdf'
OUT.mkdir(exist_ok=True)
(OUT/'reference').mkdir(exist_ok=True);(OUT/'current').mkdir(exist_ok=True)
# Every separately embedded Mikro LCD has a family. Software/other-controller
# candidates were visually reviewed separately, not mistaken for Mikro LCDs.
F={
'nav':('Kanal-NAV','nah', 'Reiter und invertierte Auswahl jetzt vorhanden. Schrift, Abstände und Linien nicht pixelgleich. OUTPUT-Vorschau trennt AUDIO/AUX1/AUX2/MIDI statt NI-Seitengruppierung; linker Seitenpfeil fehlt, rechter Pfeil wird immer gezeichnet.'),
'output':('OUTPUT / Kanal','abweichend','NI: OUTPUT links und Taktposition rechts in einer Zeile, DEST. vor LEVEL, je nach Seite 5/6 Parameter. Wir: Tempo plus Taktposition, darunter OUTPUT plus AUDIO/AUX1/AUX2/MIDI; LEVEL/PAN/DEST in drei Feldern. Gain als 0–100 ohne dB, Routingwerte intern benannt. Parameterpfeile fehlen.'),
'input':('INPUT / Kanal','abweichend','NI: INPUT links neben Taktposition, SOURCE mit Routingbezeichnung. Wir: zusätzliche Tempozeile, kein INPUT-Label im Hauptfeld. 1/2 SOURCE und 2/2 GAIN sind jetzt vorhanden, Gain aber Prozent; nur NONE/EXT STEREO/EXT LEFT/EXT RIGHT. MIDI-Inputseite und ursprüngliche Eingangsbenennung fehlen.'),
'library':('Sample-/Preset-Browser','bewusst','NI: FILTER/LIST/USER, Fokusname, Dateityp/Trefferzahl, einzelnes Resultat bzw. Filterparameter. Wir: BACK/OPEN oder LOAD/PREH und dreizeilige Ordnerliste. Das ist der vereinbarte Ordnerbrowser. NI-Preset-/Favoriten-/AutoLoad-/QuickBrowse-Anzeigen fehlen weiterhin; Samples und LV2 brauchen eigene Inhalte.'),
'select':('SELECT / EVENTS','abweichend','QUIET/EVENTS/MULTI und heller SELECT-Titel grundsätzlich vorhanden. Wir ergänzen unten SELECTION QUIET/MULTI, wo das NI-Beispiel leer bleibt. EVENTS-Auswahl zeichnet weiterhin MULTI; das konkrete aktive EVENTS-Tab wird nicht wie im Beispiel hervorgehoben. SHIFT+SELECT-Notenauswahl ist vorhanden.'),
'pad':('PAD MODE / Keyboard','abweichend','NI: PAD MODE-Titel, Soundname links, Grundton rechts, unten n/m und benannter Parameter. Wir: Name und GROUP/KEYBOARD in getrennten Zeilen, MIDI-Grundton als Zahl, kein Parameterindex. Choke/Link/Scale/Chord sind vorhanden, Darstellung und Teile der Wertebezeichnung weichen ab.'),
'repeat':('NOTE REPEAT / ARP','abweichend','NI: NOTE REPEAT oder ARP, Tempo und Position, kontextabhängig 3 bzw. 7 Parameter und Werte mit Einheiten. Wir: global acht Felder, rohe Werte und unter ARP keine Tempo-/Positionzeile. NOTE REPEAT passt im Kopf näher. Presetlabels enthalten keine Triplet-/Dotted-Kennzeichen; LOCK ist als dritter Softkey fest belegt.'),
'groove':('GROOVE','abweichend','NI: GROOVE neben Position, Amount z. B. 0.0 %. Wir: zusätzliche Tempozeile, Bereichsname im Hauptfeld fehlt und Amount ohne %. Parameterindex 1/3 ist vorhanden.'),
'sampler':('SAMPLER, sechs Seiten','abweichend','NI: 1. SAMPLER neben Position, Parameterindex und typisierte Werte. Wir: Tempo/Position plus zusätzliche 1/6 VOICE usw., roh formatierter Wert, keine Pfeile. Die sechs Seitentitel sind ähnlich, Parameterumfang/-reihenfolge nicht gleich: etwa START auf Pitch/Envelope fehlt; Envelopefelder werden unabhängig von OneShot/AHD/ADSR gezeigt. Eigene DSP ersetzt NI-Engine.'),
'plugin':('Effekt-/Instrumentparameter','ersatz','NI: Slotnummer.Pluginname neben Taktposition, Parameter mit Einheit/Enum und Pfeilen. Wir: Tempo/Position plus separate Pluginzeile ohne Slotpräfix, numerischer Wert mit drei signifikanten Stellen ohne LV2-Einheiten/Enumlabels. NI-Effekte/Instrumente sind hier nicht vorhanden; LV2 ersetzt die Inhalte, die Displaystruktur kann trotzdem angeglichen werden. Sidechain-Beispiele haben noch keine Funktionsentsprechung.'),
'grid':('GRID','abweichend','NI: PERF/PAT/STEP, Tempo/Position, je Seite VALUE/ENABLE/NUDGE. Wir: QUANT/SWING/STEP, QUANTIZE-/SWING-Ansichten statt PERF/PAT, keine Tempo-/Positionzeile. Perform/Arrange/Nudge existieren teils im Backend/Settings, aber nicht als diese Originalseiten.'),
'recsettings':('REC. MODE / Metronom','abweichend','NI: METRO bzw. 2/4/8, Tempo/Position, vier Rec.-Mode-Felder, Level in dB und QUANTIZE MODE. Wir: RECORD SETUP, METRO/COUNT/BACK, drei Felder, Level in %, Quantisierung ON/OFF. Record-Länge/Prepare und Originalanzeige fehlen.'),
'step':('STEP MODE','abweichend','FOLLOW/DOUBLE/FIX VEL und Step-Balken sind vorhanden. Wir zeigen zusätzlich Bank/Velocity/Text statt NI-Fußbereich, Balkenraster und Scroll-/Followmarkierungen sind anders. Schrift und Ziffern nicht originalgleich.'),
'pattern':('PATTERN','abweichend','DBL/DUPL/DELETE stimmen als Belegung. NI zeigt Patternname und Seitenanzeige 1/2, LENGTH 1/2. Wir zeigen PATTERN Nummer plus Bank und LENGTH 1/1; Name und zweite Originalparameterseite fehlen in dieser Ansicht.'),
'scene':('SCENE','abweichend','ALL/DUPL/DELETE sind vorhanden. NI zeigt Scenename, Seitenanzeige und POSITION #1. Wir zeigen SCENE Nummer/Bank und LENGTH in Bars; keine POSITION-Parameterseite wie abgebildet.'),
'macro':('MACRO','abweichend','NI: MACRO links neben Position, Parameterbezeichnung und 1/8. Wir: Tempo/Position, MACRO 1/8 extra, unten Mappingname/Wert ohne Parameterindex. Bei noch nicht zugewiesener Macro-Anzeige steht F2 ASSIGN, obwohl die Zuweisung inzwischen SHIFT+F2 erfordert.'),
'plugnav':('Plugin-NAV / Append','abweichend','Grundstruktur CHNL./PLUG-IN und Slotkacheln vorhanden. Wir zeigen SMP statt nummeriertem Samplerslot, ADD statt + und lassen freie Slotrahmen weg. Keine gepunkteten leeren Kacheln; Vorschau generisch PARAMETERS/BROWSE statt Main/Seitentitel bzw. (NONE)/[NO PARAMETER PAGE].'),
'pluginbrowser':('Plugin-Browser','abweichend','NI: FILTER/LIST, Fokusname, Trefferanzahl und TYPE/SUBTYPE-Parameter. Wir: EFFECT/LOAD/BACK, dreizeilige LV2-Liste, Footer LV2 EFFECT; kein FILTER/LIST-Zustand und keine TYPE-/SUBTYPE-Parameteransicht. LV2 statt INTERNAL/NI ist eine Inhaltsanpassung; Listenlayout ist eine zusätzliche Abweichung.'),
'mute':('MUTE / SOLO','abweichend','NI: ALL ON/NONE/AUDIO, Titel MUTE SOUND oder SOLO SOUND, Tempo/Position. Wir: dritter Softkey -, zusätzlich GROUP und EVENT MUTE/PADS SELECT SOUNDS. Tempo/Position vorhanden, Original-AUDIO-Tab und dessen Anzeige fehlen.'),
'record':('Sampling RECORD / MONITOR','abweichend','START/PREV/NEXT weitgehend vorhanden. NI: Sample-/Take-Name oder NO RECORDED SAMPLE im hellen Titel, zwei umrahmte Pegelbalken mit Thresholdmarker, deaktivierte History-Softkeys gepunktet. Wir: Titel RECORD, READY/WAITING/RECORDING und Quellenzeile, nur ein einpixeliger Peakbalken; keine Stereo-/Peakhalteanzeige, PREV/NEXT als - statt gepunktet. Monitor-NAV hat funktional eine eigene Seite.'),
'edit':('Sampling EDIT','abweichend','Pfeile/TRUNC/Pfeile und helle Waveform mit dunklem Signal grundsätzlich vorhanden. NI-Titel enthält nur Sample-/Take-Name; wir setzen EDIT: davor. Waveformhöhe/Marker/Schraffierung unterscheiden sich; Parameternavigationspfeile fehlen. Zonenkennung Zxx ist unsere Ergänzung. Andere Wellenformdaten sind kein Layoutfehler.'),
'stretch':('Sampling STRETCH','abweichend','NI hält die Waveform sichtbar und hat ST RCH/APPLY sowie sieben Parameter (u. a. Mode/Formant/BPM). Wir: separate Textansicht STRETCH, APPLY auf F2, BACK auf F3, nur LENGTH/PITCH und keine Waveform. Rubber-Band-Verarbeitung ist vorhanden, Funktionsumfang und Screen weichen deutlich ab.'),
'slice':('Sampling SLICE','abweichend','EDIT/APPL.TO/APPLY, helle Auswahl und dunkle übrige Segmente grundsätzlich vorhanden. Titel SLICE statt Sample-/Take-Name; kein durchgehender Originalrahmen, kleinere Waveform. Auf MANUAL zeigt NI NO PARAMETERS, wir MODE/AUTO-SNAP. Detect/Zero-X-Seiten sind vorhanden, aber Index/Seitenzahl teilweise anders. Slice-BPM/Mono und Einzelslice-Export fehlen.'),
'zone':('Sampling ZONE','abweichend','NI zeigt Sample-/Take-Name, Waveform mit Zone/Loopbereich und inaktiven schraffierten Teilen, PREV/NEXT teils deaktiviert sowie ACTIVE/START/TUNE/KEY LO als typisierte Parameter. Wir: reine Textansicht ZONE x/y plus PLAY/LOOP/TUNE/ENVELOPE/MAP und Rohwert; keine Waveform, kein ACTIVE, keine gepunkteten Softkeys, MIDI-Noten als Zahlen statt C-2.'),
'samplingnav':('Sampling-NAV','abweichend','NI: vier Kacheln REC/EDIT/SLICE/ZONE, Auswahlmarker und untere Vorschau PLAY RANGE/ENGINE/TUNE-MIX usw. Wir: vertikale Vierer-Textliste, F1/F2/F3 RECORD/EDIT/SLICE oben, ohne untere Seitenvorschau. Die zuletzt umgebaute Kanal-NAV hat diesen Sampling-Screen noch nicht angeglichen.'),
'emptyplugin':('Leere Pluginparameter','abweichend','NI zeigt (NONE) neben der Taktposition, sonst leeres Parameterfeld. Wir zeigen Tempo/Position plus (NONE) auf eigener Zeile, darunter SLOT 1 als Parameter. Fokus-Titel unterscheidet sich auch.'),
}
def family(item):
 p=item['page'];f=item['file']
 if p==44 or p==45 and f.endswith('I1.png'):return 'nav'
 if p in (45,46,413,419,423,451) or p==597 and f.endswith('I3.png') or p==607 and not f.endswith('I1.png'):return 'output'
 if 102<=p<=139:return 'library'
 if p in (168,348):return 'select'
 if p in (215,217,244,245):return 'pad'
 if p in (228,253,254):return 'repeat'
 if p in (232,233):return 'mute'
 if p==235:return 'groove'
 if 282<=p<=292:return 'sampler'
 if p in (323,327,328,755):return 'grid'
 if p in (332,334,336):return 'recsettings'
 if p==339:return 'step'
 if p in (376,713):return 'pattern'
 if p in (409,433,436,598):return 'input'
 if p==455:return 'macro'
 if p==586 or p in (600,604) and f.endswith('I1.png'):return 'plugnav'
 if p==597 and not f.endswith('I3.png') or p==607 and f.endswith('I1.png'):return 'nav'
 if p in (600,604,605):return 'pluginbrowser'
 if p==298 or p==592 or 615<=p<=673:return 'plugin'
 if p==718:return 'scene'
 if 762<=p<=775:return 'record'
 if 781<=p<=787:return 'edit'
 if p==789:return 'stretch'
 if 793<=p<=804:return 'slice'
 if p==832 and f.endswith('I1.png'):return 'samplingnav'
 if p==835 and f.endswith('I1.png'):return 'emptyplugin'
 if 812<=p<=835:return 'zone'
 raise ValueError(item)

# Reproducible example state; no Pi projects, samples, services or runtime
# settings are changed. LV2 metadata below is explicitly a render fixture.
with tempfile.TemporaryDirectory() as tmp:
 a=Application(tmp);sample=Path(tmp)/'samples/Sample01.wav'
 samples=[]
 for n in range(44100):
  decay=math.exp(-((n%11025)/1800));samples.append(round(math.sin(n*2*math.pi*110/44100)*decay*22000))
 import array
 with wave.open(str(sample),'wb') as w:w.setparams((1,2,44100,0,'NONE','not compressed'));w.writeframes(array.array('h',samples).tobytes())
 a.track().update(name='Sample01',sample=str(sample),start=0,end=44100,note=60)
 a.project['tempo']=120.;a.step=0;a.message='';a.control_level=2
 a.track()['zones']=[default_zone(a.track())];a.track()['slices']=[[0,11025],[11025,22050],[22050,33075],[33075,44100]]
 a.track()['slice_source']={'sample':str(sample),'start':0,'end':44100}
 a.slice_count=4;a.slice_mode='SPLIT';a.slice_index=0
 ports=[{'symbol':'cutoff','name':'Cutoff','default':1000.,'min':20.,'max':20000.}]
 a.plugin_catalog=[{'uri':'urn:audit:lv2','name':'LV2 Filter','kind':'EFFECT','supported':True,'ports':ports}]
 plugin={'uri':'urn:audit:lv2','kind':'EFFECT','controls':{'cutoff':1000.},'bypass':False}
 a.track()['plugins']=[copy.deepcopy(plugin)]
 a.put_note(0,0,{'note':60,'velocity':100,'probability':100,'length':24});a.put_note(0,96,{'note':60,'velocity':80,'probability':100,'length':24})
 a.audio=SimpleNamespace(capture=True,name='Audit stereo input',key='audit')
 a.capture_peak=.32;a.project['sampling']={'source':'EXT STEREO','input':'IN 1','mode':'DETECT','threshold':-24,'bars':1,'monitor':False}
 a.browser.current=sample.parent;a.browser_index=0
 baseline=copy.deepcopy(a.__dict__)
 def snapshot(fam,item):
  # Reset mutable UI state before each view. Project/content fixture is shared.
  for k in ('page','control_level','channel_page','channel_field','input_field','sampler_page','sampler_field','zone_page','zone_field','zone_index','parameter_kind','parameter_choice','keyboard_enabled','pad_field','arp_field','slice_mode','slice_field','slice_section','capture_section','capture_field','grid_tab','grid_field','record_field','select_multi','message','shift'):
   if k in baseline:setattr(a,k,copy.deepcopy(baseline[k]))
  p=item['page'];f=item['file'];a.message='';a.shift=False
  page={'nav':'PARAM NAV','output':'CHANNEL','input':'INPUT','library':'BROWSE','select':'SELECT','pad':'PAD CONFIG','repeat':'ARP' if p==254 else 'NOTE REPEAT','mute':'SOLO' if p==232 else 'MUTE','groove':'GROOVE','sampler':'SAMPLER','plugin':'PLUGIN','grid':'OPTIONS','recsettings':'RECORD SETTINGS','step':'STEP','pattern':'PATTERN','scene':'SCENE','macro':'MACRO','plugnav':'PARAM NAV','pluginbrowser':'PLUGIN BROWSE','record':'SAMPLING','edit':'SAMPLE EDIT','stretch':'STRETCH','slice':'CHOP','zone':'ZONE','samplingnav':'SAMPLING NAV','emptyplugin':'PLUGIN'}[fam]
  a.page=page
  if fam=='plugin' and p>=615 or fam=='groove' or fam=='emptyplugin' or p in (419,436):a.control_level=1
  if p==423:a.control_level=0
  if fam=='nav':
   a.parameter_kind='CHNL';a.parameter_choice=0 if p==44 or p==597 and f.endswith('I2.png') else 1
   if a.parameter_choice==1:a.channel_page=1
  if fam=='plugnav':a.parameter_kind='PLUG-IN';a.parameter_choice=2 if p==600 or p==604 or f.endswith('I2.png') else 1
  if fam=='output':a.channel_field=1 if p==46 or p==45 and f.endswith('I3.png') else 2
  if fam=='input':a.input_field=0
  if fam=='pad':
   a.keyboard_enabled=p!=215;a.pad_field={244:1}.get(p,0)
   if p==245:a.pad_field=3 if f.endswith('I2.png') else 2
  if fam=='repeat':a.arp_field=2 if p==228 else 0
  if fam=='sampler':a.sampler_page={282:0,283:1,286:2,288:3,290:4,292:5}[p]
  if fam=='grid':a.grid_tab=2 if p in (327,328) else 0;a.grid_field=2 if p==328 else 1 if p==327 and f.endswith('I1.png') else 0
  if fam=='recsettings':a.record_field=2 if p==336 and f.endswith('I2.png') else 1 if p in (332,336) else 0
  if fam=='select':a.select_multi=p==168
  if fam=='record':
   a.capture_section=int(p==768)
   if p in (766,771):a.project['sampling']['source']='INTERNAL'
   else:a.project['sampling']['source']='EXT STEREO'
  if fam=='slice':a.slice_mode='MANUAL' if p==804 else 'DETECT' if p==798 else 'SPLIT';a.slice_section=int(p==798)
  if fam=='samplingnav':a.sampling_nav=3
  if fam=='zone':a.zone_page=4 if p==835 else 2 if p==834 else 0;a.zone_field=0
  if fam=='emptyplugin':a.plugin_target()['plugins']=[]
  else:a.plugin_target()['plugins']=[copy.deepcopy(plugin)]
  envelope=read_envelope(sample) if fam in ('edit','slice','zone','stretch') else None
  pixels=frame(a,envelope)
  im=Image.new('RGB',(128,64));im.putdata([(36,38,47) if v else (242,244,247) for v in pixels])
  im=im.resize((512,256),Image.Resampling.NEAREST)
  path=OUT/'current'/item['file'];im.save(path)
  return {'page':page,'state':{k:getattr(a,k) for k in ('control_level','channel_page','channel_field','input_field','sampler_page','zone_page','parameter_kind','parameter_choice','keyboard_enabled','pad_field','capture_section','slice_mode')},'image':'current/'+item['file']}
 inventory=json.loads((ROOT/'docs/manual-audit/LCD_INVENTORY.json').read_text())
 records=[]
 for item in inventory['images']:
  fam=family(item);title,status,notes=F[fam]
  shutil.copy2(REF/item['file'],OUT/'reference'/item['file'])
  rendered=snapshot(fam,item)
  records.append(dict(item,family=fam,title=title,status=status,notes=notes,reference='reference/'+item['file'],current=rendered))

# All records are linked to the source PDF page and a current renderer snapshot.
assert len(records)==129
counts={k:sum(r['family']==k for r in records) for k in F}
metadata={'date':'2026-10-04','manual':MANUAL,'references':129,'other_candidates_reviewed':261,'pi_code_matches':True,'render_fixture':'Sample01, 120 BPM, beat 1:1:1; deterministic waveform; LV2 Filter is metadata fixture, not an installed NI or LV2 plugin assertion. No hardware screenshot.','code_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('app/ni_display.py','app/surface.py','app/navigation.py')},'family_counts':counts,'records':records}
(OUT/'inventory.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2))
E=html.escape
cards=[]
for r in records:
 href=f'{MANUAL}#page={r["page"]}'
 cards.append(f'''<article class="card" data-family="{r['family']}" data-status="{r['status']}"><h3>{E(r['title'])} <small>PDF {r['page']} · {E(r['file'])}</small></h3><div class="pair"><figure><figcaption>NI · <a href="{href}">Handbuchseite {r['page']}</a></figcaption><img src="{r['reference']}" alt="NI {E(r['title'])}"></figure><figure><figcaption>Machinista · {E(r['current']['page'])} · aktueller Renderer</figcaption><img src="{r['current']['image']}" alt="Aktuelle {E(r['current']['page'])}-Ansicht"></figure></div><p><span class="badge">{E(r['status'])}</span> {E(r['notes'])}</p></article>''')
rows=''.join(f'<tr><td><a href="#" onclick="choose(\'{k}\');return false">{E(v[0])}</a></td><td>{counts[k]}</td><td>{E(v[1])}</td><td>{E(v[2])}</td></tr>' for k,v in F.items())
style='''*{box-sizing:border-box}body{margin:0;background:#11151b;color:#e7ecf2;font:16px/1.55 system-ui,sans-serif}main{max-width:1240px;margin:auto;padding:28px}h1{font-size:30px}h2{margin-top:36px}a{color:#8ccbff}p{max-width:1050px}.note{border-left:3px solid #eab65a;padding:12px 18px;background:#21262e}.toolbar{position:sticky;top:0;background:#11151bf5;padding:12px 0;display:flex;gap:12px;flex-wrap:wrap;z-index:2}select,input,button{background:#252d39;color:#f1f4f8;border:1px solid #516071;border-radius:6px;padding:9px;font:inherit}input{min-width:250px}.card{border:1px solid #384554;border-radius:10px;padding:20px;margin:22px 0;background:#1b222c}h3{margin:0 0 14px}small{display:block;color:#a6b6c8;font-weight:400;font-size:13px}.pair{display:grid;grid-template-columns:1fr 1fr;gap:20px}figure{margin:0}figcaption{font-size:14px;color:#b7c7d9;margin-bottom:8px}img{width:100%;height:auto;aspect-ratio:2/1;object-fit:contain;background:#25262f;image-rendering:pixelated}.badge{color:#ffd98a;font-weight:600}.card[data-status=nah] .badge{color:#9bdfb0}table{border-collapse:collapse;width:100%;font-size:14px}td,th{border-bottom:1px solid #384554;padding:10px;text-align:left;vertical-align:top}td:nth-child(4){width:65%}.hidden{display:none}@media(max-width:700px){main{padding:14px}.pair{grid-template-columns:1fr}table{font-size:12px}td{padding:6px}}'''
options=''.join(f'<option value="{k}">{E(v[0])} ({counts[k]})</option>' for k,v in F.items())
script='''const family=document.querySelector('#family'),search=document.querySelector('#search');function filter(){let n=0;document.querySelectorAll('.card').forEach(c=>{let yes=(!family.value||c.dataset.family===family.value)&&c.textContent.toLowerCase().includes(search.value.toLowerCase());c.classList.toggle('hidden',!yes);if(yes)n++});document.querySelector('#count').textContent=n+' / 129 Beispiele'}function choose(k){family.value=k;filter();document.querySelector('#examples').scrollIntoView()}family.onchange=filter;search.oninput=filter;filter();'''
(OUT/'index.html').write_text(f'''<!doctype html><html lang="de"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Mikro-Displayvergleich · 2026-10-04</title><style>{style}</style><main><h1>NI Mikro ↔ Machinista: Displayvergleich</h1><p>Stand 04.10.2026. Alle <b>129 separat eingebetteten Mikro-LCD-Abbildungen</b> aus dem MK2-Handbuch erneut visuell geprüft, einschließlich mehrfach gezeigter Zustände. Zusätzlich alle <b>261 kleinen Bildkandidaten</b> geprüft: überwiegend Desktopsoftware und andere Controller; zwei Mikro-Hardwarefotos (PDF 44, 237) bestätigen den üblichen Aufbau. Nicht jede vollständige der 919 PDF-Seiten wurde neu als Bild geprüft.</p><p>Unsere Vergleichsbilder sind mit dem <b>aktuellen Displaycode</b> gerendert, dessen Prüfsummen mit dem installierten Pi übereinstimmen. Beispielprojekt: Sample01, 120 BPM, Position 1:1:1. Wellenform und LV2-Metadaten sind reproduzierbare Prüfdaten; keine Fotos vom Gerät. Andere Sample-/Plugin-Namen oder Werte sind keine Layoutfehler. Bei NI-Effekten ist rechts eine <b>LV2-Parameteransicht als strukturelle Entsprechung</b>, keine Nachbildung des NI-Effekts.</p><div class="note"><b>Ergebnis:</b> Der Stand ist noch keine originalgetreue Displayumsetzung. Kanal-NAV ist nach dem letzten Fix strukturell nah; zahlreiche übrige Screens verwenden weiterhin zusätzliche Textzeilen, andere Parameterseiten oder vereinfachte Grafiken. „Alle Screens eingebaut“ war als Aussage über Originaltreue zu weitgehend.</div><h2>Übergreifende Abweichungen</h2><ol><li><b>Typografie:</b> NI nutzt stärkere Titel- und Wertschrift. Unser Renderer verwendet überwiegend dieselbe 5×7-Schrift für Titel, Feld und Wert; Softkeys nutzen eine kleinere 3×5-Schrift.</li><li><b>Informationshierarchie:</b> NI ordnet Bereich/Slot links und Taktposition rechts an. Wir setzen oft Tempo/Position und eine zusätzliche Bereichszeile darunter. INPUT/GROOVE fehlen dort als Bereichslabel.</li><li><b>Werte und Einheiten:</b> rohe Prozent-/MIDI-/Booleanwerte statt dB, C3, ON/OFF, typisierter LV2-Enums oder Originalpräzision. Feldindex und Anzahl passen nicht überall.</li><li><b>Pfeile und deaktivierte Elemente:</b> vorheriger/nächster Parameter wird meist nicht angezeigt; leere Softkeys haben einen normalen Rahmen und „-“ statt gepunktetem deaktiviertem Rahmen.</li><li><b>Kontexttitel:</b> RECORD/SLICE/ZONE bzw. EDIT:-Präfix statt Sample-/Take-Name, teilweise ohne Slot-/Group-Kennung.</li><li><b>Grafik:</b> RECORD nur ein dünner Summenpegel, ZONE ohne Wellenform, Sampling-NAV als Liste. Die Inversion von EDIT/SLICE ist grundsätzlich vorhanden, aber Geometrie/Schraffierung weichen ab.</li><li><b>Statusmeldungen:</b> unsere helle Meldungsleiste überdeckt die untere Wertzeile; in den Vergleichsbildern ist sie bewusst leer, damit das Grundlayout sichtbar bleibt.</li></ol><h2>Bewusste Anpassungen</h2><p>MK1 MAIN statt MK2 CONTROL; MAIN allein öffnet vereinbarungsgemäß Settings. MK1 Orange/Blau statt RGB. Ordnerbrowser für SD/USB mit PREH statt NI-Library. Eigener Sampler/LV2 statt NI-Engines und NI-Inhalten. Zusätzlich eigener Pattern-Noteneditor sowie Projektbenennung/-löschung und Displayeinstellungen. Diese Anpassungen rechtfertigen nicht die übrigen Layoutabweichungen.</p><h2>Alle Screenfamilien</h2><table><thead><tr><th>Bereich</th><th>Beispiele</th><th>Einordnung</th><th>Abweichung</th></tr></thead><tbody>{rows}</tbody></table><h2>Vergleich aller 129 LCD-Abbildungen</h2><div class="toolbar"><select id="family"><option value="">Alle Bereiche</option>{options}</select><input id="search" placeholder="Suche, z. B. 832 oder ZONE"><span id="count"></span><button onclick="family.value='';search.value='';filter()">Zurücksetzen</button></div><section id="examples">{''.join(cards)}</section><h2>Nicht im LCD-Inventar dargestellte Ergänzungen</h2><p>VIEW/WAVE: unsere Zoom/Scroll-Parameterzeile und Padbefehle sind vorhanden, eine neue pixelgenaue Gegenüberstellung wurde mangels eigenständiger Mikro-LCD-Abbildung in diesem Inventar nicht behauptet. APPLY TO: funktionale Zielauswahl vorhanden, Originalgrafik in diesem Inventar nicht als einzelnes Mikro-LCD belegt. NI-Desktop-Mixer, DrumSynth und Komplete-Kontrol-S-Displays sind keine Mikro-LCD-Zielbilder. Unsere zusätzlichen Settings/Projekt-/Grid-Editor-Ansichten haben keine direkte Entsprechung in diesen 129 Bildern.</p><h2>Reihenfolge für eine spätere Korrektur</h2><ol><li>Gemeinsames Layout: Schriftgewichte, Fokuskennung, Bereich/Position, Werte, Pfeile, Disabled-Zustände.</li><li>Sampling: NAV-Kacheln, Stereo-Pegel, Sampletitel, ZONE-Waveform, STRETCH.</li><li>Kanal-/Samplerparameter: Originalseitengruppen, Reihenfolge, dynamische Envelopefelder, Einheiten.</li><li>PAD MODE, SELECT/EVENTS, Repeat/ARP, GRID, REC. MODE, PATTERN/SCENE.</li><li>LV2-Slotnavigation und Browser mit Originalstruktur, eigenen Metadaten und passenden Parametern.</li></ol><p>Dies ist ein Vergleichsbericht. Während dieses Audits wurde weder der Pi-Dienst geändert noch eine Displaykorrektur installiert.</p></main><script>{script}</script></html>''')
md=['# Displayvergleich NI Mikro / Machinista','', 'Stand 2026-10-04. [Bildvergleich aller 129 Mikro-LCD-Abbildungen](../../outputs/display-audit-2026-10-04/index.html). Aktueller Renderer und installierter Pi: Display-/Surface-/Navigation-Prüfsummen identisch. Alle neun LCD-Kontaktbögen und sechs Kandidatenkontaktbögen erneut visuell geprüft. 261 zusätzliche Kandidaten überwiegend Desktopsoftware/andere Controller. Keine neue vollständige Bildprüfung aller 919 PDF-Seiten.','', 'Die Umsetzung weicht noch deutlich ab; insbesondere Grundhierarchie, Schriftgewichte, Einheiten, Parameterpfeile und deaktivierte Softkeys. Kanal-NAV jetzt strukturell nah. Ordnerbrowser, MAIN Settings und LV2 sind vereinbarte Anpassungen. Prüfbilder sind synthetische Renderzustände, keine Hardwarefotos.','', '| Screenfamilie | Referenzen | Befund |','|---|---:|---|']
for k,v in F.items():md.append(f'| {v[0]} | {counts[k]} | {v[2]} |')
md+=['','## Vollständiges Inventar','', '| PDF-Seite / Bild | Zugeordnete Machinista-Ansicht | Befundfamilie |','|---|---|---|']
for r in records:md.append(f'| [{r["page"]} / {r["file"]}]({MANUAL}#page={r["page"]}) | {r["current"]["page"]} | {r["title"]} |')
(ROOT/'docs/manual-audit/SCREEN_COMPARISON.md').write_text('\n'.join(md)+'\n')
# Six key pairs in a compact standalone image for the chat.
keys=[('nav',44),('input',409),('sampler',282),('record',762),('samplingnav',832),('zone',812)]
canvas=Image.new('RGB',(1100,len(keys)*318),(17,21,27));d=ImageDraw.Draw(canvas)
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',20)
for i,(fam,page) in enumerate(keys):
 r=next(r for r in records if r['family']==fam and r['page']==page);y=i*318
 d.text((12,y+5),f'{r["title"]}  |  NI PDF {page} links / Machinista rechts',fill=(233,239,246),font=font)
 for x,path in ((12,OUT/r['reference']),(566,OUT/r['current']['image'])):
  im=Image.open(path).convert('RGB');im=im.resize((522,264),Image.Resampling.NEAREST);canvas.paste(im,(x,y+38+(264-im.height)//2))
canvas.save(OUT/'key-comparisons.png')
print(json.dumps({'references':len(records),'families':counts,'html':str(OUT/'index.html'),'report':str(ROOT/'docs/manual-audit/SCREEN_COMPARISON.md')},ensure_ascii=False))
