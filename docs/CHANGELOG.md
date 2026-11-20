# Changelog

## 0.1.0-beta.22 — 20 November 2026

- PAD SENS now adjusts actual pad trigger thresholds on Maschine MK1/MK2 and
  Mikro MK1/MK2. Lower values reject weaker contacts; higher values admit lighter
  hits. The setting is saved separately per controller and applied without a
  reader or audio-engine restart, including reconnects.
- Calibrated the low-sensitivity range against measured MK2 strikes:25 selects
  a1600-count contact threshold,100 keeps the existing100-count default and200
  selects61counts. Existing release/retrigger timing guards are retained.
- PAD CURVE and FIX LEVEL control velocity response; PAD SENS no longer doubles
  as velocity gain on legacy controllers. MK3/Maschine+ firmware strikes now
  respect their controller-specific sensitivity threshold too.
- Controller diagnostics confirm the sensitivity applied by the native reader.
  The hardware-page curve now shows velocity response independently of sensitivity.
- Plus is the default MK3/Maschine+ color scheme (other schemes remain available).
  Editing previously assigned slices updates them immediately without another APPLY.
- Refreshed EN/DE PDF and HTML manuals, installation image and signed beta OTA.

MK2 pad response and the backlight comparison were confirmed on the development
unit. The backlight comparison used brightness100; other users' saved brightness
values are preserved. Other controller sensitivity changes have software-test
coverage; physical calibration across all units is not claimed.

The experimental desktop port remains separate from this Pi release.
