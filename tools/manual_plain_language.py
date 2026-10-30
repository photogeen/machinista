"""Musician-first editorial layer. Keep control bindings and screen pixels intact."""

# Each introduction starts with the musical task, rather than implementation detail.
INTRO = {
'Welcome to Machinista': (
 'Make beats, play instruments and build songs with your controller. Machinista runs on a Raspberry Pi, so you can make music without keeping a laptop connected. Start with the built-in synth or add your own recordings. You do not need to know how to program.',
 'Baue Beats, spiele Instrumente und stelle Songs zusammen - direkt am Controller. Machinista läuft auf einem Raspberry Pi. Beim Musikmachen brauchst du deshalb keinen angeschlossenen Laptop. Beginne mit dem eingebauten Synthesizer oder nutze eigene Aufnahmen. Programmierkenntnisse sind nicht nötig.'),
'Setup and first start': (
 'You need a Raspberry Pi 4 or 5, its power supply, an SD card of at least 8 GB, your controller and a supported audio device for headphones or speakers. The image is a ready-to-use system file: writing it to the SD card installs Machinista and the operating system together.',
 'Du brauchst einen Raspberry Pi 4 oder 5, sein Netzteil, eine SD-Karte mit mindestens 8 GB, deinen Controller und ein unterstütztes Audiogerät für Kopfhörer oder Lautsprecher. Das Image ist eine fertig vorbereitete Systemdatei. Beim Schreiben auf die SD-Karte werden Machinista und das Betriebssystem gemeinsam installiert.'),
'Reading the displays': (
 'Read the labels along the top edge first: they tell you what the buttons above the screen do right now. The middle shows the sound, notes or waveform you are working on. Labels beside the controls tell you which setting you can change.',
 'Lies zuerst die Beschriftung am oberen Displayrand. Sie zeigt, was die Tasten darüber gerade tun. In der Mitte siehst du den Sound, die Noten oder die Wellenform, die du bearbeitest. An den Reglern steht, welche Einstellung du ändern kannst.'),
'Navigation, hold and pin': (
 'Some views stay open only while you hold their button. PIN keeps a view open so you can release the button and work with both hands. Turn PIN off if you want the view to close when you release the button.',
 'Einige Ansichten bleiben nur geöffnet, solange du ihre Taste hältst. PIN hält eine Ansicht offen. So kannst du die Taste loslassen und mit beiden Händen weiterarbeiten. Schalte PIN aus, wenn die Ansicht beim Loslassen wieder schließen soll.'),
'Projects, Groups, Sounds and Patterns': (
 'Think of a project as one song session. A Group is a set of 16 pads, a Sound is what one pad plays, and a Pattern is a repeating musical phrase. Scenes combine the Patterns for different song sections; Song puts those sections in order.',
 'Ein Projekt ist deine Arbeit an einem Song. Eine Group ist ein Satz aus 16 Pads. Ein Sound ist das, was ein Pad spielt. Ein Pattern ist eine wiederholte musikalische Phrase. Scenes verbinden die Patterns zu Songteilen; in Song legst du deren Reihenfolge fest.'),
'Your first beat': (
 'Build a simple drum loop with kick, snare and hi-hat. You need three short WAV or MP3 samples of your own; the public image includes no drum sample pack. Upload them using the WebUI chapter first, or connect a USB drive containing them.',
 'Baue einen einfachen Drumloop aus Kick, Snare und Hi-Hat. Dafür brauchst du drei eigene kurze WAV- oder MP3-Samples. Das öffentliche Image enthält kein Drum-Samplepaket. Lade die Dateien wie im WebUI-Kapitel beschrieben hoch oder schließe einen USB-Stick mit den Samples an.'),
'Browse folders and load samples': (
 'Use BROWSE to find a sample and put it on a pad. SD CARD means the card inside the Pi; USB means a connected drive. Open a folder, listen to a file and load it onto the selected pad.',
 'Mit BROWSE suchst du ein Sample und lädst es auf ein Pad. SD CARD ist die Karte im Pi, USB ein angeschlossener Datenträger. Öffne einen Ordner, höre eine Datei vor und lade sie auf das ausgewählte Pad.'),
'Play, locate and set tempo': (
 'PLAY starts and stops the music. RESTART returns to the beginning. TEMPO sets the speed in beats per minute (BPM). You can keep these controls at hand while editing a sound or a sample.',
 'PLAY startet und stoppt die Musik. RESTART springt zum Anfang. TEMPO bestimmt die Geschwindigkeit in Schlägen pro Minute (BPM). Diese Funktionen kannst du auch beim Bearbeiten eines Sounds oder Samples nutzen.'),
'Record and overdub a Pattern': (
 'Record your pad playing into a repeating Pattern. REC stores which notes you play and when you play them. It does not record incoming audio; use SAMPLING for that. Turn REC off when you only want to practise or listen.',
 'Nimm dein Pad-Spiel als wiederholtes Pattern auf. REC speichert, welche Noten du wann spielst. Eingehendes Audio wird dabei nicht aufgenommen; dafür gibt es SAMPLING. Schalte REC aus, wenn du nur üben oder zuhören möchtest.'),
'Program the Step sequencer': (
 'Build a beat one step at a time instead of playing it live. Choose a Sound, then use the 16 pads as positions in the loop. A lit step contains a note. Press it again to remove that note.',
 'Baue einen Beat Schritt für Schritt, statt ihn live einzuspielen. Wähle einen Sound. Die 16 Pads stehen dann für Positionen im Loop. Ein leuchtender Step enthält eine Note. Drücke ihn erneut, um die Note zu entfernen.'),
'Select and edit individual events': (
 'Use EVENTS to fix or change recorded notes. Each block is a note: its horizontal position tells you when it starts, and its width shows how long it lasts. Select notes before moving them or changing their pitch, strength or length.',
 'In EVENTS korrigierst oder veränderst du aufgenommene Noten. Jeder Block ist eine Note. Seine Position von links nach rechts zeigt den Start, seine Breite die Dauer. Wähle Noten aus, bevor du ihre Position, Tonhöhe, Anschlagstärke oder Länge änderst.'),
'Keyboard, scales and 16 velocities': (
 'Normal pad mode plays a different Sound on each pad. KEYBOARD plays different notes of the one selected Sound, like piano keys. SCALE helps you stay in a chosen scale. With a sliced sample, the notes can play different slices instead.',
 'Im normalen Pad-Modus spielt jedes Pad einen anderen Sound. KEYBOARD spielt verschiedene Tonhöhen des einen ausgewählten Sounds - wie Klaviertasten. SCALE hilft dir, in einer Tonleiter zu bleiben. Bei einem geslicten Sample können die Noten stattdessen verschiedene Abschnitte spielen.'),
'Note Repeat and arpeggiation': (
 'Hold a pad with NOTE REPEAT to play repeated hits, such as a fast hi-hat roll. An arpeggiator turns held notes or a chord into a repeating note pattern. With PLAY running, the repeats follow the beat.',
 'Halte mit NOTE REPEAT ein Pad, um wiederholte Anschläge zu spielen, etwa einen schnellen Hi-Hat-Wirbel. Ein Arpeggiator macht aus gehaltenen Noten oder einem Akkord eine wiederholte Notenfolge. Bei laufendem PLAY folgen die Wiederholungen dem Takt.'),
'Sampling: choose an input and record': (
 'Record audio and put the result on a pad. First choose what to record and which pad should receive it. Watch the level meters while playing the source. The threshold mark shows the level at which automatic recording starts.',
 'Nimm Audio auf und lege das Ergebnis auf ein Pad. Wähle zuerst die Aufnahmequelle und das Ziel-Pad. Spiele die Quelle ab und beobachte die Pegelanzeigen. Die Threshold-Markierung zeigt, ab welchem Pegel die automatische Aufnahme startet.'),
'Trim, select and process a sample': (
 'Remove unwanted silence or keep only the part you want to play. START and END set the playback boundaries. A separate selection tells commands such as Normalize which section to process. Check that selection before applying a change.',
 'Entferne unerwünschte Stille oder behalte nur den Teil, den du spielen möchtest. START und END bestimmen den Wiedergabebereich. Eine separate Auswahl legt fest, welchen Abschnitt Befehle wie Normalize bearbeiten. Prüfe diese Auswahl vor dem Anwenden.'),
'Zoom and scroll the waveform': (
 'Zoom in to place a cut precisely, then scroll to the part you want to edit. The waveform is a picture of your audio. Zoom and scroll only change what you see; they do not change the sound, playback speed or sample length.',
 'Vergrößere die Wellenform, um einen Schnitt genau zu setzen, und verschiebe den sichtbaren Ausschnitt an die gewünschte Stelle. Die Wellenform ist ein Bild deiner Aufnahme. Zoom und Scroll ändern nur die Ansicht - nicht Klang, Geschwindigkeit oder Sample-Länge.'),
'Slice automatically or on a grid': (
 'Turn one loop into playable pieces called slices. GRID places evenly spaced cuts; DETECT looks for attacks such as drum hits. Listen to the slices and adjust the cuts before putting them on pads.',
 'Zerlege einen Loop in spielbare Abschnitte, die Slices heißen. GRID setzt gleichmäßige Schnitte. DETECT sucht nach Anschlägen, zum Beispiel Drum-Hits. Höre die Slices an und korrigiere die Schnitte, bevor du sie auf Pads verteilst.'),
'Manual live chopping and Slice Edit': (
 'Use MANUAL to place your own cuts while listening. Then open Slice Edit to move the start or end of a slice. You can tighten one cut without starting again with the whole loop.',
 'Setze mit MANUAL eigene Schnitte beim Zuhören. Öffne danach Slice Edit, um den Anfang oder das Ende eines Slices zu verschieben. So korrigierst du einen Schnitt, ohne den gesamten Loop neu zu zerlegen.'),
'Apply slices to a Sound or Group': (
 'After checking your cuts, choose where the slices should go with APPL.TO. Keep them inside one Sound for Keyboard playing, or spread them across a Group of pads. APPLY carries out that choice. Check the destination before pressing it.',
 'Wähle nach dem Prüfen der Schnitte mit APPL.TO das Ziel. Du kannst die Slices in einem Sound behalten und über Keyboard spielen oder auf die Pads einer Group verteilen. APPLY führt die Zuordnung aus. Prüfe davor das Ziel.'),
'Zones and layered sample mapping': (
 'Make one playable instrument from several recordings. For example, use low, middle and high piano samples on different keys. Each sample has a zone: the notes and playing strengths that trigger it. ROOT is the note the original sample was recorded at.',
 'Baue aus mehreren Aufnahmen ein spielbares Instrument. Zum Beispiel übernehmen tiefe, mittlere und hohe Piano-Samples verschiedene Tasten. Jedes Sample hat eine Zone: die Noten und Anschlagstärken, bei denen es erklingt. ROOT ist die Tonhöhe der ursprünglichen Aufnahme.'),
'The Sampler: voice, envelopes and filters': (
 'Shape how a loaded sample plays. Voices set how many notes can sound together. An envelope shapes the start and fade of each note. A filter makes the sound brighter or darker. Play a few notes while changing one setting at a time.',
 'Forme, wie ein geladenes Sample spielt. Voices bestimmt, wie viele Noten gleichzeitig klingen können. Eine Hüllkurve formt Anschlag und Ausklang jeder Note. Ein Filter macht den Klang heller oder dunkler. Spiele beim Einstellen einige Noten und ändere zunächst nur einen Wert.'),
'LV2 plug-ins: add, replace and remove': (
 'Plug-ins add instruments or effects. LV2 is the plug-in format Machinista uses. An instrument makes a sound; an effect changes audio passing through it. Effects in a chain work in order, like pedals connected one after another.',
 'Plug-ins ergänzen Instrumente oder Effekte. LV2 ist das dafür verwendete Plug-in-Format. Ein Instrument erzeugt Klang, ein Effekt verändert hindurchlaufendes Audio. In einer Effektkette arbeitet ein Effekt nach dem anderen - wie hintereinandergeschaltete Pedale.'),
'Channel routing and the Mixer': (
 'Balance your sounds in the Mixer: LEVEL changes volume and PAN moves a sound between left and right. Routing means choosing where audio comes from and where it goes, such as sending a Group to a separate output on your audio device.',
 'Stimme deine Sounds im Mixer aufeinander ab. LEVEL ändert die Lautstärke, PAN verteilt einen Sound zwischen links und rechts. Routing bedeutet, den Weg des Audios festzulegen - etwa eine Group an einen eigenen Ausgang deines Audiogeräts zu schicken.'),
'Mute, solo, selection and duplication': (
 'MUTE silences a pad or Group. SOLO lets you listen to it on its own. Selecting a pad chooses what you will edit; it does not mute anything. DUPLICATE makes a copy. Check which mode is open before pressing the pads.',
 'MUTE schaltet ein Pad oder eine Group stumm. Mit SOLO hörst du es allein. Das Auswählen eines Pads bestimmt, was du bearbeitest; es schaltet nichts stumm. DUPLICATE erstellt eine Kopie. Prüfe vor dem Pad-Druck, welcher Modus geöffnet ist.'),
'Scenes and Song arrangement': (
 'Build sections such as an intro, verse and chorus as Scenes. Each Scene chooses which Pattern each Group plays. Arrange the Scenes in Song. If two Scenes use the same Pattern, editing that Pattern changes both sections.',
 'Baue Songteile wie Intro, Strophe und Refrain als Scenes. Jede Scene bestimmt, welches Pattern jede Group spielt. In Song ordnest du die Scenes an. Nutzen zwei Scenes dasselbe Pattern, wirkt eine Änderung am Pattern in beiden Songteilen.'),
'Automation, macros and MIDI Learn': (
 'Record changes to a control so they play back with the music: this is automation. A macro brings useful settings together for performance. MIDI Learn connects a knob on an external keyboard or controller to a Machinista setting.',
 'Nimm Reglerbewegungen auf, damit sie mit der Musik wiedergegeben werden. Das heißt Automation. Ein Macro fasst nützliche Einstellungen zum Spielen zusammen. MIDI Learn verbindet einen Regler am externen Keyboard oder Controller mit einer Einstellung in Machinista.'),
'MIDI ports, clock and Bluetooth': (
 'Use a keyboard to play Machinista, or let Machinista play an external instrument. MIDI carries notes and control messages, not audio. To hear an external synth through Machinista, connect its audio outputs as well as MIDI.',
 'Spiele Machinista mit einem Keyboard oder steuere ein externes Instrument an. MIDI überträgt Noten und Steuerbefehle, kein Audio. Soll ein externer Synth über Machinista hörbar sein, verbinde zusätzlich seine Audioausgänge.'),
'Project names, presets and portable saves': (
 'Save the project to keep your work. A project stores your song setup; a Sound preset lets you reuse one instrument or pad sound in another project. Collect the referenced samples before moving a project to another card or Pi.',
 'Speichere das Projekt, um deine Arbeit zu behalten. Ein Projekt enthält deinen Song-Aufbau. Mit einem Sound-Preset kannst du ein Instrument oder einen Pad-Sound in einem anderen Projekt wiederverwenden. Sammle die verwendeten Samples ein, bevor du ein Projekt auf eine andere Karte oder einen anderen Pi überträgst.'),
'Relink missing files and export': (
 'If a project cannot find a sample, Relink helps you locate the file again. Export creates an audio or MIDI file for use elsewhere, such as a finished mix for sharing or separate parts for your music software.',
 'Findet ein Projekt ein Sample nicht, hilft Relink beim erneuten Zuordnen der Datei. Export erstellt eine Audio- oder MIDI-Datei für andere Zwecke - etwa einen fertigen Mix zum Teilen oder einzelne Spuren für deine Musiksoftware.'),
'WebUI, Wi-Fi and sample transfer': (
 'The WebUI is Machinista\'s control page in a browser. Open it on a phone, tablet or computer to upload samples, manage projects and organize Sounds. No extra app is needed; connect to the same network as the Pi.',
 'Die WebUI ist die Bedienseite von Machinista im Browser. Öffne sie am Handy, Tablet oder Computer, um Samples hochzuladen, Projekte zu verwalten und Sounds zu ordnen. Eine zusätzliche App brauchst du nicht. Verbinde dich mit demselben Netzwerk wie der Pi.'),
'Shortcuts and edit safety': (
 'Shortcuts speed up familiar tasks. A + means hold the first button while pressing the second. Before using CLEAR, COPY or PASTE, check the selected pad and notes so you change the intended part of your music.',
 'Kurzbefehle beschleunigen häufige Aufgaben. Ein + bedeutet: Halte die erste Taste und drücke die zweite dazu. Prüfe vor CLEAR, COPY oder PASTE das ausgewählte Pad und die markierten Noten, damit du den gewünschten Teil deiner Musik änderst.'),
'Troubleshooting and a session checklist': (
 'If something does not sound right, check one thing at a time. Start with the selected Sound, MUTE/SOLO and the audio output. Save a copy of your project before trying changes that remove notes or replace sounds.',
 'Wenn etwas nicht wie erwartet klingt, prüfe einen Punkt nach dem anderen. Beginne mit dem ausgewählten Sound, MUTE/SOLO und dem Audioausgang. Speichere eine Projektkopie, bevor du Noten entfernst oder Sounds ersetzt.'),
'Live FX performance and recording': (
 'Play effects with the pads while your beat runs. PUNCH applies an effect only while you hold the pad. FLEX keeps it active after release. KNOB lets you turn the chosen effect on or off and adjust its depth. With REC on, your performance can be recorded.',
 'Spiele Effekte mit den Pads, während dein Beat läuft. PUNCH wirkt nur, solange du das Pad hältst. FLEX bleibt nach dem Loslassen aktiv. Mit KNOB schaltest du den gewählten Effekt ein oder aus und regelst seine Stärke. Bei aktivem REC kannst du dein Spiel aufnehmen.'),
'Scene tools, banks and quantize': (
 'Use Scene Options when you want to change a whole song section. UNIQUE PATTERNS gives a Scene its own Pattern copies, so you can change the chorus without changing the verse. Quantize moves notes towards an even timing grid.',
 'Mit Scene Options bearbeitest du einen ganzen Songteil. UNIQUE PATTERNS erstellt eigene Pattern-Kopien für eine Scene. So kannst du den Refrain ändern, ohne auch die Strophe zu ändern. Quantize rückt Noten an ein gleichmäßiges Zeitraster.'),
'Custom chords and playing variations': (
 'Put a whole chord on one pad. CUSTOM lets you choose or make your own chord assignments. All chord pads play the selected instrument Sound. Strum spreads the notes in time; inversions move notes up or down an octave to change the chord voicing.',
 'Lege einen ganzen Akkord auf ein Pad. Mit CUSTOM wählst oder erstellst du eigene Akkordbelegungen. Alle Akkord-Pads spielen den ausgewählten Instrumenten-Sound. Strum versetzt die Noten zeitlich. Umkehrungen verschieben Noten um eine Oktave und verändern so die Lage des Akkords.'),
'Sounds, Zones and Autosampler': (
 'Save an instrument so you can load and play it again from Sounds. A multisample Sound uses several recordings across the keyboard. A live plug-in Sound keeps the instrument and its settings. Autosampler plays and records a range of notes for you, then maps the recordings to keys.',
 'Speichere ein Instrument, um es später unter Sounds wieder zu laden und zu spielen. Ein Multisample-Sound nutzt mehrere Aufnahmen über die Tastatur verteilt. Ein Plug-in-Sound behält das Instrument und seine Einstellungen. Autosampler spielt und nimmt für dich mehrere Noten auf und ordnet sie den Tasten zu.'),
'WebUI files, plugins and power': (
 'Use the browser page to organize files, add plug-ins and shut down the Pi. At home, open http://machinista.local:8080 on the same network. Without a router, connect to the Machinista-XXXX Wi-Fi hotspot (password machinista) and open http://10.42.0.1:8080.',
 'Nutze die Browserseite zum Ordnen von Dateien, Installieren von Plug-ins und Herunterfahren. Öffne zu Hause http://machinista.local:8080 im selben Netzwerk. Ohne Router verbindest du dich mit dem WLAN-Hotspot Machinista-XXXX (Passwort machinista) und öffnest http://10.42.0.1:8080.'),
'Machinista Synth': (
 'Play the built-in synth straight away: no extra plug-in is needed. Choose a BANK, then a PATCH (a ready-made sound). Start with a patch you like and change one setting at a time. Four oscillators are four sound sources you can mix together; a filter and envelopes shape the result.',
 'Spiele den eingebauten Synthesizer direkt, ohne ein zusätzliches Plug-in zu installieren. Wähle BANK und dann PATCH - einen fertig eingestellten Klang. Beginne mit einem Klang, der dir gefällt, und ändere zunächst nur einen Wert. Vier Oszillatoren sind vier Klangquellen, die du mischen kannst. Filter und Hüllkurven formen das Ergebnis.'),
}

TERMS = [
 ('Sound / pad', 'One slot in a Group. It can play a sample or an instrument.', 'Ein Platz in einer Group. Er spielt ein Sample oder ein Instrument.'),
 ('Group', 'A set of 16 Sounds. For example, drums in one Group and keys in another.', 'Ein Satz aus 16 Sounds. Zum Beispiel Drums in einer Group und Keys in einer anderen.'),
 ('Pattern / event', 'A repeating phrase / one recorded note or hit in that phrase.', 'Eine wiederholte Phrase / eine darin gespeicherte Note oder ein Anschlag.'),
 ('Scene / Song', 'A combination of Patterns / the order of those song sections.', 'Eine Kombination von Patterns / die Reihenfolge dieser Songteile.'),
 ('Sample / slice / zone', 'An audio recording / a cut piece / the keys and strengths that play a sample.', 'Eine Audioaufnahme / ein ausgeschnittener Teil / die Tasten und Anschlagstärken, die ein Sample spielen.'),
 ('Bank / patch / preset', 'A collection of sounds / one saved sound setting. Init is a neutral starting sound.', 'Eine Sammlung von Klängen / eine gespeicherte Klangeinstellung. Init ist ein neutraler Ausgangsklang.'),
 ('Encoder / focus', 'A turning control / the setting currently selected for editing.', 'Ein Drehregler / die gerade zum Bearbeiten ausgewählte Einstellung.'),
 ('Velocity / voice', 'How hard a note is played / one note sounding at a time.', 'Die Anschlagstärke / eine gleichzeitig klingende Stimme.'),
 ('Routing / cue', 'The path audio takes / a separate listening output, usually for headphones.', 'Der Weg des Audios / ein separater Ausgang zum Vorhören, meist über Kopfhörer.'),
 ('MIDI / LV2 / WebUI', 'Note and control messages / an add-on instrument or effect format / the browser control page.', 'Noten und Steuerbefehle / ein Format für zusätzliche Instrumente und Effekte / die Bedienseite im Browser.'),
]

# Keep labels, bindings and musical units unchanged. These are prose-only edits.
REPLACEMENTS = {
 'en': [
  ('transport and recording', 'playback and recording'), ('Stop transport', 'Stop playback'),
  ('transport position', 'playback position'), ('transport grid', 'beat grid'),
  ('transport/recording', 'playback/recording'), ('parameter binding', 'setting assigned'),
  ('parameter movement', 'control movement'), ('parameter bank', 'page of settings'),
  ('focused Sound', 'selected Sound'), ('cursor target', 'note under the cursor'),
  ('selected set', 'selected notes'),
  ('endpoint', 'connection'), ('instantiate', 'load'),
 ],
 'de': [
  ('Stoppe Transport', 'Stoppe die Wiedergabe'), ('Transportposition', 'Wiedergabeposition'),
  ('Transport/Recording', 'Wiedergabe/Aufnahme'), ('Transport/Aufnahme', 'Wiedergabe/Aufnahme'),
  ('Transport und Aufnahme', 'Wiedergabe und Aufnahme'), ('Transport-Raster', 'Taktraster'),
  ('Parameterbindung', 'zugewiesene Einstellung'), ('fokussierten Sound', 'ausgewählten Sound'),
  ('fokussierte Wert', 'ausgewählte Wert'), ('markierte Menge', 'markierten Noten'),
  ('Cursorziel', 'Note unter dem Cursor'), ('Endpunkte', 'Anschlüsse'),
 ],
}

def simplify(text, language='en'):
    for old,new in REPLACEMENTS[language]:
        import re
        text=re.sub(r"\b"+re.escape(old)+r"\b",lambda _:new,text)
    return text


def enrich(chapters, language='en'):
    de=language=='de';idx=1 if de else 0
    by={c.get('source_title',c['title']):c for c in chapters}
    if de:
        by['Machinista Synth']=by['Machinista Synth: eigener Synthesizer']
    for title,values in INTRO.items():
        by[title]['intro']=values[idx]
    welcome=by['Welcome to Machinista']
    welcome['notes']=[
      (('Begin here','Hier anfangen')[idx],(
       'Read Setup, then try the first-sound walkthrough on the next page. Continue with Your first beat when you have drum samples. Look up other chapters when you need them; you do not have to read the screen reference before making music.',
       'Lies Einrichtung und erster Start und probiere danach den ersten Sound auf der nächsten Seite aus. Mit eigenen Drum-Samples geht es bei Dein erster Beat weiter. Lies andere Kapitel nach Bedarf. Die Displayübersicht musst du vor dem Musikmachen nicht durcharbeiten.')[idx]),
      (('Labels in this guide','Beschriftung in dieser Anleitung')[idx],(
       'CAPITALS match buttons or menu labels on the controller. Press means a short press and release; hold means keep the button down. Turn an encoder to change a setting. The screens stay English, including in the German guide.',
       'GROSSBUCHSTABEN entsprechen Tasten oder Menüeinträgen am Controller. Drücken bedeutet kurz drücken und loslassen; halten bedeutet gedrückt lassen. Ein Encoder ist ein Drehregler zum Ändern eines Werts. Die Anzeigen bleiben englisch, auch in der deutschen Anleitung.')[idx])]
    welcome.setdefault('supplements',[])[:0]=[
     dict(title=('Your first sound - no samples needed','Dein erster Sound - ohne eigene Samples')[idx],
      intro=('Once the controller and audio output work, try a built-in synth sound. This short path lets you play before learning the editing pages.','Sobald Controller und Audioausgang funktionieren, probiere einen eingebauten Synth-Klang. So kannst du direkt spielen, bevor du die Bearbeitungsseiten kennenlernst.')[idx],
      figures=['Tutorial / Keyboard'],
      steps=[
       ('Select an empty pad in normal pad mode. Open BROWSE and choose the Sounds category.','Wähle im normalen Pad-Modus ein leeres Pad. Öffne BROWSE und wähle die Kategorie Sounds.')[idx],
       ('Open Machinista Synth, choose a bank, then a patch. Use the displayed LOAD action. Loading puts this instrument and patch on the selected pad.','Öffne Machinista Synth, wähle eine Bank und dann einen Patch. Nutze die angezeigte Aktion LOAD. Dadurch werden Instrument und Klang auf das ausgewählte Pad geladen.')[idx],
       dict(mikro=('Hold SHIFT and press PAD MODE to turn KEYBOARD on. Play several pads: they now play different notes of this one sound.','Halte SHIFT und drücke PAD MODE, um KEYBOARD einzuschalten. Spiele mehrere Pads: Sie spielen jetzt verschiedene Noten dieses einen Sounds.')[idx],mk2=('Hold SHIFT and press PAD MODE to turn KEYBOARD on. Play several pads: they now play different notes of this one sound.','Halte SHIFT und drücke PAD MODE, um KEYBOARD einzuschalten. Spiele mehrere Pads: Sie spielen jetzt verschiedene Noten dieses einen Sounds.')[idx],mk3=('Press KEYBOARD and play several pads. They now play different notes of this one sound.','Drücke KEYBOARD und spiele mehrere Pads. Sie spielen jetzt verschiedene Noten dieses einen Sounds.')[idx]),
       ('Keep REC off while trying the sound. Change the output volume to a comfortable level. If you hear nothing, check the audio device, selected output and MUTE/SOLO before changing synth settings.','Lass REC beim Ausprobieren ausgeschaltet. Stelle eine angenehme Ausgangslautstärke ein. Falls nichts zu hören ist, prüfe Audiogerät, gewählten Ausgang und MUTE/SOLO, bevor du Synth-Einstellungen änderst.')[idx],
       ('Follow the Pattern recording chapter to record what you play. Then follow the Projects chapter to save it.','Im Kapitel zur Pattern-Aufnahme lernst du, dein Spiel aufzunehmen. Im Projekt-Kapitel erfährst du, wie du es speicherst.')[idx]],notes=[]),
     dict(title=('Words you will see on screen','Begriffe auf dem Display')[idx],intro=(
      'You do not need to memorize these terms. Return to this page when an English label is unfamiliar. The labels stay the same on the device and in the instructions.',
      'Du musst diese Begriffe nicht auswendig lernen. Schlage hier nach, wenn dir eine englische Beschriftung unbekannt ist. Die Namen bleiben am Gerät und in den Anweisungen gleich.')[idx],
      steps=[label+': '+values[idx] for label,*values in TERMS],notes=[]),
    ]
    setup=by['Setup and first start']
    setup['steps'][0]=(
     'On a computer, open Raspberry Pi Imager and choose the supplied .img.xz file with Use custom. Choose the SD card and write it. This erases the selected card. Finish verification, and keep the prepared account/network settings instead of adding your own Imager settings.',
     'Öffne am Computer Raspberry Pi Imager und wähle über Use custom die bereitgestellte .img.xz-Datei. Wähle die SD-Karte aus und schreibe sie. Dabei wird die ausgewählte Karte gelöscht. Lass die Prüfung abschließen. Behalte die vorbereiteten Konto-/Netzwerkeinstellungen, statt eigene Imager-Einstellungen hinzuzufügen.')[idx]
    setup['steps'][-1]=(
     'Choose AUTO to let Machinista select a connected USB audio device, or use a supported audio board attached to the Pi when no USB device is connected. MAIN OUTPUT is the pair of outputs you hear. Leave SAMPLE RATE and BUFFER at their prepared values for your first test.',
     'Wähle AUTO, damit Machinista ein angeschlossenes USB-Audiogerät auswählt. Ohne USB-Gerät kann eine unterstützte Audioplatine am Pi verwendet werden. MAIN OUTPUT ist das hörbare Ausgangspaar. Lass SAMPLE RATE und BUFFER für den ersten Test auf den vorbereiteten Werten.')[idx]
    # Keep device-specific settings shortcuts and confirmation actions verbatim.
    settings=by['Audio and controller settings']
    prior=settings['intro']
    lead=('Set the audio output, pad response and display to suit your setup. An audio interface is the device your headphones, speakers or recording input connect to. ',
          'Passe Audioausgang, Pad-Reaktion und Display an dein Setup an. Das Audiointerface ist das Gerät für Kopfhörer, Lautsprecher oder Aufnahmequellen. ')[idx]
    settings['intro']={k:lead+v for k,v in prior.items()} if isinstance(prior,dict) else lead+prior
    setup['notes'][0]=(('Trying a new setup','Ein neues Setup testen')[idx],(
     'This is a beta. After starting a new Pi or connecting a different audio device, try a sound, record a short Pattern and check the outputs before relying on the setup for a session.',
     'Dies ist eine Beta. Probiere nach dem Start eines neuen Pi oder dem Anschluss eines anderen Audiogeräts einen Sound aus. Nimm ein kurzes Pattern auf und prüfe die Ausgänge, bevor du dich in einer Session darauf verlässt.')[idx])
    by['The Sampler: voice, envelopes and filters'].setdefault('supplements',[]).append(dict(
      title=('Shape a sound by ear','Einen Klang nach Gehör formen')[idx],
      intro=('You can start with these controls instead of learning every page. The same ideas apply to many synths and samplers. Change one control while playing, then listen before changing another.',
             'Beginne mit diesen Reglern, statt gleich jede Seite zu lernen. Dieselben Ideen gelten für viele Synthesizer und Sampler. Ändere beim Spielen einen Wert und höre das Ergebnis, bevor du den nächsten änderst.')[idx],
      steps=[
       ('ATTACK: turn it up for a softer, slower start; turn it down for an immediate hit.','ATTACK: Höhere Werte lassen den Klang weicher und langsamer einsetzen. Niedrige Werte geben einen direkten Anschlag.')[idx],
       ('DECAY and SUSTAIN: Decay sets how quickly the first peak settles; Sustain sets the level while a note is held.','DECAY und SUSTAIN: Decay bestimmt, wie schnell der erste Pegel abfällt. Sustain bestimmt den Pegel während einer gehaltenen Note.')[idx],
       ('RELEASE: sets how long a note fades after release. Long releases and big chords use more voices. The selected playback mode also affects sample endings.','RELEASE: bestimmt, wie lange eine Note nach dem Loslassen ausklingt. Lange Ausklänge und große Akkorde brauchen mehr Stimmen. Bei Samples beeinflusst auch der gewählte Wiedergabemodus das Ende.')[idx],
       ('CUTOFF: with a low-pass filter, lower values make the sound darker and higher values make it brighter. Other filter types affect a different part of the sound.','CUTOFF: Bei einem Tiefpass machen niedrige Werte den Klang dunkler, höhere heller. Andere Filtertypen bearbeiten andere Klanganteile.')[idx],
       ('RESONANCE: emphasizes the sound around the filter cutoff. Start with a small amount; high settings can become loud or sharp.','RESONANCE: betont den Bereich um die Filterfrequenz. Beginne mit wenig Resonanz; hohe Werte können laut oder scharf werden.')[idx],
       ('VOICES and MONO: voices are notes sounding together. A low voice limit can cut earlier notes off. Mono playing is useful for a single-note bass or lead.','VOICES und MONO: Stimmen sind gleichzeitig klingende Noten. Bei einer niedrigen Begrenzung können frühere Noten abgeschnitten werden. Mono eignet sich für einstimmige Bässe und Leads.')[idx],
       ('LEVEL and effects: compare sounds at similar loudness. Lower the level if the output distorts before adding more processing.','LEVEL und Effekte: Vergleiche Klänge bei ähnlicher Lautstärke. Senke den Pegel bei verzerrtem Ausgang, bevor du weitere Effekte hinzufügst.')[idx]],notes=[]))
    settings.setdefault('supplements',[]).append(dict(
      title=('Audio settings without guesswork','Audioeinstellungen verständlich erklärt')[idx],
      intro=('Get sound working with the prepared settings first. You can return to these choices later. Only controls supported by your audio device can appear in its hardware mixer.',
             'Bringe den Ton zuerst mit den vorbereiteten Einstellungen zum Laufen. Diese Werte kannst du später anpassen. Im Hardware-Mixer erscheinen nur Regler, die dein Audiogerät unterstützt.')[idx],
      steps=[
       ('INTERFACE: the audio device being used. MAIN OUTPUT: the output pair sent to your speakers or headphones. CUE: a separate listening output, if available.','INTERFACE: das verwendete Audiogerät. MAIN OUTPUT: das Ausgangspaar für Lautsprecher oder Kopfhörer. CUE: ein separater Ausgang zum Vorhören, falls vorhanden.')[idx],
       ('Input gain: makes a microphone or other recording input louder before recording. Output and headphone levels change listening volume. These are different controls.','Input Gain: verstärkt ein Mikrofon oder eine andere Aufnahmequelle vor der Aufnahme. Ausgangs- und Kopfhörerpegel ändern die Abhörlautstärke. Das sind unterschiedliche Regler.')[idx],
       ('Meters and dB: 0 dB on a digital recording/output meter is the ceiling. Leave room below it for loud hits; reaching the ceiling can cause clipping, a harsh distortion. An input peak around -12 dB is a useful starting point.','Pegel und dB: 0 dB auf einer digitalen Aufnahme-/Ausgangsanzeige ist die Obergrenze. Lass Platz für laute Anschläge. An der Grenze kann Clipping entstehen, eine harte Verzerrung. Ein Eingangs-Spitzenpegel um -12 dB ist ein brauchbarer Ausgangspunkt.')[idx],
       ('BUFFER: a smaller buffer can make playing feel more immediate but gives the Pi less time to finish the audio. If you hear clicks under load, use fewer demanding sounds or try a larger buffer.','BUFFER: Ein kleinerer Puffer kann direkter reagieren, lässt dem Pi aber weniger Zeit für die Audioberechnung. Bei Knacksern unter Last nutze weniger aufwendige Sounds oder probiere einen größeren Puffer.')[idx],
       ('SAMPLE RATE: how often audio is measured each second. Higher is not automatically better for a project and uses more processing. Keep the prepared value until you have a reason to change it.','SAMPLE RATE: wie oft Audio pro Sekunde erfasst wird. Höher ist für ein Projekt nicht automatisch besser und benötigt mehr Rechenleistung. Behalte den vorbereiteten Wert, solange kein Grund zum Ändern besteht.')[idx],
       ('CPU: shows processing load, not volume. One busy core can cause dropouts even if the overall figure looks low. Try the same music with fewer instruments/effects to check whether load is the cause.','CPU: zeigt die Rechenlast, nicht die Lautstärke. Ein ausgelasteter Kern kann Aussetzer verursachen, obwohl der Gesamtwert niedrig aussieht. Probiere dieselbe Musik mit weniger Instrumenten/Effekten, um die Last als Ursache zu prüfen.')[idx]],notes=[]))
    # These rows fit the settings overview; the next page explains the terms.
    audio_rows=[
      ('AUTO chooses an available supported audio device. You can also choose one yourself.', 'AUTO wählt ein verfügbares unterstütztes Audiogerät. Du kannst es auch selbst wählen.'),
      ('Sound format and audio buffer. Keep the prepared values for your first test.', 'Klangformat und Audiopuffer. Behalte beim ersten Test die vorbereiteten Werte.'),
      ('Choose separate main and headphone-preview outputs, if your device supports them.', 'Wähle getrennte Ausgänge für Hauptmix und Vorhören, falls dein Gerät sie bietet.'),
      ('Optional timing correction for delayed effects. Off by default; change only with playback stopped.', 'Optionaler Ausgleich für verzögernde Effekte. Standardmäßig aus; nur bei gestoppter Wiedergabe ändern.'),
      ('Headphone, speaker and input levels on supported audio boards (HATs).', 'Kopfhörer-, Lautsprecher- und Eingangspegel unterstützter Audioplatinen (HATs).'),
      ('Brightness and contrast for the controller you are using.', 'Helligkeit und Kontrast für den gerade bedienten Controller.'),
      ('Pad sensitivity and how playing strength changes the volume.', 'Pad-Empfindlichkeit und Umsetzung der Anschlagstärke in Lautstärke.'),
      ('Version, processing load, memory and storage space.', 'Version, Rechenlast, Arbeitsspeicher und Platz auf Datenträgern.'),
    ]
    assert len(settings['table'])==len(audio_rows)+1
    settings['table']=[settings['table'][0]]+[(row[0],values[idx]) for row,values in zip(settings['table'][1:],audio_rows)]
    settings['supplements'].append(dict(
      title=('Display, pads and hardware levels','Display, Pads und Hardware-Pegel')[idx],
      intro=('Display and pad settings apply to the controller you are using. Hardware mixer settings affect your audio device. Keep playing a pad while adjusting its listening level so you can hear the change.',
             'Display- und Pad-Einstellungen gelten für den Controller, den du gerade bedienst. Der Hardware-Mixer gehört dagegen zum Audiogerät. Spiele beim Einstellen der Abhörlautstärke ein Pad, damit du die Änderung hören kannst.')[idx],
      steps=[],notes=settings['notes']))
    settings['notes']=[]
