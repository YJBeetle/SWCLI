"""Offline supervision checks, including one real Python child that cannot invoke CAD."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

CI = Path(__file__).resolve().parents[1] / 'scripts' / 'ci'
sys.path.insert(0, str(CI))
from gate_support import step_periodic_launch as launch, step_periodic_supervisor as supervisor


class PeriodicLaunchTests(unittest.TestCase):
    def test_windows_base_executable_and_clean_venv_launcher(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            base = root/'Python'/'python.exe'
            venv = root/'venv'/'Scripts'/'python.exe'
            base.parent.mkdir()
            venv.parent.mkdir(parents=True)
            base.touch()
            venv.touch()
            with patch.object(launch.sys, 'platform', 'win32'), \
                 patch.object(launch.sys, '_base_executable', str(base)), \
                 patch.dict(os.environ, {'__PYVENV_LAUNCHER__': 'stale'}):
                with patch.object(launch.sys, 'executable', str(venv)):
                    executable, environment = launch.worker_python()
                self.assertEqual(executable, str(base))
                self.assertEqual(environment['__PYVENV_LAUNCHER__'], str(venv))
                self.assertEqual(os.environ['__PYVENV_LAUNCHER__'], 'stale')
                with patch.object(launch.sys, 'executable', str(base)):
                    self.assertNotIn('__PYVENV_LAUNCHER__', launch.worker_python()[1])
                with patch.object(launch.sys, '_base_executable', 'relative.exe'):
                    with self.assertRaisesRegex(RuntimeError, 'absolute worker'):
                        launch.worker_python()

    def test_worker_rejects_wrong_actual_parent_pipe_prefix_or_win32_image(self):
        expected = dict(parent_pid=os.getppid(), parent_prefix=sys.prefix,
                        launch_executable=sys._base_executable)
        pid = os.getpid()
        with patch.object(launch.sys, 'platform', 'win32'), \
             patch.object(launch.sys, 'flags', SimpleNamespace(isolated=1)), \
             patch.object(launch, 'windows_process_image', return_value=sys._base_executable):
            proof = launch.verify_worker_identity(expected, io.BytesIO(f'{pid}\n'.encode()))
            self.assertEqual(proof['worker_pid'], pid)
            with self.assertRaisesRegex(RuntimeError, 'parent differs'):
                launch.verify_worker_identity(dict(expected, parent_pid=-1), None)
            with self.assertRaisesRegex(RuntimeError, 'launch pipe'):
                launch.verify_worker_identity(expected, io.BytesIO(b'0\n'))
            with self.assertRaisesRegex(RuntimeError, 'launch pipe'):
                launch.verify_worker_identity(expected, None)
            with TemporaryDirectory() as other:
                with self.assertRaisesRegex(RuntimeError, 'Python environment'):
                    launch.verify_worker_identity(dict(expected, parent_prefix=other), None)
                wrong_image = Path(other)/'python.exe'
                wrong_image.touch()
                with patch.object(launch, 'windows_process_image', return_value=str(wrong_image)), \
                     self.assertRaisesRegex(RuntimeError, 'image is not'):
                    launch.verify_worker_identity(expected, io.BytesIO(f'{pid}\n'.encode()))

    def test_real_direct_child_pipe_keeps_isolated_environment_without_com(self):
        base, environment = launch.worker_python()
        expected = dict(parent_pid=os.getpid(), parent_prefix=sys.prefix, launch_executable=base)
        command = [
            base, '-I', '-c',
            "import json,sys; sys.path.insert(0,sys.argv[1]); "
            "from gate_support.step_periodic_launch import verify_worker_identity; "
            "print(json.dumps(verify_worker_identity(json.loads(sys.argv[2]),sys.stdin.buffer))); "
            "assert 'pythoncom' not in sys.modules",
            str(CI), json.dumps(expected),
        ]
        with subprocess.Popen(command, executable=base, env=environment,
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
            try:
                stdout, stderr = process.communicate(f'{process.pid}\n'.encode(), timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
                raise
        self.assertEqual(process.returncode, 0, stderr.decode(errors='replace'))
        proof = json.loads(stdout)
        launch.verify_worker_receipt(proof, expected, process.pid)
        with self.assertRaisesRegex(RuntimeError, 'mismatched worker_pid'):
            launch.verify_worker_receipt(proof, expected, process.pid + 1)

    def test_supervisor_uses_popen_pid_and_retains_worker_startup_first_error(self):
        with TemporaryDirectory() as directory:
            output = Path(directory)
            identity = dict(parent_pid=os.getpid(), parent_prefix=sys.prefix,
                            launch_executable=sys.executable)
            sent = []
            class Pipe:
                def __enter__(self):
                    return self

                def write(self, data):
                    sent.append(data)

                def __exit__(self, *exc):
                    return None

            def spawn(command, **options):
                self.assertEqual(options['executable'], sys.executable)
                self.assertEqual(options['stdin'], subprocess.PIPE)
                supervisor.durable_json(output/'worker-startup-failure.json', dict(
                    stage='worker-startup', worker_pid=777, observed_parent_pid=999,
                    error=dict(type='RuntimeError', message='worker parent differs: actual 999, expected parent'),
                ))
                return SimpleNamespace(pid=777, stdin=Pipe(), returncode=1, poll=lambda: 1)

            code, result = supervisor.supervise(['synthetic'], output, launch=identity,
                                                environment={}, spawn=spawn)
            self.assertEqual(code, 1)
            self.assertEqual(sent, [b'777\n'])
            self.assertEqual(result['failure']['type'], 'RuntimeError')
            self.assertIn('worker parent differs', result['failure']['message'])
            self.assertNotIn('terminal_evidence_error', result)

    def test_supervisor_preserves_original_stderr_when_startup_receipt_missing(self):
        with TemporaryDirectory() as directory:
            def spawn(command, **options):
                options['stderr'].write(b'Traceback ...\nRuntimeError: worker parent differs\n')
                options['stderr'].flush()
                return SimpleNamespace(pid=777, returncode=1, poll=lambda: 1)
            code, result = supervisor.supervise(['synthetic'], Path(directory), spawn=spawn)
        self.assertEqual(code, 1)
        self.assertEqual(result['failure']['message'], 'RuntimeError: worker parent differs')
        self.assertEqual(result['failure']['stage'], 'worker-startup')

    def test_missing_final_receipt_does_not_replace_recorded_native_failure(self):
        with TemporaryDirectory() as directory:
            output = Path(directory)
            first = dict(stage='export', type='StepExportError', message='first business error')
            supervisor.durable_json(output/'report.json', dict(failure=first))
            process = SimpleNamespace(pid=777, returncode=1, poll=lambda: 1)
            code, result = supervisor.supervise(['synthetic'], output, spawn=lambda *a, **k: process)
        self.assertEqual(code, 1)
        self.assertEqual(result['failure'], first)
        self.assertEqual(result['terminal_evidence_error']['type'], 'FileNotFoundError')

    def test_supervisor_rejects_unbound_success_before_native_terminal_acceptance(self):
        with TemporaryDirectory() as directory:
            output = Path(directory)
            expected = dict(parent_pid=os.getpid(), parent_prefix=sys.prefix,
                            launch_executable=sys.executable)
            supervisor.durable_json(output/'worker-supervision.json', dict(
                parent_pid=os.getpid(), worker_pid=776, spawned_pid=776,
                prefix=sys.prefix, isolated=True, executable=sys.executable,
                process_image=sys.executable,
            ))
            pipe = io.BytesIO()
            process = SimpleNamespace(pid=777, stdin=pipe, returncode=0, poll=lambda: 0)
            with patch.object(supervisor, 'terminal_result') as terminal:
                code, result = supervisor.supervise(
                    ['synthetic'], output, launch=expected, environment={},
                    spawn=lambda *a, **k: process,
                )
            terminal.assert_not_called()
            self.assertEqual(code, 1)
            self.assertEqual(result['failure']['stage'], 'worker-supervision')
            self.assertIn('mismatched worker_pid', result['failure']['message'])
