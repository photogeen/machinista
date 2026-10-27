# Machinista 0.1.0-beta.10 — Pi 4 / Pi 5

## First installation

Download `machinista-0.1.0-beta.10-pi4-pi5.img.xz` and `SHA256SUMS` from this
release. Verify the checksum, then write the compressed image with Raspberry Pi
Imager (Use custom). Use a spare SD card of 8 GB or larger and complete write
verification. Writing an image erases the selected card. Retain the image's
prepared user/network configuration rather than applying Imager customizations.

On first boot allow two minutes for card expansion and a possible restart.
With no router connection, join `Machinista-XXXX` (last four Wi-Fi MAC hex digits),
password `machinista`, then open http://10.42.0.1:8080. Set up your router in Wi-Fi;
rejoin that network and open http://machinista.local:8080. Ethernet also works.

The system account is `machinista`, initial password `machinista`. SSH is initially
disabled and can be enabled in System/WebUI. Shut down through System > Power
or the WebUI before unplugging power. The WebUI has no login; use a trusted LAN.

## Included

- Current engine and workflows for Mikro MK1/MK2, MK1/MK2, MK3 and Maschine+
  in controller mode, with per-device display/pad settings.
- Built-in Machinista Synth, 264 original sounds in 13 category banks plus Init.
- 32 newly programmed Oberheim-style OB-Xd patches in four original CC0 banks.
  OB-Xd itself is installed separately; these banks become playable after that.
- WebUI sample/project transfers, Sounds/patch-bank management and synth editor.
- Signed Beta/Release updater available to everyone.
- Eight English/German controller manuals.

The sample library and initial project are empty. No external LV2 binaries,
manufacturer ROMs, downloaded commercial banks or personal data are included.
Optional ARM64 plug-ins and matching sources are in the linked add-on repositories.
The separate OB-Xd patch ZIP permits manual import on an existing installation.

## Beta qualification

ARM64 build, native tests, Python regressions, image service/WebUI smoke tests,
file readback and checksum reports accompany this build. Hardware cold boot,
controller/audio operation, reconnect, Wi-Fi and first-install tests on your
actual Pi remain necessary. A QEMU ARM VM does not emulate Raspberry Pi hardware.
This is a test beta, not a guarantee of completed Pi 4/Pi 5 hardware qualification.
