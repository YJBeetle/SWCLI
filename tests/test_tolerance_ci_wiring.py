"""Portable calibration wiring checks; these do not run native CAD."""
import importlib.util
import json
import tempfile
from types import SimpleNamespace
from unittest import mock
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]


class ToleranceCIWiringTests(unittest.TestCase):
    def test_optin_is_default_off_branch_only_and_does_not_run_full_gates(self):
        source=(ROOT/".github/workflows/ci.yml").read_text()
        optin=source.split("      calibrate_tolerances:",1)[1].split("      native_full:",1)[0]
        self.assertIn("default: false",optin)
        self.assertNotIn("pull_request:",source)
        job=source.split("  solidworks-e2e:",1)[1].split("  release:",1)[0]
        self.assertIn("refs/heads/codex/docprops-tolerances",job)
        self.assertIn("native-profile",job)
        self.assertIn("needs.native-profile.result == 'success'",job)
        self.assertNotIn("!inputs.calibrate_tolerances",job)
        gate=job.split("        id: tolerance_calibration",1)[1].split("      - name:",1)[0]
        self.assertIn("needs.native-profile.outputs.profile == 'tolerances-calibration'",gate)
        self.assertIn("verify-tolerance-calibration.py",gate)
        self.assertIn("$LASTEXITCODE -ne 0",gate)
        self.assertIn("timeout-minutes: 31",gate)
        summary=job.split("      - name: Summarize public test evidence",1)[1].split("      - name:",1)[0]
        self.assertIn('if ($env:SWCLI_NATIVE_PROFILE -ne "full")',summary)
        self.assertLess(summary.index("exit 0"),summary.index("summarize-tests.py"))
        self.assertIn("full_acceptance_eligible=false",summary)

    def test_supervisor_bounds_native_span_and_group_without_restart(self):
        spec=importlib.util.spec_from_file_location("_tolerance_supervisor_test",ROOT/"scripts/ci/verify-tolerance-calibration.py")
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for seconds,reason in ((601,"native_span"),(1801,"group")):
            with self.subTest(reason=reason),tempfile.TemporaryDirectory() as temporary:
                output=Path(temporary)/"evidence"
                args=SimpleNamespace(output_dir=output,swconst=Path("official.tlb"),drawing_template=Path("owned.drwdot"))
                process=mock.Mock()
                process.poll.return_value=None
                with mock.patch.object(module.subprocess,"Popen",return_value=process) as start, \
                     mock.patch.object(module.time,"time",side_effect=[0,seconds]), \
                     mock.patch.object(module.time,"sleep"):
                    self.assertEqual(module.supervise(args),124)
                start.assert_called_once()
                process.kill.assert_called_once()
                process.wait.assert_called_once()
                evidence=json.loads((output/"timeout.json").read_text())
                self.assertEqual(evidence["reason"],reason)
                self.assertFalse(evidence["full_acceptance_eligible"])
                self.assertTrue((output/"worker.stderr.log").is_file())

    def test_successful_worker_returns_original_status_without_timeout_or_restart(self):
        spec=importlib.util.spec_from_file_location("_tolerance_supervisor_success",ROOT/"scripts/ci/verify-tolerance-calibration.py")
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)/"evidence"
            args=SimpleNamespace(output_dir=output,swconst=Path("official.tlb"),drawing_template=Path("owned.drwdot"))
            process=mock.Mock(returncode=23)
            process.poll.side_effect=[None,23]
            with mock.patch.object(module.subprocess,"Popen",return_value=process) as start, \
                 mock.patch.object(module.time,"time",return_value=0), \
                 mock.patch.object(module.time,"sleep"):
                self.assertEqual(module.supervise(args),23)
            start.assert_called_once();process.kill.assert_not_called()
            self.assertFalse((output/"timeout.json").exists())


if __name__=="__main__":unittest.main()
