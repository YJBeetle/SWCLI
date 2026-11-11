"""Dispatch truth table prevents empty-green CAD routing and preserves defaults."""
import importlib.util
import itertools
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('units_route_test',ROOT/'scripts/ci/validate-units-route.py')
route=importlib.util.module_from_spec(spec);spec.loader.exec_module(route)

class UnitsRouteTests(unittest.TestCase):
    def test_all_switches_on_correct_and_wrong_refs(self):
        for ref in (route.UNITS_REF,'refs/heads/main','refs/tags/v1.0'):
            for full,units,public in itertools.product((False,True),repeat=3):
                with self.subTest(ref=ref,full=full,units=units,public=public):
                    invalid=(full and (units or public)) or (public and not units) or ((units or public) and ref!=route.UNITS_REF)
                    args=dict(event='workflow_dispatch',ref=ref,native_full=full,units_calibration=units,units_public_acceptance=public)
                    if invalid:
                        with self.assertRaises(ValueError):route.validate_route(**args)
                    else:
                        expected='units-public' if public else 'units-read-cas' if units else 'full' if full else 'portable'
                        self.assertEqual(route.validate_route(**args),expected)
    def test_nonmanual_units_rejected_and_default_tag_route_preserved(self):
        for event in ('push','pull_request'):
            self.assertEqual(route.validate_route(event=event,ref='refs/tags/v1',native_full=False,units_calibration=False,units_public_acceptance=False),'default')
            with self.assertRaises(ValueError):route.validate_route(event=event,ref=route.UNITS_REF,native_full=False,units_calibration=True,units_public_acceptance=False)
    def test_workflow_validation_is_separate_prerequisite_before_any_native_job(self):
        w=(ROOT/'.github/workflows/ci.yml').read_text()
        preflight=w.split('  units-route:',1)[1].split('  solidworks-e2e:',1)[0]
        self.assertIn("if: ${{ github.event_name == 'workflow_dispatch' }}",preflight)
        self.assertIn('python scripts/ci/validate-units-route.py',preflight)
        self.assertNotIn('secrets.',preflight)
        native=w.split('  solidworks-e2e:',1)[1].split('    runs-on:',1)[0]
        self.assertIn('needs: [test, package, tag-policy, native-profile, units-route]',native)
        self.assertIn("(github.event_name != 'workflow_dispatch' || needs.units-route.result == 'success')",native)
        self.assertIn("github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v') && needs.tag-policy.result == 'success'",native)
        self.assertNotIn('pull_request_target',w)

    def test_write_profile_route_is_bounded_and_requires_calibration(self):
        for ref in (route.UNITS_REF,'refs/heads/main','refs/tags/v1'):
            for full,units,public,writes in itertools.product((False,True),repeat=4):
                invalid=(full and (units or public or writes)) or ((public or writes) and not units) or ((units or public or writes) and ref!=route.UNITS_REF)
                args=dict(event='workflow_dispatch',ref=ref,native_full=full,units_calibration=units,units_public_acceptance=public,units_write_calibration=writes)
                with self.subTest(**args):
                    if invalid:
                        with self.assertRaises(ValueError):route.validate_route(**args)
                    else:
                        expected='units-write-public' if writes and public else 'units-write-diagnostic' if writes else 'units-public' if public else 'units-read-cas' if units else 'full' if full else 'portable'
                        self.assertEqual(route.validate_route(**args),expected)
        with self.assertRaises(ValueError):route.validate_route(event='push',ref=route.UNITS_REF,native_full=False,units_calibration=False,units_public_acceptance=False,units_write_calibration=True)

    def test_write_public_without_reviewed_production_domains_fails_before_native_setup(self):
        from unittest import mock
        import os
        values=dict(ROUTE_EVENT='workflow_dispatch',ROUTE_REF=route.UNITS_REF,ROUTE_NATIVE_FULL='false',ROUTE_UNITS_CALIBRATION='true',ROUTE_UNITS_PUBLIC='true',ROUTE_UNITS_WRITE='true')
        from swcli import document_unit_profile as catalog
        with mock.patch.dict(os.environ,values),mock.patch.object(catalog,'CALIBRATED_UNIT_WRITES',()),mock.patch.object(catalog,'CALIBRATED_UNIT_SYSTEM_RESULTS',()):
            with self.assertRaisesRegex(ValueError,'manually reviewed'):route.main()

class IntegratedUnitsWorkflowTests(unittest.TestCase):
    def test_units_and_another_feature_cannot_both_pass_their_route_preflights(self):
        spec=importlib.util.spec_from_file_location('integrated_native_profiles',ROOT/'scripts/ci/validate-native-profile.py')
        profiles=importlib.util.module_from_spec(spec);spec.loader.exec_module(profiles)
        self.assertNotIn(route.UNITS_REF,profiles.FEATURE_REFS.values())
        for flag,ref in profiles.FEATURE_REFS.items():
            with self.subTest(flag=flag):
                inputs={flag:True,'units_calibration':True,'units_write_calibration':True,'units_public_acceptance':True}
                with self.assertRaises(ValueError):profiles.resolve('workflow_dispatch',route.UNITS_REF,inputs)
                with self.assertRaises(ValueError):route.validate_route(event='workflow_dispatch',ref=ref,native_full=False,units_calibration=True,units_write_calibration=True,units_public_acceptance=True)

    def test_merged_workflow_has_unique_mapping_keys_and_at_most_25_dispatch_inputs(self):
        import yaml
        class UniqueLoader(yaml.BaseLoader):
            pass
        def mapping(loader,node):
            result={}
            for key,value in node.value:
                key=loader.construct_object(key)
                if key in result:raise AssertionError('duplicate workflow key: '+key)
                result[key]=loader.construct_object(value)
            return result
        UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,mapping)
        workflow=yaml.load((ROOT/'.github/workflows/ci.yml').read_text(),Loader=UniqueLoader)
        self.assertLessEqual(len(workflow['on']['workflow_dispatch']['inputs']),25)
        self.assertNotIn('pull_request',workflow['on']);self.assertNotIn('pull_request_target',workflow['on'])
        job=workflow['jobs']['solidworks-e2e']
        self.assertIn('native-profile',job['needs']);self.assertIn('units-route',job['needs'])
        for step in job['steps']:
            if step.get('id') in ('native_tests','property_fixtures'):
                self.assertEqual(step['if'],"${{ needs.native-profile.outputs.profile == 'full' }}")
        self.assertEqual(job['concurrency']['cancel-in-progress'],'false')
