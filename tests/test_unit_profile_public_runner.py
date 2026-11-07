"""Owned public-host lifecycle, no restart and no stop at an unproven endpoint."""
import importlib.util
import itertools
import json
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
            cli=self.args.output_dir/'cli';cli.mkdir()
            (cli/'public-unit-profile.json').write_text(json.dumps(dict(host=dict(process_id=123,owned_by_daemon=True,visible=False,shared_interactive=False))))
            return SimpleNamespace(pid=322,returncode=worker_code,poll=lambda:worker_code)
        self.popen=mock.Mock(side_effect=popen)
        def stop(command,**kw):
            self.daemon.returncode=0
            return SimpleNamespace(returncode=0,stdout=b'{"success":true}',stderr=b'')
        self.stop=mock.Mock(side_effect=stop)
        self.native_process=SimpleNamespace(Close=mock.Mock())
        self.capture=mock.Mock(return_value=self.native_process)
        self.native_wait=mock.Mock(side_effect=lambda handle:self.assertEqual(self.stop.call_count,1))
    def invoke(self,clock=None):
        with mock.patch.object(runner,'capture_owned_native_process',self.capture),mock.patch.object(runner,'wait_owned_native_process',self.native_wait),mock.patch.object(runner,'solidworks_process_ids',return_value=[]),mock.patch.object(runner.subprocess,'Popen',self.popen),mock.patch.object(runner.subprocess,'run',self.stop),mock.patch.object(runner.time,'monotonic',side_effect=itertools.chain(clock or [0,1],itertools.repeat((clock or [0,1])[-1]))):
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

    def test_native_process_exit_wait_is_once_after_shutdown_and_handle_closed(self):
        self.setup_case();self.invoke()
        self.capture.assert_called_once_with(123)
        self.native_wait.assert_called_once_with(self.native_process)
        self.native_process.Close.assert_called_once()
        report=json.loads((self.args.output_dir/'host-report.json').read_text())
        self.assertTrue(report['owned_native_exit_confirmed'])
    def test_native_exit_timeout_remains_failure_no_api_retry(self):
        self.setup_case();self.native_wait.side_effect=RuntimeError('native exit timeout')
        with self.assertRaisesRegex(RuntimeError,'native exit timeout'):self.invoke()
        self.stop.assert_called_once();self.native_wait.assert_called_once()
        self.native_process.Close.assert_called_once()
    def test_native_capture_failure_still_stops_daemon_once_and_preserves_first_failure(self):
        self.setup_case(worker_code=1);self.capture.side_effect=RuntimeError('capture failed')
        with self.assertRaisesRegex(RuntimeError,'public CLI acceptance failed'):self.invoke()
        self.stop.assert_called_once();self.native_wait.assert_not_called()
