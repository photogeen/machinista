import tempfile,unittest
from unittest.mock import patch
from app.text_marquee import Marquee,bitmap_names
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.mk2_surface import Mk2Surface
from app.mk2_display import snapshot,Mk2Renderer

class MarqueeTiming(unittest.TestCase):
    def test_wait_scroll_pause_and_restart(self):
        m=Marquee();m.begin('view')
        def offset(t):return m.offset('scale','Long scale',50,104,18,now=t)
        self.assertEqual(offset(10),0);self.assertEqual(offset(11.99),0)
        self.assertEqual(offset(13),18);self.assertEqual(offset(15),54)
        self.assertEqual(offset(16),54);self.assertEqual(offset(17),0)
    def test_selection_page_and_visibility_reset_delay(self):
        m=Marquee();m.begin('one');m.offset('x','old',30,90,now=1)
        self.assertGreater(m.offset('x','old',30,90,now=4),0)
        self.assertEqual(m.offset('x','new',30,90,now=4),0)
        m.end();m.begin('two');self.assertEqual(m.offset('x','new',30,90,now=8),0)
        m.end();m.begin('two');m.end();m.begin('two')
        self.assertEqual(m.offset('x','new',30,90,now=12),0)
    def test_short_names_need_no_refresh(self):
        m=Marquee();m.begin('view');self.assertIsNone(m.offset('x','C',58,7))
        self.assertFalse(m.active);m.end();self.assertFalse(m.entries)
    def test_bitmap_clip_never_touches_adjacent_cells(self):
        m=Marquee();s=dict(page='PAD CONFIG',fields=(('SCALE','A VERY LONG SCALE NAME'),))
        original=(bytes([1]*16384),bytes([1]*16384))
        with patch('app.text_marquee.time.monotonic',return_value=10):first=bitmap_names(m,s,original)
        with patch('app.text_marquee.time.monotonic',return_value=13):last=bitmap_names(m,s,original)
        self.assertNotEqual(first,last);self.assertEqual(last[1],original[1])
        for i,(a,b) in enumerate(zip(original[0],last[0])):
            if a!=b:self.assertTrue(4<=i%256<62 and 54<=i//256<61)

class ControllerNameScrolling(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=Application(self.tmp.name);self.s=Mk2Surface(self.a,ControllerInputs(self.a))
        self.a.page='PAD CONFIG';self.a.keyboard_enabled=True
        self.a.performance().update(chord_mode='CUSTOM',custom={'name':'A VERY LONG PRESET NAME FOR OUR CHORDS','root':60,
            'chords':[{'input':60,'name':'An extremely long custom chord name that needs to scroll across the color display','notes':[60,64,67]}]})
    def test_mk1_mk2_idle_refresh_and_name_change_reset(self):
        for controller in ('mk1','mk2'):
            r=Mk2Renderer();self.addCleanup(r.close);state=snapshot(self.s);state['controller']=controller
            with patch('app.text_marquee.time.monotonic',return_value=10):first=r(state)
            self.assertTrue(r.needs_refresh)
            with patch('app.text_marquee.time.monotonic',return_value=11.9):self.assertEqual(first,r(state))
            with patch('app.text_marquee.time.monotonic',return_value=13):self.assertNotEqual(first,r(state))
            state['fields']=tuple((f[0],'ANOTHER LONG PRESET TITLE') if f and f[0]=='PRESET' else f for f in state['fields'])
            with patch('app.text_marquee.time.monotonic',return_value=14):r(state)
            self.assertTrue(all(start==14 for key,(_,start) in r.marquee.entries.items() if key==('field',3)))
    def test_mk3_scroll_keeps_static_scene_cached(self):
        from app.mk3_display import Mk3Renderer
        r=Mk3Renderer();self.addCleanup(r.close);state=snapshot(self.s);state['controller']='mk3'
        with patch('app.text_marquee.time.monotonic',return_value=10):first=tuple(i.tobytes() for i in r.images(state))
        renders=r.scene_renders;self.assertTrue(r.needs_refresh)
        with patch('app.text_marquee.time.monotonic',return_value=11.9):self.assertEqual(first,tuple(i.tobytes() for i in r.images(state)))
        with patch('app.text_marquee.time.monotonic',return_value=13):self.assertNotEqual(first,tuple(i.tobytes() for i in r.images(state)))
        self.assertEqual(r.scene_renders,renders)
        state['page']='PAD'
        with patch('app.text_marquee.time.monotonic',return_value=14):r.images(state)
        self.assertFalse(r.marquee.active);self.assertFalse(r.marquee.entries)

class MikroOverviewScrolling(unittest.TestCase):
    def setUp(self):
        from app.live_display import live_frame
        self.state=dict(kind='CONTROL',page='PLUGIN',title='A:01 SYNTH',keys=('MASTER','GROUP','SOUND'),active=(2,),
            position='1:1:1',show_position=True,message='',pinned=False,transport_detail='',heading='SYNTH',
            caption='1/64: BANK',value='1',latency='',plugin_heading=True,pages=(0,8),
            micro_overview=dict(icon='synth',role='SOUND',name='A VERY LONG WARM ELECTRIC PIANO PATCH'))
        self.pixels=live_frame(self.state);self.marquee=Marquee()
    def draw(self,now):
        from app.text_marquee import mikro_names
        with patch('app.text_marquee.time.monotonic',return_value=now):
            return mikro_names(self.marquee,self.state,self.pixels)
    def test_wait_then_scroll_name_without_touching_icon_counter_or_footer(self):
        self.assertEqual(self.draw(10),self.pixels);self.assertEqual(self.draw(11.99),self.pixels)
        moved=self.draw(13);self.assertNotEqual(moved,self.pixels)
        for i,(before,after) in enumerate(zip(self.pixels,moved)):
            if before!=after:self.assertTrue(27<=i%128<123 and 37<=i//128<42)
        self.assertEqual(set(moved),{0,1});self.assertEqual(len(moved),8192)
    def test_selection_and_page_changes_reset_scroll_but_parameter_changes_do_not(self):
        self.draw(10);self.draw(13);self.state['value']='2'
        self.assertNotEqual(self.draw(14),self.pixels)
        self.state['micro_overview']['name']='ANOTHER VERY LONG WARM SYNTH PATCH'
        self.assertEqual(self.draw(15),self.pixels)
        self.state['title']='A:02 SYNTH';self.assertEqual(self.draw(18),self.pixels)
        self.state['page']='INPUT';self.assertEqual(self.draw(19),self.pixels)
        self.assertFalse(self.marquee.entries)
        self.state['page']='PLUGIN';self.assertEqual(self.draw(21),self.pixels)
    def test_short_names_legacy_and_non_overview_graphs_do_not_scroll(self):
        self.state['micro_overview']['name']='INIT';self.assertEqual(self.draw(10),self.pixels)
        self.assertFalse(self.marquee.active)
        del self.state['micro_overview'];self.assertEqual(self.draw(15),self.pixels)
        with patch.dict('os.environ',MACHINISTA_UI='v1'):
            self.assertEqual(self.draw(20),self.pixels)
    def test_detached_worker_applies_scrolling_to_unchanged_snapshots(self):
        from app.step_display import _render_worker
        class Pipe:
            def __init__(inner):inner.index=0;inner.sent=[]
            def recv(inner):
                inner.index+=1
                if inner.index>2:return None
                return (0,self.state)
            def send(inner,item):inner.sent.append(item)
            def close(inner):pass
        pipe=Pipe()
        with patch('app.step_display.os.nice'),patch('app.text_marquee.time.monotonic',side_effect=[10,13]):
            _render_worker(pipe)
        self.assertEqual(pipe.sent[0],(0,self.pixels));self.assertNotEqual(pipe.sent[0][1],pipe.sent[1][1])
