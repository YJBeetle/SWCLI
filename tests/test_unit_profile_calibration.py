"""Budget, durable evidence and opt-in workflow wiring without native COM."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('unit_calibration',ROOT/'scripts/ci/calibrate-document-unit-profile.py')
calibration=importlib.util.module_from_spec(spec);spec.loader.exec_module(calibration)

class UnitCalibrationTests(unittest.TestCase):
    def test_watchdog_limits_nested_calls_and_group(self):
        self.assertFalse(calibration.expired(600,0,{1:0}))
        self.assertTrue(calibration.expired(601,0,{1:0,2:500}))
        self.assertFalse(calibration.expired(1799,0,{}))
        self.assertTrue(calibration.expired(1801,0,{}))
    def test_complete_same_bytes_only_skip(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'report.json'
            calibration.durable(p,dict(success=False))
            stamp=p.stat().st_mtime_ns
            calibration.durable(p,dict(success=False))
            self.assertEqual(stamp,p.stat().st_mtime_ns)
            p.write_text('{')
            calibration.durable(p,dict(success=False))
            self.assertIn('false',p.read_text())
    def test_workflow_dispatch_only_branch_and_full_gate_is_skipped(self):
        workflow=(ROOT/'.github/workflows/ci.yml').read_text()
        self.assertIn("inputs.units_calibration && github.ref == 'refs/heads/codex/docprops-units-expanded'",workflow)
        self.assertNotIn('pull_request_target',workflow)
        self.assertIn('default: false',workflow.split('units_calibration:',1)[1].split('permissions:',1)[0])
        self.assertEqual(workflow.count('if: ${{ !inputs.units_calibration }}'),3)
        self.assertIn('python -I scripts/ci/calibrate-document-unit-profile.py',workflow)
        self.assertIn('if: always()',workflow.split('name: Upload SWCLI-generated smoke evidence')[1][:40])
