Machinista 0.1.0-beta.6 · Raspberry Pi 4 / Raspberry Pi 5 · 64 bit

Write machinista-0.1.0-beta.6-pi4-pi5.img using Raspberry Pi Imager
(Use custom image), to an SD card of 8 GB or larger.
Do not apply Imager username/SSH customizations to this prepared image.
On first boot the root partition expands; allow two minutes and a possible reboot.

With no saved Wi-Fi router, join Machinista-XXXX (last four permanent Wi-Fi MAC
hexadecimal characters); WPA2 password: machinista.
Open http://10.42.0.1:8080 for library upload and Wi-Fi setup.
Select your router under WLAN and enter its password. The single internal Wi-Fi
radio changes networks. Rejoin your home Wi-Fi and open http://machinista.local:8080
(or the Pi's DHCP address). If login fails or the router disappears, the hotspot
returns. Existing router profiles are retried only when their SSID is visible.
A router need not have Internet access to remain connected.

SMB share: smb://machinista.local/Samples (Windows: \\machinista.local\Samples).
Username machinista, password machinista. The share exposes only the SD sample
library; USB sample sources remain available through the WebUI.

Empty Library/Kicks, Snares, Hi-Hats, Loops and a blank project are supplied.
LV2 effects and instruments are not bundled. Install compatible ARM64 Linux
.lv2 bundles through the WebUI Plugins page.

User/home/application: machinista / /home/machinista / /home/machinista/Machinista.
Console login: machinista / machinista. SSH is disabled in the distributable image;
source-device SSH keys, Wi-Fi passwords, projects and recordings are excluded.
WebUI intentionally has no login, as requested for this beta.

USB class compliant audio is detected automatically. Controller support includes
Mikro MK1 and Maschine MK2. Optional Raspiaudio ULTRA V3 may require
`dtoverlay=wm8960-soundcard` in /boot/firmware/config.txt if EEPROM detection
fails; this development-board-specific forced overlay is not enabled globally.

Pi 4 / Pi 5 kernels and boot firmware are included. A cold boot on a second Pi
and a Pi 5, hotspot connectivity and actual controller/audio operation must be
verified before describing this beta as hardware-validated.
Source code is included under /home/machinista/Machinista. Debian/Raspberry Pi
package versions and source repositories are recorded with the release manifest.

Audio > Interface Mixer exposes hardware gain/volume and switch controls when
the selected interface provides them. Pads can audition sounds inside Settings.
Back up projects through the WebUI Projects page before changing cards.

### SSH access

In the WebUI, open **System → SSH → Enable SSH**. The switch shows the actual
service state and the Linux login name. Changes persist across restarts. SSH is
off in a fresh image; enabling it creates missing host keys on that Pi and starts
OpenSSH on port 22. Existing passwords and authorized keys are unchanged.
Disabling SSH stops both the service and socket activation.

### WAV uploads

The WebUI accepts integer PCM WAV and converts 32-bit IEEE floating-point WAV
to sampler-compatible 32-bit PCM. Rate, frame count and RIFF metadata are kept.
Float files exceeding full scale are reduced uniformly to prevent clipping;
the upload result shows the gain adjustment. The original source file stays
unchanged. Float files copied directly through SMB are not converted.

### Managing samples and folders

Use **Move** beside a sample or folder to choose destination storage and folder,
then **Move here**. Existing entries are never replaced. Cross-storage moves
keep a recovery copy in Trash on the original storage. **Delete** moves an item
and its contents to Trash. Open **Trash** for the selected storage and choose
**Restore** to return an item to its original folder. If that folder has moved,
restore the folder first. Name conflicts are reported without replacing files.
Trash still uses storage space. Existing project references are not rewritten;
projects that reference moved or deleted library files may need sample relinking.

### MP3 samples

The controller Browser lists WAV and MP3 files on SD and mounted USB storage.
Enable **PREHEAR**, scroll to an MP3 to preview it, then **LOAD / ENTER** to assign
it to the selected pad. MP3 decoding runs in a background worker; the first
preview/load can take a moment. Rapid scrolling cancels stale previews. A
decoded WAV is kept under `cache/decoded-audio` on internal storage and saved
projects collect it like other sample assets. Do not clear that cache manually
while projects still reference it. The source MP3 is never altered. Quick
Browse returns to the original MP3 when its source storage is available.

Web uploads accept MP3 and WAV. MP3 uploads are saved as PCM WAV with the same
base name; existing WAVs are not overwritten. MP3s already on SD or USB can
also be previewed/downloaded directly in the WebUI. Float peaks above full
scale are reduced uniformly during conversion, with the gain shown for Web
uploads. The existing 64 MiB decoded-per-sample limit also applies to MP3.
FFmpeg is required and included by the image build recipe.

The Raspiaudio ULTRA HAT button toggles Speaker Mute when that HAT is the
selected audio interface. Headphones and the saved speaker level are retained.
The button is debounced; holding it does not repeat the toggle.
