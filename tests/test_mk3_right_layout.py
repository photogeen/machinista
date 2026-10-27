import tempfile,unittest
from PIL import ImageColor
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.mk3_surface import Mk3Surface
from app.mk3_state import snapshot
from app.mk3_display import Mk3Renderer
from app.mk3_graphics import Canvas,GROUPS,INK,BG,content_y

class RightScreenLayout(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=Application(self.tmp.name);self.s=Mk3Surface(self.a,ControllerInputs(self.a))
        self.a.page='CHANNEL';self.a.control_level=2
        self.r=Mk3Renderer();self.addCleanup(self.r.close)
    def test_transport_changes_only_left_header(self):
        state=snapshot(self.s);one=self.r.images(state)
        state.update(playing=True,tempo=146.73,position='2:4:3')
        two=self.r.images(state)
        self.assertNotEqual(one[0].tobytes(),two[0].tobytes())
        self.assertEqual(one[1].tobytes(),two[1].tobytes())
    def test_right_title_moves_up_and_footer_keeps_encoder_alignment(self):
        state=snapshot(self.s);state['fields']=state['fields'][:4]+(('TEST','1'),None,None,None);left,right=self.r.images(state)
        color=ImageColor.getrgb(GROUPS[0])
        self.assertEqual(right.getpixel((11,34)),color)
        self.assertEqual(right.getpixel((11,80)),ImageColor.getrgb(BG))
        self.assertEqual(right.getpixel((100,260)),ImageColor.getrgb(GROUPS[0]))
        self.assertEqual(left.size,(480,272));self.assertEqual(right.size,(480,272))
    def test_pad_grid_uses_physical_order_group_color_and_selected_highlight(self):
        for group,pad in ((0,0),(1,5),(4,15)):
            c=Canvas();self.r.pad_grid(c,dict(group=group,pad=pad),10,60)
            selected=ImageColor.getrgb(GROUPS[group])
            for i in range(16):
                x=10+i%4*26;y=60+(3-i//4)*26
                fill=c.image.getpixel((x+3,y+3))
                if i==pad:self.assertEqual(fill,selected)
                else:self.assertNotEqual(fill,selected)
    def test_body_lines_polygons_and_text_share_vertical_coordinates(self):
        c=Canvas(compact_header=True);c.line((10,104,30,104),INK)
        c.polygon(((10,100),(14,100),(12,104)),INK)
        self.assertEqual(c.image.getpixel((20,78)),ImageColor.getrgb(INK))
        self.assertEqual(c.image.getpixel((12,75)),ImageColor.getrgb(INK))
        self.assertEqual(content_y(242,True),242)
        self.assertEqual(content_y(6,True),6)
