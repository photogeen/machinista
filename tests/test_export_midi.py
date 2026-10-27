import copy
import json
from pathlib import Path
import struct
import tempfile
import threading
import unittest
from app.model import Application
from app.export_midi import compile_midi,render_midi_export,vlq
from app.ni_display import frame


def read_midi(data):
    """Independent SMF reader: validate chunk sizes, delta times and event boundaries."""
    assert data[:4]==b'MThd'
    size,kind,count,ppq=struct.unpack('>IHHH',data[4:14]);assert (size,kind,ppq)==(6,1,96)
    offset=14;tracks=[]
    for _ in range(count):
        assert data[offset:offset+4]==b'MTrk'
        size=int.from_bytes(data[offset+4:offset+8],'big');offset+=8;end=offset+size;tick=0;events=[]
        def number():
            nonlocal offset
            value=0
            for _ in range(4):
                byte=data[offset];offset+=1;value=value*128+(byte&127)
                if byte<128:return value
            raise AssertionError('invalid VLQ')
        while offset<end:
            tick+=number();status=data[offset];offset+=1
            if status==255:
                kind=data[offset];offset+=1;length=number();payload=data[offset:offset+length];offset+=length
                events.append((tick,status,kind,payload))
                if kind==47:assert offset==end
            else:
                assert status&240 in (128,144)
                events.append((tick,status,*data[offset:offset+2]));offset+=2
        assert events[-1][1:]==(255,47,b'');tracks.append(events)
    assert offset==len(data)
    return tracks


class MidiExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.a=Application(self.root)
        self.a.put_event((0,0),dict(velocity=103,probability=0,length=48,note=60))
    def request(self,**kw):
        result=dict(project=self.a.project_for_save(),mode='PATTERN',source='GROUP',group=0,pad=0,pattern=0,scene=0,groove=False,scene_retrigger='ON');result.update(kw);return result
    def test_smf_tempo_poly_channels_empty_tracks_and_note_order(self):
        a=self.a;a.project['tempo']=123.45;a.track()['channel']=9;a.track()['mute']=True
        voice=dict(velocity=76,probability=100,length=24,note=64,_id='a'*32)
        a.put_event((0,0,'a'*32),voice)
        a.put_event((0,48),dict(velocity=90,probability=100,length=12,note=60))
        before=copy.deepcopy(a.project);data,end,count=compile_midi(a,self.request())
        tracks=read_midi(data);self.assertEqual(len(tracks),17);self.assertEqual(count,3)
        self.assertEqual(int.from_bytes(tracks[0][1][3],'big'),round(60000000/123.45))
        notes=[e for e in tracks[1] if e[1]!=255]
        self.assertIn((0,152,60,103),notes);self.assertIn((0,152,64,76),notes)
        self.assertLess(notes.index((48,136,60,0)),notes.index((48,152,60,90)))
        self.assertTrue(all(t[-1][0]==end for t in tracks));self.assertEqual(len(tracks[2]),2)
        self.assertEqual(a.project,before)
    def test_scene_song_independent_loops_retrigger_and_gate_boundary(self):
        a=self.a;a.set_pattern_length(32)
        a.project['scenes'][0]=[0]+[None]*7;a.project['scene_lengths']['0']=16
        a.project['scenes'][1]=[0]+[None]*7;a.project['scene_lengths']['1']=48;a.project['song']=[0,1]
        def onsets(**kwargs):
            tracks=read_midi(compile_midi(a,self.request(mode='SONG',**kwargs))[0]);return [e[0] for e in tracks[1] if e[1]&240==144]
        self.assertEqual(onsets(),[0,384,1152]);self.assertEqual(onsets(scene_retrigger='OFF'),[0,768])
        a.put_event((0,360),dict(note=62,velocity=127,probability=100,length=96))
        tracks=read_midi(compile_midi(a,self.request(mode='SCENE'))[0]);self.assertIn((384,128,62,0),tracks[1])
    def test_selection_groove_long_rests_and_no_link_expansion(self):
        a=self.a;a.put_event((1,24),dict(note=44,velocity=80,probability=100,length=40));a.groove_position=lambda g,p,t,l:t+7
        data,end,count=compile_midi(a,self.request(source='SOUND',pad=1,groove=True));tracks=read_midi(data)
        self.assertEqual(len(tracks),2);self.assertEqual(count,1);self.assertIn((31,144,44,80),tracks[1])
        a.set_pattern_length(4096);data,end,count=compile_midi(a,self.request(source='ALL GROUPS'))
        self.assertEqual(len(read_midi(data)),129);self.assertEqual(read_midi(data)[-1][-1][0],end)
        self.assertEqual(vlq(16384),b'\x81\x80\x00')
    def test_publication_numbering_cancel_and_empty_song(self):
        request=self.request();before=copy.deepcopy(self.a.project)
        first=render_midi_export(request,self.root);second=render_midi_export(request,self.root)
        self.assertNotEqual(first,second);self.assertEqual(json.loads((first/'Export.json').read_text())['notes'],1)
        read_midi((first/'Notes.mid').read_bytes());self.assertEqual(self.a.project,before)
        cancel=threading.Event();cancel.set()
        with self.assertRaisesRegex(ValueError,'CANCELED'):render_midi_export(request,self.root,cancel)
        with self.assertRaisesRegex(ValueError,'EMPTY'):render_midi_export(self.request(mode='SONG'),self.root)
        self.assertFalse(list((self.root/'exports').glob('.midi-*')));self.assertFalse(list((self.root/'cache').glob('midi-*')))
    def test_worker_job_and_cancel_after_start(self):
        import time
        from app.sample_jobs import SampleJobs
        jobs=SampleJobs();self.addCleanup(jobs.close)
        self.assertTrue(jobs.submit('EXPORT',None,{},render_midi_export,self.request(),self.root))
        deadline=time.monotonic()+5;result=[]
        while not result and time.monotonic()<deadline:result=jobs.poll();time.sleep(.005)
        self.assertEqual(result[0][0],'EXPORT');self.assertIsNone(result[0][4])
        read_midi((result[0][3]/'Notes.mid').read_bytes())
        cancel=threading.Event()
        class Progress:
            def put(self,text):cancel.set()
        with self.assertRaisesRegex(ValueError,'CANCELED'):render_midi_export(self.request(),self.root,cancel,Progress())
        self.assertFalse(list((self.root/'exports').glob('.midi-*')))

    def test_ui_separate_audio_options_stopped_guard_and_result(self):
        a=self.a
        from app.project_manager import MANAGE
        a.page='PROJECT MANAGE';a.manage_index=MANAGE.index('EXPORT MIDI');a.button('ENTER',True)
        self.assertEqual(a.export_kind,'MIDI');self.assertEqual(len(frame(a)),8192)
        a.export_field=1;a.rotate(-1);self.assertEqual(a.export_value(),'SOUND A:01')
        a.export_field=2;a.rotate(1);self.assertEqual(a.export_value(),'GROOVE')
        a.playing=True;a.button('F3',True);self.assertFalse(a.export_busy)
        a.playing=False;a.button('F3',True);self.assertEqual(a.actions[-1][0],'midi_export')
        self.assertNotIn('chains',a.actions[-1][1]);a.button('F1',True);self.assertEqual(a.actions[-1][0],'export_cancel')
        a.export_busy=False;a.page='EXPORT DONE';a.button('F3',True);self.assertEqual(a.export_kind,'MIDI')
        a.open_export();self.assertEqual(a.export_kind,'AUDIO');self.assertEqual(len(a.export_fields()),9)
