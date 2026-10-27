# Maschine+ in controller mode

Maschine+ uses the shared native 480x272 color views and the eight-encoder/4D
workflow of MK3, with its own `plus` input ownership and controller preferences.
It can operate alongside MK3. The Pi runs Machinista; this does not install or
replace the standalone operating system of Maschine+.

Observed device: Native Instruments USB 17cc:1820. Control HID is interface 5;
display-only bulk output is interface 6, endpoint 0x04. MK3 remains 17cc:1600
with display interface 5. Discovery, permission rules and each USB open are
scoped to the product. Audio, MIDI and DFU interfaces are not claimed/detached.

ALSA reports four playback channels and two capture channels, S32_LE with 24
valid bits, and 44.1/48/88.2/96 kHz capability. Machinista exposes its existing
supported rates, output routing and cue controls; capability reporting alone
is not an audio listening or MIDI cable test. Audio/MIDI use the existing
dynamic device discovery and are independently selectable from MK3 and HAT.

Brightness, left/right contrast, inversion, pad sensitivity and curve belong
only to the plus profile. Decoder MIDI-range velocity is not normalized a second
time. Pad triggering uses the shared MK3 contact/pressure implementation pending
physical sensitivity checks on this unit. All controller functions reuse engine
bindings rather than maintaining a separate editing implementation.

Validation: 61 local/ARM tests pass. New tests exercise ownership,
independent settings, velocity, native color views, PID validation and interface
separation. Guided hardware calibration completed all 101 steps with 101 matching results
and no skips. Installed after fresh idle verification and durable code/settings/project backup.
Both MK3 and Plus readers/displays are healthy in parallel. Four-channel playback
and two-channel capture at 48 kHz open successfully; raw MIDI opens both ways.
User confirmed normal BROWSE/SAMPLING/MIXER navigation, encoder changes and
keyboard-pad playing respond correctly with direct display and sound feedback.
Physical MIDI cable transmission, real reconnect and sustained-load tests remain
unverified.
