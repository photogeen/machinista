"""Nonblocking raw USB MIDI routing, with explicit note-off and panic handling."""
from app.note_tokens import NoteTokens
import errno
import os
import time


def flush_bridge_input(fd,path):
    # Discard bytes accumulated while the DIN input was not selected. Never
    # change termios/flush on real ALSA raw-MIDI device nodes.
    if path.startswith('/dev/pts/'):
        import termios
        termios.tcflush(fd,termios.TCIFLUSH)


class MidiBackend:
    def __init__(self):
        self.ports = {}
        self.input = self.output = None
        self.channel = 0
        self.pending = bytearray()
        self.off = []
        self.status = None
        self.data = []
        self.events=[]
        self.tokens=NoteTokens();self.auto_token=0

    def configure(self, devices, settings):
        paths = {d.key: d.path for d in devices}
        selected_in = paths.get(settings['midi_in'])
        selected_out = paths.get(settings['midi_out'])
        channel = settings['midi_channel']-1
        expected = set(p for p in (selected_in, selected_out) if p)
        if (selected_in, selected_out, channel) == (self.input, self.output, self.channel) and expected == set(self.ports):
            return
        try:
            self.panic()
        except OSError:
            # The previous ALSA device may already have disappeared.
            pass
        self.close_ports()
        try:
            for path in sorted(expected):
                # Append permits the native sequencer and live writer to share
                # an output while keeping each short MIDI write atomic.
                self.ports[path] = os.open(path, os.O_RDWR | os.O_NONBLOCK | os.O_APPEND | os.O_NOCTTY)
            if selected_in:flush_bridge_input(self.ports[selected_in],selected_in)
        except OSError:
            self.close_ports()
            raise
        self.input, self.output, self.channel = selected_in, selected_out, channel

    def port_fd(self, path):
        fd = self.ports.get(path)
        if fd is None:
            raise OSError(errno.ENODEV, 'MIDI device disconnected', path)
        return fd

    def send(self, message):
        if not self.output:
            return
        if len(self.pending)+len(message) > 4096:
            raise OSError('MIDI output queue overflow')
        self.pending.extend(message)
        self.flush()

    def flush(self):
        if self.output and self.pending:
            try:
                count = os.write(self.port_fd(self.output), self.pending)
                del self.pending[:count]
            except BlockingIOError:
                pass

    def hit(self,slot,velocity,note=None,channel=None,duration=0.1,voice_token=0):
        note = 36+slot if note is None else note
        channel = self.channel if channel is None else channel-1
        if duration is not None and voice_token==0:self.auto_token-=1;voice_token=self.auto_token
        self.tokens.start((channel,note),voice_token)
        native=getattr(self,'native_command',None)
        if native:native(f'external_note {channel} {note} {max(1,min(127,velocity))}')
        else:self.send(bytes([0x90 | channel, note, max(1, min(127, velocity))]))
        if duration is not None:self.off.append((time.monotonic()+duration,note,channel,voice_token))

    def note_off(self,note,channel=None,voice_token=None):
        channel=self.channel if channel is None else channel-1
        for _ in range(self.tokens.release_count((channel,note),voice_token)):
            native=getattr(self,'native_command',None)
            if native:native(f'external_note {channel} {note} 0')
            else:self.send(bytes([0x80|channel,note,0]))
        self.off=[item for item in self.off if not (item[1:3]==(note,channel) and (voice_token is None or item[3]==voice_token))]

    def poll(self):
        now = time.monotonic()
        remaining = []
        for deadline, note, channel, token in self.off:
            if now >= deadline:
                for _ in range(self.tokens.release_count((channel,note),token)):
                    native=getattr(self,'native_command',None)
                    if native:native(f'external_note {channel} {note} 0')
                    else:self.send(bytes([0x80 | channel, note, 0]))
            else:
                remaining.append((deadline, note, channel,token))
        self.off = remaining
        self.flush()
        notes = []
        if not self.input:
            return notes
        try:
            data = os.read(self.port_fd(self.input), 1024)
        except BlockingIOError:
            return notes
        notes=self.parse(data)
        return notes

    def parse(self,data):
        notes=[]
        for byte in data:
            if byte>=0xf8:
                self.events.append((byte,()));continue
            if byte>=0x80:
                self.status=byte if byte<0xf0 or byte==0xf2 else None;self.data=[];continue
            if self.status is None:continue
            self.data.append(byte)
            length=1 if self.status&0xf0 in (0xc0,0xd0) else 2
            if len(self.data)==length:
                if self.status==0xf2 or self.status&15==self.channel:
                    self.events.append((self.status,tuple(self.data)))
                    if self.status&0xf0==0x90 and self.data[1]>0 and 36<=self.data[0]<52:notes.append((self.data[0]-36,self.data[1]))
                self.data=[]
                if self.status==0xf2:self.status=None
        return notes

    def take_events(self):
        events,self.events=self.events,[];return events

    def panic(self):
        try:
            if self.output:
                for channel,note in list(self.tokens.active):
                    for _ in range(self.tokens.release_count((channel,note))):
                        native=getattr(self,'native_command',None)
                        if native:native(f'external_note {channel} {note} 0')
                        else:self.send(bytes([0x80|channel,note,0]))
                self.send(bytes([0xb0 | self.channel, 123, 0]))
        finally:
            self.off=[];self.tokens.clear()

    def close_ports(self):
        # Detach selections before closing so error recovery cannot send to a
        # stale path or retain a partially opened configuration.
        ports,self.ports=self.ports,{}
        self.input = self.output = None
        self.pending.clear()
        self.off=[];self.tokens.clear()
        self.status, self.data = None, []
        self.events=[]
        for fd in set(ports.values()):
            try:os.close(fd)
            except OSError:pass

    def close(self):
        try:
            self.panic()
            deadline = time.monotonic()+0.2
            while self.pending and time.monotonic() < deadline:
                self.flush()
                time.sleep(0.005)
        except OSError:
            # Shutdown must continue even if the USB device was unplugged.
            pass
        finally:
            self.close_ports()
