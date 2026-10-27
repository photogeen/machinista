import copy
import hashlib
import tempfile
import unittest
from unittest.mock import patch,Mock
from app.branding import BootSplash,boot_frame,logo_mask,paint_logo
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.mk2_surface import Mk2Surface
from app.mk2_display import Mk2Renderer,snapshot
from app.ni_display import frame
from app.system_info import system_page_count


class BrandingTests(unittest.TestCase):
    def test_logo_masks_use_transparent_holes_and_fit_both_lcds(self):
        for screen,width in ((128,120),(256,236)):
            height,mask=logo_mask(width)
            self.assertEqual(len(mask),height*width)
            self.assertLessEqual(height,34)
            self.assertEqual(set(mask),{0,1})
            bg=1 if screen==128 else 0
            p=bytearray([bg]*(screen*64));paint_logo(p,screen,4,17,width)
            for i,pixel in enumerate(mask):
                yy,xx=divmod(i,width)
                self.assertEqual(p[(yy+17)*screen+xx+4],1-bg if pixel else bg)
            boot=boot_frame(screen)
            self.assertEqual(len(boot),screen*64)
            self.assertTrue(all(v==bg for v in boot[:screen]+boot[-screen:]))

    def test_lcd_icon_keeps_all_sixteen_pad_cutouts_open(self):
        for width,pads in ((120,(6,5,2,3)),(236,(12,12,4,5))):
            height,mask=logo_mask(width)
            left=min(i%width for i,v in enumerate(mask) if v)
            px,py,size,step=pads
            for row in range(4):
                for col in range(4):
                    x=left+px+col*step;y=py+row*step
                    for yy in range(y,y+size):
                        self.assertEqual(mask[yy*width+x:yy*width+x+size],bytes(size))
                        self.assertEqual(mask[yy*width+x-1],1)

    @staticmethod
    def wordmark_runs(width):
        height,mask=logo_mask(width);runs=[];start=None
        for x in range(width+1):
            occupied=x<width and any(mask[y*width+x] for y in range(height))
            if occupied and start is None:start=x
            if not occupied and start is not None:runs.append((start,x));start=None
        return height,mask,runs

    def test_repeated_letters_match_and_all_letters_share_one_baseline(self):
        for width in (120,236):
            height,mask,runs=self.wordmark_runs(width)
            self.assertEqual(len(runs),11) # icon + ten letters
            bottoms=[];letters={}
            for letter,(x,end) in zip('Machinista',runs[1:]):
                rows=tuple(mask[y*width+x:y*width+end] for y in range(height))
                bottoms.append(max(y for y,row in enumerate(rows) if any(row)))
                if letter in letters:self.assertEqual(letters[letter],rows)
                letters[letter]=rows
            self.assertEqual(len(set(bottoms)),1)

    def test_logo_matches_the_selected_number_six_previews_exactly(self):
        for width,expected in (
            (120,'e027f032add0cb7b6f54e206893cbbbb0b3e3cbab462cd3e00044970bf9e0cce'),
            (236,'b28d9c33faa6e3fdabf7b22b6490dc9c3cb86e13be63c0f957f9969647f63ef8')):
            _,mask=logo_mask(width)
            self.assertEqual(hashlib.sha256(mask).hexdigest(),expected)

    def test_approved_icon_is_byte_identical(self):
        for width,iw,expected in (
            (120,18,'b2880cba2fb8585e02ab29009ed30f5ba7206e3a2e157b5d72f3c7dafbb624b9'),
            (236,36,'915fbf41cb4568dfc310729673c1ed1c3e2dfce09211668d940339515b3e0c0a')):
            height,mask=logo_mask(width);left=min(i%width for i,v in enumerate(mask) if v)
            icon=b''.join(mask[y*width+left:y*width+left+iw] for y in range(height))
            self.assertEqual(hashlib.sha256(icon).hexdigest(),expected)

    def test_boot_deadline_and_immediate_dismissal_without_waiting(self):
        boot=BootSplash();boot.start(20)
        self.assertTrue(boot.active(21.99));self.assertFalse(boot.active(22))
        self.assertTrue(boot.expired(22));self.assertFalse(boot.expired(23))
        boot.start(30);boot.dismiss();self.assertFalse(boot.active(30))

    def test_mk2_splash_refreshes_static_view_and_input_dismisses_it(self):
        with tempfile.TemporaryDirectory() as root:
            a=Application(root);s=Mk2Surface(a,ControllerInputs(a));state=snapshot(s)
            renderer=Mk2Renderer(startup=True)
            try:
                with patch('app.branding.time.monotonic',return_value=10):
                    self.assertEqual(renderer(state),(boot_frame(256),)*2)
                    self.assertTrue(renderer.needs_refresh)
                with patch('app.branding.time.monotonic',return_value=12.1):
                    self.assertNotEqual(renderer(state),(boot_frame(256),)*2)
                renderer.boot.start(20);renderer.dismiss_boot()
                self.assertIsNone(renderer.boot.until)
                self.assertEqual(state,snapshot(s))
            finally:renderer.close()

    def test_about_and_resource_pages_keep_all_storage_and_project_data(self):
        with tempfile.TemporaryDirectory() as root:
            a=Application(root);a.page='SYSTEM'
            a.system_stats={'cpu':12,'ram':{'percent':34},'storage':[
                dict(name=name,total=32000000000,used=8000000000,percent=25)
                for name in ('SD CARD','USB A','USB B')]}
            original=copy.deepcopy(a.project);renderer=Mk2Renderer();surface=Mk2Surface(a,ControllerInputs(a))
            try:
                self.assertEqual(system_page_count(a.system_stats),4)
                self.assertEqual(system_page_count(a.system_stats,'mk2'),3)
                micro=[];mk2=[]
                for index in range(4):
                    a.system_index=index;micro.append(bytes(frame(a)))
                self.assertEqual(len(set(micro)),4)
                for index in range(3):
                    a.system_index=index;mk2.append(tuple(bytes(p) for p in renderer(snapshot(surface))))
                self.assertEqual(len(set(mk2)),3)
                self.assertEqual(a.project,original)
            finally:renderer.close()

if __name__=='__main__':unittest.main()
