import copy
import tempfile
import unittest
from unittest.mock import patch
from tests.test_fokus_v2 import fixture
from app.controller_inputs import ControllerInputs
from app.mk2_surface import Mk2Surface
from app.mk2_display import snapshot
from app.control_display import control_state
from app.ni_display import frame
from app.ui_context import nav_preview,visible_message,pinned
from app.fokus import Canvas


class UxNavigationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=fixture(self.tmp.name);self.s=Mk2Surface(self.a,ControllerInputs(self.a))

    def test_held_nav_repeated_arrows_preview_without_opening_or_editing(self):
        a=self.a
        for origin,attribute,target,expected in (
            ('SAMPLER','sampler_page','SAMPLER','FX/FILTER'),
            ('CHANNEL','channel_page','CHANNEL','AUX 2'),
            ('ZONE','zone_page','ZONE','TUNE')):
            with self.subTest(origin=origin):
                a.page=origin;setattr(a,attribute,0);before=copy.deepcopy(a.project);a.actions.clear()
                a.button('NAV',True)
                for _ in range(2):a.button('NAV RIGHT',True);a.button('NAV RIGHT',False)
                self.assertIn(a.page,('PARAM NAV','SAMPLING NAV'))
                self.assertEqual(nav_preview(a)['section'],expected)
                self.assertEqual(nav_preview(a)['index'],2)
                self.assertEqual(a.project,before);self.assertFalse(a.actions)
                a.button('NAV',False);self.assertEqual(a.page,target)
                self.assertEqual(getattr(a,attribute),2)

    def test_mikro_nav_shows_module_choices_and_named_subpage_together(self):
        a=self.a;a.page='INPUT';a.button('NAV',True)
        with patch.object(Canvas,'rows',autospec=True) as rows,patch.object(Canvas,'field',autospec=True) as field:
            frame(a)
            self.assertEqual(rows.call_args.args[1],['>INPUT','OUTPUT','GROOVE'])
            self.assertEqual(field.call_args.args[1:],('INPUT','1/1'))
        a.rotate(1);a.button('NAV RIGHT',True)
        with patch.object(Canvas,'rows',autospec=True) as rows,patch.object(Canvas,'field',autospec=True) as field:
            frame(a)
            self.assertIn('>OUTPUT',rows.call_args.args[1])
            self.assertEqual(field.call_args.args[1:],('AUX 1','2/4'))
        a.button('NAV',False);self.assertEqual((a.page,a.channel_page),('CHANNEL',1))

    def test_mikro_switch_from_plugin_to_channel_defaults_to_output(self):
        a=self.a
        for model in ('mikro','mikro_mk2'):
            for level in (0,1,2):
                for origin in ('PLUGIN','SAMPLER'):
                    with self.subTest(model=model,level=level,origin=origin):
                        a.mikro_model=model;a.control_level=level;a.page=origin
                        a.channel_page=0;a.channel_field=0;a.actions.clear()
                        before=copy.deepcopy(a.project)
                        a.button('NAV',True);a.button('F2',True);a.button('F2',False)
                        self.assertEqual(a.parameter_choices()[a.parameter_choice],'OUTPUT')
                        self.assertEqual(nav_preview(a)['module'],'OUTPUT')
                        a.button('NAV',False)
                        self.assertEqual((a.page,a.channel_page),('CHANNEL',0))
                        self.assertEqual(a.project,before);self.assertFalse(a.actions)
        # INPUT remains an explicit, reachable choice; reopening NAV retains it.
        a.control_level=2;a.page='PLUGIN';a.button('NAV',True)
        a.button('F2',True);a.button('F2',False);a.rotate(-1)
        a.button('NAV',False);self.assertEqual(a.page,'INPUT')
        a.button('NAV',True);a.button('NAV',False);self.assertEqual(a.page,'INPUT')

    def test_mikro_plugin_nav_counts_compact_pages_instead_of_raw_ports(self):
        from app.plugin_profiles import profile
        uri='urn:machinista:instrument:synth';ports=profile(uri)['parameters']
        self.assertGreater(len(ports),64)
        a=self.a;a.control_level=2;a.page='PLUGIN';a.plugin_param=0;a.plugin_slot=0
        a.plugin_catalog=[dict(uri=uri,name='Machinista Synth',kind='INSTRUMENT',supported=True,ports=ports)]
        a.track()['plugins']=[dict(uri=uri,kind='INSTRUMENT',controls={})]
        for model in ('mikro','mikro_mk2'):
            with self.subTest(model=model):
                a.mikro_model=model;a.page='PLUGIN';a.plugin_param=0
                before=copy.deepcopy(a.project);a.actions.clear();a.button('NAV',True)
                self.assertEqual(len(a.plugin_controls()),64)
                for index in range(8):
                    preview=nav_preview(a)
                    self.assertEqual((preview['index'],preview['total']),(index,8))
                    self.assertEqual(preview['section'],a.plugin_controls()[index*8]['section'])
                    with patch.object(Canvas,'field',autospec=True) as field:
                        frame(a);self.assertEqual(field.call_args.args[2],f'{index+1}/8')
                    if index<7:a.button('NAV RIGHT',True);a.button('NAV RIGHT',False)
                a.button('NAV',False);self.assertEqual(a.page,'PLUGIN')
                self.assertEqual(a.project,before);self.assertFalse(a.actions)

    def test_plugin_nav_uses_preview_slot_without_changing_selected_slot(self):
        a=self.a;a.control_level=2;a.page='PLUGIN';a.plugin_slot=0;a.plugin_param=40
        from app.plugin_profiles import profile
        uri='urn:machinista:instrument:synth'
        a.plugin_catalog=[dict(uri=uri,name='Synth',kind='INSTRUMENT',supported=True,ports=profile(uri)['parameters']),
            dict(uri='urn:gain',name='Gain',kind='EFFECT',supported=True,ports=[dict(index=0,symbol='gain',name='GAIN',min=0,max=1,default=.5)])]
        a.track()['plugins']=[dict(uri=uri,kind='INSTRUMENT',controls={}),dict(uri='urn:gain',kind='EFFECT',controls={})]
        a.button('NAV',True);a.rotate(1)
        preview=nav_preview(a);self.assertEqual((preview['index'],preview['total']),(0,1))
        self.assertEqual(preview['section'],'GAIN');self.assertEqual((a.plugin_slot,a.plugin_param),(0,40))
        a.button('NAV',False);self.assertEqual((a.plugin_slot,a.plugin_param),(1,0))

    def test_mk2_sound_channel_modules_are_visible_and_display_arrows_switch(self):
        a=self.a;a.page='INPUT';before=copy.deepcopy(a.project)
        state=snapshot(self.s)
        self.assertEqual(state['channel_modules'],('INPUT','OUTPUT','GROOVE','MACRO'))
        self.assertEqual(state['channel_module'],'INPUT')
        self.s.softkey(7);self.assertEqual(a.page,'CHANNEL')
        self.assertEqual(snapshot(self.s)['channel_module'],'OUTPUT')
        self.s.softkey(7);self.assertEqual(a.page,'GROOVE')
        self.s.softkey(7);self.assertEqual(a.page,'MACRO')
        for _ in range(3):self.s.softkey(6)
        self.assertEqual(a.page,'INPUT');self.assertEqual(a.project,before)

    def test_mk2_physical_page_arrows_traverse_channel_modules_and_leds_agree(self):
        from app.mk2_display import leds
        a=self.a
        for scope in (0,1,2):
            a.control_level=scope;a.page='CHANNEL' if scope==0 else 'INPUT';a.channel_page=0
            before=copy.deepcopy(a.project);path=self.s.channel_page_path()
            for i,(page,index) in enumerate(path):
                self.assertEqual(a.page,page)
                if page=='CHANNEL':self.assertEqual(a.channel_page,index)
                report=leds(self.s,{})[0]
                self.assertEqual(bool(report[5]),i>0)
                self.assertEqual(bool(report[6]),i+1<len(path))
                self.s.button('PAGE RIGHT',True);self.s.button('PAGE RIGHT',False)
            self.assertEqual(a.page,'MACRO')
            for _ in range(len(path)-1):self.s.button('PAGE LEFT',True);self.s.button('PAGE LEFT',False)
            self.assertEqual(a.page,path[0][0]);self.assertEqual(a.project,before)
        # Legacy/stale INPUT at Master has a safe way back to its valid pages.
        a.control_level=0;a.page='INPUT'
        self.assertEqual(self.s.page_directions(),(False,True))
        self.s.button('PAGE RIGHT',True);self.s.button('PAGE RIGHT',False)
        self.assertEqual((a.page,a.channel_page),('CHANNEL',0))

    def test_sampling_module_choices_remain_preview_until_release(self):
        a=self.a;a.page='SAMPLING';a.button('NAV',True);a.button('F2',True)
        self.assertEqual(a.page,'SAMPLING NAV');self.assertEqual(nav_preview(a)['section'],'PLAY RANGE')
        a.button('NAV RIGHT',True);self.assertEqual(nav_preview(a)['section'],'SELECTION')
        a.pad_on(15);self.assertEqual(a.page,'SAMPLING NAV')
        a.button('NAV RIGHT',True);self.assertEqual(nav_preview(a)['section'],'LOOP')
        a.button('NAV',False);self.assertEqual((a.page,a.zone_page),('ZONE',1))

    def test_page_navigation_preserves_edit_selection_and_slice_work(self):
        a=self.a;a.page='SAMPLE EDIT';a.track().update(selection_start=100,selection_end=20000)
        before=copy.deepcopy(a.project)
        a.button('NAV',True);a.button('NAV RIGHT',True);a.button('NAV',False)
        self.assertEqual(a.project,before)
        a.page='CHOP';a.slice_edit=True;before=copy.deepcopy(a.project)
        with patch.object(a,'prepare_slice_editor',side_effect=AssertionError('must not restart slice editor')):
            a.button('NAV',True);a.button('NAV',False)
        self.assertTrue(a.slice_edit);self.assertEqual(a.project,before)

    def test_preview_uses_selected_plugin_metadata_not_previous_slot(self):
        a=self.a;a.plugin_catalog=[dict(uri='urn:fx:one',name='Tape Echo',ports=[dict(name=f'Control {i}') for i in range(17)])]
        a.track()['plugins']=[dict(uri='urn:fx:one',controls={})];a.page='SAMPLER'
        a.button('NAV',True);a.rotate(1);a.button('NAV RIGHT',True)
        preview=nav_preview(a)
        self.assertEqual(preview['module'],'2. Tape Echo')
        self.assertEqual((preview['index'],preview['total']),(1,3))
        self.assertEqual(preview['section'],'Control 8 / Control 15')
        self.assertEqual(snapshot(self.s)['nav_preview'],preview)

    def test_mk2_armed_and_running_cancel_without_deleting_sample(self):
        a=self.a;a.page='SAMPLING';original=copy.deepcopy(a.track())
        for running in (False,True):
            a.capture_started=1 if running else None;a.capture_armed=not running;a.actions.clear()
            self.assertEqual(self.s.softkeys()[5:8],('CANCEL','',''))
            self.s.softkey(5)
            self.assertIn(('capture_cancel',None),a.actions)
            self.assertEqual(a.track(),original);self.assertEqual(a.page,'SAMPLING')

    def test_history_actions_match_boundaries_and_disabled_press_does_nothing(self):
        a=self.a;a.page='SAMPLING';a.actions.clear()
        self.assertEqual(self.s.softkeys()[6:8],('',''))
        self.s.softkey(6);self.s.softkey(7);self.assertFalse(a.actions)
        a.record_history[(0,0)]=[copy.deepcopy(a.track()),copy.deepcopy(a.track())]
        self.assertEqual(self.s.softkeys()[6:8],('PREV',''))
        self.s.softkey(6);self.assertEqual(a.record_cursor[(0,0)],0)
        self.assertEqual(self.s.softkeys()[6:8],('','NEXT'))
        a.capture_armed=True;a.capture_options()['mode']='SYNC'
        self.assertEqual(self.s.softkeys()[4:6],('WAIT','CANCEL'))
        self.s.softkey(4);self.assertNotIn(('capture_trigger',None),a.actions)

    def test_transport_keeps_sound_identity_and_notice_keeps_editable_footer(self):
        a=self.a;a.page='SAMPLER';a.track()['name']='Kick';a.playing=True;a.recording=True
        state=control_state(a)
        self.assertEqual(state['title'],'A:01 Kick');self.assertTrue(state['transport_detail'].startswith('REC '))
        before=frame(a);a.message='SAMPLE ASSIGNED';after=frame(a)
        self.assertEqual(before[46*128:],after[46*128:])
        self.assertEqual(before[15*128:23*128],after[15*128:23*128])
        self.assertNotEqual(before,after)

    def test_status_notices_expire_after_one_second(self):
        a=self.a
        for message in ('PROJECT SAVED','AUDIO CONNECTED','CHOKE ALL NOTES','NO AUDIO DEVICE'):
            a.message=message
            with patch('app.ui_context.time.monotonic',return_value=100):self.assertEqual(visible_message(a),message)
            with patch('app.ui_context.time.monotonic',return_value=100.99):self.assertEqual(visible_message(a),message)
            with patch('app.ui_context.time.monotonic',return_value=101):self.assertEqual(visible_message(a),'')
            with patch('app.ui_context.time.monotonic',return_value=500):self.assertEqual(visible_message(a),'')
            self.assertEqual(a.message,message)

    def test_long_names_preserve_suffix_and_pinned_mode_is_visible(self):
        c=Canvas()
        with patch.object(c,'text',wraps=c.text) as draw:
            c.fitted(4,25,'Desert Wind - alternative take 02.wav',120)
            shown=draw.call_args.args[2]
            self.assertIn('...',shown);self.assertTrue(shown.endswith('02.wav'))
            self.assertLessEqual(c.text_width(shown),120)
        a=self.a;a.page='PAD CONFIG';normal=frame(a)
        a.pinned_modes.add('PAD MODE');self.assertTrue(pinned(a));self.assertTrue(control_state(a)['pinned'])
        self.assertNotEqual(normal,frame(a))
        a.page='PATTERN';a.pinned_modes.add('PATTERN')
        self.assertIn(0,snapshot(self.s)['active_left'])


if __name__=='__main__':unittest.main()
