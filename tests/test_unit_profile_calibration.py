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

    def test_units_group_is_profile_ref_scoped_only_for_manual_units(self):
        workflow=(ROOT/'.github/workflows/ci.yml').read_text()
        native=workflow.split('  solidworks-e2e:',1)[1].split('    env:',1)[0]
        self.assertIn("group: ${{ github.event_name == 'workflow_dispatch' && inputs.units_calibration && format('swcli-units-read-cas-{0}', github.ref) || 'swcli-hosted-windows-solidworks' }}",native)
        self.assertIn('cancel-in-progress: false',native)
        self.assertIn("github.event_name == 'workflow_dispatch' && inputs.units_calibration && github.ref == 'refs/heads/codex/docprops-units-expanded'",native)
        # Full/tag/release keeps its existing global group; units gets profile+ref.
        self.assertEqual(workflow.count("format('swcli-units-read-cas-{0}', github.ref)"),1)
        self.assertIn('group: swcli-release-${{ github.ref }}',workflow)

    def test_public_acceptance_requires_successful_manual_branch_calibration(self):
        workflow=(ROOT/'.github/workflows/ci.yml').read_text()
        self.assertIn('default: false',workflow.split('units_public_acceptance:',1)[1].split('permissions:',1)[0])
        block=workflow.split('      - name: Verify public document unit profile CLI',1)[1].split('      - name:',1)[0]
        self.assertIn("success() && github.event_name == 'workflow_dispatch' && inputs.units_calibration && inputs.units_public_acceptance && github.ref == 'refs/heads/codex/docprops-units-expanded'",block)
        self.assertIn('timeout-minutes: 32',block)
        self.assertIn('python -I scripts/ci/run-unit-profile-public.py',block)
        self.assertLess(workflow.index('name: Calibrate bounded document unit profile'),workflow.index('name: Verify public document unit profile CLI'))

    def test_closed_domain_refusal_must_not_hide_native_api_failure(self):
        for error in ('UnitProfileCalibrationRequired','ValueError'):
            calibration.require_closed_refusal(dict(ok=False,mutation=dict(attempted=False,may_have_changed=False),error=dict(type=error)))
        for error in ('com_error','RuntimeError','DocumentUnitProfileConflict'):
            with self.assertRaises(RuntimeError):calibration.require_closed_refusal(dict(ok=False,mutation=dict(attempted=False,may_have_changed=False),error=dict(type=error)))

    def test_geometry_mismatch_records_actuals_before_unchanged_exact_assertion(self):
        import math
        from copy import deepcopy
        before=dict(solid_body_count=1,volume_mm3=12000.0,surface_area_mm2=3800.0,centroid_mm=dict(x=0.0,y=0.0,z=5.0))
        after=deepcopy(before);after['volume_mm3']=math.nextafter(before['volume_mm3'],math.inf)
        case={};saved=[]
        observed=calibration.record_geometry(lambda:dict(ok=True,metrics=after),case,'reopened',lambda:saved.append(deepcopy(case)))
        with self.assertRaisesRegex(RuntimeError,'reopened geometry changed'):
            calibration.record_exact_geometry(before,observed,case,'comparison',lambda:saved.append(deepcopy(case)),'reopened geometry changed')
        self.assertEqual(saved[-1]['reopened'],after)
        self.assertFalse(saved[-1]['comparison']['exact_equal'])
        self.assertEqual(saved[-1]['comparison']['differences']['volume_mm3']['after_hex'],after['volume_mm3'].hex())
    def test_analytic_geometry_failure_keeps_complete_native_measurement(self):
        from copy import deepcopy
        result=dict(ok=True,metrics=dict(solid_body_count=1,volume_mm3=13000.0,surface_area_mm2=3800.0,centroid_mm=dict(x=0,y=0,z=5)))
        case={};saved=[]
        with self.assertRaisesRegex(RuntimeError,'analytic box mismatch'):
            calibration.record_geometry(lambda:result,case,'observed',lambda:saved.append(deepcopy(case)))
        self.assertEqual(saved[0]['observed_measurement'],result)
