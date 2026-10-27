"""Conservative discovery of driver-registered stereo I2S audio HATs.

This does not probe GPIO/I2C, load overlays, or write mixer defaults. ALSA card
IDs can be truncated to 15 characters; PCM names retain the driver/model name.
"""
import re


def identity(card):
    try:
        identifier = (card / 'id').read_text().strip()
    except OSError:
        return None
    if not re.fullmatch(r'[A-Za-z0-9_-]+', identifier):
        return None
    # Retain the existing key/settings and codec routing for installed ULTRAs.
    if identifier.lower() == 'wm8960soundcard':
        return 'hat:wm8960', 'Raspiaudio ULTRA / WM8960'
    names = [identifier]
    for info in sorted(card.glob('pcm*p/info')):
        try:
            names.extend(re.findall(r'^name:\s*(.+)$', info.read_text(), re.M))
        except OSError:
            continue
    signature = re.sub(r'[^a-z0-9]', '', ' '.join(names).lower())
    # These require different channel/topology support; do not advertise stereo.
    if any(token in signature for token in ('dac8', 'adc8', 'octo', 'digione', 'hifiberrydigi')):
        return None
    families = (
        ('hifiberrydac', 'HiFiBerry DAC / ADC'),
        ('hifiberryamp', 'HiFiBerry Amp'),
        ('rpidac', 'Raspberry Pi DAC'),
        ('rpicodeczero', 'Raspberry Pi Codec Zero'),
        ('iqaudiodac', 'IQaudio DAC'),
        ('iqaudiocodec', 'IQaudio Codec'),
        ('alloboss', 'Allo Boss DAC'),
        ('bossdac', 'Allo Boss DAC'),
        ('audioinjectorpi', 'Audio Injector Stereo'),
        ('audioinjectorstereo', 'Audio Injector Stereo'),
    )
    for token, label in families:
        if token in signature:
            return 'hat:' + identifier.lower(), label
    return None
