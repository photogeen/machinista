"""Driver-name fixtures, routing boundaries and existing ULTRA compatibility."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from app.devices import discover, choose_audio, AudioDevice, hat_identity
from app.codec_levels import supported
from app.interface_mixer import verified_card


class HatFamilyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.sound = self.root/'sys'; self.proc = self.root/'proc'; self.dev = self.root/'dev'
        self.dev.mkdir()

    def card(self, number, identifier, pcm_name='', capture=False):
        (self.sound/f'card{number}'/'device').mkdir(parents=True)
        card = self.proc/f'card{number}'; (card/'pcm0p').mkdir(parents=True)
        (card/'id').write_text(identifier)
        if pcm_name:(card/'pcm0p/info').write_text('card: 1\nname: '+pcm_name+'\n')
        if capture:(card/'pcm0c').mkdir()
        return card

    def test_common_driver_names_including_truncated_ids(self):
        fixtures = (
            ('sndrpihifiberry', 'HiFiBerry DAC+ HiFi', False),
            ('sndrpihifiberry', 'HiFiBerry DAC+ADC Pro HiFi', True),
            ('sndrpihifiberry', 'HiFiBerry DAC+ HD HiFi', False),
            ('sndrpihifiberry', 'HiFiBerry DAC HiFi', False),
            ('IQaudIODAC', 'IQaudIO DAC HiFi', False),
            ('RPiDAC', 'Raspberry Pi DAC HiFi', False),
            ('RPiDACPro', 'Raspberry Pi DAC Pro HiFi', False),
            ('RPiCodecZero', 'Raspberry Pi Codec Zero HiFi', True),
            ('IQaudIOCODEC', 'IQaudIO CODEC HiFi', True),
            ('BossDAC', 'Allo Boss DAC HiFi', False),
            ('AlloBoss2', 'Allo Boss2', False),
            ('audioinjectorpi', 'AudioInjector audio', True),
        )
        for number, (identifier, name, capture) in enumerate(fixtures):
            self.card(number, identifier, name, capture)
        audio, midi = discover(self.sound, self.proc, self.dev)
        self.assertEqual(len(audio), len(fixtures)); self.assertFalse(midi)
        by_pcm = {a.playback:a for a in audio}
        for number, (_, _, capture) in enumerate(fixtures):
            a = by_pcm[f'plughw:{number},0']
            self.assertEqual(a.transport, 'HAT')
            self.assertEqual(a.input_channels, 2 if capture else 0)
            self.assertEqual(a.capture, f'plughw:{number},0' if capture else None)
            self.assertFalse(supported(a))  # No ULTRA defaults or GPIO button.

    def test_no_accidental_onboard_unknown_digital_or_multichannel_selection(self):
        for i, (identifier, name) in enumerate((
            ('Headphones', 'bcm2835 Headphones'), ('vc4hdmi0', 'vc4-hdmi-0'),
            ('GenericDAC', 'PCM5122'), ('sndrpihifiberry', 'HifiBerry Digi HiFi'),
            ('sndrpihifiberry', 'HifiBerry DAC8x HiFi'),
            ('audioinjectoroc', 'AudioInjector Octo'), ('sndrpihifiberry', ''),
        )):
            self.card(i, identifier, name)
        self.assertEqual(discover(self.sound, self.proc, self.dev)[0], [])

    def test_renumber_manual_selection_and_usb_priority(self):
        self.card(1, 'IQaudIODAC', 'IQaudIO DAC HiFi')
        before = discover(self.sound, self.proc, self.dev)[0][0]
        (self.sound/'card1').rename(self.sound/'card7'); (self.proc/'card1').rename(self.proc/'card7')
        after = discover(self.sound, self.proc, self.dev)[0][0]
        self.assertEqual(before.key, after.key); self.assertEqual(after.playback, 'plughw:7,0')
        usb = AudioDevice('usb', 'USB', 'plughw:2,0', None)
        self.assertEqual(choose_audio([after, usb], 'AUTO', after.key), usb)
        self.assertEqual(choose_audio([after, usb], after.key), after)
        self.assertEqual(choose_audio([after], 'AUTO', usb.key), after)

    def test_generic_mixer_checks_the_new_hat_identity(self):
        card = self.card(1, 'RPiDACPro', 'Raspberry Pi DAC Pro HiFi')
        audio = discover(self.sound, self.proc, self.dev)[0][0]
        with patch('app.interface_mixer.hat_identity', return_value=hat_identity(card)), patch.object(Path, 'exists', return_value=True):
            self.assertEqual(verified_card(audio), '1')
        with patch('app.interface_mixer.hat_identity', return_value=('hat:other', 'Other')):
            with self.assertRaises(ValueError):verified_card(audio)

    def test_ultra_key_and_controls_are_unchanged(self):
        self.card(3, 'wm8960soundcard', 'wm8960-soundcard', True)
        a = discover(self.sound, self.proc, self.dev)[0][0]
        self.assertEqual(a.key, 'hat:wm8960:pcm0'); self.assertTrue(supported(a))

    def test_disappearing_or_invalid_card_is_ignored(self):
        self.assertIsNone(hat_identity(self.proc/'gone'))
        self.assertIsNone(hat_identity(self.card(0, '../IQaudIODAC')))
