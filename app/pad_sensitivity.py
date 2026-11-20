"""Send source-local trigger sensitivity to the native reader without blocking."""
import os
from app.controller_settings import preference_values

class PadSensitivitySender:
    def __init__(self):
        self.process=None;self.value=None
    def update(self,process,app,source):
        if process is not self.process:
            self.process=process;self.value=None
        value=preference_values(app,'pad_sensitivity',source)['pad_sensitivity']
        if value==self.value or process is None or process.stdin is None:return
        # One short write is atomic even alongside MK1's display packets.
        packet=f'SENS {value}\n'.encode()
        try:count=os.write(process.stdin.fileno(),packet)
        except BlockingIOError:return  # Retry latest value next poll, never wait.
        if count!=len(packet):raise OSError('short pad sensitivity command')
        self.value=value
