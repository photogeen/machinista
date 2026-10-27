import tempfile,unittest
from app.controller_renderer import ProcessRenderer
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.mk2_surface import Mk2Surface
from app.mk2_display import snapshot,Mk2Renderer

class ControllerRendererTests(unittest.TestCase):
 def test_process_pixels_match_existing_layout_and_shutdown(self):
  with tempfile.TemporaryDirectory() as root:
   a=Application(root);surface=Mk2Surface(a,ControllerInputs(a));state=snapshot(surface)
   expected=Mk2Renderer();actual=ProcessRenderer()
   try:
    self.assertNotEqual(actual.process.pid,__import__('os').getpid())
    self.assertEqual(actual(state),expected(state))
    actual.dismiss_boot();a.page='SETTINGS';self.assertEqual(actual(snapshot(surface)),expected(snapshot(surface)))
   finally:expected.close();actual.close()
   self.assertFalse(actual.process.is_alive())
 def test_failed_worker_is_detected_without_reusing_stale_frame(self):
  actual=ProcessRenderer();actual.process.terminate();actual.process.join(timeout=2)
  try:
   with self.assertRaises(OSError):actual({})
  finally:actual.close()
if __name__=='__main__':unittest.main()
