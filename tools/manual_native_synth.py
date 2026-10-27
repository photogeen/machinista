"""Illustrated built-in synth chapters, localized without changing screen labels."""
import copy,hashlib,tempfile
from pathlib import Path
from PIL import Image


def synth_catalog(assets):
 from app.model import Application
 from app.plugin_profiles import profile
 from app.synth_library import URI
 from app.controller_inputs import ControllerInputs
 from app.mk2_surface import Mk2Surface
 from app.mk3_surface import Mk3Surface
 from app.mk3_display import Mk3Renderer
 from app.mk3_state import snapshot as mk3_snapshot
 from app.mk1_session import Mk1Surface
 from app.mk2_display import Mk2Renderer,snapshot
 from app.ni_display import frame
 result=[]
 with tempfile.TemporaryDirectory() as tmp:
  a=Application(tmp);p=profile(URI);a.page='PLUGIN';a.control_level=2;a.track()['name']='Vowel Motion'
  a.plugin_catalog=[dict(uri=URI,name=p['title'],kind='INSTRUMENT',supported=True,builtin=True,ports=p['parameters'])]
  a.track()['plugins']=[dict(uri=URI,kind='INSTRUMENT',controls={v['symbol']:v['default'] for v in p['parameters']})];a.track()['plugins'][0]['controls'].update(osc1_wave=28,osc1_shape=.4)
  inputs=ControllerInputs(a);mk2=Mk2Surface(a,inputs);mk1=Mk1Surface(a,inputs);renderer=Mk2Renderer();color_renderer=Mk3Renderer();mk3=Mk3Surface(a,inputs)
  try:
   for section,label in [('OSC 1 / WAVE','Wave'),('AMP / FILTER ENV','Envelope'),('FILTER 1','Filter'),('LFO 1','LFO'),('SYNTH / PRESETS','Presets')]:
    a.plugin_param=next(i for i,v in enumerate(a.plugin_controls()) if v.get('section')==section);a.message='';paths={};hashes={};fields={}
    for device,surface in [('mk1',mk1),('mk2',mk2),('mikro',None),('mk3',mk3)]:
     if device=='mk3':
      state=mk3_snapshot(surface);im=Image.new('RGB',(976,272),'#29231e')
      for index,image in enumerate(color_renderer.images(state)):im.paste(image,(index*496,0))
      fields[device]=[(v[0],v[1]) for v in state['fields'] if v]
     elif surface:
      state=snapshot(surface);pair=renderer(state);im=Image.new('RGB',(528,64),'#29231e')
      for index,pixels in enumerate(pair):one=Image.new('L',(256,64));one.putdata([v*255 for v in pixels]);im.paste(one,(index*272,0))
      fields[device]=[(v[0],v[1]) for v in state['fields'] if v]
     else:im=Image.new('L',(128,64));im.putdata([(1-v)*255 for v in frame(a)]);im=im.convert('RGB')
     hashes[device]=hashlib.sha256(im.tobytes()).hexdigest();path=assets/f'synth-{label.lower()}-{device}.png';im.resize((im.width*3,im.height*3),Image.Resampling.NEAREST).save(path);paths[device]=str(path)
    result.append(dict(label='Native Synth / '+label,page='PLUGIN',paths=paths,hashes=hashes,fields=fields['mk2'],fields_by_device=fields))
  finally:renderer.close();color_renderer.close()
 return result


def enrich(chapters,lang='en'):
 if any(ch['title'] in ('Machinista Synth','Machinista Synth: eigener Synthesizer') for ch in chapters):return
 de=lang=='de'
 choose=lambda en,deutsch:deutsch if de else en
 text=dict(
  title=choose('Machinista Synth','Machinista Synth: eigener Synthesizer'),screens=[],
  intro=choose('Machinista Synth is a built-in instrument with four oscillator layers, original factory waves and user wavetables. It needs no LV2 upload. It occupies the instrument position on the selected Sound and uses the existing effect strip.','Machinista Synth ist ein eingebautes Instrument mit vier Oszillator-Layern, eigenen Factory-Waves und importierbaren Wavetables. Ein LV2-Upload ist nicht erforderlich. Der Synth belegt den Instrument-Slot des ausgewählten Sounds und nutzt dessen Effektkette.'),
  steps=[
   choose('Select the destination Sound. Open the plug-in browser, choose INSTRUMENT, select Machinista Synth and use the displayed LOAD action.','Wähle den Ziel-Sound. Öffne den Plug-in-Browser, wähle INSTRUMENT, dann Machinista Synth und die angezeigte LOAD-Aktion.'),
   choose('On the first parameter bank choose BANK = Machinista Factory and a named PATCH, or begin with Init. Changes belong to this Sound; another pad is not a separate oscillator.','Wähle auf der ersten Parameterseite BANK = Machinista Factory und einen PATCH oder beginne mit Init. Änderungen gehören zu diesem Sound; ein anderes Pad ist kein eigener Oszillator.'),
   choose('Use SHIFT + PAD MODE to enable Keyboard. Play notes or chords while adjusting the synth. In Events, keyboard pads keep playing this Sound instead of selecting other Sound slots. REC is required to record notes.','Aktiviere Keyboard mit SHIFT + PAD MODE. Spiele während der Bearbeitung Noten oder Akkorde. Auch in Events spielen die Keyboard-Pads diesen Sound, statt andere Sound-Slots zu wählen. Noten werden nur mit REC aufgenommen.'),
   {'mikro':choose('Use the encoder and arrows to move through the named parameter banks. The page count and focused value remain visible.','Wähle mit Encoder und Pfeilen die benannten Parameterseiten. Seitenzahl und aktueller Wert bleiben sichtbar.'),'mk1':choose('Use the page arrows and eight parameter encoders. Confirm choices with the labelled display action; no master-encoder push is needed.','Nutze die Seitenpfeile und acht Parameterregler. Bestätige mit der beschrifteten Displayaktion; ein Druck auf einen Master-Encoder ist nicht nötig.'),'mk2':choose('Use the page arrows and eight parameter encoders. Waveform and modulation graphics appear above the parameter strip.','Nutze die Seitenpfeile und acht Parameterregler. Wellenform- und Modulationsgrafiken stehen über der Parameterleiste.')},
   choose('Save a named Sound through the existing controller Sound-save workflow or WebUI Save current Sound / LV2 patch. The native synth patch and its effect strip stay together.','Speichere einen benannten Sound über den Sound-Speicherablauf oder in der WebUI mit Save current Sound / LV2 patch. Der native Synth-Patch und seine Effektkette bleiben zusammen.')],
  notes=[
   (choose('Processing load','Rechenlast'),choose('More voices, oscillators, unison and effects require more CPU. Start with the factory settings on Pi 4. A high VOICES setting is not a guarantee that every maximum combination fits the audio deadline.','Mehr Stimmen, Oszillatoren, Unison und Effekte benötigen mehr CPU. Beginne auf Pi 4 mit den Factory-Einstellungen. Ein hoher VOICES-Wert garantiert nicht, dass jede Maximalkombination rechtzeitig berechnet wird.')),
   (choose('Original instrument','Eigenständiges Instrument'),choose('This is an original synth. FM/feedback FM and proprietary third-party oscillator/filter algorithms are not included.','Dies ist ein eigenständiger Synth. FM/Feedback-FM und proprietäre Oszillator- oder Filteralgorithmen anderer Hersteller sind nicht enthalten.'))],
  supplements=[dict(title=choose('Oscillators, envelopes and modulation','Oszillatoren, Hüllkurven und Modulation'),intro=choose('Choose one of the eight controller pages, then play the current Sound while editing. Controls that do not apply to the selected wave show N/A.','Wähle eine der acht Controllerseiten und spiele den aktuellen Sound beim Bearbeiten. Regler ohne Funktion für die gewählte Wave zeigen N/A.'),figures=['Native Synth / Wave','Native Synth / Envelope'],steps=[
   choose('OSC 1–4: choose WAVE, SEMI, FINE in cents, LEVEL and PAN. POSITION scans a wavetable; PULSE WIDTH changes a pulse. The controller has eight curated pages: Presets/Voicing, OSC 1-4, Filter, Envelopes and Modulation. Character, response and detailed Ring settings are in WebUI > Synth.','OSC 1–4: Wähle WAVE, SEMI, FINE in Cents, LEVEL und PAN. POSITION durchfährt eine Wavetable; PULSE WIDTH verändert eine Pulswelle. Der Controller hat acht kompakte Seiten: Presets/Voicing, OSC 1-4, Filter, Envelopes und Modulation. Character, Response und Ring-Details liegen unter WebUI > Synth.'),
   choose('Two filters work in Series or Parallel. Four DAHDSR envelopes and four LFOs provide movement. Choose a matrix SOURCE and TARGET with nonzero AMOUNT; VIA, MOD SHAPERS and MIN/MAX shape the route. LFO 1 example on controller page 8: WAVE Sine, RATE 2 Hz, SYNC Off, LEVEL 100%, SOURCE LFO 1, TARGET FILTER1 CUTOFF, AMOUNT 20%, VIA Off. Enable a low-pass filter near 1 kHz and hold a note. LFO shape/rate alone do not change the sound without a matrix route. This is a control-rate matrix, not an FM engine.','Zwei Filter arbeiten seriell oder parallel. Vier DAHDSR-Hüllkurven und vier LFOs erzeugen Bewegung. Wähle in der Matrix SOURCE und TARGET mit AMOUNT ungleich null; VIA, MOD SHAPERS und MIN/MAX gestalten die Verbindung. LFO-1-Beispiel auf Controllerseite 8: WAVE Sine, RATE 2 Hz, SYNC Off, LEVEL 100%, SOURCE LFO 1, TARGET FILTER1 CUTOFF, AMOUNT 20%, VIA Off. Aktiviere einen Low-Pass-Filter bei etwa 1 kHz und halte eine Note. LFO-Wellenform und Rate allein ändern den Klang ohne Matrixverbindung nicht. Die Matrix arbeitet mit einer Steuerrate und ist keine FM-Engine.')]),
   dict(title=choose('Graphical Synth editor in WebUI','Grafischer Synth-Editor in der WebUI'),intro=choose('Open the Synth tab for the complete instrument. It follows the selected Sound and keeps the controller workflow compact.','Öffne den Tab Synth für das vollständige Instrument. Er folgt dem ausgewählten Sound und hält die Controllerbedienung kompakt.'),images=['synth-editor'],steps=[
    choose('Load Machinista Synth on a Sound and select its pad. Choose the instrument slot if there is more than one synth. Bank and Patch load a starting preset; Save Sound keeps your edited patch and effect strip.','Lade Machinista Synth auf einen Sound und wähle dessen Pad. Bei mehreren Synths wählst du den Instrument-Slot. Bank und Patch laden ein Preset; Save Sound speichert den bearbeiteten Patch samt Effektkette.'),
    choose('Use Oscillators, Filters, Envelopes, LFOs, Matrix and Voicing. Drag knobs vertically or move their sliders. Type an exact value below a knob. Percent fields use 0-100 and FINE uses cents. Open the folded Character, Response, Ring and Loop sections for details.','Nutze Oscillators, Filters, Envelopes, LFOs, Matrix und Voicing. Ziehe Drehregler vertikal oder bewege die Schieberegler. Unter dem Regler kannst du einen genauen Wert eingeben. Prozentfelder verwenden 0-100, FINE verwendet Cents. Klappe Character, Response, Ring und Loop für Details auf.'),
    choose('The graphs update while you edit; pads and a connected keyboard audition the same Sound. Live parameter edits also work during playback. Use the controller to record parameter automation. Stop playback before saving the Sound.','Die Grafiken ändern sich beim Bearbeiten; Pads und eine angeschlossene Tastatur spielen denselben Sound. Parameteränderungen funktionieren auch während der Wiedergabe. Zeichne Parameterautomation am Controller auf. Stoppe die Wiedergabe vor Save Sound.'),
    choose('Matrix selects one of 32 routes. Choose Source, Target and Amount, then optional Via and Shaper. No synthesis parameters are removed by the compact controller layout.','Matrix wählt eine von 32 Verbindungen. Wähle Source, Target und Amount, dann bei Bedarf Via und Shaper. Durch die kompakte Controlleransicht gehen keine Syntheseparameter verloren.')]),
   dict(title=choose('Import your own synth waves','Eigene Synth-Waves importieren'),intro=choose('The WebUI has a separate Synth Waves tab. It manages waveform sources, not finished Sound patches.','Die WebUI hat einen eigenen Tab Synth Waves. Dort verwaltest du Wellenformquellen, keine fertigen Sound-Patches.'),images=['synth-waves'],steps=[
    choose('Open Synth Waves. Keep Single cycle for a WAV containing exactly one cycle. For wavetables select the samples per cycle, enter an optional folder and tags, then import. Stereo conversion must be enabled explicitly.','Öffne Synth Waves. Wähle Single cycle für eine WAV mit genau einer Periode. Bei Wavetables stellst du die Samples pro Periode ein, vergibst bei Bedarf Ordner und Tags und importierst die Datei. Stereo-Konvertierung muss ausdrücklich aktiviert werden.'),
    choose('Supported: PCM16/24/32 and float32 WAV, 32–16384 samples per cycle, up to 256 cycles and 32 MiB per upload. Common 600-sample single cycles work too. The import worker prepares filtered playback tables.','Unterstützt werden PCM16/24/32- und Float32-WAVs, 32–16384 Samples pro Periode, bis zu 256 Perioden und 32 MiB pro Upload. Auch Single Cycles mit 600 Samples funktionieren. Der Importprozess bereitet gefilterte Wiedergabetabellen vor.'),
    choose('Choose the imported name in an OSC WAVE field. Save the Sound or project to collect its user waves. Removing a library entry leaves saved Sounds/projects playable; retained assets still use storage.','Wähle den importierten Namen im OSC-Feld WAVE. Speichere Sound oder Projekt, damit die User-Waves mitgesichert werden. Entfernen aus der Bibliotheksliste erhält gespeicherte Sounds/Projekte; aufbewahrte Dateien benötigen weiterhin Speicher.')])])
 chapters.append(text)
