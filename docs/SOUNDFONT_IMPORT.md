# Native SoundFont import

SoundFont instruments can become portable native sampler Sounds. No FluidSynth or LV2 instrument is required for playback. This is a first-stage SF2 converter, not a complete SoundFont synthesis engine.

## Workflow

1. Open **WebUI → Sounds → Import SoundFont** and upload an uncompressed `.sf2` file.
2. Select its instrument and click **Inspect instrument**. Review the zone count, compatibility notes and any blocking errors.
3. Accept the compatibility notes, choose a Sound name, folder and tags, then click **Import native Sound**.
4. Close the importer. The instrument appears in the Sounds library. Select a destination pad and use **Load on selected pad**, or open **BROWSE → SOUNDS** on the controller and load it there. Stop transport and recording before loading.
5. Enable Keyboard mode to play pitches, use Chords, or play a connected MIDI keyboard. The imported zones remain editable through the existing sampler controls and WebUI zone editor.

Imported Sounds own copies of their extracted samples. Removing the original SF2 upload with **Remove upload** does not remove those Sounds. Importing does not change the currently selected pad automatically. Uploads are retained locally for importing other instruments from the same font.

## Mapping and compatibility

The converter reads PCM 16-bit and 24-bit SF2 samples, preset/instrument global and local generators, key and velocity ranges, root notes, fine/coarse tuning, attenuation, pan, sample offsets and sustain loops. It maps a shared envelope and basic filter to the native sampler. Existing native sampler settings determine playback; original SoundFont modulation and velocity/envelope curves are not reproduced exactly.

The inspection explicitly reports differences before import:

- Per-zone envelopes and filters cannot all be reproduced by the shared native settings. The first zone supplies those settings.
- Custom modulators, modulation LFOs, delay/hold stages, SoundFont-specific resonance, scale tuning, exclusive classes and fixed-key/velocity behavior are not fully mapped.
- Stereo members remain separate mono zones with their explicit SF2 panning; implicit stereo-link behavior is not reconstructed.
- Continuous loops become sustain loops and stop looping on note release. Empty loop markers within the sample bounds can be repaired to a full-sample loop, with an explicit note. Other invalid loop bounds block import.
- ROM samples, compressed SF3 samples and unsupported sample types block import.

A `SoundFont.json` sidecar in each imported Sound records its source preset and compatibility notes. The importer does not ship any third-party SoundFonts.

## Limits

Uploads: 512 MiB per file, 64 stored fonts. Instruments: 128 native zones, 64 MiB decoded audio per sample region, 256 MiB total unique decoded sample data, and 512 MiB encoded Sound sample storage. A free-space reserve is kept. Large or unsupported instruments are rejected before extraction rather than partially imported.

Conversion runs on a low-priority background worker. File upload/import can still use CPU and storage bandwidth, so finish large imports before a critical performance.
