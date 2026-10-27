# Sounds, zones and Autosampler

Open the WebUI, refresh it after an update, and choose **Sounds**.

A **Sampler Sound** stores its samples, zones, sampler parameters and any saved effect strip. A **live LV2 Sound** stores the instrument, the rest of its plug-in strip, control values and the plug-ins' saved state/resources. Saving an LV2 patch does not sample it. Plug-in binaries are not included: the same compatible LV2 plug-ins must be installed when loading it.

## Import a SoundFont

Use **Sounds → Import SoundFont** to convert an SF2 instrument into a native sampler Sound, with its samples and zones. Inspect and acknowledge compatibility notes before importing. No external instrument plug-in is needed. See [Native SoundFont import](SOUNDFONT_IMPORT.md) for the workflow, supported features and conversion limits.

## Build an instrument from recorded notes

1. Upload WAV or MP3 files in **Samples** first. MP3 uploads become PCM WAV. Existing PCM WAV files on SD or USB can be selected directly.
2. **Sounds → New sampler Sound → Add samples**. Navigate storage/folders and select the files. This picker currently accepts WAV files.
3. Give each zone its original MIDI **Root** note. Note 60 is C3 on the controllers. Root sets the pitch at which that sample plays unchanged.
4. Select **Map between root notes** to split key ranges at midpoints. **Extend to full keyboard** fills the outer ranges to MIDI 0/127. This does not detect pitch from audio: enter the original root notes yourself.
5. The map's horizontal axis is MIDI pitch; its vertical axis is velocity. Click a zone to select it. Drag its edges to change its key range, or enter key/velocity limits in the table. Overlapping ranges deliberately layer samples. Zones sharing a root keep their velocity ranges when key mapping is recalculated.
6. Edit selected-zone tuning, gain, pan, start/end frames, loop bounds and crossfade below the table. Envelope, polyphony and release apply to the whole Sound. The controller still exposes its full existing parameter set.
7. Enter a Sound name, a folder such as `Keys/Electric Piano`, and optional comma-separated tags. **Save Sound** copies its samples into managed storage. Originals are left unchanged.
8. Select the destination Sound-slot on the controller, then **Load on selected pad** in the WebUI. Confirm the displayed group/pad. Stop transport and recording first. Alternatively open the controller's BROWSE source **SOUNDS**, navigate its folders and press LOAD/ENTER.
9. Play in Keyboard mode or use a connected MIDI keyboard. Ordinary WAV/MP3 browsing and the existing controller ZONE workflow remain available.

**Edit current pad zones** reads a snapshot; it creates a separate saved instrument. It does not silently rewrite the currently playing project. If the current Sound has a plug-in strip, first use **Save current Sound / LV2 patch**, then edit the saved Sound, so its strip/state is retained. After editing a saved instrument, explicitly load it again to use that version in a project.

## Save a live LV2 instrument or complete current Sound

Select the desired Sound-slot on the controller. Click **Save current Sound / LV2 patch**, enter name/folder/tags, and save. The engine captures a consistent Sound snapshot and requests state from every plug-in in the strip; file collection happens in a background worker. A missing/failed state prevents publication. No PCM recording is made for a pure LV2 instrument.

The saved card identifies it as **LV2 instrument + strip**. Edit changes its name, folder and tags. Edit actual plug-in parameters on the controller and save a new snapshot. Loading recalls the whole strip and state. Missing/incompatible plug-ins leave the destination Sound unchanged.

## Autosampler

Autosampler makes a sampled copy of an external or internal instrument; it is separate from live LV2 patch saving.

1. Stop playback and recording. Open **Sounds → Autosampler**.
2. Choose **Current LV2 instrument**, with the source Sound selected on the controller; or **External MIDI instrument**, with MIDI output/channel and the active audio interface's input selected. Connect MIDI OUT to the external instrument and its audio output to that input. Adjust input gain before recording.
3. Enter the Sound's name/folder/tags; lowest/highest MIDI note; semitone interval; velocity layers such as `32, 64, 96, 127`; note length; tail and inter-note gap. The upper endpoint is included even when it is not an exact interval multiple.
4. Optional **Trim leading silence** uses −60 dB and retains 2 ms before the detected attack. A very slow attack may need trimming disabled. No automatic looping or pitch detection is performed.
5. Start. Keep the source/device/project unchanged. Live controller-pad and MIDI-keyboard playing is suppressed while the automatic capture owns the recorder, to avoid contaminating takes. Note-off is sent after each note length; the tail is then recorded. Choose enough tail/gap for the source's release and effects to decay.
6. After all takes finish, the Sound is saved with automatically split key and velocity ranges, ADSR and polyphony 16. It appears in **Sounds** and in controller **BROWSE → SOUNDS**. The original source Sound is not replaced. Load the new instrument explicitly.
7. **Cancel recording** releases the active note and stops capture; no partial Sound is published. Incomplete/error recordings are retained in private `samples/.autosampler/<session>` for recovery. Successful temporary takes are removed after publication. Completely silent sessions fail; partially silent or clipped takes are reported after saving.

Limits: 128 zones per Sound; up to 8 velocity layers; MIDI 0–127; note interval 1–24 semitones; note length 0.05–30 seconds; tail 0–10 seconds; gap 0.05–5 seconds. Each zone must fit the existing 64 MiB decoded sample limit. Sound samples are capped at 512 MiB; sessions reserve space for both takes and collected assets plus 256 MiB free. Native engine capture writes WAV away from its audio callback; the application schedules capture/MIDI control, while asset work runs in lower-priority background workers.

## Organization and backups

Folder navigation is available on the controllers and WebUI. Name/tag search is currently in the WebUI. Ordinary sample Prehear is unchanged; Sound presets must be loaded before they can be auditioned on pads.

Visible entries are `.sound` catalog links in `presets/Sounds/<folder>`. The associated complete bundles live in hidden `presets/Sounds/.library/<id>`. Back up the **whole `presets/Sounds` directory including hidden files**; a `.sound` link alone is not an instrument backup. Existing controller-written Sound preset folders remain loadable in BROWSE. The new WebUI index currently lists its managed `.sound` entries.

Sample and state assets keep stable paths when a Sound is renamed, moved or edited. Earlier sample assets are retained so projects using an older revision keep working. Explicit Sound deletion/purging, standalone Sound ZIP transfer and automatic sample looping are not part of this update. A collected project ZIP includes the assets/state actually used in that project.

## Deutsch

Unter **WebUI → Sounds** lassen sich Sample-Instrumente und echte LV2-Patches verwalten. **New sampler Sound → Add samples** fügt WAV-Dateien aus SD-/USB-Ordnern hinzu. Pro Sample die ursprüngliche MIDI-Root-Note eingeben und anschließend **Map between root notes** wählen. Die Grafik zeigt Tastatur- und Velocity-Bereiche; überlappende Zonen spielen gleichzeitig. Name, Ordner und Tags vergeben, speichern und anschließend auf den gewünschten Sound-Slot laden. Die bisherige ZONE-Bedienung am Controller bleibt erhalten.

**Save current Sound / LV2 patch** speichert den ausgewählten Sound mit vollständigem Plugin-Strip und Patch-State. Ein reiner LV2-Sound wird dabei nicht gesampelt. Die verwendeten Plugins müssen auf dem Zielsystem installiert sein. Bei einem Sound mit Effekten zuerst diesen kompletten Snapshot speichern und danach seine Zonen bearbeiten.

Der **Autosampler** nimmt wahlweise den ausgewählten LV2-Synth oder ein externes Instrument über MIDI-Ausgang und Audioeingang auf. Notenbereich, Tonabstand, Anschlagstärken, Notenlänge und Ausklangzeit einstellen, Namen vergeben und starten. Zonen und Velocity-Layer werden automatisch zugeordnet. Der ursprüngliche Sound bleibt bestehen; das neue Sample-Instrument erscheint unter **BROWSE → SOUNDS**. Während der Aufnahme nicht den Sound oder das Interface wechseln. Für lange Release-/Effektfahnen genügend Tail und Gap einstellen. Abbruch sendet Note-off und veröffentlicht keinen halbfertigen Sound.

Ordner sind auch am Controller sichtbar, die Tag-Suche befindet sich in der WebUI. Zum Sichern die vollständige Struktur `presets/Sounds` einschließlich `.library` kopieren. Die aktuelle Beta-Image-Datei wird durch diese Installation nicht neu erstellt.

## Autosampler on the controllers

Stop playback and recording first. Select the source Sound before entering Sampling.

- **MK2:** press SAMPLING, then PAGE RIGHT twice (once for an internal recording source). The following three pages are Autosampler setup, output and velocities. The top keys SETUP / OUTPUT / VELOCITY jump directly between these pages. Each encoder edits the parameter directly above it.
- **Mikro:** press SAMPLING, hold NAV, turn the encoder to AUTO and release NAV. Left/right selects a parameter; the encoder changes its value. ENTER edits Sound name or folder. F1 returns to Record, F2 starts, F3 cancels.

Choose LV2 for the currently selected instrument or EXTERNAL for a MIDI-connected instrument. Set the note range, semitone interval, layer count and hold/tail/gap. Changing layer count creates evenly spaced velocities; the velocity page allows individual adjustment. EXTERNAL additionally needs MIDI output, channel and audio input. Set the Sound name before Start; folder defaults to Autosampled. The MK2 NAME / FOLDER keys open the name editor. Finish with its SAVE key; CANCEL returns without changing the name.

The progress bar and zone count follow the same capture job in the WebUI. A completed instrument appears under Sounds; it does not replace the source Sound. Cancel releases the current note and prevents publishing a partial instrument. While recording, settings are locked. The controller workflow uses the same native recorder and background asset worker as the WebUI; the display does no audio processing.

### Autosampler am Controller

Zuerst Wiedergabe und Aufnahme stoppen und den Quell-Sound auswählen.

- **MK2:** SAMPLING drücken und zweimal PAGE RIGHT (bei interner Aufnahmequelle einmal). SETUP / OUTPUT / VELOCITY wechseln die drei Autosampler-Seiten direkt. Die acht Encoder ändern jeweils den darüber angezeigten Wert.
- **Mikro:** SAMPLING drücken, NAV halten, mit dem Encoder AUTO wählen und NAV loslassen. Links/rechts wählt einen Parameter, der Encoder ändert den Wert. ENTER öffnet die Namenseingabe für Sound oder Ordner. F1 zurück, F2 Start, F3 Abbruch.

LV2 nimmt das ausgewählte Instrument auf; EXTERNAL ein externes Instrument über MIDI-Ausgang und Audioeingang. Notenbereich, Intervall, Layer-Anzahl und Aufnahmezeiten einstellen. Bei EXTERNAL zusätzlich MIDI-Ausgang, Kanal und Audioeingang wählen. Die einzelnen Velocity-Werte stehen auf der letzten Seite. Sound-Namen vor dem Start vergeben; als Ordner ist Autosampled voreingestellt. Auf der MK2 öffnen NAME / FOLDER die Namenseingabe.

Fortschrittsbalken und Zonenanzahl zeigen dieselbe Aufnahme wie die WebUI. Der fertige Sound erscheint unter Sounds; die Quelle wird nicht ersetzt. Abbruch beendet die Note und veröffentlicht kein unvollständiges Instrument. Während der Aufnahme sind die Einstellungen gesperrt.

## Root notes from filenames

When adding WAV files in the WebUI Sound editor, a separate note token in the
filename sets its root automatically, for example `Rhodes A2.WAV`,
`Piano_F#3_v100.wav` or `EP Bb2.wav`. Sharps and flats are accepted. Root and
key-range controls display note names; saved MIDI values are unchanged.
Choose filename octave notation before adding: the controller convention is
C3 = MIDI 60; scientific notation is C4 = MIDI 60. The displayed note names
always follow the controllers. Filename interpretation does not analyze audio.
Unrecognized or ambiguous names keep their existing root (new zones use C3).
Existing Sounds are not silently retuned. Use **Roots from filenames** to
explicitly read roots again, then **Map between root notes** to distribute
keyboard ranges. Save the Sound when finished.

### Grundtöne aus Dateinamen

Beim Hinzufügen von WAV-Dateien erkennt die WebUI einzelne Notenangaben im
Dateinamen, etwa `Rhodes A2.WAV`, `Piano_F#3_v100.wav` oder `EP Bb2.wav`.
Root und Tastaturgrenzen zeigen Notennamen; die gespeicherten MIDI-Werte bleiben
unverändert. Voreinstellung ist C3 = MIDI 60 passend zu den Controllern. Für
Dateinamen mit wissenschaftlicher Oktavzählung lässt sich C4 = MIDI 60 wählen.
Die Anzeige selbst folgt weiterhin der Controller-Zählung. Dies ist eine
Dateinamen-Erkennung, keine Tonhöhenanalyse der Audiodatei.
Nicht erkannte oder mehrdeutige Namen behalten ihren Grundton; neue Zonen starten
in diesem Fall mit C3. **Roots from filenames** liest die Namen für bereits
hinzugefügte Zonen erneut. Danach verteilt **Map between root notes** die
Tastaturbereiche. Den Sound anschließend speichern.

## Keyboard note display and default range

Keyboard ROOT and custom chord note fields show note names on both controllers.
New projects and Groups start at C3 (MIDI 60). Saved Group roots are retained,
including the special slice range beginning at MIDI 0. Change ROOT in PAD MODE
→ KEYBOARD to adjust an existing project's keyboard range.

Keyboard-ROOT und die Notenfelder eigener Akkorde zeigen auf beiden Controllern
Notennamen. Neue Projekte und Gruppen beginnen bei C3 (MIDI 60). Gespeicherte
Gruppen-Tonlagen bleiben erhalten, einschließlich Slice-Zuordnungen ab MIDI 0.
Bei bestehenden Projekten lässt sich ROOT unter PAD MODE → KEYBOARD ändern.
