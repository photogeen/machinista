"""German prose; controller/menu labels and renderer pixels stay English."""
from copy import deepcopy
CH=[]
def either(mikro,mk2):return dict(mikro=mikro,mk2=mk2)
def chapter(title,intro,steps=(),notes=(),table=None):
    CH.append(dict(title=title,intro=intro,steps=steps,notes=notes,table=table))

chapter('Willkommen bei Machinista',
 'Machinista macht aus einem Raspberry Pi eine eigenständige Sampling-Groovebox mit Controller-Bedienung. Stelle Kits aus eigenen WAV-Dateien zusammen, nimm Audio auf, zerlege Loops, spiele und bearbeite Patterns, arrangiere Scenes, richte das Audio-Routing ein und nutze kompatible LV2-Plug-ins.',
 notes=[('Eigene Sounds und Plug-ins','Baue deine Library mit eigenen WAV-Samples sowie kompatiblen LV2-Instrumenten und -Effekten auf.'),
 ('So nutzt du diese Anleitung','Beginne mit Einrichtung und erstem Start sowie deinem ersten Beat. Lies anschließend die Kapitel zu Sampling und Sequencing nach Bedarf. Die Displayübersicht am Ende enthält die Arbeitsbereiche, Parameterseiten und wichtigen Varianten. Im Index findest du Anzeigen anhand ihres englischen Namens.')])

chapter('Einrichtung und erster Start',
 'Verbinde den Controller über USB und schließe Kopfhörer oder Lautsprecher an ein unterstütztes Audiogerät an. Das vorbereitete Beta-Image startet die Anwendung ohne Desktop.',
 steps=['Schreibe das bereitgestellte Image für Pi 4 / Pi 5 als eigenes Image auf eine SD-Karte mit mindestens 8 GB. Überschreibe dabei weder den vorbereiteten Benutzernamen noch die SSH-Einstellungen im Imaging-Werkzeug.',
 'Setze die Karte ein, verbinde Controller und Audiogerät und schalte den Pi ein. Nach dem Verbinden zeigt der Controller etwa zwei Sekunden lang das Machinista-Logo; jede Eingabe beendet diese Anzeige. Plane für den ersten Start etwa zwei Minuten und einen möglichen Neustart ein.',
 either('Öffne die Einstellungen mit SHIFT + MAIN. F1 wählt AUDIO. Wähle INTERFACE mit dem Encoder und drücke ENTER.','Öffne die Einstellungen mit SHIFT + CONTROL. Displaytaste 1 wählt AUDIO. Wähle INTERFACE mit Encoder 1 und drücke ENTER.'),
 'Wähle AUTO für die automatische Auswahl eines USB-Audiointerfaces mit dem unterstützten HAT als Rückfalloption. Alternativ kannst du ein verfügbares Interface ausdrücklich auswählen. Prüfe vor dem Spielen SAMPLE RATE, BUFFER und MAIN OUTPUT.'],
 notes=[('Unterstützte Beta-Hardware','Das Image enthält die Startunterstützung für Pi 4 und Pi 5. Bei einer neuen Platine, einem USB-Interface oder HAT müssen Start und Audiofunktion dennoch geprüft werden. Vorhandene Firmware allein ersetzt diesen Test nicht.'),('Datenträger','Lass die Start-SD-Karte im eingeschalteten Pi. Übertrage Samples über USB-Datenträger oder die WebUI.')])

chapter('Deinen Controller kennenlernen',
 either('Die Mikro MK1 besitzt ein Display mit 128 x 64 Pixeln, drei Displaytasten und einen drückbaren Encoder. Die kontextabhängige Navigation erschließt weitere Funktionen ohne Computer.','Die MK2 besitzt zwei Displays mit je 256 x 64 Pixeln, acht Displaytasten und acht Parameter-Encoder. Der große Master-Encoder und die eigenen Group-Tasten ermöglichen zusätzliche direkte Eingaben.'),
 notes=[('Bedienelemente am Display',either('F1, F2 und F3 liegen über dem Display. Ihre Belegung steht am oberen Displayrand. Drehe den Encoder, um den fokussierten Wert zu ändern. Die beiden Pfeile unter dem Display wechseln je nach Anzeige zwischen Feldern oder Seiten.','Displaytasten 1-4 gehören zum linken, 5-8 zum rechten Display. Encoder 1-4 liegen unter dem linken, 5-8 unter dem rechten Display. Ein Wert über einem Encoder gehört zu diesem Encoder; leere Felder haben keine Parameterzuordnung.')),
 ('Pad-Nummern','Pad 1 liegt unten links. Jede Reihe zählt von links nach rechts: 1-4, darüber 5-8, 9-12 und ganz oben 13-16. Funktion und Beleuchtung der Pads richten sich nach dem aktiven Modus.'),
 ('Navigation',either('MAIN öffnet die dauerhafte Anzeige für Volume/Swing/Tempo. SHIFT + MAIN öffnet die Einstellungen. NAV wählt kontextabhängige Parameter. Halte VIEW, wähle SONG, MIXER, EVENTS oder LIVE FX mit dem Encoder und lass VIEW zum Öffnen los.','CONTROL führt zur Steuerungsansicht zurück. SHIFT + CONTROL öffnet die Einstellungen. Die Seitenpfeile unter SAMPLING wechseln Parameterseiten. NAVIGATE übernimmt die Funktionen, die auf der Mikro unter VIEW liegen.'))])

chapter('Die Anzeigen verstehen',
 'Die obere Leiste zeigt die Aktionen der Displaytasten. Darunter stehen der aktuelle Arbeitsbereich und sein Inhalt. Im unteren Teil erscheinen Parameternamen, Werte oder Transportinformationen. Hervorhebungen kennzeichnen die aktive Auswahl.',
 notes=[('Auswahl und Fokus','Ein invertiertes Feld oder eine hervorgehobene Listenzeile kennzeichnet die Auswahl. In der Wellenform bleibt der Wiedergabebereich unverändert; die Bereiche vor START und nach END werden invertiert. Sample- und Slice-Marken zeigen die bearbeitbaren Grenzen.'),
 ('Seiten und Felder',either('Seitenzahlen zeigen, wie viele Parameterseiten vorhanden sind. NAV zeigt das Ziel schon vor dem Loslassen an. Seitenpfeile sind nur aktiv, wenn eine Nachbarseite existiert. Feldpositionen dienen der Parameterauswahl und sind keine zusätzlichen Arbeitsbereiche.','Seitenzahlen beziehen sich auf die aktuelle Parameterbank. Die physischen Seitenpfeile wechseln die Bank; sie verschieben nicht automatisch die Transportposition. Dafür gibt es die beiden separaten STEP-Pfeile im Transportbereich.')),
 ('Vorübergehende Meldungen','Statusmeldungen, etwa zu einer Audioverbindung oder CHOKE ALL NOTES, verschwinden nach einer Sekunde. Sie ersetzen die zugrunde liegenden Parameterwerte nicht.')])

chapter('Navigation, Halten und Anheften',
 'Ein gehaltener Modus ist ein vorübergehender Arbeitsbereich. Durch Anheften bleibt ein unterstützter Modus nach dem Loslassen geöffnet. SHIFT-Kombinationen haben eigene Bedeutungen und sind kein allgemeiner Befehl zum Anheften.',
 steps=[either('Halte SCENE, PATTERN oder PAD MODE für den vorübergehenden Zugriff. Drücke dabei MAIN, um den Anheftstatus umzuschalten. Lass die Modustaste los. Einen angehefteten Modus kannst du mit seiner eigenen Taste schließen und erneut öffnen.','Halte eine padbezogene Modustaste für den vorübergehenden Zugriff. Wo PIN angezeigt wird, schaltet die zugehörige Displaytaste den Anheftstatus um. Lass die Modustaste los. Mit CONTROL kehrst du zur Steuerungsansicht zurück.'),
 either('Halte in der Steuerungsansicht NAV. F2 wählt CHNL, F3 wählt PLUG-IN. Wähle das Ziel mit dem Encoder und prüfe seinen Namen vor dem Loslassen von NAV. NAV + Pfeile wählt die Seite.','Drücke CONTROL für die Steuerungsansicht. Displaytasten 1-3 wählen MASTER/GROUP/SOUND; 5 wählt CHANNEL, 6 wählt PLUG-IN. Navigiere mit den Seitenpfeilen und den angezeigten Modulpfeilen.'),
 either('Halte in Sampling NAV, wähle RECORD, EDIT, SLICE oder ZONE mit dem Encoder und lass NAV los. SHIFT + SAMPLING öffnet Edit direkt.','In Sampling wählen Displaytasten 1-4 direkt RECORD, EDIT, SLICE und ZONE. SHIFT + SAMPLING öffnet Edit direkt.')],
 notes=[('Ansichtsnavigation',either('Halte VIEW und wähle mit dem Encoder eines der Icons SONG, MIXER, EVENTS oder LIVE FX. Beim Loslassen öffnet sich die Auswahl. Beim erneuten Aufrufen bleibt das aktive Icon markiert. Encoder drücken oder F3 OFF wählt es ab; danach VIEW loslassen, um zurückzukehren. F1 BACK wählt alle Icons ab; lass VIEW los, um zur letzten Sound-/Steuerungsansicht zurückzukehren. Im Events-Editor bleibt Zoom/Scroll über VIEW + F2 GRID erreichbar, in Sample Edit oder Slice über VIEW + F2 WAVE. SHIFT + VIEW öffnet Mixer weiterhin direkt.','Halte NAVIGATE und wähle IDEAS, SONG, MIXER, BROWSE oder EVENTS mit der beschrifteten Displaytaste. Das Ziel wird vor dem Loslassen von NAVIGATE hervorgehoben.'))])

chapter('Projects, Groups, Sounds und Patterns',
 'Ein Project enthält Groups mit ihren Sounds und Patterns sowie Scenes und den Song. Wenn du weißt, zu welcher Ebene eine Einstellung gehört, bearbeitest du gezielt den richtigen Teil deines Sets.',
 table=[('Objekt','Inhalt und Wirkung'),('Sound','Ein Pad-Slot: Sample-Zonen oder ein LV2-Instrument, Stimmenparameter, Plug-ins sowie Audio- und MIDI-Routing.'),('Group','Sechzehn Sound-Slots, eigene Patterns, Skalen-Einstellungen für das Spielen, Mixer und Effekte.'),('Pattern','Events für eine Group. Verschiedene Groups können gleichzeitig unterschiedliche Patterns spielen.'),('Scene','Eine Kombination von Verweisen auf Group-Patterns. Ein leerer Clip steuert kein Pattern bei.'),('Song','Eine geordnete Folge von Scene-Verweisen. Wiederverwendete Scenes verwenden dieselben Patterns.'),('Master','Die abschließende Projektmischung und Master-Bearbeitung statt des ausgewählten Sounds.')],
 notes=[('Die richtige Ebene wählen',either('In der Steuerungsansicht wählt F1 MASTER, F2 GROUP und F3 SOUND. Halte GROUP und wähle das zugehörige Pad zum Wechseln der Group.','In der Steuerungsansicht wählen Displaytasten 1, 2 und 3 MASTER, GROUP und SOUND. Die eigenen Tasten A-H wählen Groups in der aktuellen Bank.')),
 ('Auswählen löscht nichts','Das Auswählen eines Pads oder Wechseln eines Patterns beziehungsweise einer Group löscht deren Inhalt nicht. Ein fehlender oder stummgeschalteter Scene-Clip kann eine belegte Group dennoch unhörbar machen.')])

chapter('Dein erster Beat',
 'In diesem kurzen Einstieg baust du ein Drum-Kit, nimmst einen Loop auf und speicherst ihn. Beginne mit einem leeren Project und drei WAV-Dateien: Kick, Snare und Hi-Hat.',
 steps=['Wähle Group A und Sound 1. Drücke BROWSE. Öffne SD CARD und dann Library/Kicks oder deinen eigenen Ordner. Wähle eine WAV-Datei und verwende LOAD oder ENTER.',
 'Wähle ohne Verlassen von Browse Sound 2 über sein Pad und lade eine Snare. Wähle Sound 3 und lade eine Hi-Hat. Aktiviere PREHEAR, um die ausgewählte Datei vorzuhören.',
 either('Drücke MAIN, wähle TEMPO mit F3 und stelle ein angenehmes Tempo ein. Kehre zur Sound-Ansicht zurück.','Drücke TEMPO und drehe den großen Master-Encoder. Drücke TEMPO erneut, um die Anzeige zu verlassen.'),
 'Wähle ein leeres Pattern und lege vor der Aufnahme seine Länge fest. Aktiviere bei Bedarf das Metronom. Schalte REC ein, starte PLAY und spiele die Pads.',
 'Lass das Pattern loopen. Schalte REC aus, um die aufgenommenen Noten ohne weitere Ergänzungen zu hören. PLAY stoppt und startet die Wiedergabe; RESTART springt zum Anfang.',
 either('Öffne PROJECT über die SHIFT-Aktionen der Scene-Ansicht oder die System-Einstellungen. Wähle SAVE. Mit MANAGE benennst du ein neues Project oder erstellst eine separate Kopie.','Speichere mit SHIFT + ALL. Öffne PROJECT über die System-Einstellungen, um ein neues Project zu benennen oder SAVE AS zu verwenden.')],
 notes=[('Ergebnis prüfen','Kick, Snare und Hi-Hat sollten sich entsprechend der angezeigten Pattern-Länge wiederholen. Spielen bei ausgeschaltetem REC darf keine Sequencer-Noten erzeugen.')])

chapter('Ordner durchsuchen und Samples laden',
 'Browse zeigt deine Ordner und Sample-Dateien. Quellen enthalten Ordner und WAV-Dateien. Ordner erscheinen vor Dateien; die Liste ist nach Namen sortiert.',
 steps=[either('Drücke BROWSE. Drehe den Encoder, um in der Liste auf- oder abwärts zu gehen. Drücke ENTER oder die Displaytaste OPEN/LOAD. F1 BACK führt zum übergeordneten Ordner; an der Wurzel einer Quelle gelangst du zur Quellenliste.','Drücke BROWSE. Navigiere mit dem angezeigten Auswahl-Encoder durch die Liste. ENTER oder Displaytaste 8 LOAD öffnet die Auswahl. Displaytaste 1 BACK geht eine Ebene höher.'),
 'Wähle SD CARD oder eine angeschlossene USB-Quelle. Öffne die Ordner bis zur gewünschten WAV-Datei. Ein Ordner-Präfix unterscheidet Ordner von Samples.',
 either('F3 PREH schaltet das Vorhören um. Vorhören lädt die Datei noch nicht in den Sound.','Displaytaste 4 PREHEAR schaltet das Vorhören um. Vorhören lädt die Datei noch nicht in den Sound.'),
 'Wähle das Ziel-Pad, während Browse geöffnet bleibt, und lade das ausgewählte Sample. Wiederhole dies für weitere Pads, ohne zur Sound-Hauptansicht zurückzukehren.'],
 notes=[('USB-Datenträger und Projects','Eine USB-Quelle erscheint nach dem Einhängen und verschwindet beim Entfernen. Nutze COLLECT SAMPLES vor dem Übertragen eines Projects auf ein anderes System. Eine extern durchsuchte Datei liegt nicht automatisch im portablen Projektordner.'),
 ('Unterstützte Inhalte','Der Datei-Browser am Controller zeigt WAV-Dateien. Kompatible LV2-Instrumente und -Effekte lädst du über den Plug-in-Browser.')])

chapter('Wiedergabe, Position und Tempo',
 'Die Transportsteuerung ist unabhängig von der aktuellen Sound- oder Sample-Edit-Seite. Die Tempo-Anzeige bleibt bis zum Verlassen geöffnet und ist keine kurze Statusmeldung.',
 table=[('Bedienelement','Aktion'),('PLAY','Wiedergabe umschalten. REC ist ein separater Aufnahmezustand.'),('RESTART','Zum Anfang springen, auch während laufender Wiedergabe.'),('Transport STEP links / rechts','Position entsprechend Arrange Grid verschieben. Gehalten wiederholt sich die Bewegung alle 0,25 Sekunden.'),('SHIFT + Transport STEP','Position mit dem feineren Step Grid verschieben.'),('SHIFT + PLAY','Metronom umschalten.'),('SHIFT + REC','Aufnahme mit Vorzähler starten.'),('SHIFT + MUTE','Alle Stimmen, Vorhör-Samples und gehaltenen Generatoren aus jedem Arbeitsbereich stoppen.')],
 notes=[('Tempo',either('MAIN öffnet die Anzeige für Volume/Swing/Tempo; F3 wählt TEMPO. Drehe den Encoder für normale Änderungen. Halte SHIFT für Feineinstellungen mit zwei Nachkommastellen. SHIFT + ENTER ist Tap Tempo.','TEMPO öffnet die Master-Tempo-Anzeige. Drehe den großen Master-Encoder; halte SHIFT für Feineinstellungen. Tap Tempo liegt in dieser Beta auf SHIFT + ENTER. VOLUME und SWING öffnen ihre dauerhaften Anzeigen.')),
 ('Getrennte Pfeile',either('Die Pfeile unter dem Display navigieren durch Parameter. Die beiden unteren Transportpfeile verschieben die Wiedergabeposition.','Die Pfeile unter SAMPLING wechseln Seiten. Die unteren Transportpfeile verschieben die Wiedergabeposition. Verwechsle sie nicht mit den Pfeilen im Master-Bereich.'))])

chapter('Ein Pattern aufnehmen und ergänzen',
 'Eine Pattern-Aufnahme speichert Pad- und MIDI-Noten als Events. Audio-Sampling nimmt eine Wellenform am Eingang auf; dies sind getrennte Vorgänge. REC bestimmt, ob dein Spielen im Sequencer gespeichert wird.',
 steps=['Wähle die gewünschte Group und das Pattern. Drehe in PATTERN den Mikro-Encoder oder MK2-Encoder 1, um LENGTH einzustellen; mit SHIFT sind einzelne Steps möglich. Prüfe, dass die Scene einen aktiven Clip für diese Group enthält.',
 'Drücke GRID für Raster- und Quantisierungsoptionen; SHIFT + GRID öffnet RECORD SETTINGS. Stelle dort Aufnahmequantisierung und Vorzähler ein. Auch eine Sekunde Halten von REC öffnet die Vorbereitung für Länge und Raster; Loslassen führt zur Aufnahme zurück.',
 'Aktiviere REC, starte PLAY und spiele. Die angezeigte Pattern-Länge bestimmt den Loop. In weiteren Durchläufen ergänzt Overdub neue Events, sofern kein anderer Aufnahmemodus gewählt ist.',
 'Schalte REC zum Anhören aus. Lösche falsche Noten oder mache die Eingabe rückgängig, statt den Sound-Slot zu leeren. Speichere das fertige Ergebnis.'],
 notes=[('Quantisierung und Timing','Quantisierung verschiebt Noten zum gewählten Raster. Quantize 50% bewegt sie nur einen Teil des Weges. Swing und Nudge sind separate Timing-Werkzeuge und können die Wiedergabe bewusst vom geraden Raster abweichen lassen.'),
 ('Keine unbeabsichtigte Aufnahme','Prüfe zuerst REC, wenn beim Vorhören scheinbar neue Noten entstehen. Ein aktiver Aufnahmezustand kann beim Ansichtswechsel eingeschaltet bleiben. Prüfe den Events-Editor, statt eine Änderung am Sample zu vermuten.'),
 ('Pattern-Länge','Lange Patterns besitzen weitere Step-Bänke und Editor-Seiten. FOLLOW führt den sichtbaren Ausschnitt mit der Wiedergabe mit. Ausschalten ändert nur die Ansicht, nicht die Loop-Länge.')])

chapter('Den Step-Sequencer programmieren',
 'Die sechzehn Pads schalten Steps für den ausgewählten Sound. Leuchtende Steps enthalten Noten; der Playhead zeigt die laufende Position. Zusätzliche Bänke decken längere Patterns ab.',
 steps=[either('Öffne Step mit dem STEP MODE-Kurzbefehl SHIFT + NOTE REPEAT. Wähle zuvor den Sound oder die Keyboard-Note, die du programmieren möchtest.','Drücke STEP. Wähle zuvor den Sound oder die Keyboard-Note, die du programmieren möchtest.'),
 'Drücke Pads zum Setzen oder Löschen von Steps in der sichtbaren Bank. Bei einem geslicten oder tonal gespielten Sound wird nach Möglichkeit die zuletzt gespielte Keyboard-Note verwendet, statt immer den ersten Slice zu nehmen.',
 'Wechsle die Step-Bank mit den Navigationsfunktionen. Aktiviere FOLLOW, damit die Bank der aktuellen Wiedergabeposition automatisch sichtbar wird.',
 'Nutze FIX VEL für gleichmäßige Anschlagstärken beim Einfügen. DOUBLE verlängert das Pattern durch Duplizieren seines Inhalts.'],
 notes=[('Ansicht und Inhalt','FOLLOW fügt keine Noten hinzu und ändert die Pattern-Länge nicht. Fehlt der Playhead, prüfe, ob dieses Pattern der aktive Clip ist und die Wiedergabe läuft.'),
 ('Einzelne Events bearbeiten','Im Events- beziehungsweise Raster-Editor änderst du einzelne Noten, Wahrscheinlichkeit oder Länge. Step-Pads eignen sich für schnelles Ein- und Ausschalten, weniger für detaillierte Bearbeitung mehrerer Noten.')])

chapter('Einzelne Events auswählen und bearbeiten',
 'Der Events-Editor stellt Sound-Zeilen oder MIDI-Tonhöhen über der Zeit dar. Hier kannst du einzelne Noten auswählen, verschieben und gezielt ändern.',
 steps=[either('Öffne PATTERN und drücke ENTER oder nutze SHIFT + SELECT. F1 wechselt zwischen Sound-Zeilen und Tonhöhen.','Öffne PATTERN und verwende EDITOR oder nutze SHIFT + SELECT. Die Displayaktionen SELECT/EVENTS wechseln die Editor-Darstellung.'),
 either('Drehe den Encoder zum Verschieben des Zeitcursors. Halte SHIFT und drehe, um die Sound-Zeile oder Tonhöhe zu wechseln. F2 schaltet die Noten am Cursor in die Auswahl oder daraus heraus. SHIFT + F2 schaltet alle relevanten Noten um.','Nutze die beschrifteten Zeit- und Zeilenregler sowie die SELECT-Aktionen. ALL und NONE setzen oder löschen die Event-Auswahl; UP/DOWN verschieben den sichtbaren Zeilenfokus.'),
 either('Drücke F3, ENTER oder den Encoder zum Öffnen der Event-Bearbeitung. Die Pfeile wählen POSITION, NOTE, VELOCITY, PROBABILITY oder LENGTH. Drehe den Encoder zum Ändern.','Öffne EVENTS/Edit für die fokussierte Auswahl. Drehe den Encoder unter POSITION, NOTE, VELOCITY, PROBABILITY oder LENGTH zum Ändern.'),
 'Kehre mit der Abschluss- oder Zurück-Aktion ins Raster zurück. Mit ERASE und Bestätigung löschst du ausgewählte Events. Cursor-Navigation pausiert Follow, damit die Ansicht beim Bearbeiten stehen bleibt.'],
 notes=[('Umfang der Auswahl','Eine markierte Menge hat Vorrang vor dem Ziel am Cursor. In der Tonhöhenansicht bleibt der Sound gleich, während sich die Note ändert. Liegen mehrere Noten in einer Zelle, wechselt SHIFT + Navigationspfeile auf der Mikro die fokussierte Stimme.'),
 ('Zoom und Follow',either('Ansichtsnavigation ändert den sichtbaren Zeitbereich und seine Position. Sie ist kein Editor zur Notenauswahl. Aktiviere FOLLOW erneut, wenn die Anzeige wieder der Wiedergabe folgen soll. Auf der Mikro: SHIFT + F1 oder VIEW halten, F2 GRID und danach F3 FOLLOW.','Ansichtsnavigation ändert den sichtbaren Zeitbereich und seine Position. Sie ist kein Editor zur Notenauswahl. Aktiviere FOLLOW erneut, wenn die Anzeige wieder der Wiedergabe folgen soll. Drücke die Displaytaste FOLLOW (Taste 3); Markierung und LED zeigen den Zustand an.'))])

chapter('Keyboard, Skalen und 16 Anschlagstärken',
 'Im normalen Pad-Modus spielst du sechzehn verschiedene Sounds. Keyboard spielt unterschiedliche Tonhöhen eines fokussierten Sounds. Ein geslicter Sound nutzt zugeordnete Notenzonen, sodass verschiedene Keyboard-Pads verschiedene Slices ansprechen.',
 steps=['Wechsle mit SHIFT + PAD MODE zu Keyboard. Wähle ROOT und SCALE und spiele. Der Sound bleibt ausgewählt, während die Pads unterschiedliche MIDI-Noten erzeugen.',
 'Wähle bei Bedarf einen Akkordmodus. HARM bildet Akkorde aus der gewählten Skala oder chromatischen Intervallen; SET nutzt die Akkord-Voicings von Machinista.',
 'FIX VEL liefert eine konstante Anschlagstärke. 16 VEL verteilt stattdessen sechzehn Anschlagstärken des fokussierten Sounds auf die Pads.',
 'Kehre zu PAD zurück, wenn du sechzehn verschiedene Drum-Sounds statt Tonhöhen eines einzelnen Sounds brauchst.'],
 notes=[('Beleuchtung','Gehaltene Keyboard-Noten leuchten während des Spielens. Grund- und C-Noten werden im Layout hervorgehoben. Zugeordnete Slices und der ausgewählte beziehungsweise zuletzt gespielte Slice sind erkennbar; ein unbelegtes Pad wirkt dadurch nicht wie ein geladener Slice.'),
 ('Choke und Link','Pad-Einstellungen enthalten auch Choke- und Link-Gruppen samt Modi. Eine gemeinsame Choke-Gruppe eignet sich für gegenseitig ausschließende Klänge wie offene und geschlossene Hi-Hats. Link-Gruppen können zugehörige Sounds gemeinsam auslösen.'),
 ('Transponieren per Kurzbefehl','SHIFT + Pads 13/14 und 15/16 transponiert Sequencer-Events um Halbtöne und Oktaven. Dies ist kein allgemeiner Kurzbefehl zum Verschieben der Keyboard-Oktave.')])

chapter('Note Repeat und Arpeggiator',
 'Note Repeat erzeugt wiederholte Drum-Schläge bei gehaltenen Pads. Der Arpeggiator erzeugt Noten aus gehaltenen Tonhöhen oder Akkorden. Bei laufender Wiedergabe folgen Wiederholungen dem Transportraster.',
 steps=['Halte NOTE REPEAT und spiele die Pads. Wähle die Rate vor oder während des Spielens. Mit LOCK bleibt Repeat nach dem Loslassen der Modustaste verfügbar.',
 either('F1/F2 wählen die angezeigten Repeat-Presets. SHIFT + F3 wechselt die Preset-Bank. Wähle RATE oder DIVISION mit den Pfeilen und drehe den Encoder für weitere Werte.','Displaytasten 5-8 wählen 1/8, 1/16, 1/32 oder 1/64. DIVISION wechselt zwischen NORMAL, TRIPLET und DOTTED. LOCK und HOLD haben eigene beschriftete Aktionen.'),
 'Nutze für melodische Wiederholungen Keyboard und die Arpeggiator-Parameter. Wähle Richtung, Oktavumfang, Gate, Dynamik und Sequenz nach Bedarf.',
 'Aktiviere REC, wenn das erzeugte Spiel im Pattern gespeichert werden soll. SHIFT + MUTE beendet alle gehaltenen und wiederholten Noten.'],
 notes=[('Am Raster ausrichten','Bei laufender Wiedergabe wartet ein Pad-Anschlag zwischen den Unterteilungen auf die nächste Repeat-Grenze. Er startet den Repeat-Takt nicht neu. Bei gestopptem Transport nutzt Repeat sein eigenes Zeitintervall.'),
 ('HOLD und LOCK','LOCK hält den Repeat-Modus aktiv. HOLD hält die gespielten Arpeggiator-Noten. Schalte HOLD aus, wenn Noten nach dem Loslassen nicht weiterlaufen sollen. Die beiden Funktionen haben unterschiedliche Aufgaben.')])

chapter('Sampling: Eingang wählen und aufnehmen',
 'Sampling nimmt eine Wellenform in den ausgewählten Sound auf. Du kannst das Ziel-Pad wählen, während die Record-Seite geöffnet bleibt. Die Stereo-Pegelanzeigen zeigen Eingangssignal und Detect-Schwelle.',
 steps=['Drücke SAMPLING und wähle RECORD. Wähle EXT MONO, EXT STEREO oder INTERNAL. Wähle einen verfügbaren Eingangskanal beziehungsweise ein Kanalpaar oder die interne Quelle zum Resampling.',
 'Spiele die Quelle ab und beobachte die Pegelanzeigen. Passe die Verstärkung an der Quelle und bei unterstütztem HAT auch Input Gain an. Lass Pegelreserve: Eine übersteuerte Aufnahme wird durch Normalisieren nicht repariert.',
 'DETECT bereitet eine Aufnahme ab einem Schwellwert vor; SYNC dient der Aufnahme in Bezug auf Transport und Raster. Stelle Schwelle beziehungsweise Länge und Synchronisation vor dem Scharfschalten ein.',
 'Nutze die angezeigte START/REC-Aktion. In DETECT wartet die Aufnahme auf das Überschreiten der Schwelle. Die manuelle Auslöseaktion kann sie im scharfgeschalteten Zustand starten. STOP beendet die Aufnahme, CANCEL verwirft sie.',
 'Spiele das Ziel-Pad zum Prüfen. Aufnahmen erhalten einfache nummerierte Sample-Namen. Mit den verfügbaren History-Aktionen kannst du zu einer früheren Aufnahme zurückkehren.'],
 notes=[('Abtastrate am Eingang','Nutze eine vom angeschlossenen Interface unterstützte Sample Rate. Eine falsche Rate kann wie ein Bitcrusher klingen. Prüfe nach einem Gerätewechsel AUDIO > SAMPLE RATE erneut.'),
 ('Audio und Noten getrennt aufnehmen','Die Record-Seite nimmt Audio auf. REC im Transportbereich steuert die Sequencer-Events. Prüfe vor einer neuen Aufnahme den richtigen Zustand.')])

chapter('Sample kürzen, auswählen und bearbeiten',
 'Sample Edit trennt den Wiedergabebereich von der Bearbeitungsauswahl. START und END begrenzen den abgespielten Bereich. Eine Auswahl bestimmt den Abschnitt für einen Bearbeitungsbefehl.',
 steps=['Öffne Edit direkt mit SHIFT + SAMPLING. Wähle den richtigen Sound und das richtige Sample, bevor du eine Grenze änderst.',
 either('Wähle START oder END mit den Pfeilen und drehe den Encoder. Halte NAV zum Wählen der Seite für Wiedergabebereich oder Auswahl. Prüfe das angezeigte Ziel vor dem Loslassen.','Encoder 1 und 2 steuern START und END. Die Seitenpfeile wechseln zwischen Wiedergabebereich und Auswahl. Encoder 3 und 4 bleiben ZOOM und SCROLL.'),
 'Wähle die Bearbeitungsfunktion mit den beschrifteten Vorher-/Weiter-Aktionen. NORMALIZE hebt den Sample-Pegel an; andere Funktionen wirken entsprechend ihren Einstellungen auf den ausgewählten Audiobereich. Prüfe den Bereich vor APPLY.',
 'Stelle für STRETCH Tempo und Länge ein und höre das Ergebnis vor APPLY an. CANCEL kehrt zurück, ohne die Vorschau zu übernehmen.'],
 notes=[('Normalisieren und Slices','Normalisiere das Quell-Sample, wenn alle Slices die Änderung übernehmen sollen. Ein Slice ist ein Bereich dieser Quelle und kein eigenes Normalisierungsziel. Zone Gain ist ein separater Wiedergabeparameter.'),
 ('Originaldateien','Bearbeitung erzeugt abgeleitete Audiodateien, statt die Quelle unbemerkt zu überschreiben. Nutze trotzdem SAVE AS und COLLECT SAMPLES, bevor du ein wichtiges Project grundlegend änderst.'),
 ('Löschen','Das Leeren eines Sound-Slots entfernt dessen Zuordnung. Es löscht nicht automatisch die Aufnahme oder Datei. Nutze zum Löschen einer Datei die ausdrückliche Sample-Delete-Ansicht mit Bestätigung.')])

chapter('Wellenform zoomen und verschieben',
 'Zoom ändert die sichtbare Audiomenge, nicht die Wiedergabegeschwindigkeit oder Sample-Länge. Scroll verschiebt den sichtbaren Ausschnitt. Der bearbeitete Bereich und seine Marken bleiben Teil der Wellenform.',
 steps=[either('Halte in Sample Edit oder Slice VIEW und drücke F2 WAVE. Wähle ZOOM mit dem linken oder SCROLL mit dem rechten Pfeil; drehe den Encoder.','Drehe in Edit, Slice oder Zone Encoder 3 für ZOOM und Encoder 4 für SCROLL. Diese Regler liegen auf derselben Seite wie die Wellenform.'),
 either('Du kannst auch Pads verwenden: Pad 2 zoomt heraus, Pad 6 hinein; Pads 1 und 3 scrollen nach links und rechts. Halte VIEW und drücke MAIN zum Anheften, wenn du VIEW anschließend loslassen möchtest.','Zoome an die zu prüfende Schnittstelle und scrolle bei Bedarf. Beim Zoomen dient die relevante Bereichsgrenze als Anker, sofern sie sichtbar ist.'),
 'Kehre zur Grenzsteuerung zurück, um START oder END zu verschieben. Nach dem Hineinzoomen lassen sich kleine Änderungen leichter beurteilen.',
 'Spiele in Slice Edit den Slice erneut, um seine Grenze ohne Verlust der gewählten Zoomstufe zu fokussieren.'],
 notes=[('Slice-Fokus','In der Übersicht steht der ausgewählte Slice mit benachbartem Audio mittig. Bei starkem Zoom wird stattdessen die gewählte START- oder END-Schnittstelle zentriert. Wähle in Slice Edit mit linker/rechter Seitennavigation START oder END. Erneutes Spielen behält diese Wahl bei.'),
 ('Ansicht beibehalten','Erneutes Spielen eines Slices behält den Zoom bei. Ein anderes Sample kann den Ausschnitt zurücksetzen. Zoom verändert nur die Ansicht, nicht die Slice-Positionen.')])

chapter('Automatisch oder nach Raster slicen',
 'Slice setzt Schnittpunkte in ein Quell-Sample. Höre die Schnitte an und verbessere sie, bevor du Slices Sounds oder Keyboard-Zonen zuweist.',
 table=[('Modus','Einsatz und wichtigste Einstellung'),('SPLIT','Gleich große Abschnitte. Wähle Unterteilung beziehungsweise Anzahl.'),('GRID','Musikalische Unterteilung anhand von Quelltempo und gewähltem Raster.'),('DETECT','Schnitte anhand von Transienten. Stelle die Empfindlichkeit ein und prüfe die Grenzen.'),('MANUAL','Schnitte während der Wiedergabe mit den Pads setzen; siehe nächstes Kapitel.')],
 steps=['Öffne SAMPLING > SLICE. Wähle MODE und stelle seine Parameter ein. Wellenform und Slice-Anzahl werden entsprechend aktualisiert.',
 'Wähle bei BPM AUTO, wenn das erkannte Tempo passt, oder MANUAL, wenn du das Quelltempo kennst. ADJUST mit halbem/doppeltem Tempo korrigiert eine Erkennung im falschen musikalischen Vielfachen.',
 'Höre die Slices über die Pads an. Öffne EDIT zur Korrektur einer Schnittstelle vor dem Anwenden. Mit APPL.TO wählst du eine andere Group oder einen bestimmten Sound als Ziel.'],
 notes=[('Ein umkehrbarer Schnittplan','Während der Bearbeitung sind Schnitte Metadaten für Bereiche. APPLY macht daraus spielbare Zuordnungen. Änderungen an automatischen Aufteilungen können den Plan neu erzeugen. Sichere wichtige Arbeit vor einem Wechsel der Schnittstrategie.'),
 ('Tempo der Quelle','Slice-BPM beschreibt den Quell-Loop und die Interpretation des erzeugten Patterns. Es bedeutet nicht, dass die Quelle mit dem Project-Tempo aufgenommen wurde.')])

chapter('Manuell choppen und Slices bearbeiten',
 'Beim manuellen Choppen setzt du Schnitte während des Hörens. Anschließend kannst du in Slice Edit die Grenzen korrigieren, ohne den gesamten Schnittplan neu aufzubauen.',
 steps=['Wähle MANUAL bei ausgeschaltetem EDIT. Drücke Pad 1 zum Starten der Quelle. Schlage das nächste unbenutzte Pad an der gewünschten Schnittstelle an. Fahre mit den folgenden Pads fort.',
 'Drücke ein bereits belegtes Slice-Pad zum Abspielen ab seiner Startposition. Auch nach dem Ende des Samples kann ein vorhandenes Slice-Pad die Wiedergabe erneut starten. Du musst die Slices nicht neu erzeugen.',
 'Aktiviere EDIT und spiele den zu bearbeitenden Slice. Zunächst ist START fokussiert. Wähle START oder END mit der Links-/Rechts-Navigation und verschiebe dann die entsprechende Grenze.',
 'Prüfe den Schnitt mit Zoom und Scroll. Erneutes Spielen behält Zoom und START/END-Fokus bei. SPLIT/ADD ergänzt eine Grenze, REMOVE entfernt den gewählten Schnitt; DEL ALL leert den gesamten Schnittplan.'],
 notes=[('Vorhandene Arbeit erhalten','Das Vorhören eines belegten Pads fügt keinen Slice hinzu. Das nächste unbenutzte Pad erzeugt nur beim Live-Choppen einen Schnitt. Lass EDIT beim Verfeinern vorhandener Schnitte aktiv und vermeide ein versehentliches Neuerzeugen durch einen automatischen Modus.'),
 ('Umgebung der Schnittstelle','In der Übersicht erscheint der Slice mittig mit seinen Nachbarn. Passt das Sample nicht mehr vollständig ins Display, wird die gewählte Schnittstelle sichtbar gemacht. So hörst und siehst du dieselbe Grenze.')])

chapter('Slices einem Sound oder einer Group zuweisen',
 'APPL.TO wählt das Ziel vor APPLY. Du kannst Slices innerhalb eines Sounds verteilen oder auf eine Group anwenden. Die Einzelslice-Zuweisung überträgt den ausgewählten Bereich auf einen Sound-Slot.',
 steps=['Höre den gewünschten Slice an, wähle ihn und öffne APPL.TO. Wähle die Ziel-Group und den ersten Sound beziehungsweise das angezeigte Ziel für alle Sounds.',
 either('Nutze Zielfelder und Encoder. GROUP mit einem Pad kann die Group wählen; Bank-Aktionen erschließen weitere Group-Bänke. Prüfe vor dem Anwenden das angezeigte Ziel.','Nutze die GROUP- und SOUND-Encoder auf der Zielseite oder eine eigene Group-Taste. BANK-/BANK+ erschließen weitere Bänke. Prüfe die angezeigte Group und den Sound.'),
 'Wähle für einen einzelnen Slice die Einzeloption, also SINGLE / EDIT auf der Apply-To-Seite, dann den Sound-Slot und APPLY. Dies ist eine direkte Zuweisung; ein vorheriger WAV-Export ist nicht nötig.',
 'Wähle für alle Slices das Ziel und die Option zur Pattern-Erstellung, dann APPLY. Kehre bei Keyboard-Zuordnung zu Keyboard zurück und spiele die zugeordneten Slice-Noten.'],
 notes=[('MONO steuert Stimmen','MONO beim Anwenden auf eine Group setzt Polyphony = 1 und Choke Group = 1 für die zugewiesenen Sounds. Es wandelt eine Stereo-WAV nicht in eine Monodatei um.'),
 ('Vorhandener Zielinhalt','Das Anwenden auf belegte Sounds kann deren Zuordnungen ersetzen. Nutze eine andere Group oder sichere eine Project-Kopie, wenn das vorhandene Kit erhalten bleiben soll.'),
 ('Weiterbearbeitung','ZONE zeigt die zugewiesenen Noten- und Anschlagstärkebereiche sowie die Wiedergabeparameter je Zone. Kehre zum Bearbeiten des Schnittplans zu SLICE > EDIT zurück, statt versehentlich einen anderen Sound zu verändern.')])

chapter('Zones und mehrschichtige Sample-Zuordnung',
 'Eine Zone verbindet einen Sample-Bereich mit Noten- und Anschlagstärkebereichen. Nutze Zones für geslicte Keyboard-Belegungen, Multisamples und Velocity-Layer. Ein Sound kann mehrere Zones enthalten.',
 table=[('Zone-Seite','Parameter'),('PLAY','START und END der Zone.'),('LOOP','Loop ein/aus, Loop-Anfang und -Ende sowie Crossfade.'),('TUNE','Stimmung, Verstärkung, Panorama und Grundnote.'),('ENVELOPE','Attack und Decay der Zone.'),('MAP','Tiefste/höchste Note und niedrigste/höchste Anschlagstärke.')],
 steps=['Öffne SAMPLING > ZONE und wähle die zu prüfende Zone. PREV/NEXT wechselt die Zone; ADD legt eine weitere Zuordnung an und REMOVE entfernt die gewählte.',
 either('Halte NAV und wähle die Parameterseite mit den Seitenpfeilen. Die normalen Pfeile wählen Felder; drehe anschließend den Encoder.','Die Seitenpfeile wechseln Parameterbänke. Encoder 1/2 ändern die angezeigten Zone-Felder; 3/4 bleiben ZOOM/SCROLL.'),
 'Spiele Noten über die Noten- und Anschlagstärkebereiche und prüfe die ausgelösten Samples. Prüfe die Grundnote, wenn ein zugewiesener Slice oder ein Multisample falsch gestimmt klingt.'],
 notes=[('Gain und Normalisieren','Zone Gain multipliziert den Wiedergabepegel. Es schreibt die Quelldatei weder neu noch normalisiert es sie. Normalisiere die Quelle in Sample Edit, bevor du einen vollständig geslicten Sound beurteilst.'),
 ('Überlappende Zuordnungen','Überlappende Noten- und Anschlagstärkebereiche können Audio schichten. Prüfe bei unerwarteter Lautstärke die überlappenden Zones, statt nur den Master abzusenken.')])

chapter('Sampler: Stimmen, Hüllkurven und Filter',
 'Sampler-Parameter gehören zu einem Sound. Spiele die Pads beim Einstellen, um die Wirkung zu hören. Ein LV2-Instrument im ersten Instrument-Slot ersetzt für diesen Sound die eingebaute Sample-Quelle.',
 table=[('Seite','Zweck'),('VOICE','Polyphonie, Legato-Glide und Pitch-Bend-Bereich.'),('PITCH/ENV','Stimmung, Rückwärtswiedergabe und Lautstärkehüllkurve ONESHOT/AHD/ADSR.'),('FX/FILTER','Kompression, Drive, Sample-Rate-/Bit-Reduktion und Filter OFF/LP2/BP2/HP2/EQ.'),('MOD ENV','Attack-/Decay-Modulation von Tonhöhe, Cutoff und Panorama.'),('LFO','Form, freie/synchronisierte Rate, Phase und Modulationstiefe für Tonhöhe/Filter/Panorama.'),('VEL/MOD','Einfluss von Anschlagstärke und Modulationsrad, einschließlich Start und Cutoff.')],
 steps=[either('Wähle SOUND mit F3. Halte NAV, wähle PLUG-IN mit F3, dann SAMPLER und lass NAV los. NAV mit Pfeilen wechselt Seiten; Pfeile allein wählen Felder.','Wähle SOUND mit Displaytaste 3, PLUG-IN mit Taste 6 und den Sampler-Slot. Die Seitenpfeile wechseln Parameterbänke; die Encoder unter den Feldern ändern Werte.'),
 'Wähle ADSR für einen gehaltenen, geformten Sound. Nutze ONESHOT oder AHD für Drum-Schläge. Nicht verwendete Parameter des Hüllkurventyps werden ausgeblendet.',
 'Wähle LP2, BP2, HP2 oder EQ und stelle Cutoff und Resonanz beziehungsweise EQ-Gain und -Breite ein. Spiele dasselbe Pad wiederholt zum Vergleichen.'],
 notes=[('Zwei Arten von Effekten','Der Sampler-Filter ist auf Sound-Ebene eingebaut. Ein LV2-Filter ist ein separates Plug-in der Kette und kann auch eine Group oder den Master bearbeiten. Absichtliche SR/BITS-Reduktion erzeugt einen Bitcrusher-Effekt; sie ist keine Einstellung der Aufnahmerate.')])

chapter('LV2-Plug-ins hinzufügen, ersetzen und entfernen',
 'Jeder Sound, jede Group und der Master besitzen eine eigene Plug-in-Kette. Kompatible LV2-Effekte bearbeiten Audio; ein Instrument gehört an die erste Instrumentposition der Sound-Kette.',
 steps=['Wähle die gewünschte Ebene MASTER, GROUP oder SOUND. Öffne die PLUG-IN-Navigation und wähle einen vorhandenen Slot oder ADD PLUGIN.',
 'SHIFT + BROWSE öffnet den Plug-in-Browser auch bei bereits belegtem Slot. Wähle ein kompatibles Instrument oder einen Effekt und lade es an die gewählte Position.',
 'Drehe die angezeigten Regler und spiele Pads zum Anhören. Weitere Parameter liegen auf zusätzlichen Seiten. BYPASS vergleicht bearbeitetes und unbearbeitetes Audio.',
 either('Wähle den Slot mit NAV + Pfeilen. Nutze in der Plug-in-Navigation/Slot-Bearbeitung REMOVE oder SHIFT + BROWSE mit dem Entfernen-Eintrag. Bestätige REMOVE PLUGIN?.','Halte SHIFT in der Plug-in-Ansicht für Kettenaktionen. Displaytaste 6 öffnet BROWSE, 7 ist REMOVE; bestätige das Entfernen. COPY/PASTE/MOVE stehen links.')],
 notes=[('Kette verwalten','COPY/PASTE dupliziert den gewählten Plug-in-Zustand; MOVE ändert die Reihenfolge. Ein Instrument muss an erster Stelle bleiben. Entfernen und Verschieben aktualisiert zugehörige Parameterverweise. Sichere vor dem Umbau komplexer automatisierter Ketten eine Kopie.'),
 ('Echtzeit-Leistung','Plug-ins unterscheiden sich stark bei Rechenbedarf und gemeldeter Latenz. Teste jede Kette mit der gewünschten Puffergröße. Tape- oder Look-ahead-Effekte können hörbar verzögern, obwohl Pads und Displays sofort reagieren.')])

chapter('Channel-Routing und Mixer',
 'Channel-Eigenschaften legen fest, wo ein Sound oder eine Group Audio empfängt und ausgibt. Der Mixer zeigt Pegel, Panorama und Routing gemeinsam. Direkte Hardwareziele hängen vom ausgewählten Interface ab.',
 steps=['Wähle SOUND, GROUP oder MASTER. Öffne CHANNEL und wähle OUTPUT. AUDIO steuert das Hauptziel, AUX1/AUX2 die Sends und MIDI auf Sound-Ebene die externe Notenausgabe.',
 'Wähle für getrennte Interface-Ausgänge den angebotenen Ausgangsport oder das Kanalpaar. Route den Sound oder die Group und prüfe das Ziel auch am Interface.',
 either('Öffne den Mixer mit SHIFT + VIEW. F1/F2/F3 wählen Master/Group/Sound. Navigiere zum Kanal und wähle Pegel-, Panorama- oder Ausgangsfeld.','Halte NAVIGATE und wähle MIXER. Displaytasten 1-3 wählen die Ebene; 5-7 wählen LEVEL, PAN oder ROUTE. Die vertikalen Kanalzüge sind den Parameter-Encodern zugeordnet.'),
 'Stelle Main Output und einen getrennten Cue Output in Audio ein. Cue Level regelt das Vorhören. Main und Cue dürfen nicht dieselben Hardwarekanäle überlappend nutzen.'],
 notes=[('Eingang und Rückkopplung','INPUT wählt externe/interne Kanalquellen und Monitoring-Eigenschaften. Route ein Ziel nicht auf seinen eigenen Eingang zurück; ungültige Routing-Schleifen werden abgewiesen.'),
 ('Musikalischer Pegel und Interface-Pegel','Master Level regelt die Project-Mischung. Die Kopfhörer-/Lautsprecherregler des ULTRA HAT ändern den Codec-Ausgangspegel; Input Gain ändert die Aufnahmeverstärkung. Diese Hardwareregler sind keine universellen Gain-Regler für USB-Interfaces.')])

chapter('Mute, Solo, Auswahl und Duplizieren',
 'Der Fokus bestimmt, was du bearbeitest. Mehrfachauswahl bestimmt eine Zielmenge. Mute/Solo bestimmt, was hörbar ist. Diese Zustände sind unabhängig und über ihre Ansichten und LEDs erkennbar.',
 steps=['Halte MUTE oder SOLO und drücke das gewünschte Sound-Pad zum Umschalten. Aktionen auf Group-Ebene betreffen die gewählte Group. Auf der MK2 steuern die eigenen Group-Tasten in diesen Ansichten Group-Mute/-Solo.',
 'Mute beendet den laufenden Sample-Klang sofort, statt sein Ausklingen abzuwarten. Prüfe bei einer vollständig stummen Group zusätzlich Group-Mute und Scene-Clip-Aktivierung.',
 'SELECT dient zur lautlosen Fokussierung und Mehrfachauswahl. Nutze ALL/NONE, wo angeboten. Auf der MK2 wechselt ALL zwischen allen sechzehn Sounds und dem fokussierten Sound; im Event-Raster schaltet es die Event-Auswahl um.',
 'Nutze DUPLICATE mit der passenden Quell- und Zielauswahl. Prüfe vor dem Bestätigen, ob du einen Sound, ein Pattern oder eine Scene duplizierst.'],
 notes=[('Alle Stimmen stoppen','SHIFT + MUTE stoppt von jeder Anzeige aus aktive Sample-Stimmen, Plug-in-/MIDI-Noten, Vorhör-Samples und gehaltene Repeat-/Arp-Noten. Der Arbeitsbereich bleibt geöffnet.'),
 ('CLEAR setzt keinen Sound zurück','SHIFT + CLEAR entfernt die betroffenen Pattern-Noten. Halte zum Leeren eines Sound-Slots SHIFT + ERASE und drücke dessen Pad. Das entfernt Sample-/Plug-in-Zuordnungen und ist ein anderer Vorgang als Mute.')])

chapter('Scenes und Song-Arrangement',
 'Eine Scene ruft je Group einen Pattern-Verweis auf. Song ist eine geordnete Scene-Liste. Eine wiederholte Scene nutzt dieselben Verweise. Änderungen an einem gemeinsamen Pattern wirken an allen Stellen, die es verwenden.',
 steps=['Erstelle Patterns in den benötigten Groups. Wähle eine Scene und dann für jede Group das zugehörige Pattern. Lass einen Clip leer, wenn die Group nicht spielen soll.',
 'Wähle eine weitere Scene und erstelle eine Variation. Bei laufender Wiedergabe bestimmt Perform Grid, wann ein angeforderter Scene-Wechsel wirksam wird.',
 either('Öffne SCENE, halte SHIFT und nutze SONG. PROJECT liegt als benachbarte Zusatzaktion daneben.','Halte NAVIGATE und wähle SONG. Lass NAVIGATE los, sobald das Song-Ziel hervorgehoben ist.'),
 'Wähle vor dem Öffnen von Song eine Scene. INSERT (F1 / Displaytaste 1) fügt sie an der ausgewählten Song-Position ein. Der Auswahl-Encoder bewegt die Markierung. PLAY (F2 / Taste 2) schaltet Song-Wiedergabe um; DELETE (F3 / Taste 3) entfernt einen Eintrag nach Bestätigung.'],
 notes=[('Scene-Länge','Automatische Scene-Länge folgt den aktiven Patterns; eine ausdrücklich gewählte Länge kann dies überschreiben. Patterns dürfen unterschiedlich lang sein und innerhalb einer längeren Scene loopen.'),
 ('Eine unabhängige Variation','Eine duplizierte Scene besitzt nicht zwingend unabhängige Patterns. Nutze den Unique-/Kopierablauf, wenn die Variation eigenständig bearbeitbare Patterns braucht.'),
 ('Master-Automation','Pattern-Automation gehört zum Group-Pattern. Song-Master-Automation wird getrennt von diesen Pattern-Spuren verwaltet.')])

chapter('Automation, Macros und MIDI Learn',
 'Automation speichert Parameterbewegungen im musikalischen Zeitverlauf. Macros bündeln nützliche Regler. MIDI Learn verbindet einen externen Controller mit dem zuletzt berührten Parameter.',
 steps=[either('Spiele das Pattern und nutze die in der Parameteransicht vorgesehene AUTO-Schreibgeste. Halte auf der Mikro SHIFT beim Ändern unterstützter Parameter, um deren Bewegung aufzuzeichnen.','Spiele das Pattern, halte AUTO WR. und drehe einen Parameter-Encoder zum Aufzeichnen. SHIFT + AUTO WR. schaltet einen eingerasteten Schreibzustand um; AUTO WR. beendet ihn wieder.'),
 'Beende den Schreibmodus und höre den nächsten Loop. Die Parameterwiedergabe wirkt vorübergehend: Der gespeicherte Grundwert bleibt vom automatisierten Wert getrennt.',
 'Wähle in Macro Assign einen Zielparameter und mache ihn auf der Macro-Seite zugänglich. Prüfe vor dem Zuweisen die Ebene Sound/Group/Master.',
 'Berühre für MIDI Learn den Zielparameter, öffne MIDI LEARN und sende die externe Steuernachricht. Teste die Zuordnung zuerst ohne aktives Automationsschreiben.'],
 notes=[('Die richtige Spur löschen','SHIFT + Pad 10 (CLR AUTO) löscht Automation entsprechend dem aktuellen Ziel und der Auswahl. Sample und Pattern-Noten bleiben erhalten. Speichere vor dem Löschen eventuell noch benötigter Automation.'),
 ('Ebene und Speicherung','Sampler-, Routing-, Wert- und kompatible Plug-in-Parameter besitzen Automationsziele. MIDI-Zuordnungen und Plug-in-Verweise werden im Project gespeichert; Verschieben oder Entfernen eines Plug-ins verändert die entsprechenden Ziele.')])

chapter('MIDI-Ports, Clock und Bluetooth',
 'Unter Settings > MIDI findest du Eingang, Ausgang, Kanal, Clock, Offset und Learn. Verfügbare USB-MIDI- und DIN-Anschlüsse des Controllers erscheinen, sobald die Geräte verbunden sind.',
 steps=['Wähle MIDI INPUT für eingehende Noten und Regler sowie MIDI OUTPUT für das externe Ziel. Stelle den Ausgangskanal des Sounds passend zum empfangenden Instrument ein.',
 'Stelle CLOCK auf OFF, IN oder OUT. IN folgt einer externen Clock; OUT sendet Clock. Passe CLOCK OFFSET nach einem Test mit Metronom an das empfangende Setup an.',
 'Öffne BLUETOOTH MIDI und aktiviere es mit ON/OFF. Auf der Mikro sucht F2 nach Geräten, SHIFT + F2 öffnet das Pairing und ENTER schaltet die Verbindung zum gewählten Gerät um. Nutze auf der MK2 die beschrifteten Displaytasten PAIR, SCAN, CONNECT und DISCONN.',
 'Verbinde ein iPad über eine Bluetooth-MIDI-fähige App. Versetze ein Keyboard in seinen Bluetooth-MIDI-Pairing-Modus und suche/verbinde es anschließend über Machinista.'],
 notes=[('Bluetooth MIDI ist kein Bluetooth-Audio','Die Verbindung überträgt unterstützte Noten-, Steuer- und Clock-Nachrichten. Sie ist keine Audioverbindung zum iPad und macht den USB-C-Stromanschluss des Pi nicht zu einem universellen Audio-/MIDI-Geräteanschluss.'),
 ('Verfügbarkeit prüfen','Ein sichtbarer Port ersetzt keinen vollständigen Kabel-/App-Test. Prüfe bei fehlenden Noten Portauswahl, Kanal, Pairing und empfangende App, statt dich allein auf den Gerätenamen zu verlassen.')])

chapter('Project-Namen, Presets und portable Speicherung',
 'PROJECT bietet SAVE, LOAD und MANAGE. Manage erstellt benannte Projects, benennt gespeicherte Einträge um oder löscht sie, sammelt Samples und speichert/lädt Sound- oder Group-Presets.',
 steps=['Öffne PROJECT über die System-Einstellungen oder die SHIFT-Aktionen der Scene-Ansicht. Wähle MANAGE und dann NEW PROJECT. Der Name beginnt leer.',
 'Wähle mit dem Namens-Encoder ein Zeichen und bewege den Cursor mit den Navigationspfeilen. RANDOM schlägt einen Namen vor. SHIFT macht aus CANCEL die Aktion CLEAR; OK übernimmt einen gültigen Namen.',
 'RENAME ändert den Anzeigenamen, SAVE AS erstellt einen unabhängigen gespeicherten Eintrag. DELETE verlangt Bestätigung. Nach dem Löschen eines gespeicherten Eintrags bleibt die aktuelle Arbeitskopie als UNTITLED verfügbar.',
 'SAVE SOUND/SAVE GROUP erzeugt wiederverwendbare Presets. COLLECT SAMPLES kopiert referenzierte Samples vor einer Übertragung in einen portablen Project-Speicherort.'],
 notes=[('Mehr sichern als die Project-JSON','Bewahre das Project zusammen mit gesammeltem Audio und Plug-in-Zuständen auf. Sichere das Original, bevor du Samples ersetzt oder eine Kette umbaust.'),
 ('Schnell speichern',either('Nutze PROJECT > SAVE. Der Project-Arbeitsbereich ist auch über die System-Einstellungen erreichbar.','SHIFT + ALL speichert das aktuelle Project. ALL allein steuert die Auswahl, nicht das Speichern.')),
 ('RAM und Datenträger','Samples werden für die Wiedergabe in den RAM geladen; der Sampler streamt nicht vom Datenträger. SAMPLE RAM zeigt die Nutzung und kann bei gestopptem Transport ungenutzten Sample-Speicher freigeben.')])

chapter('Fehlende Dateien zuordnen und exportieren',
 'Ein Project kann auf nicht verfügbare externe Audiodateien verweisen. Relink findet Ersatzdateien. Export erzeugt Audio- oder MIDI-Dateien für andere Anwendungen, ohne die physischen Ausgänge in Echtzeit aufnehmen zu müssen.',
 steps=['Öffne bei fehlenden Samples MANAGE > RELINK SAMPLES. Prüfe Eintrag und Suchergebnisse oder navigiere zur richtigen Ersatzdatei. Wähle keine nur ähnlich benannte, inhaltlich andere Datei.',
 'Wähle für Audio MANAGE > EXPORT AUDIO. Stelle RANGE auf PATTERN, SCENE oder SONG und SOURCE auf MIX, SOUND, GROUP oder eine Stem-Auswahl.',
 'Stelle Sample Rate, Format/Bittiefe, Ausklanglänge, Normalisierung, Loop-Optimierung und Ziel ein. Prüfe freien Platz auf SD/USB und starte das Rendern.',
 'Wähle für Noten EXPORT MIDI. Prüfe nach dem Export auf der Abschlussseite Ziel und Dateinamen. Teste die Datei in der empfangenden Anwendung.'],
 notes=[('Den richtigen Bereich wählen','PATTERN exportiert das ausgewählte Group-Pattern. SCENE enthält dessen aktive Clips; SONG folgt der Song-Liste. Ein Song-Export benötigt ein nicht leeres Arrangement.'),
 ('Ausklang und Loops','Ein Ausklang erhält das Nachklingen von Effekten nach dem musikalischen Ende. Loop-Optimierung und lange Ausklänge dienen unterschiedlichen Zielen. Wähle passend zum wiederholten Loop oder fertigen Track.'),
 ('Grenzen des Exports','Der Offline-Renderer nutzt die Project-Engine und kompatible Plug-ins. Audio externer Hardware wird durch MIDI-Export oder Export einer internen Mischung nicht nachgebildet.')])

chapter('Audio- und Controller-Einstellungen',
 'SHIFT + MAIN auf der Mikro oder SHIFT + CONTROL auf der MK2 öffnet die drei Ordner AUDIO, MIDI und SYSTEM. Wähle den Ordner mit seiner Displaytaste, markiere einen Eintrag und öffne ihn mit ENTER.',
 table=[('Ordner / Eintrag','Verwendung'),('AUDIO / INTERFACE','AUTO oder ein erkanntes Class-Compliant-Interface.'),('SAMPLE RATE / BUFFER','Abtastrate und Verhältnis von Latenz zu CPU-Bedarf. Beginne stabil und verkleinere dann den Puffer.'),('MAIN / CUE','Getrennte, nicht überlappende Ausgänge und Vorhörpegel wählen.'),('PLUGIN DELAY','Optionale Latenzkompensation, für geringe Latenz standardmäßig aus. Nur bei gestopptem Transport ändern.'),('HEADPHONE / SPEAKER / INPUT','Codec-Pegel für unterstützte ULTRA-HAT-Hardware.'),('SYSTEM / Display','Helligkeit und Kontrast pro Controller; auf der MK2 eigener Kontrast für links/rechts.'),('SYSTEM / Pads','Empfindlichkeit und Anschlagstärkekurve pro Controller.'),('SYSTEM INFO','Zuerst Logo/Version, dann Gesamt-CPU, RAM und seitenweise Datenträgerbalken.')],
 notes=[('Nur den bedienten Controller ändern','Display- und Pad-Einstellungen gelten für das Gerät, von dem aus du sie änderst. System Info beginnt mit Logo und Version. Auf der Mikro folgen CPU/RAM und Datenträger; auf der MK2 stehen CPU/RAM bereits rechts, Datenträger auf Folgeseiten.'),
 ('CPU-Anzeige','Der Prozentwert ist die Gesamtauslastung über alle Kerne, kein Einzelkernwert. Plug-ins, Stimmen, Abtastrate und Puffergröße bestimmen die Leistungsreserve. Eine niedrige Leerlauflast garantiert keinen Betrieb schwerer Sets ohne Aussetzer.')])

chapter('WebUI, WLAN und Sample-Übertragung',
 'Die WebUI verwaltet Library-Dateien, zeigt Systeminformationen und verbindet den Pi mit einem Router. Du kannst sie im Browser eines Computers, Tablets oder Smartphones nutzen.',
 steps=['Wenn kein gespeicherter Router verbunden ist, verbinde dich mit Machinista-XXXX. XXXX steht für die letzten vier Hexadezimalzeichen der permanenten WLAN-MAC-Adresse. Das Hotspot-Passwort ist machinista.',
 'Öffne http://10.42.0.1:8080. Lade WAV-Dateien nach Library/Kicks, Library/Snares, Library/Hi-Hats, Library/Loops oder in eigene Ordner. Öffne diese Ordner am Controller.',
 'Suche und wähle unter WLAN deinen Router und gib sein Passwort ein. Der Pi wechselt das Netzwerk. Verbinde dich wieder mit diesem Heimnetz und öffne http://machinista.local:8080 oder die zugewiesene IP-Adresse.',
 'Scheitert die Router-Verbindung oder geht sie verloren, kehrt der Hotspot zurück. Für lokale Nutzung braucht der Router keinen Internetzugang. Das einzelne interne WLAN-Modul wechselt zwischen Router- und Hotspot-Betrieb.',
 'Nutze für SMB smb://machinista.local/Samples; unter Windows \\\\machinista.local\\Samples. Benutzername und Passwort lauten beide machinista. Die Freigabe zeigt die Sample-Library auf der SD-Karte.'],
 notes=[('Vorhören und Zugriff','Vorhören in der WebUI spielt auf deinem Browser-Gerät, nicht über die Audioausgänge des Pi. Diese Beta hat bewusst keine WebUI-Anmeldung. Alle im verbundenen Netzwerk können auf die angebotenen Dateifunktionen zugreifen.'),
 ('Übertragungsgrenzen','WAV-Uploads sind auf 1 GiB pro Datei begrenzt und berücksichtigen eine Freiplatzreserve. Vorhandene lokale Dateien werden nicht stillschweigend überschrieben. Angeschlossene USB-Quellen sind über die WebUI erreichbar.'),
 ('Konten im Start-Image','Das verteilbare Image nutzt das Konto machinista. Persönliche Projects und WLAN-Zugangsdaten des Quellgeräts sind nicht enthalten. SSH ist im Image deaktiviert.')])

chapter('Kurzbefehle und sicheres Bearbeiten',
 'Die Beschriftungen über den Pads zeigen SHIFT-Event-Befehle. Diese wirken auf die aktuelle Event-Auswahl oder das betreffende Pattern-Ziel; nicht alle verändern die Sound-Zuordnung.',
 table=[('Tastenkombination','Ergebnis'),('SHIFT + Pad 1 / 2','Undo / Redo.'),('SHIFT + Pad 3 / 4','Step Undo / Step Redo; Hardwarebeschriftung COMPARE / SPLIT.'),('SHIFT + Pad 5 / 6','Quantisierung 100% / 50%.'),('SHIFT + Pad 7 / 8','Ausgewählte oder relevante Events nach links / rechts verschieben.'),('SHIFT + Pad 9','Nur die Events des gewählten Sound-Pads in diesem Pattern löschen; das Sample bleibt erhalten.'),('SHIFT + Pad 10','Automation im aktuellen Ziel löschen.'),('SHIFT + Pad 11 / 12','11: Events des gewählten Pads kopieren. Zielpad wählen, dann 12: an den ursprünglichen Pattern-Positionen einfügen.'),('SHIFT + Pad 13 / 14','Events um -1 / +1 Halbton transponieren.'),('SHIFT + Pad 15 / 16','Events um -12 / +12 Halbtöne transponieren.'),('SHIFT + ERASE + Sound-Pad','Sound-Slot samt Zuordnung zurücksetzen.'),('SHIFT + MUTE','Alle Noten, Stimmen und Vorhör-Samples global stoppen.')],
 notes=[('Vor einer löschenden Aktion','Prüfe Ebene, Group, Sound, Pattern und Auswahl. Eine invertierte Bestätigung verlangt eine Entscheidung und ist keine Statusmeldung. Lies die Frage und nutze die beschriftete Bestätigen-/Abbrechen-Aktion.'),
 ('Sampling-Kurzbefehle','SHIFT + SAMPLING öffnet Sample Edit; SHIFT + PAD MODE aktiviert Keyboard; SHIFT + SELECT öffnet Events. Verwechsle diese Aktionen nicht mit dem Anheften von Modi.')])

chapter('Fehlersuche und Checkliste',
 'Scheinbare Stille oder Timing-Probleme lassen sich meist leichter finden, wenn du Signalweg und aktive Zustände in einer festen Reihenfolge prüfst.',
 table=[('Symptom','In dieser Reihenfolge prüfen'),('Kein Klang','Interface und Main Output; Group-/Scene-Clip; Sound-/Group-Mute oder Solo; Sample-Zuordnung; Pegel.'),('Noten werden nicht aufgenommen','REC aktiv; aktives Group-Pattern; Pattern-Länge; richtige Keyboard-Note; nächster Loop.'),('Lange Verzögerung nach Pad-Anschlag','Effekte der Kette umgehen, besonders Look-ahead/Tape; dann Puffer und CPU prüfen.'),('Verzerrte Aufnahme','Übersteuerung am Eingang; gewählte und unterstützte Sample Rate; SR/BITS-Effekte im Sound.'),('Nur ein Slice erklingt','Notenzonen und gespielte Note; richtiger Ziel-Sound; Noten-/Anschlagstärkegrenzen der Zone.'),('Editor folgt nicht','FOLLOW aktiv; aktuelles Pattern aktiv; Transport läuft; Cursor-Bearbeitung hat Follow pausiert.'),('Group bleibt stumm','Group-Mute, andere Group auf Solo, leerer Scene-Clip, Ausgangsroute und gewähltes Pattern.'),('USB-Datei fehlt','Datenträger eingehängt; richtiger Ordner; WAV-Endung; fehlende externe Dateien neu zuordnen.')],
 notes=[('Vor dem Ende einer Session','Beende Aufnahmen, speichere das Project und sammle Samples vor einer Übertragung. Sichere Project- und Audioordner. Fahre das System geordnet herunter, bevor du Strom trennst oder den HAT wechselst.'),
 ('Ein Problem melden','Notiere Controller, Arbeitsbereich, Group/Pattern, Audiointerface, Sample Rate/Buffer und genaue Bedienfolge. Ein Displayfoto und ein möglichst kleines gespeichertes Project erleichtern die Reproduktion.'),
 ('Weiter zur Displayübersicht','Die folgenden Seiten sind eine Bildreferenz, kein weiterer Einstieg. Beschriftungen benennen Arbeitsbereich und sichtbare Parameterzuordnungen, damit du die Anzeige dem beschriebenen Ablauf zuordnen kannst.')])

SCREEN_HELP={
'PAD':'Wähle vor dem Ändern des Pegels Master, Group oder Sound. Dies ist die Haupt-Steuerungsansicht, nicht die Pad-Konfiguration.',
'CHANNEL':'Output-Seiten enthalten Audio, Aux 1 und Aux 2; Sound zusätzlich MIDI. Wähle vor einer Pegeländerung das Ziel.',
'INPUT':'Wähle Kanalquelle, Gain und Monitoring. Input gehört zu Sound/Group; Master besitzt kein Input-Modul.',
'GROOVE':'Passe Stärke und Timing des Grooves auf der gewählten Ebene an. Dies ist getrennt von einer dauerhaften Event-Quantisierung.',
'MACRO':'Wähle ein Macro, ordne ein kompatibles Ziel zu oder lösche die Zuordnung. Die Ebene bestimmt das bearbeitete Macro-Set.',
'MACRO ASSIGN':'Wähle ein kompatibles Parameterziel und APPLY. Eine leere Liste bedeutet, dass aktuell kein zuweisbares Ziel verfügbar ist.',
'SAMPLER':'Wähle Parameterseite und Feld. Der Hüllkurventyp bestimmt die sichtbaren Regler. Spiele den Sound beim Einstellen.',
'PLUGIN':'Parameter gehören zum gewählten Kettenslot. SHIFT + BROWSE öffnet Ersetzen/Entfernen auch bei geladenem Plug-in.',
'PLUGIN SLOTS':'Wähle einen Slot vor Kopieren, Verschieben, Bypass oder Entfernen. Instrument-Slots müssen zuerst stehen.',
'PARAM NAV':'Prüfe Modul und Unterseite bei gehaltenem NAV. Loslassen öffnet das angezeigte Ziel.',
'BROWSE':'Drehen wählt Ordner oder WAV. Öffne Ordner; BACK geht zurück, PREHEAR hört vor. Pads wählen den Ziel-Sound.',
'PLUGIN BROWSE':'Wähle ein kompatibles LV2-Instrument, einen Effekt oder den Entfernen-Eintrag. Laden ersetzt einen belegten Slot.',
'PLUGIN MOVE':'Wähle den Ziel-Slot und bestätige MOVE. Abbrechen lässt die Reihenfolge unverändert.',
'PLUGIN SC':'Wähle eine Sidechain-Quelle nur für ein Plug-in mit Sidechain-Eingang. Rückkopplungsschleifen werden abgewiesen.',
'SAMPLING':'Wähle Quelle, Eingang und Detect/Sync-Optionen. START schaltet scharf, STOP beendet, CANCEL verwirft die Aufnahme.',
'SAMPLING NAV':'Prüfe Record, Edit, Slice oder Zone vor dem Loslassen von NAV. Die Unterseitenanzeige folgt dem gewählten Ziel.',
'SAMPLE EDIT':'START/END begrenzen Wiedergabe oder Auswahl. Wähle Bearbeitung und Bereich und bestätige APPLY.',
'CHOP':'Wähle Split/Grid/Detect/Manual, höre Schnitte an und bearbeite Grenzen mit EDIT. APPL.TO wählt das Ziel.',
'ZONE':'Wähle die Zone vor dem Ändern von Wiedergabebereich, Loop, Stimmung, Hüllkurve oder Noten-/Anschlagstärkebereichen.',
'STRETCH':'Passe Länge und Tonhöhe an, höre vor und wähle APPLY oder Abbrechen. Erst Bestätigen übernimmt die Vorschau.',
'SLICE TARGET':'Wähle Group und ersten Sound/alle Sounds. SINGLE weist nur den gewählten Slice zu. Prüfe belegte Ziele vor APPLY.',
'SAMPLE DELETE':'Wähle REMOVE FROM PAD oder DELETE FILE und bestätige. Zuordnung entfernen und Datei löschen sind getrennte Vorgänge.',
'PAD CONFIG':'Wähle Pad, Keyboard oder 16 VEL. Fixed Velocity beeinflusst das Spielen, getrennt von Zone Gain und Normalisierung.',
'NOTE REPEAT':'Wähle Rate und Unterteilung und halte Pads. Bei laufender Wiedergabe folgt Repeat dem musikalischen Raster.',
'ARP':'Gehaltene Keyboard-Noten speisen den Arpeggiator. Gate, Richtung, Oktavumfang und Hold bestimmen sein Spielverhalten.',
'GROUP':'Wähle die Group in der aktuellen Bank. Patterns und Sound-Fokus folgen ihr; Group-Output/Mute kann das ganze Kit verstummen lassen.',
'SELECT':'Fokussiere lautlos oder wähle mehrere Ziele. Event- und Sound-Auswahl sind getrennte Ebenen.',
'DUPLICATE':'Wähle Quelle und Ziel auf der aktuellen Objektebene. Die Events-Option bestimmt, ob zugehörige Notendaten mitkopiert werden.',
'MUTE':'Sound-Pads schalten Mute um. Prüfe auch die Group; stummgeschaltetes Audio wird sofort beendet.',
'SOLO':'Solo kann andere, nicht stummgeschaltete Kanäle unhörbar machen. Nutze bei der Fehlersuche die Reset-Aktionen.',
'STEP':'Pads schalten Steps des gewählten Sounds/der Note. Bank und Follow ändern den Ausschnitt, nicht die Pattern-Länge.',
'PATTERN':'Pads wählen Patterns. LENGTH, DOUBLE und DUPLICATE wirken auf das Group-Pattern. ENTER/EDITOR öffnet das Event-Raster.',
'PATTERN GRID':'Navigiere durch Zeit und Zeile/Tonhöhe, markiere eine Auswahl und öffne EDIT. Cursorbewegungen pausieren Follow.',
'GRID EDIT':'Ändere Position, Tonhöhe, Anschlagstärke, Wahrscheinlichkeit oder Dauer der aktiven Zielmenge. DELETE verlangt Bestätigung.',
'EVENT':'Prüfe das fokussierte Event in der kompakten Anzeige. Vorher/Weiter bewegt den Cursor; Löschen verlangt Bestätigung.',
'OPTIONS':'Grid, Quantisierungsstärke und Swing haben unterschiedliche Aufgaben. Wähle zuerst den gewünschten Reiter.',
'RECORD SETTINGS':'Stelle Metronompegel, Vorzählerlänge und Aufnahmequantisierung ein. SHIFT + GRID öffnet diese Ansicht.',
'RECORD PREPARE':'Halte REC eine Sekunde für Länge/Raster. Loslassen kehrt aufnahmebereit zur vorherigen Ansicht zurück.',
'MIDI TRACK':'Stelle Notenquelle, MIDI-Ziel/-Kanal und Notenverhalten des Sounds für externe Instrumente ein.',
'VIEW NAV':'Stelle Ansichtszoom und Scroll ein oder wähle das beschriftete Ziel. Dies ist keine Einzelnoten-Bearbeitung.',
'SCENE':'Pads rufen Scenes auf. Jede Scene enthält Group-Pattern-Verweise; Wechsel erfolgen nach Perform Grid.',
'SONG':'INSERT fügt die gewählte Scene ein, PLAY schaltet Arrangement-Wiedergabe um, DELETE entfernt nach Bestätigung den Eintrag.',
'SONG AUTO':'Wähle eine Song-Master-Automationsspur. Aktiviere/deaktiviere oder entferne sie, ohne den Scene-Verweis zu löschen.',
'MIXER':'Wähle Ebene, dann Level/Pan/Route. Pegel zeigen Audioaktivität, nicht das Vorhandensein von Pattern-Noten.',
'PROJECT':'SAVE speichert das Project; LOAD wählt einen Speicherplatz; MANAGE bietet Namen, Presets, Relink und Export.',
'PROJECT LOAD':'Wähle und lade ein gespeichertes Project. SHIFT-Aktionen benennen den Eintrag um/löschen ihn; NEW beginnt die Namenseingabe.',
'PROJECT MANAGE':'Wähle einen Vorgang und OPEN. New, Rename und Save As wirken unterschiedlich auf gespeicherte Einträge.',
'PROJECT NAME':'Pfeile bewegen den Cursor; der Encoder ändert Zeichen. RANDOM schlägt Namen vor, SHIFT + CANCEL leert, OK übernimmt.',
'PRESET LOAD':'Wähle ein kompatibles Sound-/Group-Preset und lade es in das aktuelle Ziel. Prüfe die Zielebene.',
'MISSING SAMPLES':'Suche nach fehlenden referenzierten Audiodateien. Suche erneut nach dem Anschließen der fehlenden USB-Quelle.',
'RELINK RESULTS':'Prüfe Kandidaten vor dem Ersetzen. Navigiere manuell, wenn kein genauer Treffer gefunden wird.',
'RELINK BROWSE':'Navigiere zur richtigen Ersatz-WAV. Ähnliche Dateinamen belegen keinen identischen Audioinhalt.',
'SAMPLE RAM':'REFRESH fragt geladenen Sample-Speicher ab. PURGE gibt ungenutzte Daten bei gestoppter Wiedergabe/Aufnahme frei.',
'EXPORT':'Wähle Bereich, Quelle, Format/Bittiefe und Ziel. Rendern erfolgt unabhängig vom Live-Audiogerät.',
'EXPORT DONE':'Prüfe Ausgabeort und Dateinamen. BACK geht zurück; NEW bereitet einen weiteren Export vor.',
'CONFIRM':'Lies vor dem Bestätigen die ganze Frage. YES führt aus; CANCEL behält den aktuellen Inhalt.',
'SETTINGS':'Wähle Audio, MIDI oder System, dann Zeile und ENTER. Einstellungen bleiben nach Neustarts erhalten.',
'SYSTEM':'Zuerst erscheinen Machinista-Logo und Version. Auf der Mikro folgen CPU/RAM und Speicher. Auf der MK2 stehen CPU/RAM bereits rechts; Folgeseiten zeigen Speicher.',
'BLUETOOTH MIDI':'Aktiviere, kopple/suche und verbinde ein MIDI-Gerät. Dies überträgt MIDI, keinen Bluetooth-Audiostream.',
}

def localize_chapters(source):
    if len(CH)<len(source):
        from tools.manual_updates_beta6 import de_update
        de_update(CH,source,SCREEN_HELP)
    assert len(source)==len(CH),(len(source),len(CH))
    result=[]
    for original,german in zip(source,CH):
        assert len(original['steps'])==len(german['steps']),original['title']
        assert len(original['notes'])==len(german['notes']),original['title']
        assert len(original.get('table') or [])==len(german.get('table') or []),original['title']
        entry=deepcopy(german);entry['screens']=original['screens'];entry['source_title']=original['title']
        result.append(entry)
    return result
