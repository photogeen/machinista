# Optional LV2 ports

Machinista's core repository contains the LV2 host and controller integration,
not third-party instrument/effect implementations or compiled plug-in bundles.
The built-in Machinista Synth and its original categorized factory patches remain
part of the standard installation. One image and updater are available to everyone.

Optional, independently licensed ARM64 ports are maintained separately:

| Port | Repository | Licensing |
| --- | --- | --- |
| Dexed | https://github.com/photogeen/machinista-dexed-lv2 | GPLv3; MSFA Apache 2.0; original dependency notices |
| OB-Xd (2DaT source) | https://github.com/photogeen/machinista-obxd-lv2 | GPLv3; original notices retained |
| RaffoSynth | https://github.com/photogeen/machinista-raffosynth-lv2 | MIT |
| Calf Essentials / Color | https://github.com/photogeen/machinista-calf-lv2 | LGPL/GPL components and original dependency licenses |

Each repository's Releases page provides ARM64 bundles, matching complete source,
build information and SHA256 checksums. Upload the **binary ZIP** through
WebUI > LV2 Plugins > Upload & check. Do not upload the source archive.
These are independent community ports, not official releases from upstream.
A different Linux runtime may require a rebuild.

The core license's resale restrictions do not apply to these separately licensed
third-party ports. Preserve their notices and meet source-distribution requirements.
Repository separation does not itself settle license compatibility of a combined
host/plugin product; assess the actual combination and licenses before distribution.

VirtualJV and Roland ROMs are excluded from this publication plan.

## Native synth bank consolidation

The standard factory collection has 264 unique sounds in 13 category banks,
followed by Init. The legacy aggregate Factory bank remains as compatibility data
but is hidden when every patch is covered by the category banks. Existing project
controls are not changed. The same category catalog is used by controllers and
Browser/WebUI Sounds. Incomplete or customized aggregate banks remain visible,
so sound data is never silently discarded.

## Original OB-Xd patch banks

Clean image payloads include 32 independently authored CC0-1.0 parameter patches:
**Machinista Bass**, **Machinista Keys**, **Machinista Leads** and **Machinista Pads**,
eight patches each. They are data only; OB-Xd itself remains an optional separate
installation. Once OB-Xd is installed, its banks appear on the controller and in
Sounds grouped by instrument and bank. Init remains last. No downloaded third-party
bank is included. Existing user banks are preserved.

For an existing installation, download `Machinista-OBXd-Patches.zip` from the
OB-Xd repository's Releases and import its four JSON files via WebUI > Patch banks,
with OB-Xd selected. Each bank may also be imported individually.
