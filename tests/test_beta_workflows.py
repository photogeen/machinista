"""Repeat actual controller gestures across origins without modifying Projects."""
import copy,tempfile,unittest
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.mk1_session import Mk1Surface
from app.mk2_surface import Mk2Surface
from app.mk3_surface import Mk3Surface

class BetaWorkflowTests(unittest.TestCase):
    def test_hold_pin_close_reopen_and_unpin_across_all_surfaces(self):
        for model,cls in (('mikro',None),('mikro_mk2',None),('mk1',Mk1Surface),('mk2',Mk2Surface),('mk3',Mk3Surface)):
            with self.subTest(model=model),tempfile.TemporaryDirectory() as root:
                a=Application(root);a.mikro_model=model if cls is None else 'mikro'
                inputs=ControllerInputs(a);s=cls(a,inputs) if cls else None
                def button(key,on):
                    if s:s.button(key,on)
                    else:inputs.button('mikro',key,on)
                def tap(key):button(key,True);button(key,False)
                def pin():
                    if s:s.softkey(0)
                    else:tap('MAIN')
                before=copy.deepcopy(a.project)
                for origin in ('BROWSE','PLUGIN','SAMPLER'):
                    for key,page in (('SCENE','SCENE'),('PATTERN','PATTERN'),('PAD MODE','PAD CONFIG')):
                        a.page=origin;a.pinned_modes.clear();a.mode_origins.clear()
                        button(key,True);self.assertEqual(a.page,page)
                        button(key,False);self.assertEqual(a.page,origin)
                        button(key,True);pin();button(key,False)
                        self.assertEqual(a.page,page);self.assertIn(key,a.pinned_modes)
                        tap(key);self.assertEqual(a.page,origin)
                        tap(key);self.assertEqual(a.page,page)
                        tap(key);button(key,True);pin();button(key,False)
                        self.assertEqual(a.page,origin);self.assertNotIn(key,a.pinned_modes)
                self.assertEqual(a.project,before)
    def test_keyboard_shortcut_preserves_workspace_and_never_adds_pin(self):
        for model,cls in (('mikro',None),('mikro_mk2',None),('mk1',Mk1Surface),('mk2',Mk2Surface),('mk3',Mk3Surface)):
            with self.subTest(model=model),tempfile.TemporaryDirectory() as root:
                a=Application(root);a.mikro_model=model if cls is None else 'mikro'
                inputs=ControllerInputs(a);s=cls(a,inputs) if cls else None
                def button(key,on):
                    if s:s.button(key,on)
                    else:inputs.button('mikro',key,on)
                for page in ('PLUGIN','SAMPLER','PATTERN GRID','CHOP'):
                    a.page=page;a.keyboard_enabled=False;a.pinned_modes.clear()
                    button('SHIFT',True)
                    for enabled in (True,False):
                        button('PAD MODE',True);button('PAD MODE',False)
                        self.assertEqual(a.keyboard_enabled,enabled)
                        self.assertEqual(a.page,page);self.assertFalse(a.pinned_modes)
                    button('SHIFT',False)
    def test_repeated_shared_pad_play_and_disconnect_never_records_or_releases_peer(self):
        with tempfile.TemporaryDirectory() as root:
            a=Application(root);inputs=ControllerInputs(a);before=copy.deepcopy(a.project)
            sources=('mikro','mk1','mk2','mk3')
            for _ in range(50):
                for source in sources:inputs.pad_on(source,0,100);inputs.button(source,'SHIFT',True)
                self.assertEqual(len(inputs.pads),4)
                for i,source in enumerate(sources):
                    inputs.disconnect(source)
                    self.assertEqual(len(inputs.pads),3-i);self.assertEqual(a.shift,i<3)
                self.assertFalse(a.live_notes);self.assertFalse(a.recording)
            self.assertEqual(a.project,before);self.assertFalse(a.notes())
