"""ULTRA hardware gain controls; subprocess work stays outside audio/UI threads."""
import queue
import subprocess
import threading
from pathlib import Path

CONTROLS = {
    'HEADPHONE LEVEL': ('hat_headphone', 101, 127, 'Headphone'),
    'SPEAKER LEVEL': ('hat_speaker', 101, 127, 'Speaker'),
    'INPUT GAIN': ('hat_input', 39, 63, 'Capture'),
}

MUTES={'HEADPHONE MUTE':('hat_headphone_mute','hat_headphone'),
       'SPEAKER MUTE':('hat_speaker_mute','hat_speaker')}

def dac_context(app):
    return app.page in ('HEADPHONE LEVEL','SPEAKER LEVEL')

def supported(device):
    return bool(device and device.transport == 'HAT' and device.key.startswith('hat:wm8960:'))

def caption(page, value):
    db = value - 121 if page != 'INPUT GAIN' else value * .75 - 17.25
    return 'MUTE' if page != 'INPUT GAIN' and value == 0 else f'{db:+.2f} dB'

class CodecLevels:
    def __init__(self):
        self.condition = threading.Condition()
        self.pending = None
        self.stopped = False
        self.results = queue.SimpleQueue()
        self.thread = threading.Thread(target=self._run, name='codec-levels', daemon=True)
        self.thread.start()

    def submit(self, device, settings):
        snapshot = (device, {**{key:settings[key] for key,_,_,_ in CONTROLS.values()},**{key:settings.get(key,False) for key,_ in MUTES.values()}}) if supported(device) else None
        with self.condition:
            self.pending = snapshot
            self.condition.notify()

    @staticmethod
    def apply(device, values):
        # Use the selected card and recheck its identity; never touch a USB device.
        card = device.playback.split(':',1)[1].split(',')[0]
        if not card.isdigit() or 'wm8960' not in (Path('/proc/asound')/f'card{card}'/'id').read_text().lower():
            raise ValueError('ULTRA card changed')
        # Fresh images have no saved ALSA state for a newly attached HAT.
        # Restore its digital signal path without changing user analog gains.
        commands = [('Playback','255,255'),
                    ('Left Output Mixer PCM','on'),('Right Output Mixer PCM','on'),
                    ('Left Input Mixer Boost','on'),('Right Input Mixer Boost','on')]
        for key,_,maximum,control in CONTROLS.values():
            value = values[key]
            if type(value) is not int or not 0 <= value <= maximum:
                raise ValueError('invalid codec level')
            muted=values.get(key+'_mute',False) if control in ('Headphone','Speaker') else False
            if type(muted) is not bool:raise ValueError('invalid codec mute')
            effective=0 if muted else value
            commands.append((control,f'{effective},{effective}'))
        for control,value in commands:
            subprocess.run(['amixer','-q','-c',card,'sset',control,value],
                           check=True,timeout=2,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)

    def _run(self):
        while True:
            with self.condition:
                self.condition.wait_for(lambda:self.stopped or self.pending is not None)
                if self.stopped:return
                device,values = self.pending
                self.pending = None
            try:
                self.apply(device,values)
                error = ''
            except (OSError,ValueError,subprocess.SubprocessError):
                error = 'HARDWARE LEVEL ERROR'
            self.results.put((device.key,error))

    def poll(self):
        latest = None
        while not self.results.empty():latest = self.results.get()
        return latest

    def close(self):
        with self.condition:
            self.stopped = True
            self.condition.notify()
        self.thread.join(timeout=.1)
