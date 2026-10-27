# Machinista WebUI

Open http://machinista.local:8080 on the same network as the Pi. In hotspot mode,
join Machinista-XXXX with password machinista and open http://10.42.0.1:8080.
The WebUI intentionally has no login. The service is machinista-web.service.
All interface assets are local; no external packages or CDNs are loaded.

- **Samples:** browse SD/USB folders, preview audio, create folders and upload WAV
  or MP3 files. MP3 and floating-point WAV uploads are converted to sampler PCM.
  Existing files are never overwritten. Move selects another destination folder;
  Delete moves items to Trash, where Restore recovers them.
- **Sounds:** create multisample instruments, edit key/velocity zones, save the
  selected live LV2 Sound and plug-in strip, or run the Autosampler. See
  SOUNDS_AND_AUTOSAMPLER.md for English/German workflows on WebUI and controllers.
- **Projects:** upload and download project archives with their sample assets.
- **Chords:** import MPC progression and Ripchord chord presets and edit mappings.
- **LV2 Plugins:** upload compatible compiled Linux ARM64 bundles, check them,
  list installed plug-ins and remove them. No plug-ins are bundled in the image.
- **System:** resource information, graceful restart/shutdown, SSH switch and
  Wi-Fi network selection. SSH is disabled initially on a fresh image.

Preview plays through the browser device. On the controllers, samples are played
by the Pi's selected audio interface. Read-only USB media can be browsed; uploads
need writable storage. Moving library files does not rewrite saved project
references. Back up projects before changing cards or reorganizing sample paths.
