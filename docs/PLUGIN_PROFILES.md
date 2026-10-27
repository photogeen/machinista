# Plugin profiles and preset banks

Profiles live in `app/plugin_profiles_data/*.json`. The plugin URI selects its
profile. Unknown plugins retain their ordinary LV2 metadata and controls.

OB-Xd's profile describes the ordered eight-encoder pages, control labels,
switches and discrete choices, original engine parameter indices and Init
values. Its first page provides BANK and PATCH. MK1/MK2 show their numbers on
the left and names on the right. Mikro shows the selected name as the parameter
value. All 77 native controls remain reachable. Bank and patch selectors use
the existing deliberate-turn encoder filtering, not the continuous level rate.

The VirtualJV single and multi profiles point to their existing parameter JSON
and specialized providers. Their ROM decoding and multitimbral behavior stay
in those providers. Adding a JSON layout alone cannot implement an arbitrary
plugin's proprietary patch format; a matching provider is necessary.

## Controller units and page order

Continuous LV2 controls whose native range lies within 0–1 (including a small positive
minimum such as Raffo Release at 0.01) are displayed as whole-number 0–100%. A normal encoder step changes one percentage point; SHIFT on MK1/MK2
or holding the Mikro encoder changes 0.1 percentage point. Imported fractional
values are preserved. Rendering does not rewrite controls, presets, automation
or projects; all retain native values. Switches, enumerated choices, integer
controls and parameters with other ranges keep their existing units. These
are equal control increments, not a change to the synthesizer's DSP curves.

Tune uses cents with one-cent normal and 0.1-cent fine increments. Profile
metadata stores the native-to-display scale/offset: OB-Xd master Tune maps to
−100…+100 cents, its oscillator tuning to 0…4800 cents, Dexed master Tune to
−200…+200 cents, and Raffo oscillator tuning converts native semitones to cents.
These scales follow the installed DSP sources. Dexed operator fine/detune retain
the DX7 parameter units, which are not a linear cent offset. OB-Xd STEP (pitch
quantization), when enabled, still quantizes oscillator pitch in the synth.
Saved controls always remain native values. Dexed output gain has an explicit
percentage unit (native 0–2 becomes 0–200%, unity gain is 100%).

OB-Xd has eleven eight-encoder pages. PATCH / TONE puts bank, patch, volume,
cutoff, resonance, filter envelope amount and amp attack/release first. Both
ADSR envelopes follow on page two, then oscillator tuning/mix and shapes,
filter, LFO, modulation, global, performance, character and voice pan pages.
Every native control remains available. Common controls repeat intentionally.

The ordering is a Machinista workflow choice informed by the OB-Xd panel,
[Dexed's operator/algorithm design](https://asb2m10.github.io/dexed/) and
[RaffoSynth's oscillator/filter/envelope controls](https://github.com/zynthian/moog).

## User workflow

1. Install `obxd-linux-arm64.zip` using WebUI > LV2 Plugins > Upload & check.
2. Unzip a downloaded OB-Xd sound pack. Under **Preset banks**, import its
   **OB-Xd 2** `.fxb` bank or `.fxp` patch. Version 3 banks use a different format.
3. Load OB-Xd in the first instrument slot of the desired Sound. On its first
   parameter page turn BANK, then PATCH. Each bank starts at its first patch.
4. Edit the remaining parameters and save the project or Sound as usual.

Patches are parameter snapshots in the project's existing plugin controls.
Selecting a patch updates the current instance's parameters; it does not
recreate the instrument. Bank selectors themselves are not automation lanes.
Existing native parameter automation continues to work.

Imported banks are data-only JSON under `presets/plugin-banks/obxd/`. Removing a
bank in WebUI leaves saved project/Sound patches playable. Their bank label
becomes MISSING BANK; choosing a different bank explicitly replaces the patch.
Actual bank data are cached outside the render thread; unchanged files are
not reparsed on each UI update.

Command-line alternative:

```sh
python3 tools/import_plugin_bank.py /path/to/Bank.fxb --root /path/to/Machinista
```

The importer checks bounded VST/legacy JUCE XML input, normalized finite control
values and plugin identity. No uploaded code is loaded during bank import.
JSON banks require a complete parameter snapshot and the matching plugin URI.

Stamina by Daniel Stawczyk (128 presets) is available separately from
https://www.discodsp.com/en/soundware/ and includes an OB-Xd 2 bank. It is used
only as a separately imported test bank on the development Pi. The public clean
image contains no OB-Xd executable, third-party banks, samples or ROMs.

## Dexed / DX7

The Dexed URI `https://github.com/dcoredump/dexed.lv2` uses
`app/plugin_profiles_data/dexed.json`. All 168 native controls are available on
25 pages aligned to eight encoders. The first page contains BANK/PATCH, Gain,
Algorithm, Feedback, Cutoff, Resonance and Transpose. The next pages provide
all six operator levels, the OP1 envelope, and an operator frequency overview.
LFO and the individual operator oscillator/envelope/scaling pages follow, then
performance, pitch envelope and MIDI controllers. Operator levels and rates
retain their native 0–99 units. Algorithm/Feedback repeat on scaling pages so
operators keep the same layout. Categorical switches use deliberate knob travel.

Install the separate `dexed-linux-arm64.zip`, then select **Dexed** in WebUI >
LV2 Plugins > Preset banks and upload a `.syx` file. Accepted formats are original
DX7 32-voice VMEM banks (4104 bytes per message) and single-voice VCED dumps
(163 bytes). A file may concatenate complete dumps, up to 256 patches. The
importer checks Yamaha ID, message type/size, 7-bit data, checksum and every
parameter's native range; unrelated SysEx types are rejected. This is a file
import, not a command sent to external MIDI hardware.

```sh
python3 tools/import_plugin_bank.py /path/to/Cartridge.syx --profile dexed
```

The importer handles the packed operator fields and reversed OP6-to-OP1 order.
The LV2 port's algorithm is 1–32, whereas DX7 data use 0–31. Detune is exposed
as −7…+7 instead of 0…14. Imported patches retain safe defaults for controls
outside the DX7 voice data (output filter, engine and performance controllers).
Native values are saved, not normalized 0…1 approximations. The same project
persistence, missing-bank behavior and bank removal rules apply as for OB-Xd.

The development Pi has the separately imported ROM1A bank from the existing
user-supplied source package (32 patches). It is not added to profile JSON or
the public clean image. No plugin or voice bank is included in that image.

## RaffoSynth

Install the optional `raffosynth-linux-arm64.zip`, then import the separate
`starter-bank.json` under **Preset banks > RaffoSynth**. It contains eight
original Machinista parameter recipes. The first instrument page offers BANK,
PATCH, Volume, Cutoff, Resonance, Glide, Attack and Release. Four oscillator
pages follow the combined amp/filter envelope and oscillator mixer pages
(seven pages total). All 32 native controls remain reachable; repeated global fields keep oscillator
pages aligned to the eight encoders.

The headless adapter uses URI `urn:machinista:ports:raffosynth`, independently of
the legacy plugin. It is monophonic with four oscillators, last-note priority,
sustain and panic. Original fixed-velocity amplitude is preserved. It has no
ROM requirement. It is based on the portable upstream oscillator and EQ code,
with MIDI/lifecycle, filter-state and numeric corrections documented in its
build package. The x86 assembly and GTK editor are not used.

Legacy RaffoSynth GUI `.dat` files contain 32 ordered numeric values. Upload one
as a single named patch, or upload a Machinista JSON bank containing multiple
complete snapshots. Data are validated against implemented choices and ranges;
unsupported waveform4 and invalid values are rejected rather than imported as
silent/corrupt sounds. Native Minimoog/SysEx/DX7 banks are different formats.

```sh
python3 tools/import_plugin_bank.py /path/to/Bass.dat --profile raffosynth
```

The starter bank and plugin remain separate addons. They are not copied into
controller profile data or the public clean image.


## Instrument banks in Sounds

Installed Machinista Synth, Dexed, OB-Xd and RaffoSynth banks also appear under Browser → Sounds → instrument → bank. Choose a destination pad, then load a patch to replace that pad with the instrument and its complete parameter snapshot. Missing plug-ins are excluded. Factory wavetables are retained. Catalog updates run on the background preset worker while transport is idle.

The same entries appear in WebUI Sounds and can be loaded there. Bank entries are read-only; load one and use Save current Sound / LV2 patch for an editable independent Sound. Removing a bank does not alter patches already loaded into projects.
