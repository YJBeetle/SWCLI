import ast
from contextlib import redirect_stdout
import importlib.util
from io import StringIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/dev/run-document-properties-calibration.py'
spec = importlib.util.spec_from_file_location('docprops_local_driver', SCRIPT)
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


class CalibrationWatchdogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'trace.jsonl'
        self.progress = driver.TraceProgress(1000)

    def append(self, *rows):
        with self.path.open('a', encoding='utf-8') as stream:
            for row in rows:
                row = dict(row)
                if row.get('phase') in ('end', 'error'): row.setdefault('elapsed_seconds', 0.01)
                stream.write(json.dumps(row) + '\n')

    def test_running_call_enforces_600_even_with_other_progress(self):
        self.append({'phase': 'begin', 'call': 'COM.Set'})
        self.progress.consume(self.path, 1001)
        self.assertIsNone(self.progress.limit_failure(1600.9))
        self.assertEqual(self.progress.limit_failure(1601), 'native-timeout')

    def test_missing_or_stalled_trace_has_same_native_bound(self):
        self.progress.consume(self.path, 1100)
        self.assertEqual(self.progress.limit_failure(1600), 'native-progress-timeout')

    def test_group_deadline_is_not_extended_by_successful_calls(self):
        self.append({'phase': 'begin', 'call': 'COM.Read'}, {'phase': 'end', 'call': 'COM.Read'})
        self.progress.consume(self.path, 2799)
        self.assertIsNone(self.progress.limit_failure(2799.9))
        self.assertEqual(self.progress.limit_failure(2800), 'group-timeout')

    def test_double_terminal_is_rejected(self):
        self.append({'phase': 'begin', 'call': 'COM.Read'}, {'phase': 'end', 'call': 'COM.Read'},
                    {'phase': 'error', 'call': 'COM.Read'})
        with self.assertRaises(ValueError): self.progress.consume(self.path, 1001)

    def test_overlap_or_wrong_terminal_is_rejected(self):
        for rows in (({'phase': 'begin', 'call': 'a'}, {'phase': 'begin', 'call': 'b'}),
                     ({'phase': 'begin', 'call': 'a'}, {'phase': 'end', 'call': 'b'})):
            self.path.unlink(missing_ok=True)
            self.progress = driver.TraceProgress(1000)
            self.append(*rows)
            with self.assertRaises(ValueError): self.progress.consume(self.path, 1001)

    def test_partial_line_is_not_consumed_or_a_successful_terminal(self):
        self.append({'phase': 'begin', 'call': 'a'})
        self.progress.consume(self.path, 1001)
        with self.path.open('a') as stream: stream.write('{"phase":"end","call":"a","elapsed_seconds":0.01}')
        self.progress.consume(self.path, 1100)
        self.assertIsNotNone(self.progress.active)
        self.assertEqual(self.progress.limit_failure(1601), 'native-timeout')
        with self.path.open('a') as stream: stream.write('\n')
        self.progress.consume(self.path, 1602)
        self.assertIsNone(self.progress.active)

    def test_final_partial_tail_cannot_claim_complete_evidence(self):
        self.append({'phase': 'begin', 'call': 'a'}, {'phase': 'end', 'call': 'a'})
        with self.path.open('a') as stream: stream.write('{"phase":')
        with self.assertRaises(ValueError): self.progress.finish(self.path, 1001)

    def test_reported_call_duration_cannot_bypass_watchdog_between_polls(self):
        self.append({'phase': 'begin', 'call': 'a'}, {'phase': 'end', 'call': 'a', 'elapsed_seconds': 600})
        with self.assertRaises(ValueError): self.progress.finish(self.path, 1001)

    def test_final_flush_records_are_counted(self):
        self.append({'phase': 'begin', 'call': 'a'})
        self.progress.consume(self.path, 1001)
        self.append({'phase': 'end', 'call': 'a'})
        self.progress.finish(self.path, 1002)
        self.assertEqual(self.progress.complete_records, 2)

    def test_final_success_cannot_bypass_whole_group_deadline(self):
        self.append({'phase': 'begin', 'call': 'a'}, {'phase': 'end', 'call': 'a'})
        with self.assertRaises(ValueError): self.progress.finish(self.path, 2800)

    def test_empty_trace_cannot_be_a_success(self):
        self.path.write_text('')
        with self.assertRaises(ValueError): self.progress.finish(self.path, 1001)

    def test_error_terminal_allows_cleanup_but_cannot_claim_success(self):
        self.append({'phase': 'begin', 'call': 'a'}, {'phase': 'error', 'call': 'a'},
                    {'phase': 'begin', 'call': 'cleanup'}, {'phase': 'end', 'call': 'cleanup'})
        self.progress.consume(self.path, 1001)
        self.assertEqual(self.progress.error_records, 1)
        self.assertIsNone(self.progress.active)
        with self.assertRaises(ValueError): self.progress.finish(self.path, 1002)

    def test_missing_terminal_elapsed_is_not_defaulted_to_zero(self):
        self.path.write_text('\n'.join(json.dumps(row) for row in
            ({'phase': 'begin', 'call': 'a'}, {'phase': 'end', 'call': 'a'})) + '\n')
        with self.assertRaises(ValueError): self.progress.finish(self.path, 1001)


class WorkerAuthorizationTests(unittest.TestCase):
    """Pure local fixtures only: these subprocesses never import COM or SWCLI."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.source = self.root / 'source'
        (self.source / 'src/swcli').mkdir(parents=True)
        (self.source / 'src/swcli/__init__.py').write_text('')
        self.deps = self.root / 'venv-site-packages'
        self.deps.mkdir()
        (self.deps / 'fixture_venv_dependency.py').write_text('VALUE = 37\n')
        self.site_marker = self.root / 'site-loaded.txt'
        (self.deps / 'fixture.pth').write_text(
            'import pathlib; pathlib.Path(' + repr(str(self.site_marker)) + ').write_text("authorized site")\n')
        self.marker = self.root / 'fixture-executed.txt'
        self.script = self.root / 'fixture.py'
        self.write_fixture()
        self.args = SimpleNamespace(python=driver.default_python(), script=str(self.script),
            source_root=str(self.source), output=str(self.root / 'evidence'), attach_pid=2940,
            stage='read', swconst=None, drawing_template=None, font_typeface=None)

    def write_fixture(self, pid_delta=0, omit_pid=False):
        self.script.write_text('''import argparse, json, os
from pathlib import Path
import fixture_venv_dependency
assert fixture_venv_dependency.VALUE == 37
parser = argparse.ArgumentParser()
parser.add_argument('--attach-pid', type=int)
parser.add_argument('--stage')
parser.add_argument('--output')
args = parser.parse_args()
Path(MARKER).write_text(str(os.getpid()))
out = Path(args.output)
out.mkdir()
(out / 'trace.jsonl').write_text(json.dumps({'phase':'begin','call':'portable-fixture-only'})+'\\n'+json.dumps({'phase':'end','call':'portable-fixture-only','elapsed_seconds':0.001})+'\\n')
report = {'success':True,'cleanup_errors':[],'manual_host_still_running':True,'actual_attach_pid':args.attach_pid}
if not OMIT_PID: report['python_process_id'] = os.getpid() + PID_DELTA
(out / 'report.json').write_text(json.dumps(report))
'''.replace('MARKER',repr(str(self.marker))).replace('OMIT_PID',repr(omit_pid)).replace('PID_DELTA',repr(pid_delta)))

    def config(self):
        folder = self.root / 'driver'
        folder.mkdir()
        with mock.patch.object(driver, 'driver_site_packages', return_value=[driver.normal_path(self.deps)]):
            return driver.worker_config(self.args, self.script, self.source, folder)

    def run_fixture(self):
        with mock.patch.object(driver, 'WORKSPACE_ROOT', self.root), mock.patch.object(
                driver, 'driver_site_packages', return_value=[driver.normal_path(self.deps)]), redirect_stdout(StringIO()):
            code = driver.run(self.args)
        return code, json.loads((self.root / 'evidence-driver/driver.json').read_text())

    def test_default_executable_is_real_base_not_the_driver_venv_launcher(self):
        with mock.patch.object(driver.sys, '_base_executable', str(self.root / 'real-python')), mock.patch.object(
                driver.sys, 'executable', str(self.root / 'venv-launcher')):
            self.assertEqual(driver.default_python(), str(self.root / 'real-python'))

    def test_identity_precedes_authorization_site_and_fixture_execution(self):
        config = self.config()
        command = [driver.default_python(), '-I', '-S', '-c', driver.BOOTSTRAP, json.dumps(config)]
        child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        def cleanup():
            if child.poll() is None: child.kill()
            child.communicate(timeout=5)
        self.addCleanup(cleanup)
        path = Path(config['identity_file'])
        deadline = time.monotonic() + 5
        while not path.exists() and child.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(path.is_file())
        identity = json.loads(path.read_text())
        self.assertEqual(identity, driver.expected_identity(config, child.pid, driver.default_python()))
        self.assertEqual(identity['preauthorization_imports'], [])
        self.assertFalse(self.marker.exists())
        self.assertFalse(self.site_marker.exists())
        self.assertFalse(Path(config['authorization_file']).exists())
        driver.authorize_worker(config, child, driver.default_python())
        stdout, stderr = child.communicate(timeout=5)
        self.assertEqual(child.returncode, 0, (stdout, stderr))
        self.assertTrue(self.marker.exists())
        self.assertTrue(self.site_marker.exists())
        self.assertEqual(int(self.marker.read_text()), child.pid)

    def test_normal_driver_binds_terminal_report_to_authorized_popen_worker(self):
        code, receipt = self.run_fixture()
        self.assertEqual(code, 0, receipt)
        self.assertTrue(receipt['success'])
        self.assertTrue(receipt['worker_authorized'])
        self.assertEqual(receipt['worker_identity']['pid'], receipt['child_python_pid'])
        self.assertEqual(receipt['child_report_python_pid'], receipt['child_python_pid'])
        self.assertEqual(receipt['worker_identity']['parent_pid'], os.getpid())
        self.assertEqual(receipt['driver_site_packages'], [driver.normal_path(self.deps)])
        self.assertFalse(receipt['child_termination_attempted'])
        self.assertFalse(receipt['host_termination_attempted'])

    def test_launcher_pid_mismatch_never_authorizes_or_executes_fixture(self):
        created = []
        class Launcher:
            pid = 54320
            def __init__(inner, command, **kwargs):
                inner.killed = False
                config = json.loads(command[-1])
                # Model a venv shim whose actual interpreter has another PID.
                identity = driver.expected_identity(config, inner.pid + 1, command[0])
                Path(config['identity_file']).write_text(json.dumps(identity))
                inner.config = config
                created.append(inner)
            def poll(inner): return -9 if inner.killed else None
            def kill(inner): inner.killed = True
            def wait(inner, timeout): return -9
        with mock.patch.object(driver.subprocess, 'Popen', side_effect=Launcher):
            code, receipt = self.run_fixture()
        self.assertEqual(code, 1)
        self.assertFalse(receipt['worker_authorized'])
        self.assertIn('PID mismatch', receipt['failure'])
        self.assertFalse(Path(created[0].config['authorization_file']).exists())
        self.assertFalse(self.marker.exists())
        self.assertFalse(self.site_marker.exists())
        self.assertTrue(created[0].killed)  # Only the fake Popen shim was killed.
        self.assertFalse(receipt['host_termination_attempted'])

    def test_missing_authorization_times_out_at_fixed_ten_seconds_without_fixture(self):
        config = self.config()
        with mock.patch.object(sys, 'argv', ['-c', json.dumps(config)]), mock.patch.object(
                time, 'monotonic', side_effect=[0.0, 10.0]), mock.patch.object(time, 'sleep') as sleep:
            with self.assertRaisesRegex(SystemExit, 'within 10 seconds'):
                exec(compile(driver.BOOTSTRAP, '<worker-bootstrap>', 'exec'), {})
        self.assertTrue(Path(config['identity_file']).is_file())
        self.assertFalse(self.marker.exists())
        self.assertFalse(self.site_marker.exists())
        sleep.assert_not_called()
        self.assertEqual(driver.AUTHORIZATION_TIMEOUT_SECONDS, 10)

    def test_wrong_or_missing_terminal_python_pid_is_not_a_success(self):
        for delta, missing in ((1, False), (0, True)):
            with self.subTest(delta=delta, missing=missing):
                self.args.output = str(self.root / ('evidence-' + str(delta) + '-' + str(missing)))
                self.write_fixture(pid_delta=delta, omit_pid=missing)
                with mock.patch.object(driver, 'WORKSPACE_ROOT', self.root), mock.patch.object(
                        driver, 'driver_site_packages', return_value=[driver.normal_path(self.deps)]), redirect_stdout(StringIO()):
                    code = driver.run(self.args)
                receipt = json.loads(Path(self.args.output + '-driver/driver.json').read_text())
                self.assertEqual(code, 1)
                self.assertTrue(receipt['worker_authorized'])
                self.assertFalse(receipt['success'])
                self.assertIn('terminal report Python PID', receipt['failure'])
                self.assertFalse(receipt['child_termination_attempted'])

    def test_completed_error_terminal_retains_original_child_failure_and_cleanup(self):
        original = {'type': 'PermissionError', 'message': 'original report lock first cause'}
        source = self.script.read_text().replace("'phase':'end'", "'phase':'error'")
        source = source.replace("'success':True", "'success':False,'failure':" + repr(original))
        self.script.write_text(source + '\nraise SystemExit(1)\n')
        code, receipt = self.run_fixture()
        self.assertEqual(code, 1)
        self.assertFalse(receipt['success'])
        self.assertEqual(receipt['child_failure'], original)
        self.assertEqual(receipt['child_cleanup_errors'], [])
        self.assertEqual(receipt['child_report_python_pid'], receipt['child_python_pid'])
        self.assertEqual(receipt['trace_error_records'], 1)
        self.assertIn('invalid-final-evidence', receipt['failure'])

    def test_parent_nonce_executable_and_source_must_match_before_grant(self):
        config = self.config()
        child = SimpleNamespace(pid=54320, poll=lambda: None)
        good = driver.expected_identity(config, child.pid, driver.default_python())
        for field, value in (('nonce', 'other-run'), ('parent_pid', os.getpid() + 1),
                             ('executable', '/other/python'), ('source_root', '/other/source'),
                             ('script_args', ['unapproved.py']), ('preauthorization_imports', ['runpy'])):
            with self.subTest(field=field):
                Path(config['identity_file']).write_text(json.dumps({**good, field: value}))
                with self.assertRaisesRegex(ValueError, 'identity/Popen PID mismatch'):
                    driver.authorize_worker(config, child, driver.default_python())
                self.assertFalse(Path(config['authorization_file']).exists())
                self.assertFalse(self.marker.exists())

    def test_forged_authorization_never_reaches_site_or_fixture(self):
        config = self.config()
        Path(config['authorization_file']).write_text(json.dumps({'protocol': driver.IDENTITY_PROTOCOL,
            'authorized_by_pid': os.getppid(), 'identity': {'pid': os.getpid()}}))
        with mock.patch.object(sys, 'argv', ['-c', json.dumps(config)]):
            with self.assertRaisesRegex(SystemExit, 'authorization does not match'):
                exec(compile(driver.BOOTSTRAP, '<worker-bootstrap>', 'exec'), {})
        self.assertFalse(self.marker.exists())
        self.assertFalse(self.site_marker.exists())

    def test_bootstrap_authorizes_before_site_source_and_runpy(self):
        source = driver.BOOTSTRAP
        ast.parse(source)
        grant_check = source.index('if canonical(authorization) != canonical(expected_grant):')
        self.assertLess(source.index('os.getpid()'), grant_check)
        self.assertGreater(source.index('import site'), grant_check)
        self.assertGreater(source.index('site.addsitedir(directory)'), grant_check)
        self.assertGreater(source.index('sys.path.insert'), grant_check)
        self.assertGreater(source.index('import runpy'), grant_check)
        self.assertGreater(source.index('runpy.run_path'), grant_check)
        parent_source = SCRIPT.read_text()
        self.assertIn("'-I', '-S', '-c', BOOTSTRAP", parent_source)
        tree = ast.parse(parent_source)
        kills = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute) and node.func.attr == 'kill']
        self.assertEqual(len(kills), 1)
        self.assertEqual(ast.unparse(kills[0].func), 'child.kill')
        self.assertFalse(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                             and node.func.attr in ('ExitApp','DispatchEx','TerminateProcess') for node in ast.walk(tree)))


class IsolationWorkerConfigTests(unittest.TestCase):
    def test_isolated_host_flag_is_part_of_the_exact_authorized_script_arguments(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args = SimpleNamespace(attach_pid=123, stage='standards', output=str(root / 'output'),
                                   swconst=None, drawing_template=None, font_typeface=None, isolated_host=True)
            with patch.object(driver, 'driver_site_packages', return_value=[]):
                config = driver.worker_config(args, root / 'probe.py', root, root / 'driver')
            self.assertEqual(config['script_args'].count('--isolated-host'), 1)
            expected = driver.expected_identity(config, 456, driver.default_python())
            changed = json.loads(json.dumps(expected))
            changed['script_args'].remove('--isolated-host')
            self.assertFalse(driver.exact_json(changed, expected))


if __name__ == '__main__': unittest.main()
