# Architecture

| Path | Responsibility |
| --- | --- |
| app/ | Project model, controller state/workflows, display snapshots, local services |
| src/audio/ | Native sampler/synth, sequencer, LV2 hosting, routing and DSP |
| src/controller/ | Native USB/HID input decoders |
| tools/ | Entrypoints, diagnostics, bank tools, manual/image tooling |
| web/ | Local browser UI and its assets |
| deploy/ | Generic systemd, udev, Samba and updater examples |
| tests/ | Python/native regressions and bounded original fixtures |
| captures/*.json | Sanitized generic protocol maps only in the export |
| assets/ | Fonts/notices, branding, illustrations and Factory declarations |
| presets/ | Only declared original Factory banks/wavetables in the export |

Audio/recording deadlines have priority over display work. USB transport,
controller output, file jobs, preset catalog updates and native rendering use
separate workers where required. Display snapshots must not run file decoding
or plug-in scanning in the audio callback.

Runtime state belongs in config/, projects/, samples/, cache/, exports/ and
managed preset storage. Those local files do not belong in Git. Generated images,
manual PDFs and native binaries are separate release artifacts.

Controller profiles adapt the shared engine and workflow to each device.
Color and monochrome rendering share state but have distinct renderers.
See app/controller_inputs.py, app/controller_output.py, app/native_sequence.py,
app/runtime_audio.py and app/live_banks.py for the important boundaries.
