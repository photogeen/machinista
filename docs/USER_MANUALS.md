# Controller user manuals

Edition: 27 October 2026, Machinista 0.1.0-beta.10 / Fokus V2.

`output/pdf/` contains separate illustrated English and German manuals for
Mikro MK1, full-size MK1, MK2 and MK3. Screens and menu names stay English in both
languages. Each guide has 40 workflow/reference chapters, linked contents,
workspace index, current screen atlas and shortcut/troubleshooting reference.
Topic-local illustrated continuation pages document WebUI operations and
Keyboard/CUSTOM chords; TOC page numbers and links include these pages.
The manuals contain 111 pages (Mikro), 103 pages (MK1/MK2),
and 160 pages per language (MK3).

This edition includes Live FX/recording, restored mode actions and pinning,
Scene Options/banks/Quantize, current Tap Tempo, custom chord imports/variations,
Sounds/Zones/Autosampler, WebUI file/project/plugin management, hardware mixer
levels and power controls. The MK1 guide uses its dedicated master encoders and
labelled confirmation actions instead of a nonexistent master push/ENTER.

The standard image includes Machinista Synth and its categorized Factory patches,
but no third-party LV2 plugins or personal samples. Install compatible ARM64
Linux LV2 bundles separately using the WebUI. The updater is available to everyone
with Beta and Release channels; installation requires a configured signed feed.

## Rebuilding

Run with Python including Pillow and ReportLab:

    python3 tools/build_user_manuals.py
    PYTHONPATH=. python3 tools/build_user_manuals_de.py
    python3 tools/verify_user_manuals.py

The generator uses disposable fixtures and the actual current renderers. It
never sends USB/audio commands and copies no private projects or samples.
German prose uses the same English pixels. Intermediate figures/catalogs and
build/overflow reports are under `tmp/pdfs/manual-assets/`. Generators reject
content extending into the footer. Final PDFs are rendered and visually checked.

### WebUI and Chord documentation revision

WebUI instructions accompany Browse/Library, project backup, LV2 installation,
Keyboard/Custom Chords, Zones, live LV2 patch capture, Autosampler, Wi-Fi and
system/power/SSH. Controller Keyboard instructions distinguish OFF/HARM/SET/
CUSTOM, preset/bank choice, strum/timing/velocity variations, voice editing,
MIDI LEARN (pitches only), recording and slice-mode limitations. Project chord
copies are distinguished from reusable library presets.

`assets/manual-web/` contains actual WebUI captures with illustrative data, not
private user data. Regenerate with `node tools/capture_manual_web.cjs` and an
installed Playwright browser. Optional MACHINISTA_PLAYWRIGHT and
MACHINISTA_CHROME select local module/executable paths. Screens remain English.

### 24 October 2026: MK3 and current editing workflows

The MK3 guide uses the actual 480 x 272 color renderer for both displays,
not enlarged monochrome artwork. It covers its dedicated CHANNEL, PLUG-IN,
SETTINGS, EVENTS, FOLLOW, KEYBOARD and CHORDS buttons, 4D encoder, Smart Strip,
VARIATION navigation (SHIFT + VARIATION for Grid/Swing/Quantize), four audio outputs/two inputs and DIN MIDI ports.
Controller wording is resolved separately in each guide; other-controller
instructions are excluded.

All editions now document the selected-pad-only Events time range, both SELECT
hold actions where available, EVENT/POSITION encoders, selected-note outlines,
FOLLOW recovery, stopped playhead position and moving keyboard viewport.
Ducktor and native SoundFont import have topic-local instructions. Existing
WebUI sample/project transfers, chords, Sounds/Zones, Autosampler, live patches,
synth editor/waves and network/system controls remain included.

The MK3 atlas contains 191 distinct render states; its larger figures use two
states per atlas page. MK3 contents are generated in two passes so continuation
pages do not shift chapter links. English menu labels and screen pixels are
identical in both language editions. Verification checks page margins, outline
destinations, required workflows, date and controller-specific wording, then
renders review sheets and updates both manifests and the all-manuals ZIP.
