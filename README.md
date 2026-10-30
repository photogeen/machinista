# Machinista

![Machinista logo](assets/branding/machinista-github.svg)

[![Source and workflow checks](https://github.com/photogeen/machinista/actions/workflows/ci.yml/badge.svg?branch=beta)](https://github.com/photogeen/machinista/actions/workflows/ci.yml)

[Repository](https://github.com/photogeen/machinista) · [Issues](https://github.com/photogeen/machinista/issues)

Make beats, play instruments and turn loops into songs - directly from your
controller. Machinista runs on a Raspberry Pi, so you can make music without
keeping a laptop connected. Use your own recordings or start playing with the
built-in Machinista Synth and its ready-made sounds.

**Machinista is currently a beta for Raspberry Pi 4 and Pi 5.** It is ready for
musicians to try and help test, but it still needs testing with different
controllers and audio devices. Save backups of work you want to keep.

[Beschreibung auf Deutsch](docs/OVERVIEW_DE.md)

## What can I make with it?

- **Beats:** play drums on the pads, record a repeating phrase, or place hits one
  step at a time. Correct individual notes afterwards.
- **Sample-based music:** record audio, load WAV/MP3 files, cut loops into playable
  slices, and turn several recordings into one keyboard instrument.
- **Synth parts:** play the built-in four-oscillator synth, choose a ready-made
  patch (a saved sound), and adjust it with the controller or browser editor.
- **Chords and melodies:** play notes across the pads, choose a scale, put a chord
  on one pad, or use Note Repeat and an arpeggiator for rhythmic patterns.
- **Whole songs:** combine Patterns (repeating phrases) into Scenes (song sections),
  then put those sections in order. Record knob movements as automation.
- **Live performances:** mute parts, balance sounds in the Mixer and play effects
  with the pads. Ducktor can lower one sound when another plays - for example,
  making room in the bass whenever the kick hits.
- **Audio loops:** record a loop that plays with your Pattern, or bounce a playing
  part to another pad to keep working with it as audio.
- **Extra instruments and effects:** install compatible LV2 plug-ins. LV2 is the
  add-on format; the public image does not include third-party plug-ins.
- **External gear:** play from a MIDI keyboard, control an external instrument,
  use supported Bluetooth MIDI devices, and choose audio inputs and outputs.
- **Easy file management:** open the WebUI (a browser control page) on a phone,
  tablet or computer to upload samples, back up projects and organize Sounds.

## What do I need?

A Raspberry Pi 4 or 5 with its power supply, an SD card of at least 8 GB, a
supported controller below, and a supported audio device for headphones or
speakers. A computer is needed to prepare the SD card. Afterwards, use the
controller to make music; the browser page is there when you want easier file
management or more detailed editing. The public image includes synth sounds,
but no drum samples or personal recordings.

## Controller support

| Controller | Displays |
| --- | --- |
| Maschine Mikro MK1 / Mikro MK2 | Single monochrome |
| Maschine MK1 / MK2 | Dual monochrome |
| Maschine MK3 | Dual color |
| Maschine+ in controller mode | Dual color |

For Maschine+, switch the unit to Controller mode and connect it to the Pi.
Machinista runs on the Pi; it does not replace the software inside Maschine+.

## Install the beta

[Download the Pi 4 / Pi 5 beta image](https://github.com/photogeen/machinista/releases/tag/v0.1.0-beta.10)
for first installation. Use the `.img.xz` and verify `SHA256SUMS`, then write it to
a spare SD card with Raspberry Pi Imager. Writing erases that card. First boot,
hotspot and account instructions are in [Installation](docs/INSTALL.md).

Existing installations use System / WebUI > Updates. A new SD image is needed
for first installation, not every application update. Beta images still need
real controller/audio and Pi-model testing.

## Screens

Actual application renderers with illustrative project data, not hardware photos.
Mikro images also represent Mikro MK2; MK2 screens represent MK1/MK2;
MK3 color screens also apply to Maschine+ in controller mode.

| Feature | Mikro | MK1 / MK2 | MK3 / Maschine+ |
| --- | --- | --- | --- |
| Synth and patch banks | ![Mikro synth](assets/screens/synth-mikro.png) | ![MK2 synth](assets/screens/synth-mk2.png) | ![MK3 synth](assets/screens/synth-mk3.png) |
| Slice editing | ![Mikro slices](assets/screens/slicing-mikro.png) | ![MK2 slices](assets/screens/slicing-mk2.png) | ![MK3 slices](assets/screens/slicing-mk3.png) |
| Events / note editing | ![Mikro events](assets/screens/events-mikro.png) | ![MK2 events](assets/screens/events-mk2.png) | ![MK3 events](assets/screens/events-mk3.png) |
| Mixer | ![Mikro mixer](assets/screens/mixer-mikro.png) | ![MK2 mixer](assets/screens/mixer-mk2.png) | ![MK3 mixer](assets/screens/mixer-mk3.png) |
| Custom chords | ![Mikro chords](assets/screens/chords-mikro.png) | ![MK2 chords](assets/screens/chords-mk2.png) | ![MK3 chords](assets/screens/chords-mk3.png) |
| Live effects | ![Mikro live effects](assets/screens/live-fx-mikro.png) | ![MK2 live effects](assets/screens/live-fx-mk2.png) | ![MK3 live effects](assets/screens/live-fx-mk3.png) |

[Full-size screen gallery](assets/screens/README.md).

## Learn to use it

Start with [installation and first sound](docs/INSTALL.md), then choose the
[illustrated manual for your controller](docs/USER_MANUALS.md). Each manual
starts with setup, a first sound and a first beat. You can look up the editing
and reference chapters later; you do not need to learn every page first.

The [WebUI guide](docs/WEB_UI.md) explains the browser controls. For making
instruments from several recordings, see [Sounds and Autosampler](docs/SOUNDS_AND_AUTOSAMPLER.md).

## For developers

You do not need to build or program anything to use the prepared SD-card image.
If you want to change the software, see [building from source](docs/BUILD.md),
[software structure](docs/ARCHITECTURE.md), [plug-in profiles](docs/PLUGIN_PROFILES.md)
and [release preparation](docs/GITHUB_PUBLISH.md).
The audio engine uses C++20; controller and browser workflows use Python.
The public repository excludes personal samples, projects, passwords, ROMs and
third-party LV2 binaries. Images and PDFs are provided as release downloads.

## Network access

On a configured image the WebUI is available at `http://machinista.local:8080`.
Without a router connection, the fallback hotspot is `Machinista-XXXX`, password
`machinista`, with the WebUI at `http://10.42.0.1:8080`.
The WebUI has no login and is intended for a trusted local network. Keep it off
public internet interfaces. See [security guidance](SECURITY.md).

## Contributing and licensing

Read [CONTRIBUTING.md](CONTRIBUTING.md), [LICENSING.md](LICENSING.md) and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Original code uses the custom [Machinista Source-Available License](LICENSE.md):
free forks and commercial music production are permitted; software resale and
paid activation require separate permission. Third-party licenses remain intact.

Machinista is an independent project. Hardware and plug-in product names
identify compatibility; no manufacturer sponsorship or endorsement is implied.

## Optional plug-ins

Third-party LV2 bundles are available from the separate [plug-in port repositories](docs/PLUGIN_PORTS.md). They retain their upstream licenses and are installed through the WebUI. Machinista Synth and its original factory patches are included.

One image includes the updater for everyone, with signed Beta and Release channels. Beta currently supplies application updates; Release becomes available when a stable version is published. Projects, samples and installed plug-ins are retained. Hardware update/recovery testing remains part of beta qualification.
