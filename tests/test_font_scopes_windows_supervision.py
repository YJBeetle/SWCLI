"""Supervision tests never launch SOLIDWORKS or import pythoncom."""
import importlib.util
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/ci/run-font-scopes-calibration.py"
spec = importlib.util.spec_from_file_location("_font_watchdog_identity_test", RUNNER)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
supervision = runner.supervision


class FontWindowsSupervisionTests(unittest.TestCase):
    def test_base_launch_retains_venv_and_discards_stale_launcher(self):
        with patch.object(sys, "executable", "/fixtures/venv/Scripts/python.exe"):
            base, env = supervision.base_launch({"__PYVENV_LAUNCHER__": "stale", "GITHUB_SHA": "a" * 40})
        self.assertTrue(os.path.samefile(base, sys._base_executable))
        self.assertEqual(env["__PYVENV_LAUNCHER__"], "/fixtures/venv/Scripts/python.exe")
        self.assertEqual(env["GITHUB_SHA"], "a" * 40)
        with patch.object(sys, "executable", sys._base_executable):
            _, env = supervision.base_launch({"__PYVENV_LAUNCHER__": "stale"})
        self.assertNotIn("__PYVENV_LAUNCHER__", env)

    def test_parent_prefix_pid_and_image_mismatches_fail_closed(self):
        with patch.object(os, "getppid", return_value=524), patch.object(os, "getpid", return_value=748), \
                patch.object(sys, "flags", SimpleNamespace(isolated=1)), \
                patch.object(supervision, "windows_process_image", return_value=sys._base_executable) as image:
            for parent, prefix, wire, reason in (
                (555, sys.prefix, b"748\n", "parent PID"),
                (524, "/wrong/prefix", b"748\n", "Python prefix"),
                (524, sys.prefix, b"555\n", "worker PID"),
                (524, sys.prefix, b"", "worker PID"),
            ):
                with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, reason):
                    supervision.worker_identity(parent, prefix, BytesIO(wire))
            image.assert_not_called()
            proof = supervision.worker_identity(524, sys.prefix, BytesIO(b"748\n"))
            self.assertEqual((proof["worker_pid"], proof["parent_pid"], proof["spawned_pid"]), (748, 524, 748))
            image.return_value = __file__
            with self.assertRaisesRegex(ValueError, "worker image"):
                supervision.worker_identity(524, sys.prefix, BytesIO(b"748\n"))

    def test_parent_accepts_only_proof_for_launched_child(self):
        proof = dict(worker_pid=114, spawned_pid=114, parent_pid=222, claimed_parent_pid=222, prefix=sys.prefix,
                     process_image=sys._base_executable, base_executable=sys._base_executable, isolated=True)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "supervision.json"
            kwargs = dict(worker_pid=114, parent_pid=222, executable=sys._base_executable, prefix=sys.prefix)
            path.write_text(json.dumps(proof))
            supervision.check_worker_proof(path, **kwargs)
            for field, value in (("spawned_pid", 995), ("claimed_parent_pid", 995), ("process_image", __file__)):
                with self.subTest(field=field), self.assertRaises(ValueError):
                    path.write_text(json.dumps({**proof, field: value}))
                    supervision.check_worker_proof(path, **kwargs)

    @unittest.skipUnless(sys.platform == "win32", "requires the Windows process image")
    def test_windows_probe_binds_real_child_and_leaves_no_native_report(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "probe"
            common = ["--scope", "tables", "--swconst", "unused.tlb", "--drawing-template", "unused.drwdot"]
            env = {k: v for k, v in os.environ.items() if k != "GITHUB_SHA"}
            completed = subprocess.run([sys.executable, "-I", str(RUNNER), "--profile", "next-fixture",
                "--output-dir", str(output), "--source-head", "a" * 40, "--supervision-probe", *common],
                capture_output=True, timeout=60, env=env)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            receipt = json.loads((output / "watchdog.json").read_text(encoding="utf-8"))
            proof = json.loads((output / "native/supervision.json").read_text(encoding="utf-8"))
            self.assertTrue(receipt["success"])
            self.assertTrue(receipt["supervision_verified"])
            self.assertEqual(receipt["worker_pid"], proof["worker_pid"])
            self.assertEqual(receipt["supervisor_pid"], proof["parent_pid"])
            self.assertFalse((output / "native/report.json").exists())
            direct = Path(folder) / "direct"
            done = subprocess.run([sys.executable, "-I", str(RUNNER.with_name("prepare-font-scopes-next-fixture.py")),
                "--output-dir", str(direct), "--supervision-probe", *common], input=b"", capture_output=True, timeout=30)
            self.assertEqual(done.returncode, 2, done.stderr)
            self.assertIn(b"watchdog launch pipe", done.stderr)
            self.assertFalse(direct.exists())
