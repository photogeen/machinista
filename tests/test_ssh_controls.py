import subprocess
import unittest
from unittest.mock import Mock,call
from tools.power_service import SSHManager

class SSHTests(unittest.TestCase):
    def runner(self,state='masked',active='inactive'):
        def run(args,**kw):
            if '--value' in args:out='masked\n'
            elif 'show' in args:out=f'ActiveState={active}\nUnitFileState={state}\n'
            else:out=''
            return subprocess.CompletedProcess(args,0,stdout=out)
        return Mock(side_effect=run)
    def test_masked_fresh_image_status_and_login(self):
        manager=SSHManager(self.runner(),user='machinista')
        self.assertEqual(manager.status(),dict(active=False,enabled=False,user='machinista'))
    def test_enable_uses_fixed_privileged_unit(self):
        run=self.runner('enabled','active');manager=SSHManager(run)
        self.assertTrue(manager.change('ssh-enable')['active'])
        self.assertEqual(run.call_args_list[0].args[0],['systemctl','start','machinista-ssh-enable.service'])
    def test_disable_starts_only_fixed_unit(self):
        run=self.runner();manager=SSHManager(run)
        self.assertFalse(manager.change('ssh-disable')['active'])
        self.assertEqual(run.call_args_list[0].args[0],['systemctl','start','machinista-ssh-disable.service'])
    def test_bad_actions_never_execute(self):
        run=self.runner();manager=SSHManager(run)
        for action in ('enable','ssh-enable; reboot',None):
            with self.assertRaises(ValueError):manager.change(action)
        run.assert_not_called()
    def test_failed_enable_unit_is_reported(self):
        run=Mock(side_effect=subprocess.CalledProcessError(1,'systemctl'))
        with self.assertRaises(subprocess.CalledProcessError):SSHManager(run).change('ssh-enable')
        self.assertEqual(run.call_count,1)
