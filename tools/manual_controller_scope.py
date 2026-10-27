"""Resolve shared workflow prose into instructions for one controller only."""


def scope_chapters(chapters, language='en'):
    de=language=='de'
    by={c.get('source_title',c['title']):c for c in chapters}
    def text(en,german):return german if de else en
    def variant(micro,large,mk1=None):return dict(mikro=micro,mk2=large,mk1=mk1 or large)
    ch=by['Know your controller']
    title,body=ch['notes'][2]
    body['mk2']=body['mk1']=text('CONTROL returns to the control view. SHIFT + CONTROL opens settings. The arrows below SAMPLING switch parameter pages. Hold NAVIGATE to preview and select a workspace.','CONTROL führt zur Steuerungsansicht zurück. SHIFT + CONTROL öffnet die Einstellungen. Die Pfeile unter SAMPLING wechseln Parameterseiten. Halte NAVIGATE, um Arbeitsbereiche vorab anzuzeigen und auszuwählen.')
    ch['notes'][2]=(title,body)
    ch['notes'][-1]=(text('Confirm a choice','Auswahl bestätigen'),ch['notes'][-1][1])

    ch=by['Record and overdub a Pattern']
    ch['steps'][0]=variant(
        text('Select the Group and Pattern. In PATTERN, turn the encoder to set LENGTH; SHIFT gives single-step changes. Check that the Scene has an active clip for this Group.','Wähle Group und Pattern. Drehe in PATTERN den Encoder, um LENGTH einzustellen; SHIFT ermöglicht einzelne Steps. Prüfe, dass die Scene einen aktiven Clip für diese Group enthält.'),
        text('Select the Group and Pattern. In PATTERN, turn encoder 1 to set LENGTH; SHIFT gives single-step changes. Check that the Scene has an active clip for this Group.','Wähle Group und Pattern. Drehe in PATTERN Encoder 1, um LENGTH einzustellen; SHIFT ermöglicht einzelne Steps. Prüfe, dass die Scene einen aktiven Clip für diese Group enthält.'))
    ch=by['Select and edit individual events'];title,_=ch['notes'][0]
    ch['notes'][0]=(title,variant(
        text('A selected set takes priority over the cursor target. In pitch view, the Sound stays selected while the note changes. When notes share a cell, SHIFT + navigation arrows cycle the focused voice.','Eine markierte Menge hat Vorrang vor dem Cursorziel. In der Tonhöhenansicht bleibt der Sound gewählt. Bei mehreren Noten in einer Zelle wechseln SHIFT + Navigationspfeile die fokussierte Stimme.'),
        text('A selected set takes priority over the cursor target. In pitch view, the Sound stays selected while the note changes. Use the labelled selection controls before changing event parameters.','Eine markierte Menge hat Vorrang vor dem Cursorziel. In der Tonhöhenansicht bleibt der Sound gewählt. Nutze die beschrifteten Auswahlaktionen, bevor du Event-Parameter änderst.')))

    ch=by['Mute, solo, selection and duplication']
    ch['steps'][0]=variant(
        text('Hold MUTE or SOLO and press a Sound pad to toggle its state. Use the displayed Group action to change Group scope.','Halte MUTE oder SOLO und drücke ein Sound-Pad zum Umschalten. Die angezeigte Group-Aktion wechselt zur Group-Ebene.'),
        text('Hold MUTE or SOLO and press a Sound pad to toggle its state. The dedicated A-H keys toggle Group mute or solo in these views.','Halte MUTE oder SOLO und drücke ein Sound-Pad zum Umschalten. Die Tasten A-H schalten in diesen Ansichten Group-Mute oder -Solo.'))
    ch['steps'][2]=variant(
        text('Use SELECT for quiet focus and multi-selection. Use the displayed ALL/NONE action to select or clear the relevant set.','SELECT dient zur lautlosen Fokussierung und Mehrfachauswahl. Die angezeigte Aktion ALL/NONE wählt die entsprechende Menge aus oder hebt sie auf.'),
        text('Use SELECT for quiet focus and multi-selection. ALL toggles between all sixteen Sounds and the focused Sound; in the event grid it toggles event selection.','SELECT dient zur lautlosen Fokussierung und Mehrfachauswahl. ALL wechselt zwischen allen sechzehn Sounds und dem fokussierten Sound; im Event-Raster schaltet es die Event-Auswahl um.'))
    by['MIDI ports, clock and Bluetooth']['steps'][2]=variant(
        text('Open BLUETOOTH MIDI and enable ON/OFF. F2 scans, SHIFT + F2 opens pairing and ENTER toggles connection for the selected device.','Öffne BLUETOOTH MIDI und aktiviere ON/OFF. F2 sucht, SHIFT + F2 öffnet Pairing und ENTER schaltet die Verbindung zum gewählten Gerät um.'),
        text('Open BLUETOOTH MIDI and enable ON/OFF. Use the labelled PAIR, SCAN, CONNECT and DISCONN display buttons for the selected device.','Öffne BLUETOOTH MIDI und aktiviere ON/OFF. Nutze die beschrifteten Displaytasten PAIR, SCAN, CONNECT und DISCONN für das gewählte Gerät.'))

    ch=by['Audio and controller settings']
    ch['table']=[(k,variant(text('Brightness and contrast for this display.','Helligkeit und Kontrast dieses Displays.'),text('Brightness and separate left/right display contrast.','Helligkeit und getrennter Kontrast für linkes und rechtes Display.'))) if k in ('SYSTEM / display','SYSTEM / Display') else (k,v) for k,v in ch['table']]
    title,_=ch['notes'][0]
    ch['notes'][0]=(title,variant(
        text('Display and pad settings apply to this controller. System Info opens with the logo/version, followed by CPU/RAM, per-core CPU bars with percentages, then storage pages.','Display- und Pad-Einstellungen gelten für diesen Controller. System Info beginnt mit Logo/Version, danach folgen CPU/RAM, Balken mit Prozentwerten je CPU-Kern und die Datenträgerseiten.'),
        text('Display and pad settings apply to this controller. System Info opens with the logo/version on the left and CPU/RAM on the right. Following pages show each CPU core as a bar/percentage, then storage.','Display- und Pad-Einstellungen gelten für diesen Controller. System Info beginnt mit Logo/Version links und CPU/RAM rechts. Die Folgeseiten zeigen jeden CPU-Kern als Balken mit Prozentwert und danach die Datenträger.')))

    ch=by['Record and overdub a Pattern']
    ch['notes']=list(ch['notes']);ch['notes'].append((text('Grid tabs','Grid-Reiter'),variant(
        text('Hold GRID. F1 QUANT, F2 SWING and F3 GRID select the timing section; NAV arrows choose its parameter, including REC QUANT in the GRID section. QUANT applies with ENTER.','Halte GRID. F1 QUANT, F2 SWING und F3 GRID wählen den Timing-Bereich; NAV-Pfeile wählen den Parameter, einschließlich REC QUANT im GRID-Bereich. QUANT wird mit ENTER angewendet.'),
        text('Hold GRID. Display buttons 2 SWING, 3 GRID and 4 QUANT select the highlighted section. Only the selected timing section shows its parameters. GRID sets resolution, enable and nudge; encoder 5 REC QUANT controls recording quantization. SWING adjusts playback timing; QUANT sets strength and Sound/Group target. Button 8 APPLY quantizes existing notes only in QUANT. Button 1 controls PIN while GRID is held; afterward BACK returns to the previous view.','Halte GRID. Displaytasten 2 SWING, 3 GRID und 4 QUANT wählen den markierten Bereich. Nur der gewählte Timing-Bereich zeigt seine Parameter. GRID setzt Raster, Aktivierung und Nudge; Encoder 5 REC QUANT steuert die Aufnahmequantisierung. SWING ändert das Wiedergabe-Timing; QUANT setzt Stärke und Sound-/Group-Ziel. Taste 8 APPLY quantisiert vorhandene Noten nur unter QUANT. Taste 1 steuert PIN bei gehaltenem GRID; danach führt BACK zur vorherigen Ansicht.'))))

    ch=by['The Sampler: voice, envelopes and filters']
    ch['steps'][-1]=text('Choose LP2, BP2, HP2 or EQ, then adjust cutoff and resonance or EQ gain/width. Cutoff uses equal travel per octave; hold SHIFT for four-times-finer changes. Play the pad to compare the result.','Wähle LP2, BP2, HP2 oder EQ und stelle Cutoff sowie Resonance beziehungsweise EQ Gain/Width ein. Cutoff hat einen gleichmäßigen Drehweg pro Oktave; SHIFT regelt viermal feiner. Spiele das Pad zum Vergleichen.')

    ch=by['Your first beat'];step=ch['steps'][2]
    step['mk1']=text('Turn the dedicated TEMPO encoder to set a comfortable tempo. Hold SHIFT for fine changes.','Stelle mit dem eigenen TEMPO-Regler ein angenehmes Tempo ein. Halte SHIFT für Feineinstellungen.')
    ch=by['Navigation, hold and pin'];title,body=ch['notes'][0]
    back=text('Hold NAVIGATE and choose IDEAS, SONG, MIXER, BROWSE or EVENTS. The destination is highlighted before release. Select the active destination again to return to the previous workspace; its highlight clears immediately. This also works with PIN enabled. Each display button has a matching workspace icon. BACK cancels the selection. Zoom and scroll remain in the editors; FOLLOW stays in the Pattern/Step views.','Halte NAVIGATE und wähle IDEAS, SONG, MIXER, BROWSE oder EVENTS. Das Ziel ist vor dem Loslassen markiert. Wähle das aktive Ziel erneut, um zum vorherigen Arbeitsbereich zurückzukehren; die Markierung verschwindet sofort. Das gilt auch bei aktiviertem PIN. Jede Displaytaste hat ein passendes Symbol. BACK verwirft die Auswahl. Zoom und Scroll bleiben in den Editoren; FOLLOW bleibt in den Pattern-/Step-Ansichten.')
    body['mk1']=body['mk2']=back;ch['notes'][0]=(title,body)


def scope_text(value,device):
    """Remove mixed button notation in shared captions and steps."""
    micro=device=='mikro'
    for n in (1,2,3):
        value=value.replace(f'F{n} / display button {n}',f'F{n}' if micro else f'display button {n}')
        value=value.replace(f'F{n} / Displaytaste {n}',f'F{n}' if micro else f'Displaytaste {n}')
        value=value.replace(f'F{n} / Taste {n}',f'F{n}' if micro else f'Taste {n}')
    if device=='mk1':
        value=value.replace('LOAD or ENTER','the labelled LOAD action').replace('LOAD oder ENTER','die beschriftete Aktion LOAD')
        value=value.replace('ENTER or display button 8 LOAD','Display button 8 OPEN/LOAD').replace('ENTER oder Displaytaste 8 LOAD','Displaytaste 8 OPEN/LOAD')
        value=value.replace('and ENTER','and the labelled OPEN action').replace('und ENTER','und die beschriftete Aktion OPEN')
        value=value.replace('ENTER/EDITOR','EDITOR').replace('mit ENTER','mit der beschrifteten Aktion OPEN')
    return value


def system_hint(language='en'):
    if language=='de':
        return dict(mikro='Zuerst erscheinen Logo und Version. Wechsle danach zu CPU/RAM und den Datenträgerseiten.',mk1='Logo und Version stehen links, CPU/RAM rechts. Folgeseiten zeigen Datenträger.',mk2='Logo und Version stehen links, CPU/RAM rechts. Folgeseiten zeigen Datenträger.')
    return dict(mikro='The first page shows the logo/version. Continue to CPU/RAM, then storage pages.',mk1='Logo/version appears on the left and CPU/RAM on the right. Following pages show each CPU core as a bar/percentage, then storage.',mk2='Logo/version appears on the left and CPU/RAM on the right. Following pages show each CPU core as a bar/percentage, then storage.')
