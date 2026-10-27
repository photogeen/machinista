"""Cross-surface regressions from the October workflow audit."""
import copy
import tempfile
import unittest
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.mk1_session import Mk1Surface
from app.mk2_surface import Mk2Surface
from app.mk3_surface import Mk3Surface
from app.plugin_profiles import profile
from app.mk2_display import snapshot
from app.control_display import control_state
from app.ni_display import frame

CLASSES=(Mk1Surface,Mk2Surface,Mk3Surface)

class WorkflowConsistencyTests(unittest.TestCase):
    def app(self,cls=None):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        a=Application(tmp.name);a.control_level=2;inputs=ControllerInputs(a)
        s=cls(a,inputs) if cls else None
        def press(key):
            if s:s.button(key,True);s.button(key,False)
            else:inputs.button('mikro',key,True);inputs.button('mikro',key,False)
        return a,s,press
    def plugins(self,a):
        uri='urn:machinista:instrument:synth'
        a.plugin_catalog=[dict(uri=uri,name='Synth',kind='INSTRUMENT',supported=True,ports=profile(uri)['parameters']),
          dict(uri='urn:gain',name='Gain',kind='EFFECT',supported=True,ports=[dict(index=0,symbol='gain',name='GAIN',min=0,max=1,default=.5)])]
        a.track()['plugins']=[dict(uri=uri,kind='INSTRUMENT',controls={}),dict(uri='urn:gain',kind='EFFECT',controls={})]
        a.page='PLUGIN';a.plugin_slot=0;a.plugin_param=16
    def test_mk3_dedicated_workspace_exits_clear_all_fx_modes_and_ownership(self):
        for mode in (0,1,2):
            for key in ('CHANNEL','PLUG-IN','MIXER','EVENTS','KEYBOARD','CHORDS','ARRANGER','SETTINGS','FILE','MACRO'):
                with self.subTest(mode=mode,key=key):
                    a,s,press=self.app(Mk3Surface);a.open_live_fx();a.live_fx_mode=mode
                    a.live_fx_pad_on(2,100,owner='mk3');a.actions.clear();press(key)
                    self.assertNotEqual(a.page,'LIVE FX');self.assertEqual(a.live_fx_current,0)
                    self.assertFalse(a.live_fx_held);self.assertFalse(a.live_fx_pad_off(2,owner='mk3'))
                    self.assertTrue(any(action=='live_fx' and value[1:4]==(0,0,0) for action,value in a.actions))
    def test_mk3_fx_exit_records_off_and_keeps_the_requested_destination(self):
        a,s,press=self.app(Mk3Surface);a.page='MIXER';a.open_live_fx();a.live_fx_mode=1
        a.playing=a.recording=True;a.step=0;a.clock_phase=24
        a.live_fx_pad_on(2,100,owner='mk3');a.clock_phase=48;press('MIXER')
        self.assertEqual(a.page,'MIXER');self.assertEqual(a.live_fx_current,0)
        lane=next(iter(a.project['groups'][0]['automation'].values()))
        self.assertEqual(lane['points']['48'],2048)
        self.assertFalse(a.live_fx_held)

    def test_fx_controls_and_transport_do_not_exit_workspace(self):
        a,s,press=self.app(Mk3Surface);a.open_live_fx();a.live_fx_mode=1;a.live_fx_pad_on(2,100,owner='mk3')
        for key in ('FIXED VEL','FOLLOW','STOP','LOCK'):
            press(key);self.assertEqual(a.page,'LIVE FX');self.assertEqual(a.live_fx_current,3)
    def test_mk3_strip_cannot_reactivate_hidden_effect_after_exit(self):
        a,s,press=self.app(Mk3Surface);press('PERFORM');a.live_fx_pad=2
        s.strip(600);self.assertEqual(a.live_fx_current,3)
        press('MIXER');self.assertEqual(a.live_fx_current,0);self.assertIsNone(s.strip_mode)
        s.strip(700);self.assertEqual(a.live_fx_current,0)
    def test_all_fullsize_f8_switches_reset_to_valid_first_page(self):
        for cls in CLASSES:
            a,s,press=self.app(cls);self.plugins(a);project=copy.deepcopy(a.project);actions=list(a.actions)
            press('DISPLAY 8')
            self.assertEqual((a.page,a.plugin_slot,a.plugin_param),('PLUGIN',1,0))
            state=snapshot(s);self.assertEqual(state['page_index'],0);self.assertEqual(state['fields'][0],('GAIN','50%'))
            self.assertEqual(a.project,project);self.assertEqual(a.actions,actions)
    def test_mikro_nav_change_resets_but_unchanged_plugin_preserves_page(self):
        a,s,press=self.app();self.plugins(a)
        a.button('NAV',True);a.button('NAV',False);self.assertEqual(a.plugin_param,16)
        a.button('NAV',True);a.rotate(1);a.button('NAV',False)
        self.assertEqual((a.plugin_slot,a.plugin_param),(1,0));self.assertEqual(control_state(a)['caption'],'1/1: GAIN')
    def test_mikro_new_slot_can_be_paged_while_nav_is_held(self):
        a,s,press=self.app();self.plugins(a)
        a.plugin_slot=1;a.plugin_param=0;a.button('NAV',True);a.rotate(-1)
        a.button('NAV RIGHT',True);a.button('NAV RIGHT',False);a.button('NAV',False)
        self.assertEqual((a.plugin_slot,a.plugin_param),(0,8))
    def test_all_grid_tabs_expose_record_quantize_without_changing_edit_grid(self):
        for cls in (None,)+CLASSES:
            a,s,press=self.app(cls);a.page='OPTIONS';a.grid_tab=2
            a.put_note(0,13,dict(velocity=90,note=36));notes=copy.deepcopy(a.event_notes());grid=a.timing()['grid']
            a.grid_selected=set(a.event_notes());selection=set(a.grid_selected)
            if s:
                self.assertEqual(s.softkeys()[2],'GRID');self.assertEqual(s.fields()[4].label,'REC QUANT')
                s.rotate(5,-1)
            else:
                self.assertEqual(a.softkeys()[2],'GRID')
                for _ in range(3):press('NAV RIGHT')
                self.assertEqual(a.grid_field,3);a.rotate(-1);self.assertEqual(len(frame(a)),8192)
            self.assertFalse(a.timing()['record_quantize']);self.assertTrue(a.timing()['grid_on'])
            self.assertEqual(a.timing()['grid'],grid);self.assertEqual(a.event_notes(),notes);self.assertEqual(a.grid_selected,selection)
    def test_custom_chord_inversions_have_same_meaning_on_every_surface(self):
        for cls in (None,)+CLASSES:
            a,s,press=self.app(cls);a.keyboard_enabled=True;a.page='PAD CONFIG'
            p=a.performance();p['chord_mode']='CUSTOM';p['custom']={'name':'Audit','root':60,'chords':[{'notes':[60,64,67]}]}
            if s:s.pad_page=2;press('DISPLAY 6')
            else:
                a.shift=True;self.assertEqual(a.softkeys(),('LEARN','INV-','INV+'));press('F2')
            self.assertEqual(a.chord_row()['notes'],[55,60,64])
            if s:press('DISPLAY 7')
            else:press('F3')
            self.assertEqual(a.chord_row()['notes'],[60,64,67])
    def test_every_fullsize_final_slot_has_add_plug_and_shift_keeps_actions(self):
        for cls in CLASSES:
            a,s,press=self.app(cls);self.plugins(a);a.plugin_slot=1
            self.assertEqual(s.softkeys()[7],'ADD PLUG');press('DISPLAY 8');self.assertEqual(a.page,'PLUGIN BROWSE')
            a.page='PLUGIN';a.plugin_slot=1;a.shift=True;self.assertNotEqual(s.softkeys()[7],'ADD PLUG')
