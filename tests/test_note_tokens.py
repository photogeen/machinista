import unittest
from app.audio import AudioBackend
from app.midi import MidiBackend
from app.note_tokens import NoteTokens
class NoteTokenTests(unittest.TestCase):
    def test_lv2_releases_only_after_last_same_pitch_token(self):
        audio=AudioBackend.__new__(AudioBackend);sent=[];audio.command=sent.append;audio.loaded={};audio.instrument_tokens=NoteTokens()
        track=dict(note=60,plugins=[dict(kind='INSTRUMENT')])
        audio.hit(0,0,51,track,voice_token=10);audio.hit(0,0,111,track,voice_token=11)
        audio.note_off(0,0,60,10);self.assertNotIn('plugin_note 0 60 0',sent)
        audio.note_off(0,0,60,11);self.assertEqual(sent.count('plugin_note 0 60 0'),2)
        audio.note_off(0,0,60,10);self.assertEqual(sent.count('plugin_note 0 60 0'),2)
        self.assertIn('off 0 60 10',sent)
    def test_midi_live_release_and_old_loop_gate_preserve_new_note(self):
        midi=MidiBackend();sent=[];midi.send=sent.append
        midi.hit(0,51,60,2,duration=None,voice_token=10);midi.hit(0,111,60,2,duration=None,voice_token=11)
        midi.note_off(60,2,10);self.assertEqual(len(sent),2)
        midi.hit(0,90,60,2,duration=None);midi.note_off(60,2,0);self.assertEqual(len(sent),3)
        midi.note_off(60,2,11);self.assertEqual(sent[-1],bytes([0x81,60,0]))
        midi.hit(0,90,60,2,duration=None,voice_token=12);midi.note_off(60,2,11);self.assertEqual(sent[-1],bytes([0x91,60,90]))


class CountedInstrumentTests(unittest.TestCase):
    def test_shared_chord_tones_leave_no_held_synth_voices(self):
        audio=AudioBackend.__new__(AudioBackend);audio.loaded={}
        held={}
        def command(line):
            fields=line.split()
            if fields[0]=='plugin_note':
                pitch=int(fields[2]);velocity=int(fields[3])
                held[pitch]=held.get(pitch,0)+1 if velocity else max(0,held.get(pitch,0)-1)
        audio.command=command
        track=dict(note=60,plugins=[dict(kind='INSTRUMENT')])
        # Two overlapping chords share C and G; release in either order.
        for reverse in (False,True):
            for token,notes in ((10,(60,64,67)),(11,(60,65,67))):
                for note in notes:audio.hit(0,0,100,track,note-60,token)
            for token,notes in sorted(((10,(60,64,67)),(11,(60,65,67))),reverse=reverse):
                for note in notes:audio.note_off(0,0,note,token)
            self.assertFalse(any(held.values()),held)
            self.assertFalse(audio.instrument_tokens.active)
            self.assertFalse(audio.instrument_tokens.attacks)

    def test_midi_balances_attacks_for_counting_receivers(self):
        midi=MidiBackend();messages=[];midi.send=messages.append
        for token in (10,11,12):midi.hit(0,90,60,1,duration=None,voice_token=token)
        midi.note_off(60,1,11);midi.note_off(60,1,10)
        self.assertEqual(len(messages),3)
        midi.note_off(60,1,12)
        self.assertEqual(messages.count(bytes((0x80,60,0))),3)
        midi.note_off(60,1,12)
        self.assertEqual(len(messages),6)
