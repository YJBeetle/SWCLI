"""Portable partial-angle candidate evidence; no native acceptance claim."""

from copy import deepcopy
import math
import unittest
from unittest import mock

from swcli.hosts import windows_revolves as worker
from swcli.operation_schemas import validate_operation_request
from swcli.result_schemas import validate_operation_result, OperationResultInvalid
from swcli.revolve_geometry import (validate_revolve_intent, cylinder_expectation,
                                   sector_expectation, verify_sector_metrics, CALIBRATED_REVOLVE_FRAMES)
import test_revolve as base
from test_revolve import IDENTITY, VALUES


class SectorOracleTests(unittest.TestCase):
    def test_known_quarter_half_and_three_quarter_sector_integrals(self):
        # r=10, h=20; hand-integrated local first moments, independent cases.
        cases = ((90, 500*math.pi, 150*math.pi+400, 40/(3*math.pi), 40/(3*math.pi)),
                 (180, 1000*math.pi, 300*math.pi+400, 0, 40/(3*math.pi)),
                 (270, 1500*math.pi, 450*math.pi+400, -40/(9*math.pi), 40/(9*math.pi)))
        for angle, volume, area, x, z in cases:
            for sign in (-1, 1):
                with self.subTest(angle=angle, sign=sign):
                    expected = sector_expectation([0,-5,10,15], IDENTITY, angle, rotation_sign=sign)
                    self.assertAlmostEqual(expected['volume_mm3'], volume)
                    self.assertAlmostEqual(expected['surface_area_mm2'], area)
                    for axis, value in zip('xyz', (x, 5, sign*z)):
                        self.assertAlmostEqual(expected['centroid_mm'][axis], value)
                    verify_sector_metrics(expected, expected)

    def test_all_origin_frames_transform_the_signed_centroid(self):
        d = 40/(3*math.pi)
        centers = ((d,5,d), (d,d,-5), (d,5,-d))
        for frame, center in zip(CALIBRATED_REVOLVE_FRAMES, centers):
            expected = sector_expectation([0,-5,10,15], frame, 90, rotation_sign=1)
            for axis, value in zip('xyz', center):
                self.assertAlmostEqual(expected['centroid_mm'][axis], value)

    def test_nearly_full_sector_keeps_radial_faces_and_full_turn_is_unchanged(self):
        almost = sector_expectation([0,-5,10,15], IDENTITY, math.nextafter(360,0), rotation_sign=1)
        full = cylinder_expectation([0,-5,10,15], IDENTITY)
        self.assertAlmostEqual(almost['surface_area_mm2'] - full['surface_area_mm2'], 400)
        for sign in (-1,1):
            self.assertEqual(sector_expectation([0,-5,10,15], IDENTITY, 360, rotation_sign=sign), full)
        tiny = sector_expectation([0,-5,10,15], IDENTITY, 1e-10, rotation_sign=1)
        self.assertGreater(tiny['centroid_mm']['z'], 0)
        self.assertAlmostEqual(tiny['centroid_mm']['x'], 20/3)
        self.assertGreater(tiny['volume_mm3'], 0)

    def test_invalid_angle_direction_frame_and_wrong_signed_centroid_refuse(self):
        for angle in (0,-1,360.01,math.inf,math.nan,True,'90'):
            with self.subTest(angle=angle), self.assertRaises(ValueError):
                validate_revolve_intent(VALUES['expected_profile_mm'], VALUES['axis_mm'], angle)
        for sign in (None,0,True,1.0):
            with self.assertRaises(ValueError):
                sector_expectation([0,-5,10,15], IDENTITY, 90, rotation_sign=sign)
        frame = IDENTITY[:];frame[9] = 1
        with self.assertRaises(ValueError):
            sector_expectation([0,-5,10,15], frame, 90, rotation_sign=1)
        expected = sector_expectation([0,-5,10,15], IDENTITY, 90, rotation_sign=1)
        wrong = deepcopy(expected);wrong['centroid_mm']['z'] *= -1
        with self.assertRaisesRegex(ValueError,'analytic sector'):
            verify_sector_metrics(wrong,expected)


class PublicPartialGateTests(unittest.TestCase):
    def test_unevidenced_partial_requests_refuse_before_native_version_or_selection(self):
        intent = [dict(VALUES, angle_deg=angle)
                  for angle in (1e-10, 60, 123.456, math.nextafter(360,0))]
        intent.append(dict(VALUES, angle_deg=90, expected_profile_mm=[0,-5,11,15]))
        for values in intent:
            validate_operation_request('feature.revolve', values, document_id='d-ab12cd', expected_update_stamp=1)
            with mock.patch.object(worker,'_native_constants',side_effect=AssertionError('COM platform read')), \
                 mock.patch.object(worker,'_calibrate_revolve_windows_with_handle') as candidate:
                result, feature = worker.create_revolve_windows_with_handle(
                    app=object(), document=object(), sketch_feature=object(),
                    **{k:v for k,v in values.items() if k!='sketch_id'})
            self.assertIsNone(feature)
            result['sketch_id'] = values['sketch_id']
            validate_operation_result('feature.revolve', result)
            self.assertFalse(any(result['mutation'].values()))
            self.assertEqual(result['error']['type'],'RevolveNotCalibrated')
            candidate.assert_not_called()

    def test_public_success_requires_evidenced_bounds_frame_direction_and_matching_geometry(self):
        from test_result_schemas import DOCUMENT
        from test_windows_features import DIAGNOSTICS
        result = dict(ok=True,action='feature.revolve',document=DOCUMENT,**VALUES,
            mutation=dict(attempted=True,creation_returned=True,may_have_changed=True),cleanup_errors=[],
            feature=dict(name='Revolve',type='Revolution',feature_id='f-ab12cd'),verified=True,
            diagnostics=DIAGNOSTICS,model_to_sketch_transform=IDENTITY,
            definition=dict(cleanup_errors=[],angle_rad=2*math.pi,reverse=False,kind=0,boss=True,
                thin=False,merge=True,axis_type=10,contour_count=0,axis_matches=True),
            expected_metrics=cylinder_expectation([0,-5,10,15],IDENTITY),
            metrics=cylinder_expectation([0,-5,10,15],IDENTITY))
        validate_operation_result('feature.revolve',result)
        for frame in CALIBRATED_REVOLVE_FRAMES:
            for angle in (45, 90, 180, 270):
                expected = sector_expectation(VALUES['expected_profile_mm'], frame, angle, rotation_sign=-1)
                confirmed = deepcopy(result)
                confirmed.update(angle_deg=angle, model_to_sketch_transform=list(frame),
                                 expected_metrics=expected, metrics=deepcopy(expected))
                confirmed['definition'].update(angle_rad=math.radians(angle),
                                               axis_points_mm=[[0,-5,0],[0,15,0]])
                validate_operation_result('feature.revolve',confirmed)
        for break_evidence in (
                lambda r: r.update(angle_deg=60),
                lambda r: r.update(expected_profile_mm=[0,-5,11,15]),
                lambda r: r.update(model_to_sketch_transform=[-1,*IDENTITY[1:]]),
                lambda r: r['definition'].pop('axis_points_mm'),
                lambda r: r['definition']['axis_points_mm'].reverse(),
                lambda r: r['definition'].update(angle_rad=math.pi),
                lambda r: r['metrics']['centroid_mm'].update(z=3)):
            altered = deepcopy(confirmed)
            break_evidence(altered)
            with self.assertRaises(OperationResultInvalid):
                validate_operation_result('feature.revolve',altered)


class PartialCandidateTests(unittest.TestCase):
    setUp = base.CandidateTests.setUp
    call = base.CandidateTests.call
    def partial(self, angle=90, **updates):
        return self.call(angle_deg=angle, rotation_sign=1, axis_direction=1, **updates)

    def prepare(self, angle=90, sign=1):
        self.definition.GetRevolutionAngle = lambda forward: math.radians(angle)
        worker.measure_part_windows.return_value = dict(ok=True,
            metrics=sector_expectation([0,-5,10,15],IDENTITY,angle,rotation_sign=sign))

    def test_public_adapter_preserves_verified_axis_and_post_creation_failure(self):
        for injected_failure in (None, RuntimeError('first definition observation failure')):
            self.document.GetBodies2.return_value=()
            self.prepare(sign=-1)
            with mock.patch.object(worker,'_native_constants',return_value=base.CONSTANTS):
                if injected_failure:
                    self.definition.AccessSelections.side_effect=injected_failure
                result,feature=worker.create_revolve_windows_with_handle(
                    app=self.app,document=self.document,sketch_feature=self.sketch_feature,
                    expected_profile_mm=VALUES['expected_profile_mm'],axis_mm=VALUES['axis_mm'],angle_deg=90)
            self.assertIs(feature,self.feature)
            self.assertNotIn('candidate',result)
            self.assertTrue(all(result['mutation'].values()))
            self.assertEqual(result['ok'],injected_failure is None)
            if injected_failure is None:
                self.assertEqual(result['definition']['axis_points_mm'],[[0,-5,0],[0,15,0]])
            else:
                self.assertEqual(result['error'],dict(type='RuntimeError',message=str(injected_failure)))
        self.assertEqual(self.create.call_count,2)

    def test_discrete_candidates_use_exact_radians_and_ordered_axis_readback(self):
        for angle in (45,90,180,270):
            self.document.GetBodies2.return_value=()
            self.prepare(angle)
            result,feature = self.partial(angle)
            self.assertTrue(result['ok'],result)
            self.assertIs(feature,self.feature)
            self.assertEqual(self.create.call_args.args[8],math.radians(angle))
            self.assertEqual(result['definition']['axis_points_mm'],[(0,-5,0),(0,15,0)])
            self.assertEqual(result['candidate']['axis_direction'],1)
            self.assertEqual(self.selected,[])

    def test_missing_hypothesis_unsupported_angle_and_axis_direction_refuse_before_creation(self):
        for params in (dict(angle_deg=90),dict(angle_deg=90,rotation_sign=1),
                       dict(angle_deg=90,rotation_sign=True,axis_direction=1),
                       dict(angle_deg=123,rotation_sign=1,axis_direction=1)):
            result,feature=self.call(**params)
            self.assertEqual(result['error']['type'],'UnsupportedRevolveCalibration')
            self.assertFalse(any(result['mutation'].values()))
            self.assertIsNone(feature)
        result,_=self.call(angle_deg=90,rotation_sign=1,axis_direction=-1)
        self.assertEqual(result['error']['type'],'RevolveAxisMismatch')
        self.create.assert_not_called()
        self.assertEqual(self.selected,[])

    def test_wrong_rotation_hypothesis_preserves_partial_handle_and_never_retries(self):
        self.prepare(sign=-1)
        result,feature=self.partial()
        self.assertFalse(result['ok'])
        self.assertIn('analytic sector',result['error']['message'])
        self.assertIs(feature,self.feature)
        self.assertTrue(all(result['mutation'].values()))
        self.create.assert_called_once()
        self.assertEqual(self.selected,[])

    def test_partial_definition_angle_and_ordered_axis_faults_keep_first_failure(self):
        self.prepare()
        self.definition.GetRevolutionAngle=lambda forward:math.pi
        result,feature=self.partial()
        self.assertEqual(result['error']['type'],'RevolveDefinitionMismatch')
        self.assertIs(feature,self.feature)
        self.assertTrue(all(result['mutation'].values()))
        self.create.assert_called_once()

    def test_definition_readback_accepts_a_fresh_reopened_axis_handle_with_original_endpoints(self):
        from types import SimpleNamespace as NS
        self.prepare()
        reopened_axis = NS(GetStartPoint2=self.axis.GetStartPoint2, GetEndPoint2=self.axis.GetEndPoint2)
        self.definition.Axis = reopened_axis
        evidence = worker.observe_revolve_definition(self.app, self.document, self.feature,
            reopened_axis, base.CONSTANTS, angle_deg=90, expected_axis_points_mm=[(0,-5,0),(0,15,0)])
        self.assertEqual(evidence['axis_points_mm'],[(0,-5,0),(0,15,0)])
        self.assertTrue(evidence['axis_matches'])
        self.create.assert_not_called()
        self.definition.ReleaseSelectionAccess.assert_called_once()

    def test_ordered_axis_reversal_after_creation_is_a_partial_failure(self):
        self.prepare()
        create=self.create.side_effect
        def reverse_axis(*args):
            feature=create(*args)
            self.axis.GetStartPoint2,self.axis.GetEndPoint2=self.axis.GetEndPoint2,self.axis.GetStartPoint2
            return feature
        self.create.side_effect=reverse_axis
        self.definition.ReleaseSelectionAccess.side_effect=RuntimeError('secondary release failure')
        result,feature=self.partial()
        self.assertEqual(result['error']['type'],'RevolveAxisMismatch')
        self.assertEqual(result['definition']['axis_points_mm'],[(0,15,0),(0,-5,0)])
        self.assertIn('secondary release failure',result['definition']['cleanup_errors'][0]['error'])
        self.assertIs(feature,self.feature)
        self.assertTrue(all(result['mutation'].values()))
        self.create.assert_called_once()
        self.assertEqual(self.selected,[])


if __name__ == '__main__':
    unittest.main()
