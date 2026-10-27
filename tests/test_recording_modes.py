import tempfile
import unittest
from pathlib import Path
from app.model import Application,validate_project
from app.audio import AudioBackend
from app.layout import GROUP_BASE,MASTER

class RecordingModesTests(unittest.TestCase):
    def test_ni_source_input_mode_context_and_monitor_pages(self):
        with tempfile.TemporaryDirectory() as root:
            a=Application(root);a.page='SAMPLING'
            self.assertEqual(a.capture_fields(),('source','input','mode','threshold'))
            a.rotate(1);self.assertEqual(a.capture_options()['source'],'EXT MONO')
            a.button('NAV RIGHT',True);a.rotate(1);self.assertEqual(a.capture_options()['input'],'IN 1 R')
            a.button('NAV RIGHT',True);a.rotate(1);self.assertEqual(a.capture_options()['mode'],'SYNC')
            self.assertEqual(a.capture_fields(),('source','input','mode','bars'))
            a.button('NAV RIGHT',True);a.rotate(2);self.assertEqual(a.capture_options()['bars'],4)
            a.button('NAV',True);a.button('NAV RIGHT',True);a.button('NAV',False)
            self.assertEqual(a.page,'SAMPLING');self.assertEqual(a.capture_fields(),('monitor',));a.rotate(1)
            self.assertTrue(a.capture_options()['monitor']);validate_project(a.project)
            a.save();b=Application(root);self.assertEqual(b.capture_options(),a.capture_options())
    def test_migration_and_internal_group_selection(self):
        with tempfile.TemporaryDirectory() as root:
            a=Application(root);a.project['sampling']=dict(source='MASTER',mode='MANUAL',bars=32,threshold=-24,monitor=True)
            options=a.capture_options();self.assertEqual((options['source'],options['input'],options['mode'],options['bars'],options['monitor']),('INTERNAL','MASTER','DETECT',16,False))
            a.project['sampling']['input']='GROUP 3';validate_project(a.project);self.assertEqual(a.capture_source_label(),'GROUP D')
    def test_detect_waiting_f1_starts_and_f2_cancels(self):
        with tempfile.TemporaryDirectory() as root:
            a=Application(root);a.page='SAMPLING';a.capture_armed=True;a.button('F1',True)
            self.assertEqual(a.actions[-1][0],'capture_trigger');self.assertTrue(a.capture_armed)
            a.button('F2',True);self.assertEqual(a.actions[-1][0],'capture_cancel')
    def test_detect_slice_engine_page_is_separate(self):
        with tempfile.TemporaryDirectory() as root:
            a=Application(root);a.page='CHOP';a.slice_mode='DETECT'
            a.button('NAV',True);a.button('NAV RIGHT',True);a.button('NAV',False)
            self.assertEqual((a.page,a.slice_section,a.slice_field),('CHOP',1,0))
            a.rotate(-1);self.assertFalse(a.slice_zero)
            a.button('NAV',True);a.button('NAV LEFT',True);a.button('NAV',False)
            self.assertEqual((a.page,a.slice_section),('CHOP',0))
    def test_native_capture_is_bounded_and_finishes_asynchronously(self):
        with tempfile.TemporaryDirectory() as root:
            b=AudioBackend.__new__(AudioBackend);b.root=Path(root);b.recorder=b.capture_pending=b.native_capture=None;b.sample_rate=44100;b.command=lambda c:commands.append(c);commands=[]
            b.start_native_capture(None,(2,3),{'source':'INTERNAL','input':'GROUP 5','mode':'SYNC','threshold':-24,'bars':4,'monitor':False},120)
            self.assertTrue(commands[-1].endswith(f'{GROUP_BASE+5} 0 1 -24 352800 0'));self.assertEqual(b.native_capture['target'],(2,3))
            self.assertIsNone(b.native_record_event({'status':'waiting','peak':.1}))
            path=b.native_capture['path'];path.write_bytes(b'data');self.assertEqual(b.native_record_event({'status':'finished','frames':4}),((2,3),path));self.assertIsNone(b.native_capture)
    def test_free_length_and_monitor_follow_selected_mono_channel(self):
        with tempfile.TemporaryDirectory() as root:
            b=AudioBackend.__new__(AudioBackend);b.root=Path(root);b.recorder=b.capture_pending=b.native_capture=None;b.sample_rate=44100;b.monitor_source=0;b.meter_source=-99;commands=[];b.command=commands.append
            options={'source':'EXT MONO','input':'IN 1 R','mode':'SYNC','threshold':-24,'bars':'FREE','monitor':True}
            self.assertTrue(b.sampling_io(options,True));self.assertEqual(commands,['monitor_source -3','meter_source -3'])
            b.start_native_capture('hw:1',(0,0),options,120);self.assertTrue(commands[-1].endswith('-3 0 1 -24 8388608 1'))
