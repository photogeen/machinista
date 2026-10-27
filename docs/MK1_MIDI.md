# MK1 DIN MIDI

The full-size MK1's rear MIDI IN and MIDI OUT sockets are available while its displays, pads and controls are in use. Connect the controller by USB as usual. No additional MIDI interface or kernel-module setup is required.

Open **Settings → MIDI** and select **Maschine MK1 MIDI DIN** for MIDI IN and/or MIDI OUT. Choose the receive/send channel and the existing keyboard/pad input mode to suit the instrument. MIDI OUT is used by live playing, the native sequencer and existing clock/transport options. MIDI IN uses the existing note, controller and clock handling. Enabling a port does not enable clock transmission or change its settings automatically.

The choice has a stable device ID and returns after reconnecting the MK1. The transient raw device number may change. The port is absent when the controller is disconnected; a stale bridge manifest is not advertised. Queued input from before selecting the port is discarded.

The MK1 uses the same USB interface for DIN MIDI and controls. Machinista owns that interface while connected, so these ports are integrated into Machinista's MIDI selection rather than exposed as separate ALSA card ports to other applications. MIDI bytes travel through a raw pseudo-terminal bridge; no MIDI parsing, synthesis or display work happens on the audio callback. Output runs independently of framebuffer writes. MIDI Clock, running-status messages and SysEx bytes retain their wire values; the application's existing MIDI feature set still determines how incoming messages are used.

## Verification

Automated tests cover USB framing, invalid packets, bidirectional raw transport, SysEx chunking, realtime bytes, the native sequencer MIDI writer, discovery, stale manifests and existing controller/MIDI regression tests. A physical DIN loopback or external instrument is still required to verify the rear connectors and cable electrically. For a loopback, connect MK1 MIDI OUT to MK1 MIDI IN; avoid enabling MIDI thru or an external feedback route during the test.

Protocol references: Linux caiaq [command constants](https://github.com/torvalds/linux/blob/v6.12/sound/usb/caiaq/device.h), [input dispatch](https://github.com/torvalds/linux/blob/v6.12/sound/usb/caiaq/device.c), and [MIDI framing](https://github.com/torvalds/linux/blob/v6.12/sound/usb/caiaq/midi.c). Bridge implementation is local to Machinista.
