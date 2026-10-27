# Machinista

[![Source and workflow checks](https://github.com/photogeen/machinista/actions/workflows/ci.yml/badge.svg?branch=beta)](https://github.com/photogeen/machinista/actions/workflows/ci.yml)

[Repository](https://github.com/photogeen/machinista) · [Issues](https://github.com/photogeen/machinista/issues)

A standalone sampling groovebox for Raspberry Pi, controlled by legacy and
current Maschine hardware. The audio engine runs in C++20; controller workflows,
color/monochrome displays and the local WebUI are implemented in Python.

**Status: beta.** Raspberry Pi 4 / Pi 5 with 64-bit Raspberry Pi OS are the
primary target. Automated Linux tests do not replace hardware/audio qualification.
See [licensing status](LICENSING.md) before reusing or redistributing the code.

## Features

- Sample recording, editing, manual/grid/transient slicing, zones and multisamples.
- Pattern recording, step sequencing, note editing, scenes and song arrangement.
- Keyboard, scales, custom chords, note repeat and automation.
- Native four-oscillator Machinista Synth with original Factory patches/wavetables.
- Live performance effects and the native Ducktor sidechain ducker.
- Optional LV2 instruments/effects, parameter pages, preset banks and saved Sounds.
- Audio Loops, resampling, Bounce to Pad and external/LV2 autosampling.
- ALSA audio routing, supported USB/HAT interfaces, MIDI and Bluetooth MIDI.
- Local WebUI for samples/projects/Sounds, synth editing, plug-in installation,
  Wi-Fi configuration, storage and system controls.

## Controller support

| Controller | Displays |
| --- | --- |
| Maschine Mikro MK1 / Mikro MK2 | Single monochrome |
| Maschine MK1 / MK2 | Dual monochrome |
| Maschine MK3 | Dual color |
| Maschine+ in controller mode | Dual color |

Controller mode requires a host Pi; this project does not replace Maschine+
standalone firmware. Device-specific hardware tests remain necessary.

## Start here

- [Build and test from source](docs/BUILD.md)
- [Image installation and first boot](docs/INSTALL.md)
- [Architecture and source layout](docs/ARCHITECTURE.md)
- [Preparing GitHub and release branches](docs/GITHUB_PUBLISH.md)
- [Controller manuals](docs/USER_MANUALS.md)
- [WebUI](docs/WEB_UI.md), [Sounds and autosampling](docs/SOUNDS_AND_AUTOSAMPLER.md)
- [Plug-in profiles and banks](docs/PLUGIN_PROFILES.md)
- [Factory synth collection](docs/synth/FACTORY_BANK.md)

The public source export includes original Factory assets and reproducible test
fixtures. It excludes personal samples, projects, credentials, ROMs, recorded
hardware captures, disk images and optional third-party LV2 binaries/banks.
Images and generated manuals belong in release assets, not Git source history.

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

One image includes the updater for everyone, with Beta and Release channels. Signed-feed setup and a real SD-card update test are required before application updates can be offered.
