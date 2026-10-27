import tempfile
import unittest
from pathlib import Path
from app.model import Application,validate_project
from app.storage import load_json
from app.ni_display import frame

class ProjectManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.a=Application(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def named(self,name):
        self.a.save_as();self.a.name_value=name;self.a.finish_project_name()
        return self.a.active_project_file()
    def test_rename_survives_restart_and_save_updates_named_file(self):
        a=self.a;path=self.named('FIRST');a.track()['gain']=45
        a.open_name_dialog('RENAME',path);a.name_value='RENAMED';a.finish_project_name()
        self.assertEqual(a.active_project_file(),path);self.assertEqual(load_json(path,{})['name'],'RENAMED')
        b=Application(self.temp.name);self.assertEqual(b.project['name'],'RENAMED')
        b.track()['gain']=30;b.save();self.assertEqual(load_json(path,{})['groups'][0]['pads'][0]['gain'],30)
        validate_project(b.project)
    def test_new_dialog_preserves_previous_and_rejects_duplicate_or_empty(self):
        a=self.a;old=self.named('OLD');a.track()['gain']=55
        a.start_new();self.assertEqual(a.page,'PROJECT NAME');a.name_value='OLD';a.finish_project_name()
        self.assertEqual(a.message,'NAME ALREADY EXISTS');self.assertEqual(len(a.project_files()),1)
        a.name_value='';a.finish_project_name();self.assertEqual(a.message,'ENTER A NAME')
        a.name_value='NEW';a.finish_project_name()
        self.assertEqual(a.project['name'],'NEW');self.assertEqual(a.track()['gain'],80)
        self.assertEqual(load_json(old,{})['groups'][0]['pads'][0]['gain'],55)
        self.assertEqual(len(a.project_files()),2)
    def test_nonactive_rename_and_confirmed_delete_do_not_touch_samples(self):
        a=self.a;old=self.named('OLD');current=self.named('CURRENT')
        sample=Path(self.temp.name)/'samples'/'keep.wav';sample.write_bytes(b'keep')
        a.open_name_dialog('RENAME',old);a.name_value='ARCHIVE';a.finish_project_name()
        self.assertEqual(load_json(old,{})['name'],'ARCHIVE');self.assertEqual(a.project['name'],'CURRENT')
        a.page='PROJECT LOAD';a.confirm_project_delete(old);a.button('F1',True);self.assertTrue(old.exists())
        a.confirm_project_delete(old);a.button('F2',True);self.assertFalse(old.exists());self.assertTrue(current.exists())
        a.confirm_project_delete(current);a.button('F2',True);self.assertIsNone(a.active_project_file())
        a.save();self.assertEqual(a.project_files(),[]);self.assertTrue(sample.exists())
        self.assertIsNone(Application(self.temp.name).active_project_file())
    def test_name_editor_cursor_characters_random_cancel_and_display(self):
        a=self.a;a.page='PROJECT';a.button('F3',True);a.button('ENTER',True)
        self.assertEqual(a.page,'PROJECT NAME');self.assertEqual(a.name_value,'');a.name_value='A';a.rotate(1);self.assertEqual(a.name_value,'B')
        a.button('NAV RIGHT',True);a.rotate(1);self.assertEqual(a.name_value,'BA')
        a.button('F2',True);self.assertRegex(a.name_value,r'^[A-Z]+ [A-Z]+$')
        a.button('SHIFT',True);self.assertEqual(a.softkeys()[0],'CLEAR')
        a.button('F1',True);self.assertEqual(a.name_value,'');self.assertEqual(a.page,'PROJECT NAME')
        self.assertEqual(a.name_cursor,0);a.button('SHIFT',False)
        self.assertEqual(a.softkeys()[0],'CANCEL')
        a.name_cursor=31;p=frame(a);self.assertEqual(len(p),8192);self.assertTrue(all(p[63*128:]))
        a.button('F1',True);self.assertEqual(a.page,'PROJECT MANAGE');self.assertEqual(a.project_files(),[])

    def test_random_pool_has_many_unique_names_and_remembers_recent_after_restart(self):
        from app.project_names import FIRST,SECOND
        self.assertGreater(len(FIRST)*len(SECOND),10000)
        a=self.a;names={a.random_project_name() for _ in range(600)}
        self.assertEqual(len(names),600)
        recent=set(a.settings['recent_project_names']);self.assertEqual(len(recent),512)
        b=Application(self.temp.name)
        self.assertTrue(all(b.random_project_name() not in recent for _ in range(50)))
