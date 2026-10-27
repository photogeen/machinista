"""Full-size plug-in picker uses five spaced rows on the unassigned right LCD."""
import copy,unittest
from tests import test_fokus_v2 as fixtures
from app.mk2_display import snapshot
from app.fokus_mk2_style import Canvas

class PluginBrowserLayoutTests(unittest.TestCase):
 setUp=fixtures.FokusV2Tests.setUp
 def prepare(self,count=12):
  a=self.a;a.page='PLUGIN BROWSE';a.plugin_filter='EFFECT';a.message=''
  a.plugin_catalog=[dict(uri=f'urn:fx:{i}',name=f'Effect {i:02}',kind='EFFECT',supported=True,ports=[]) for i in range(count)]
  return a
 def test_five_complete_rows_and_selection_scroll_at_both_ends(self):
  a=self.prepare();before=copy.deepcopy(a.project)
  for selected in (0,1,5,6,11,12):
   a.plugin_browser_index=selected-1;s=snapshot(self.surface);entries,index,kind=s['plugin_browser'];self.assertEqual(index,selected)
   frame=self.renderer(s)[1];first=max(0,min(selected-2,len(entries)-5));expected=Canvas()
   for row,value in enumerate(entries[first:first+5]):
    y=25+row*7;chosen=first+row==selected
    if chosen:expected.rect(3,y-1,244,7)
    expected.fitted(5,y,value,239,font='bold5' if chosen else 'regular5',ink=expected.bg if chosen else expected.ink)
   for y in range(24,60):self.assertEqual(frame[y*256+3:y*256+247],expected.finish()[y*256+3:y*256+247])
   top=24+(selected-first)*7
   self.assertTrue(all(frame[top*256+x] for x in range(3,247)),'selection needs one solid pixel above the glyphs')
   self.assertFalse(any(frame[61*256:]));self.assertFalse(any(s['fields'][4:]))
  self.assertEqual(a.project,before)
 def test_empty_slot_remove_and_instrument_filter(self):
  a=self.prepare(0);a.plugin_browser_index=-1;s=snapshot(self.surface);self.assertEqual(s['plugin_browser'][0],('*EMPTY SLOT*',));self.renderer(s)
  a.track()['plugins']=[dict(uri='urn:fx:0',kind='EFFECT',controls={})];self.assertEqual(snapshot(self.surface)['plugin_browser'][0],('REMOVE PLUG-IN',))
  a.plugin_filter='INSTRUMENT';a.plugin_catalog=[dict(uri='urn:synth',name='Synth',kind='INSTRUMENT',supported=True,ports=[])];self.assertEqual(snapshot(self.surface)['plugin_browser'],(('REMOVE PLUG-IN','Synth'),0,'INSTRUMENT'))
 def test_notices_do_not_cover_right_hand_choices(self):
  a=self.prepare();a.plugin_browser_index=4;plain=self.renderer(snapshot(self.surface));a.message='PLUGIN SCANNED';notice=self.renderer(snapshot(self.surface));self.assertEqual(plain[1],notice[1]);self.assertNotEqual(plain[0],notice[0])
