import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from app.model import Application
from app.mk2_surface import Mk2Surface
from app.controller_inputs import ControllerInputs
from app.controller_settings import controller_context,seed_mk2_settings
from app.mk2_settings import configure_displays
from app.mk2_output import Mk2Output
from app.mk2_display import snapshot,Mk2Renderer

class ControllerSettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=Application(self.tmp.name);self.inputs=ControllerInputs(self.a);self.s=Mk2Surface(self.a,self.inputs)

    def test_mk2_display_edit_reset_and_persistence_never_changes_mikro(self):
        a=self.a;seed_mk2_settings(a,dict(brightness=59,contrast_left=38,contrast_right=42))
        original=(a.settings['display_brightness'],a.settings['display_contrast'])
        a.page='CONTRAST R';self.s.rotate(4,9)
        self.assertEqual(a.settings['controllers']['mk2']['contrast_right'],51)
        self.assertEqual(a.settings['controllers']['mk2']['contrast_left'],38)
        self.assertEqual(original,(a.settings['display_brightness'],a.settings['display_contrast']))
        self.assertIn(('controller_display_settings','mk2'),a.actions)
        self.assertNotIn(('display_settings',None),a.actions)
        # Same shared page, input from Mikro: only its one contrast changes.
        a.rotate(-5);self.assertEqual(a.settings['display_contrast'],37)
        self.assertEqual(a.settings['controllers']['mk2']['contrast_right'],51)
        reopened=Application(self.tmp.name)
        self.assertEqual(reopened.settings['controllers']['mk2']['contrast_right'],51)
        self.assertEqual(reopened.settings['display_contrast'],37)

    def test_pad_sensitivity_and_curve_follow_the_input_source(self):
        a=self.a;a.page='PAD SENS';self.s.rotate(2,100)
        self.assertEqual(a.settings['pad_sensitivity'],100)
        self.assertEqual(a.settings['controllers']['mk2']['pad_sensitivity'],200)
        self.assertGreater(a.pad_velocity(500,'mk2'),a.pad_velocity(500,'mikro'))
        before=a.pad_velocity(500,'mk2');a.rotate(-50)
        self.assertEqual(a.pad_velocity(500,'mk2'),before)
        self.assertLess(a.pad_velocity(500,'mikro'),before)
        self.s.rotate(5,1)
        self.assertEqual(a.settings['controllers']['mk2']['pad_curve'],'HARD')
        self.assertEqual(a.settings['pad_curve'],'LINEAR')

    def test_mk3_decoded_velocity_uses_midi_range_once(self):
        from app.mk3_protocol import Decoder
        a=self.a;decoder=Decoder()
        def hit(raw):
            events=decoder.decode(bytes((2,0,0x10|(raw>>8),raw&255))+bytes(60))
            event=next(e for e in events if e['kind']=='pad_on')
            return a.pad_velocity(event['value'],'mk3')
        self.assertEqual(hit(2000),127)
        self.assertEqual(hit(1000),64)
        self.assertGreater(hit(200),10)
        self.assertEqual(a.pad_velocity(1,'mk3'),1)
        values=[a.pad_velocity(v,'mk3') for v in range(1,128)]
        self.assertEqual(values,list(range(1,128)))

    def test_mk3_settings_sensitivity_curve_persistence_and_isolation(self):
        from app.mk3_surface import Mk3Surface
        a=self.a;s=Mk3Surface(a,self.inputs);a.page='PAD SENS'
        before={src:a.pad_velocity(700,src) for src in ('mikro','mk2','mk1','mikro_mk2')}
        self.assertEqual(a.pad_velocity(64,'mk3'),64)
        s.rotate(2,100)
        self.assertEqual(a.settings['controllers']['mk3']['pad_sensitivity'],200)
        self.assertEqual(a.pad_velocity(64,'mk3'),64)
        from app.mk3_pads import trigger_threshold
        self.assertLess(trigger_threshold(200),trigger_threshold(100))
        self.assertEqual(before,{src:a.pad_velocity(700,src) for src in before})
        reopened=Application(self.tmp.name)
        self.assertEqual(reopened.settings['controllers']['mk3']['pad_sensitivity'],200)
        a.settings['controllers']['mk3']['pad_sensitivity']=100
        a.settings['controllers']['mk3']['pad_curve']='SOFT'
        self.assertGreater(a.pad_velocity(32,'mk3'),32)
        a.settings['controllers']['mk3']['pad_curve']='HARD'
        self.assertLess(a.pad_velocity(32,'mk3'),32)
        a.settings['controllers']['mk3']['pad_curve']='FIXED';a.velocity_value=90
        self.assertEqual(a.pad_velocity(32,'mk3'),90)

    def test_reset_and_menu_entries_are_device_local(self):
        a=self.a;seed_mk2_settings(a,dict(brightness=59,contrast_left=38,contrast_right=42))
        a.settings_folder='SYSTEM';a.settings_section='DISPLAY'
        self.assertEqual(a.setting_entries()[:2],('BRIGHTNESS','CONTRAST'))
        with controller_context(a,'mk2'):
            self.assertEqual(a.setting_entries()[:3],('BRIGHTNESS','CONTRAST L','CONTRAST R'))
            a.page='CONTRAST L';a.button('SHIFT',True);a.button('F1',True);a.button('SHIFT',False)
        self.assertEqual(a.settings['controllers']['mk2']['contrast_left'],42)
        self.assertEqual(a.settings['display_contrast'],42)
        a.page='PAD SENS';a.settings['pad_sensitivity']=70
        with controller_context(a,'mk2'):
            a.settings['controllers']['mk2']['pad_sensitivity']=180;a.preferences_button('F1',True)
        self.assertEqual(a.settings['pad_sensitivity'],70)
        self.assertEqual(a.settings['controllers']['mk2']['pad_sensitivity'],100)
        self.assertEqual(a.controller_source,'mikro')

    def test_first_connection_preserves_hardware_values_and_later_seed_cannot_overwrite_edits(self):
        a=self.a;seed_mk2_settings(a,dict(brightness=59,contrast_left=38,contrast_right=42))
        a.page='BRIGHTNESS';self.s.rotate(1,1)
        seed_mk2_settings(a,dict(brightness=59,contrast_left=38,contrast_right=42))
        self.assertEqual(a.settings['controllers']['mk2']['brightness'],60)
        self.assertEqual(a.settings['display_brightness'],100)

    def test_hardware_screen_fields_and_master_encoder_ignore_volume_shortcut(self):
        a=self.a;a.page='BRIGHTNESS';self.s.master_mode='VOLUME'
        self.assertEqual([f.label for f in self.s.fields()[:4]],['BRIGHT.','PAD SENS','CNTR. L','CNTR. R'])
        self.s.rotate(0,-5)
        self.assertEqual(a.settings['controllers']['mk2']['brightness'],95)
        self.assertEqual(a.settings['display_brightness'],100)
        state=snapshot(self.s);self.assertTrue(state['hardware'])
        renderer=Mk2Renderer();self.addCleanup(renderer.close)
        self.assertTrue(all(len(p)==16384 for p in renderer(state)))

    def test_feature_read_modify_write_preserves_unknown_fields_and_independent_contrast(self):
        registers=[bytearray.fromhex('f8000140000101003b2600'),bytearray.fromhex('f9000140000202013b2a01')]
        before=[bytes(b) for b in registers];writes=[]
        def ioctl(fd,request,data,mutate):
            index=data[0]-248
            if request&255==7:data[:]=registers[index]
            else:
                writes.append(bytes(data));registers[index][:]=data
                for b in registers:b[8]=data[8] # Actual hardware's coupled backlight.
            return 11
        with patch('app.mk2_settings.fcntl.ioctl',side_effect=ioctl):
            actual=configure_displays(4,dict(brightness=None,contrast_left=None,contrast_right=50))
        self.assertEqual(actual,dict(brightness=59,contrast_left=38,contrast_right=50))
        self.assertEqual(len(writes),1);self.assertEqual(writes[0][0],249)
        self.assertEqual(bytes(registers[0]),before[0])
        self.assertEqual(bytes(registers[1])[:9],before[1][:9]);self.assertEqual(registers[1][10],before[1][10])
        with patch('app.mk2_settings.fcntl.ioctl',side_effect=ioctl):
            actual=configure_displays(4,dict(brightness=72,contrast_left=40,contrast_right=50))
        self.assertEqual(registers[0][8],72);self.assertEqual(registers[1][8],72)
        self.assertEqual(registers[0][9],40);self.assertEqual(registers[1][9],50)

    def test_feature_readback_failure_is_reported(self):
        reports=[bytearray.fromhex('f8000140000101003b2600'),bytearray.fromhex('f9000140000101003b2a00')]
        with patch('app.mk2_settings.read_feature',side_effect=reports+reports),patch('app.mk2_settings.write_feature'):
            with self.assertRaises(OSError):configure_displays(4,dict(contrast_right=99))

    def test_hardware_configuration_runs_off_dispatch_and_coalesces(self):
        entered=threading.Event();release=threading.Event();done=threading.Event();seen=[];threads=[]
        def configure(fd,values):
            threads.append(threading.get_ident());seen.append(values.copy())
            if len(seen)==1:entered.set();release.wait(2)
            else:done.set()
            return values
        worker=Mk2Output(3,lambda s:(bytes(16384),bytes(16384)),write=lambda *args:None,configure=configure,settings=dict(brightness=59))
        self.addCleanup(worker.close)
        try:
            self.assertTrue(entered.wait(1))
            worker.display_settings(dict(brightness=60));worker.display_settings(dict(brightness=61));release.set()
            self.assertTrue(done.wait(1));worker.close()
            self.assertEqual(seen,[dict(brightness=59),dict(brightness=61)])
            self.assertTrue(all(t!=threading.get_ident() for t in threads))
        finally:release.set()

if __name__=='__main__':unittest.main()
