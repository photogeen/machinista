"""Color roles, independent persistence, native cache invalidation and mixer values."""
import copy,tempfile,unittest
from pathlib import Path
from PIL import ImageColor
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.controller_settings import controller_context
from app.mk3_surface import Mk3Surface
from app.plus_session import PlusSurface
from app.mk3_state import snapshot
from app.mk3_display import Mk3Renderer
from app.mk3_graphics import BG,GROUPS
from app.mk3_theme import SCHEMES,PALETTES,resolve,active
from app.mk2_encoders import choice_binding

class ThemeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=Application(self.tmp.name);inputs=ControllerInputs(self.a)
        self.s=Mk3Surface(self.a,inputs);self.plus=PlusSurface(self.a,inputs)
        self.r=Mk3Renderer();self.addCleanup(self.r.close)
    def test_menu_only_on_color_controllers_and_choice_encoder(self):
        a=self.a;a.settings_section='DISPLAY'
        for source in ('mikro','mikro_mk2','mk1','mk2','mk3','plus'):
            with controller_context(a,source):self.assertEqual('COLOR SCHEME' in a.setting_entries(),source in ('mk3','plus'))
        a.page='COLOR SCHEME';f=self.s.fields()[0]
        self.assertEqual(f.value,'Plus');self.assertTrue(choice_binding(self.s,f))
    def test_choice_save_restart_reset_and_device_isolation(self):
        a=self.a;a.page='COLOR SCHEME';before=copy.deepcopy(a.settings)
        a.settings['controllers']['mk3']['color_scheme']='furnace'
        a.settings['controllers']['plus']['color_scheme']='furnace'
        self.s.rotate(1,1);self.assertEqual(a.settings['controllers']['mk3']['color_scheme'],'polar')
        self.plus.rotate(0,2);self.assertEqual(a.settings['controllers']['plus']['color_scheme'],'voltage')
        self.assertEqual(a.controller_source,'mikro')
        for source in ('mk1','mk2','mikro_mk2'):self.assertEqual(a.settings['controllers'][source],before['controllers'][source])
        reopened=Application(self.tmp.name)
        self.assertEqual(reopened.settings['controllers']['mk3']['color_scheme'],'polar')
        self.assertEqual(reopened.settings['controllers']['plus']['color_scheme'],'voltage')
        self.s.softkey(1)
        self.assertEqual(a.settings['controllers']['mk3']['color_scheme'],'original')
        self.assertEqual(a.settings['controllers']['plus']['color_scheme'],'voltage')
    def test_saved_color_scheme_survives_upgrade(self):
        from app.storage import save_json
        for device, scheme in (('mk3','current'),('plus','original')):
            self.a.settings['controllers'][device]['color_scheme']=scheme
        save_json(self.a.settings_path,self.a.settings)
        reopened=Application(self.tmp.name)
        self.assertEqual(reopened.settings['controllers']['mk3']['color_scheme'],'current')
        self.assertEqual(reopened.settings['controllers']['plus']['color_scheme'],'original')

    def test_snapshot_uses_origin_device_and_no_global_theme_leak(self):
        self.a.page='CHANNEL';self.a.settings['controllers']['mk3']['color_scheme']='polar'
        self.a.settings['controllers']['plus']['color_scheme']='amber'
        self.assertEqual(snapshot(self.s)['color_scheme'],'polar')
        self.assertEqual(snapshot(self.plus)['color_scheme'],'amber')
        s=snapshot(self.s);before=copy.deepcopy(s);images=self.r.images(s)
        self.assertEqual(images[0].getpixel((0,0)),ImageColor.getrgb(PALETTES['polar'][0]))
        self.assertEqual(s,before);self.assertEqual(active(),'current');self.assertEqual(resolve(BG),BG)
        self.assertEqual(images[0].getpixel((13,39)),ImageColor.getrgb(GROUPS[0]))
        # Same renderer switches schemes through its real cache, then returns byte-identically.
        current=dict(s,color_scheme='current');base=self.r.images(current)[0].tobytes()
        self.r.images(s);self.assertEqual(self.r.images(current)[0].tobytes(),base)
    def test_plus_scheme_is_default_and_seen_at_start_of_menu(self):
        self.a.page='COLOR SCHEME'
        self.plus.rotate(0,-len(SCHEMES))
        self.assertEqual(self.plus.fields()[0].value,'Plus')
        state=snapshot(self.plus)
        self.assertEqual(state['color_scheme'],'original')
        left,_=self.r.images(state)
        self.assertEqual(left.getpixel((450,92)),ImageColor.getrgb(PALETTES['original'][5]))

    def test_every_palette_renders_all_existing_workspaces_and_inverts(self):
        for scheme in SCHEMES:
            self.a.settings['controllers']['mk3']['color_scheme']=scheme
            for page in ('COLOR SCHEME','CHANNEL','PLUGIN','SAMPLING','PAD CONFIG','PATTERN GRID','MIXER','SETTINGS'):
                with self.subTest(scheme=scheme,page=page):
                    self.a.page=page;s=snapshot(self.s);before=copy.deepcopy(self.a.project)
                    images=self.r.images(s);self.assertEqual(tuple(im.size for im in images),((480,272),(480,272)))
                    self.assertEqual(images[0].getpixel((0,0)),ImageColor.getrgb(PALETTES[scheme][0]))
                    self.assertEqual(self.a.project,before)
            s=snapshot(self.s);normal=self.r(s);inverted=self.r(dict(s,display_invert=True))
            self.assertEqual(normal[0][:2],bytes(v^255 for v in inverted[0][:2]))
    def test_mixer_group_colors_clip_peaks_baselines_and_actual_gain(self):
        a=self.a;a.page='MIXER';a.mixer_level=1;a.mixer_field=0
        bus,count=a.mixer_watch();a.mixer_levels={bus+i:(.2,.3) for i in range(count)}
        a.mixer_peaks={bus+i:(.3,.4) for i in range(count)}
        a.project['groups'][0]['gain']=50;a.project['groups'][4]['gain']=25
        for scheme in SCHEMES:
            a.settings['controllers']['mk3']['color_scheme']=scheme;s=snapshot(self.s)
            self.assertEqual(s['fields'][0][1],'-6.0 DB');self.assertEqual(s['fields'][4][1],'-12.0 DB')
            im=self.r.images(s)
            for i in range(8):
                self.assertEqual(im[i//4].getpixel((23+(i%4)*118,185)),ImageColor.getrgb(GROUPS[i]))
            if scheme=='original':
                self.assertEqual(im[0].getpixel((110+118,100)),ImageColor.getrgb('#070501'))
                self.assertEqual(im[0].getpixel((110,100)),ImageColor.getrgb('#201e1a'))
                for i in range(8):
                    self.assertEqual(im[i//4].getpixel((110+(i%4)*118,96)),ImageColor.getrgb(GROUPS[i]))
                self.assertEqual(im[1].getpixel((20,262)),ImageColor.getrgb('#070501'))
            # Fader heads reflect gain; they are not invented input controls.
            self.assertEqual(im[0].getpixel((80,159)),ImageColor.getrgb(PALETTES[scheme][3]))
            self.assertEqual(im[1].getpixel((80,173)),ImageColor.getrgb(PALETTES[scheme][3]))
        a.mixer_levels[bus]=(1.2,0);s=snapshot(self.s);im=self.r.images(s)
        self.assertEqual(im[0].getpixel((23,123)),ImageColor.getrgb(PALETTES[scheme][10]))
        a.mixer_level=0;s=snapshot(self.s);self.r.images(s)
        a.mixer_level=2;a.mixer_field=1;self.r.images(snapshot(self.s))
        a.mixer_field=2;self.r.images(snapshot(self.s))
