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
        import yaml
        job=yaml.load(workflow,Loader=yaml.BaseLoader)['jobs']['solidworks-e2e']
        conditions={step.get('id'):step.get('if','') for step in job['steps']}
        for ident in ('property_fixtures','annotation_fixtures','native_tests'):
            self.assertIn("needs.native-profile.outputs.profile == 'full'",conditions[ident])
            self.assertNotIn('units',conditions[ident])  # Units resolves as portable in this independent profile gate.
        self.assertIn('python -I scripts/ci/calibrate-document-unit-profile.py',workflow)
        self.assertIn('if: always()',workflow.split('name: Upload SWCLI-generated smoke evidence')[1][:40])

    def test_units_group_is_profile_ref_scoped_only_for_manual_units(self):
        workflow=(ROOT/'.github/workflows/ci.yml').read_text()
        native=workflow.split('  solidworks-e2e:',1)[1].split('    env:',1)[0]
        self.assertIn("group: ${{ github.event_name == 'workflow_dispatch' && inputs.units_calibration && format('swcli-units-read-cas-{0}', github.ref) ||",native)
        self.assertIn("|| 'swcli-hosted-windows-solidworks' }}",native)
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

    def test_approved_centroid_bound_is_absolute_inclusive_and_units_only(self):
        import math
        from copy import deepcopy
        before=dict(solid_body_count=1,volume_mm3=12000.0,surface_area_mm2=3800.0,centroid_mm=dict(x=0.0,y=0.0,z=0.0))
        for axis in 'xyz':
            for sign in (-1,1):
                for delta in (0.0,1e-12,math.nextafter(1e-12,math.inf)):
                    with self.subTest(axis=axis,sign=sign,delta=delta):
                        after=deepcopy(before);after['centroid_mm'][axis]=sign*delta
                        if delta<=1e-12:calibration.require_unit_geometry_unchanged(before,after,'geometry changed')
                        else:
                            with self.assertRaises(RuntimeError):calibration.require_unit_geometry_unchanged(before,after,'geometry changed')
        after=deepcopy(before);before['centroid_mm']['x']=1e6;after['centroid_mm']['x']=1e6+1e-9
        with self.assertRaises(RuntimeError):calibration.require_unit_geometry_unchanged(before,after,'no relative tolerance')
    def test_volume_area_and_entity_count_remain_exact(self):
        import math
        from copy import deepcopy
        before=dict(solid_body_count=1,volume_mm3=12000.0,surface_area_mm2=3800.0,centroid_mm=dict(x=0.0,y=0.0,z=5.0))
        for field in ('volume_mm3','surface_area_mm2'):
            for direction in (math.inf,-math.inf):
                after=deepcopy(before);after[field]=math.nextafter(before[field],direction)
                with self.subTest(field=field,direction=direction),self.assertRaises(RuntimeError):
                    calibration.require_unit_geometry_unchanged(before,after,'one ULP must fail')
        for count in (2,True,1.0):
            after=deepcopy(before);after['solid_body_count']=count
            with self.assertRaises(RuntimeError):calibration.require_unit_geometry_unchanged(before,after,'count must be exact int')
    def test_nonfinite_metrics_rejected_on_either_side(self):
        from copy import deepcopy
        before=dict(solid_body_count=1,volume_mm3=12000.0,surface_area_mm2=3800.0,centroid_mm=dict(x=0.0,y=0.0,z=5.0))
        for side in ('before','after'):
            for field in ('volume_mm3','surface_area_mm2','x','y','z'):
                for value in (float('nan'),float('inf'),-float('inf')):
                    left,right=deepcopy(before),deepcopy(before)
                    target=left if side=='before' else right
                    if field in 'xyz':target['centroid_mm'][field]=value
                    else:target[field]=value
                    with self.subTest(side=side,field=field,value=value),self.assertRaises(RuntimeError):
                        calibration.require_unit_geometry_unchanged(left,right,'nonfinite must fail')
    def test_approved_centroid_delta_keeps_raw_hex_and_exact_false(self):
        from copy import deepcopy
        before=dict(solid_body_count=1,volume_mm3=12000.0,surface_area_mm2=3800.0,centroid_mm=dict(x=0.0,y=0.0,z=5.0))
        after=deepcopy(before);after['centroid_mm']['x']=1e-12
        case={};saved=[]
        calibration.record_exact_geometry(before,after,case,'comparison',lambda:saved.append(deepcopy(case)),'geometry changed')
        self.assertFalse(case['comparison']['exact_equal'])
        self.assertTrue(case['comparison']['accepted_under_units_centroid_bound'])
        self.assertEqual(case['comparison']['differences']['centroid_mm.x']['after_hex'],(1e-12).hex())
        self.assertFalse(saved[0]['comparison']['accepted_under_units_centroid_bound'])
        self.assertTrue(saved[-1]['comparison']['accepted_under_units_centroid_bound'])

    def test_write_journal_fsyncs_every_nested_call_without_reserializing_report(self):
        import json
        from unittest import mock
        with tempfile.TemporaryDirectory() as folder:
            with (Path(folder)/'trace.jsonl').open('w',encoding='utf-8') as trace:
                persist=mock.Mock()
                call=calibration.traced_calls(trace,persist,checkpoint_each_call=False)
                with mock.patch.object(calibration.os,'fsync',wraps=calibration.os.fsync) as fsync:
                    self.assertEqual(call('outer',lambda:call('native-getter',lambda:42)),42)
                    self.assertEqual(fsync.call_count,4)
                persist.assert_not_called()
            rows=[json.loads(s) for s in (Path(folder)/'trace.jsonl').read_text().splitlines()]
            self.assertEqual([(r['sequence'],r['phase']) for r in rows],[(1,'begin'),(2,'begin'),(2,'end'),(1,'end')])

    def test_default_read_checkpoint_and_native_exception_no_retry_are_preserved(self):
        import json
        from unittest import mock
        for explicit in (False,True):
            with tempfile.TemporaryDirectory() as folder:
                with (Path(folder)/'trace.jsonl').open('w',encoding='utf-8') as trace:
                    persist=mock.Mock();cause=RuntimeError('first native failure');native=mock.Mock(side_effect=cause)
                    call=calibration.traced_calls(trace,persist,checkpoint_each_call=explicit)
                    with self.assertRaises(RuntimeError) as raised:call('setter',native)
                    self.assertIs(raised.exception,cause);native.assert_called_once()
                    self.assertEqual(persist.call_count,int(explicit))
                rows=[json.loads(s) for s in (Path(folder)/'trace.jsonl').read_text().splitlines()]
                self.assertEqual([r['phase'] for r in rows],['begin','error'])
                self.assertEqual(rows[-1]['error'],'first native failure')

    def test_trace_begin_failure_prevents_any_native_call(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as folder:
            with (Path(folder)/'trace.jsonl').open('w',encoding='utf-8') as trace:
                native=mock.Mock();call=calibration.traced_calls(trace,mock.Mock(),checkpoint_each_call=False)
                with mock.patch.object(calibration.os,'fsync',side_effect=OSError('trace disk failure')):
                    with self.assertRaises(OSError):call('setter',native)
                native.assert_not_called()
