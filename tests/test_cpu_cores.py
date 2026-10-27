import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from app.system_info import read_resources,system_page_count
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.mk2_surface import Mk2Surface
from app.mk2_display import Mk2Renderer,snapshot
from app.ni_display import frame

class CpuCoreTests(unittest.TestCase):
    def test_delta_per_core_hotplug_reset_and_guest_not_double_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc=Path(tmp)
            (proc/'stat').write_text('cpu 100 0 0 300 0 0 0 0 900 0\ncpu0 50 0 0 50 0 0 0 0\ncpu2 50 0 0 250 0 0 0 0\n')
            first,before=read_resources(proc,[],proc=proc)
            self.assertIsNone(first['cpu']);self.assertEqual([x['id'] for x in first['cpu_cores']],[0,2])
            self.assertTrue(all(x['percent'] is None for x in first['cpu_cores']))
            (proc/'stat').write_text('cpu 200 0 0 400 0 0 0 0 999 0\ncpu0 150 0 0 50 0 0 0 0\ncpu2 50 0 0 350 0 0 0 0\ncpu3 500 0 0 500 0 0 0 0\n')
            stats,current=read_resources(proc,[],before,proc)
            self.assertEqual(stats['cpu'],50)
            self.assertEqual(stats['cpu_cores'],[dict(id=0,percent=100),dict(id=2,percent=0),dict(id=3,percent=None)])
            (proc/'stat').write_text('cpu 1 0 0 2 0 0 0 0\ncpu0 1 0 0 1 0 0 0 0\n')
            reset,_=read_resources(proc,[],current,proc);self.assertIsNone(reset['cpu']);self.assertIsNone(reset['cpu_cores'][0]['percent'])

    def test_core_pages_leave_every_storage_page_accessible(self):
        with tempfile.TemporaryDirectory() as root:
            a=Application(root);a.page='SYSTEM'
            a.system_stats={'cpu':40,'cpu_cores':[dict(id=i,percent=value) for i,value in enumerate((100,20,10,30))],'ram':{'percent':30},'storage':[dict(name=n,percent=25,total=32e9,used=8e9) for n in ('SD CARD','USB A','USB B')]}
            self.assertEqual(system_page_count(a.system_stats),5);self.assertEqual(system_page_count(a.system_stats,'mk2'),4)
            before=copy.deepcopy(a.project);s=Mk2Surface(a,ControllerInputs(a));r=Mk2Renderer()
            try:
                micro=[];large=[]
                for i in range(5):a.system_index=i;micro.append(frame(a))
                for i in range(4):a.system_index=i;large.append(r(snapshot(s)))
                self.assertEqual(len(set(micro)),5);self.assertEqual(len(set(large)),4)
                self.assertEqual(a.project,before)
            finally:r.close()
