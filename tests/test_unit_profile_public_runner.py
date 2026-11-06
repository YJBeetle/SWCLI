"""Owned public-host lifecycle, no restart and no stop at an unproven endpoint."""
import importlib.util
import itertools
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('public_units_runner_test',ROOT/'scripts/ci/run-unit-profile-public.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)

class PublicRunnerTests(unittest.TestCase):
    def setup_case(self,*,ready=True,worker_code=0):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        root=Path(temp.name);fixtures=root/'fixtures';fixtures.mkdir();(fixtures/'report.json').write_text('{"success":true}')
        self.args=SimpleNamespace(fixture_dir=fixtures,output_dir=root/'output')
        self.daemon=SimpleNamespace(pid=321,returncode=None)
        self.daemon.poll=lambda:self.daemon.returncode
        self.daemon.wait=mock.Mock(side_effect=lambda timeout: self.daemon.returncode)
        self.daemon.terminate=mock.Mock(side_effect=lambda:setattr(self.daemon,'returncode',-15))
        def popen(command,**kw):
            if '-m' in command:
                if ready:kw['stdout'].write(b'{"action": "daemon.serve"}\n');kw['stdout'].flush()
                return self.daemon
            return SimpleNamespace(pid=322,returncode=worker_code,poll=lambda:worker_code)
        self.popen=mock.Mock(side_effect=popen)
        def stop(command,**kw):
            self.daemon.returncode=0
            return SimpleNamespace(returncode=0,stdout=b'{"success":true}',stderr=b'')
        self.stop=mock.Mock(side_effect=stop)
    def invoke(self,clock=None):
        with mock.patch.object(runner,'solidworks_process_ids',return_value=[]),mock.patch.object(runner.subprocess,'Popen',self.popen),mock.patch.object(runner.subprocess,'run',self.stop),mock.patch.object(runner.time,'monotonic',side_effect=itertools.chain(clock or [0,1],itertools.repeat((clock or [0,1])[-1]))):
            runner.execute(self.args)
    def test_success_creates_one_daemon_one_worker_and_shutdown_once(self):
        self.setup_case();self.invoke()
        self.assertEqual(self.popen.call_count,2)
        self.stop.assert_called_once()
        self.assertIn('stop',self.stop.call_args.args[0])
        self.assertNotIn('--attach',self.popen.call_args_list[0].args[0])
        self.daemon.terminate.assert_not_called()
    def test_worker_failure_keeps_first_error_stops_owned_daemon_no_restart(self):
        self.setup_case(worker_code=1)
        with self.assertRaisesRegex(RuntimeError,'public CLI acceptance failed'):self.invoke()
        self.assertEqual(self.popen.call_count,2)
        self.stop.assert_called_once()
    def test_startup_timeout_never_sends_shutdown_to_unproven_endpoint(self):
        self.setup_case(ready=False)
        with self.assertRaisesRegex(RuntimeError,'readiness deadline'):self.invoke(clock=[0,181])
        self.assertEqual(self.popen.call_count,1)
        self.stop.assert_not_called()
        self.daemon.terminate.assert_called_once()
    def test_group_budget_boundary(self):
        self.assertFalse(runner.group_expired(0,1800))
        self.assertTrue(runner.group_expired(0,1801))
