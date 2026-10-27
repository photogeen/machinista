# Machinista on MK3

## Controls

The eight display buttons operate the labels directly above the screens. The eight encoders operate the parameter cells directly below them. Page arrows change parameter pages. Turn the 4D encoder to select an item; press it to confirm.

- **CHANNEL / PLUG-IN:** channel routing or instrument/effect parameters. MASTER, GROUP and SOUND remain available on the display buttons. The illustrated chain appears only on the first parameter page. Later pages use both displays for the detailed parameter views. In Plug-in, push the 4D encoder left/up for the previous slot or right/down for the next. Numbered names above the sliding illustration identify the chain; arrowheads and the slot count show available neighbours. The page arrows still change parameter pages and all eight parameter encoders remain available. Sampler appears only for a loaded sample or sample zones; instruments and effect-only Sounds open their own illustration directly. An effect-only Sound is a populated, illuminated pad and can process its configured external input.
- **BROWSE:** folders, samples and Sounds. Select a destination pad while browsing; turn the encoder and press to load.
- **SAMPLING:** recording, editing, slicing, zones and autosampling. **SHIFT + SAMPLING** opens Edit. Zoom and Scroll remain on encoders 3 and 4 in waveform editing. In Slice, either pair of left/right arrows focuses the selected slice’s start/end boundary. SHIFT + page arrows opens the slice parameter pages. Boundary focus retains the chosen zoom, and subsequent pad auditions keep that focus.
- **MIXER / ARRANGER / EVENTS:** Mixer, Song and the note editor. FOLLOW enables or disables the current editor's follow function. **SHIFT + FOLLOW (GRID)** opens the GRID tab without toggling Follow. Encoder 1 selects resolution, encoder 2 enables the editing grid, encoder 3 sets nudge, and encoder 5 REC QUANT enables/disables recording quantization independently. The GRID tab is labelled GRID (not STEP); the physical STEP button opens the separate step sequencer.
- **KEYBOARD:** enable or disable melodic pads. **CHORDS:** enable or disable custom chords and open their settings. PAD MODE retains the shared held-mode/PIN behavior.
- **FIXED VEL:** toggle fixed velocity. NOTE REPEAT, PLAY, REC, STOP, RESTART retain their transport/performance roles. **TAP** sets tap tempo; **SHIFT + TAP** toggles the metronome without changing tempo or transport. While SHIFT is held, the TAP LED shows the metronome state.
- **VARIATION:** hold to choose a workspace using the display buttons, then release to enter it. The navigation Back button clears the workspace selection. SHIFT + VARIATION opens the existing Grid/Swing/Quantize settings; there is no separate random pattern generator.
- **FILE:** project manager. **SHIFT + FILE:** save. SETTINGS opens settings. MACRO opens the current target's macros. AUTO supports held writing and SHIFT-latched writing.

## Smart Strip

In Events, 4D Up/Down moves the pitch cursor (or Sound row in drum view) without changing its time position. This pauses Follow; use FOLLOW to resume it.

PITCH sends pitch bend and returns to centre on release. MOD sends modulation-wheel values. NOTES plays across the current pad mapping, including keyboard notes and chords. Press a selected strip-mode button again to disable it. While untouched, the LED strip shows the current pattern's playhead across all 25 LEDs at full brightness, including when PITCH or MOD is selected. STOP holds the current position. During contact it shows the finger position; releasing returns to the pattern playhead.

PERFORM opens Live FX and assigns the strip to the selected effect's intensity. The existing PUNCH/FLEX/KNOB controls and recording of Live FX gestures remain available.

LOCK provides one A/B snapshot of gains, sampler/routing/macro parameters and the controls/bypass states of existing plug-ins. Press again to restore those values. It does not restore notes, samples, plug-in slots or an entire project. There are no extended Lock banks or morph transitions. Pedal analog reports have been identified but are not mapped without a pedal calibration.

## Color displays and device preferences

Both displays render at their native 480 × 272 resolution. Group identity stays visible in the A–H header and mixer strips. Orange marks selection and active controls. Color Layers uses cyan for time/modulation, purple for pitch/envelopes, yellow for filters/playheads, and green/red for playback, recording and peak status. Waveforms, slice markers, playheads, mixer levels and the keyboard use the real application state. Views follow the MK2 division: waveforms and context on the left; all sixteen pad/slice targets together on the right. Events shows its native piano roll and playhead on the right, with selected-note details and event velocities on the left. Routing diagrams, keyboard and plug-in names appear on the right; plug-in chains and source graphs stay on the left. Navigate shows all eight workspace icons aligned with their display buttons. Position, length and pitch use musical notation; their underlying encoder bindings remain unchanged. The same eight parameter bindings used by the existing engine are retained. File loading, waveform indexing and color drawing run outside live input dispatch. USB output keeps only the newest pending snapshot. It replaces each changed display with a complete frame and reuses the static scene while redrawing playheads. Partial rectangle updates are disabled after physical testing showed stale screen contents. Snapshot generation targets 30 Hz; actual display refresh is limited by rendering and USB transfer time. Saturated group/role colors replace the muted study palette. Active buttons use full brightness, inactive buttons dim, and unavailable actions remain off. Rendering and USB processing stay outside the audio thread.

Brightness, left/right contrast, inversion, pad sensitivity and curve are stored under the MK3 controller profile. They do not change the other controllers' preferences.

## Audio and MIDI

Select the MK3 under Settings → Audio → Interface. It exposes two input channels and four output channels. Main L/R use outputs 1/2; headphones use 3/4. Assign the desired main, cue and per-Sound/Group output routes using the existing routing controls. Hardware knobs control analog input/output levels; this device does not expose additional ALSA mixer gain controls.

The DIN MIDI input and output appear as **Maschine MK3 MIDI 1** under MIDI input/output settings. USB audio and MIDI stay attached to their Linux drivers; the display transport claims only USB interface 5.

## Verification

The attached MK3 passed all 101 calibration steps: buttons/LEDs, encoders, touch sensors, pads, RGB and the Smart Strip. Local and ARM tests cover framing, RGB565 colors, pad order, releases/retriggers, encoder wrap, device preferences and shared surface regressions. A separate ALSA test opened four playback channels and two capture channels at 48 kHz with no reported errors; the MIDI port opened in both directions. Physical audio listening, DIN cable transmission, live performance load, pedal behavior and extended workflow acceptance remain hardware checks, not automated-test guarantees.

Protocol facts were cross-checked against the device descriptors and the public hardware map at https://github.com/autotel/maschine-mk3-linux. The Python driver implementation is original to this project. The supplied DejaVu fonts retain their complete license in `assets/fonts/LICENSE-DejaVu.txt`.


Display transport verification (2026-10-23): the native frame is a 16-byte
rectangle header, one 0x00 literal command with a 24-bit count of pixel pairs,
RGB565 bytes, 0x03 blit and 0x40 end. No extra 0x02 commands are sent. Independent
references: [ni-controllers-lib LCD transport](https://github.com/asutherland/ni-controllers-lib/blob/master/lib/components/output/ni_lcd_displays.ts)
and [MK3Kit display protocol](https://github.com/chaoyi-ai/MK3Kit/blob/main/Sources/MK3Kit/MK3DisplayProtocol.swift).
Full-frame transport remains enabled pending physical confirmation after the
reported mixed/shifted views; software packet tests alone do not confirm LCD output.


Display acceleration: `mk3_pixels.so` is an optional, display-only CMake target.
It packs RGB565 and encodes lossless repeated pixel pairs (0x01) interspersed
with literal runs (0x00). Every changed screen still overwrites all 480x272
pixels; no dirty rectangles or skip commands are used. If the helper is absent,
portable RGB565 conversion and uncompressed full-frame transfer remain available.
The renderer caches text rasterizations (1024 bounded entries). No audio code or
controller input timing is changed. Native packets are independently decoded in
regression tests to verify complete and exact pixel replacement.


Stability hold: after a spontaneous Pi reboot during the first accelerated test,
the optional native helper is disabled by default. `MACHINISTA_MK3_NATIVE=1` is
reserved for isolated diagnostics, not the supported runtime setting. The reboot
cause is not established; previous-boot logs were volatile. Damaged newly written
helper files were recovered and flushed to disk. Text caching remains enabled,
uncompressed full-screen transfer is active, and the user confirmed stability.
Current performance is still limited; do not advertise a sustained 30 fps.

Pad trigger calibration: MK3 report 0x02 distinguishes light PressOn contacts
(0x00, PressOff0x20) from firmware strikes (NoteOn0x10, NoteOff0x30). Both are
now handled. PAD SENS controls a software contact/pressure threshold (higher
sensitivity lowers the threshold); PAD CURVE controls velocity response. MK3
PAD SENS no longer multiplies velocity. Only an armed contact can start a note
from pressure; idle pressure does not. Firmware promotion cannot double an
already sounding contact; release and ordinary deliberate retriggers are kept.
Pad1 measured trace had27light contacts and17strikes; atdefault100 the corrected
path recognizes44on/offpairs, versus17strikes before. Other controllers unchanged.

The accelerated output now uses `build/mk3_frame_encoder`, an isolated stdin/stdout
helper rather than loading a native library into Python. Only RGB images and
bounded complete display packets cross its pipes. It has a 128 MiB address-space
limit, no USB/audio handles, and terminates when its renderer closes the pipe.
RGB565 conversion and lossless full-frame literal/repeat encoding run there.
The parent checks packet size/header/footer and imposes a 500 ms deadline. Failure
closes the helper and falls back to the portable complete-frame encoder. The old
`MACHINISTA_MK3_NATIVE` ctypes optimization remains disabled.
Build the CMake `mk3_frame_encoder` target for the destination CPU; the release
native payload automatically includes it. A missing executable retains compatible
full-frame output. `display_timing.display_updates` counts actual changed screen
cycles for measurement, whereas `output_frames` also includes unchanged snapshots.

In Events, every selected note has a white outline. Hold physical SELECT or the
SELECT display button and turn the master, EVENT or POSITION encoder to extend
a time selection from the current cursor, restricted to the selected Sound/pad. Turn back to shrink it; release SELECT
to retain the selected notes. The orange time band appears immediately while
holding SELECT. Tapping the SELECT display button toggles the current note.

The shared group/transport/BPM/position row appears only on the left display. Right-side headings and body artwork move up by 26 native pixels; softkeys and encoder footers retain their hardware alignment. Sound OUTPUT uses a square 4x4 pad grid in the current group color, with the selected pad fully lit (pad 1 bottom left, pad 16 top right). A Sound without a sample waveform also uses the pad grid as its left-side overview.
