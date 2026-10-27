import copy
import http.client
import json
import os
from pathlib import Path
import random
import tempfile
import threading
import unittest
from unittest.mock import Mock,patch
from app.chords import parse,normalize,plan,validate_play
from app.chord_library import ChordLibrary
from app.model import Application,validate_project
from app.controller_inputs import ControllerInputs
from app.midi_performance import MidiPerformance
from app.live_timing import LiveTiming
from app.mk2_surface import Mk2Surface
from app.mk2_display import snapshot,Mk2Renderer
from app.waveform import Waveforms
from app.web_server import Library,Server

PRESET={'name':'Own voicings','root':60,'chords':[{'input':60,'name':'C / G','notes':[55,60,64]},{'input':63,'name':'Dm','notes':[57,62,65]}]}

class FormatTests(unittest.TestCase):
    def test_rpc_preserves_sparse_input_keys_and_voicings(self):
        p=parse(b'<ripchord><preset><input note="63"><chord name="Dm" notes="57;62;65;"/></input></preset></ripchord>','Own.rpc')
        self.assertEqual(p['chords'],[PRESET['chords'][1]]);self.assertEqual(p['name'],'Own')
    def test_mpc_progression_and_portable_json(self):
        p=parse(json.dumps({'progression':{'chords':[{'name':'C / G','notes':[55,60,64]}]}}).encode(),'Voicings.progression')
        self.assertEqual(p['chords'][0],PRESET['chords'][0]);self.assertEqual(parse(json.dumps(PRESET).encode(),'x.json'),normalize(PRESET))
    def test_reject_invalid_unbounded_entity_and_ambiguous_maps(self):
        for data,name in [(b'<!DOCTYPE ripchord [<!ENTITY x SYSTEM "file:///etc/passwd">]><ripchord/>','x.rpc'),(b'x','x.xpm'),(b'{}','x.progression'),(b'x'*1048577,'x.rpc')]:
            with self.subTest(name=name),self.assertRaises(ValueError):parse(data,name)
        for notes in ([True],[128],[-1],[60]*33):
            value=copy.deepcopy(PRESET);value['chords'][0]['notes']=notes
            with self.assertRaises(ValueError):normalize(value)
        value=copy.deepcopy(PRESET);value['chords'][1]['input']=60
        with self.assertRaises(ValueError):normalize(value)
    def test_strum_span_independent_velocity_direction_and_alternation(self):
        settings={'strum':90,'direction':'UP ALT','velocity_spread':40,'velocity_direction':'DOWN'}
        a=plan([67,60,64],100,settings,0);b=plan([67,60,64],100,settings,1)
        self.assertEqual(a,[(0,60,120),(.045,64,100),(.09,67,80)])
        self.assertEqual(b,[(0,67,80),(.045,64,100),(.09,60,120)])
        self.assertEqual(plan([60],100,settings),[(0,60,100)])
    def test_randomization_is_bounded_reproducible_and_defaults_are_neutral(self):
        self.assertEqual(plan([64,60],77,{}),[(0,60,77),(0,64,77)])
        p={'human_time':30,'human_velocity':64,'velocity_spread':127}
        a=plan([60,64,67],5,p,rng=random.Random(4));self.assertEqual(a,plan([60,64,67],5,p,rng=random.Random(4)))
        self.assertTrue(all(0<=d<=.03 and 1<=v<=127 for d,n,v in a))
        with self.assertRaises(ValueError):validate_play({'strum':501})

class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.a=Application(self.tmp.name)
        a=self.a;a.page='PAD CONFIG';a.keyboard_enabled=True;a.fixed_velocity=False;a.keyboard_root=60;a.performance().update(chord_mode='CUSTOM',custom=copy.deepcopy(PRESET),root=60)
    def test_pad_banks_transpose_and_portable_project_copy(self):
        a=self.a;self.assertEqual(a.performance_notes(0),[55,60,64]);self.assertEqual(a.performance_notes(1),[57,62,65]);self.assertEqual(a.performance_notes(2),[])
        a.keyboard_root=72;self.assertEqual(a.performance_notes(0),[67,72,76]);validate_project(a.project)
        a.save();b=Application(self.tmp.name);self.assertEqual(b.performance()['custom'],PRESET)
        rows=[dict(input=i,name=str(i),notes=[60]) for i in range(33)];a.performance()['custom']['chords']=rows;a.performance()['custom_bank']=2
        self.assertTrue(a.performance_notes(0));self.assertFalse(a.performance_notes(1))
    def test_catalog_preset_select_and_project_edits_do_not_mutate_library(self):
        a=self.a;a.chord_presets=({'id':'a','preset':PRESET},);a.select_chord_preset(1);a.performance()['custom']['name']='Project copy'
        self.assertEqual(PRESET['name'],'Own voicings');a.chord_edit('ADD');self.assertEqual(len(a.chord_row()['notes']),4);a.chord_edit('REMOVE');self.assertEqual(len(a.chord_row()['notes']),3)
    def test_only_rec_records_and_records_actual_strum_offsets_velocities(self):
        a=self.a;a.performance()['play']={'strum':100,'velocity_spread':40};a.playing=True;a.clock_phase=a.step=0;a.clock_last=None
        a.pad_on(0,100);self.assertFalse(a.event_notes());a.release_pad(0);a.recording=True
        a.pad_on(0,100);events=sorted(a.event_notes().items(),key=lambda kv:kv[0][1]);self.assertEqual([v['velocity'] for k,v in events],[80,100,120])
        self.assertEqual([k[1] for k,v in events],[0,round(.05/a.clock_interval()),round(.1/a.clock_interval())])
        self.assertEqual(len([1 for action,_ in a.actions if action=='chord_note']),6)
    def test_controller_release_cancels_pending_and_keeps_captured_targets(self):
        a=self.a;a.performance()['play']={'strum':100};p=ControllerInputs(a);audio=Mock();midi=Mock()
        p.pad_on('mk2',0,100)
        for action,value in a.actions:p.dispatch(action,value,audio,midi)
        self.assertEqual(audio.hit.call_count,1);self.assertEqual(len(p.timing.pending),2)
        a.actions=[];a.group=1;a.pad=4;p.pad_off('mk2',0)
        for action,value in a.actions:p.dispatch(action,value,audio,midi)
        self.assertFalse(p.timing.pending);self.assertEqual({c.args[:2] for c in audio.note_off.call_args_list},{(0,0)})
    def test_bluetooth_usb_midi_uses_original_sparse_mappings_and_correct_noteoffs(self):
        a=self.a;audio=Mock();midi=Mock();p=MidiPerformance(a,audio,midi)
        p.event(0x90,(61,100));self.assertEqual(audio.hit.call_count,0);p.event(0x80,(61,0))
        p.event(0x90,(63,100));self.assertEqual([c.args[4]+36 for c in audio.hit.call_args_list],[57,62,65])
        a.keyboard_root=84;a.group=1;a.pad=4;p.event(0x80,(63,0));self.assertEqual([c.args[2] for c in audio.note_off.call_args_list],[57,62,65])
    def test_learn_raw_midi_chord_and_cancel_stale_project(self):
        a=self.a;audio=Mock();p=MidiPerformance(a,audio,Mock());a.chord_edit('LEARN')
        p.event(0x90,(61,80));p.event(0x90,(66,90));p.event(0x80,(61,0));self.assertIsNotNone(a.chord_learning)
        p.event(0x80,(66,0));self.assertEqual(a.chord_row()['notes'],[61,66]);self.assertIsNone(a.chord_learning)
        a.chord_edit('LEARN');a.project_generation+=1;p.event(0x90,(70,90));self.assertIsNone(a.chord_learning)
    def test_pending_midi_cancel_and_timing_queue_no_catchup_burst(self):
        a=self.a;a.performance()['play']={'strum':100};audio=Mock();p=MidiPerformance(a,audio,Mock());p.event(0x90,(60,90));self.assertEqual(len(p.timing.pending),2)
        p.event(0x80,(60,0));self.assertFalse(p.timing.pending)
        q=LiveTiming();f=Mock()
        with patch('app.live_timing.time.monotonic',return_value=1):q.add(.1,1,f)
        q.tick(1.099);f.assert_not_called();q.tick(1.101);f.assert_called_once()
    def test_controller_controls_all_three_pages_and_piano_snapshot(self):
        a=self.a;surface=Mk2Surface(a,ControllerInputs(a));self.assertEqual(surface.page_state(),(0,3));self.assertEqual(surface.fields()[3].value,'Own voicings')
        surface.pad_page=1;self.assertEqual(surface.fields()[1].label,'VEL DIR');surface.pad_page=2
        self.assertEqual(surface.softkeys()[4:7],('LEARN','INV-','INV+'));surface.rotate(2,1);self.assertEqual(a.chord_row()['notes'][0],56)
        state=snapshot(surface);self.assertEqual(state['keyboard_notes'],(56,60,64))
        renderer=Mk2Renderer();self.addCleanup(renderer.close)
        pixels=renderer(state);self.assertTrue(all(len(p)==256*64 for p in pixels));self.assertNotEqual(pixels[1][26*256:45*256],bytes(19*256))

class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);(self.root/'samples').mkdir();self.lib=ChordLibrary(self.root)
    def test_roundtrip_edit_delete_and_traversal_rejection(self):
        row=self.lib.save(PRESET);self.assertEqual(self.lib.list(),[row]);value=copy.deepcopy(PRESET);value['name']='Edited';self.lib.save(value,row['id']);self.assertEqual(len(self.lib.list()),1)
        with self.assertRaises(ValueError):self.lib.delete('../etc')
        self.lib.delete(row['id']);self.assertEqual(self.lib.list(),[])
    def test_symlink_store_and_entries_are_rejected(self):
        outside=self.root/'outside';outside.mkdir();(self.root/'samples/.chords').symlink_to(outside,target_is_directory=True)
        with self.assertRaises(OSError):self.lib.save(PRESET)
        (self.root/'samples/.chords').unlink();self.lib.save(PRESET)
        (self.root/'samples/.chords'/('a'*32+'.json')).symlink_to(self.root/'secrets')
        self.assertEqual(len(self.lib.list()),1)
    def test_web_upload_edit_list_and_csrf(self):
        library=Library(self.root,source_scan=lambda:[]);server=Server(('127.0.0.1',0),library);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        def request(method,path,body=None,auth=True):
            c=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=4);c.request(method,path,body,{'X-Machinista-Token':library.token} if auth else {});r=c.getresponse();status=r.status;data=json.loads(r.read());c.close();return status,data
        self.assertEqual(request('POST','/api/chords/upload?name=own.json',json.dumps(PRESET),False)[0],403)
        status,row=request('POST','/api/chords/upload?name=own.json',json.dumps(PRESET));self.assertEqual(status,200)
        self.assertEqual(request('GET','/api/chords')[1],[row]);self.assertEqual(request('POST','/api/chords/save?id='+row['id'],json.dumps(PRESET))[0],200)
        self.assertEqual(request('POST','/api/chords/delete?id='+row['id'])[0],200)


class ShortStrokeTests(unittest.TestCase):
    setUp=RuntimeTests.setUp
    def test_released_before_strum_finishes_does_not_record_unplayed_voices(self):
        a=self.a;a.performance()['play']={'strum':200};a.playing=a.recording=True;a.step=a.clock_phase=0;a.clock_last=None
        a.input_timestamp=10;a.pad_on(0,100);a.input_timestamp=10.05;a.release_pad(0)
        self.assertEqual([v['note'] for v in a.event_notes().values()],[55]);self.assertFalse(a.chord_offsets)
    def test_short_external_midi_chord_records_only_sounded_notes(self):
        a=self.a;a.performance()['play']={'strum':200};a.playing=a.recording=True;a.step=a.clock_phase=0;a.clock_last=None
        p=MidiPerformance(a,Mock(),Mock());a.input_timestamp=10;p.event(0x90,(60,100));a.input_timestamp=10.05;p.event(0x80,(60,0))
        self.assertEqual([v['note'] for v in a.event_notes().values()],[55])
    def test_mikro_all_fields_reachable_and_edit_controls_work(self):
        from app.control_display import control_state
        a=self.a
        for i,key in enumerate(a.keyboard_fields()):
            a.pad_field=i;state=control_state(a);self.assertTrue(state['caption']);a.performance_rotate(1)
        a.shift=True;a.performance_button('F1',True);self.assertIsNotNone(a.chord_learning);a.performance_button('F1',True);self.assertIsNone(a.chord_learning)

class SchedulerSafetyTests(unittest.TestCase):
    def test_project_change_cancels_midi_before_due_attack(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=Application(tmp);a.keyboard_enabled=True;a.keyboard_root=60;a.performance().update(chord_mode='CUSTOM',custom=copy.deepcopy(PRESET),play={'strum':100})
            audio=Mock();m=MidiPerformance(a,audio,Mock());m.event(0x90,(60,100));self.assertTrue(m.timing.pending)
            a.project_generation+=1;m.tick(1e12);self.assertFalse(m.timing.pending);self.assertEqual(audio.hit.call_count,1)
    def test_queue_limit_is_bounded_and_does_not_raise(self):
        q=LiveTiming();f=Mock()
        for i in range(4096):self.assertTrue(q.add(.5,i,f))
        self.assertFalse(q.add(.5,4097,f));self.assertEqual(len(q.pending),4096)

if __name__=='__main__':unittest.main()
