# Installation and first boot

Use an explicitly published, checksummed Machinista Pi4/Pi5 image. No image or
release-download URL is embedded in this source preparation before publication.

1. Back up existing work and use a spare SD card of 8 GB or larger.
2. Select the supplied .img.xz as a custom image in Raspberry Pi Imager. Retain
   its prepared account/network configuration and complete write verification.
3. Connect controller and audio interface, insert the card and power the Pi.
   Allow about two minutes for initial card expansion and a possible restart.
4. Select the desired Audio Interface and main/headphone routing in Settings.
5. Open http://machinista.local:8080 from the same local network. If no router is
   connected, join Machinista-XXXX (password machinista) and open
   http://10.42.0.1:8080 to configure the router connection.

The image account is machinista. Default password: machinista. SSH starts
masked and is enabled explicitly through the device/WebUI system controls.
Shut down through System > Power or the WebUI before removing power.

Public images exclude third-party LV2 binaries, commercial/downloaded banks,
ROMs, personal projects and sample collections. Original Machinista Synth
Factory assets remain included. Private tester editions have their own clearly
identified component list and accompanying source/license package.

A newly built image must still be cold-boot tested on the actual target board,
including audio, controller reconnect, storage and first-boot networking.
