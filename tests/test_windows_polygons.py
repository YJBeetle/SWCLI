import copy
import importlib.util
import math
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest import mock

from swcli.hosts import windows_polygons as native
from swcli.polygon_geometry import validate_polygon


POINTS = [dict(x=0, y=0), dict(x=20, y=0), dict(x=0, y=15)]


def sketch(points=POINTS):
    def point(p):
        return NS(X=p['x'] / 1000, Y=p['y'] / 1000, Z=0)
    edges = [NS(ConstructionGeometry=False, GetType=lambda: 0,
                GetStartPoint2=point(p), GetEndPoint2=point(points[(i + 1) % len(points)]))
             for i, p in enumerate(points)]
    return NS(GetSketchSegments=edges, GetSketchContours=[NS(IsClosed=True)])


class PolygonNativeBoundaryTests(unittest.TestCase):
    def test_native_order_does_not_replace_requested_cycle(self):
        observed = sketch(); observed.GetSketchSegments.reverse()
        result = native.observe_polygon_sketch(observed, validate_polygon(POINTS))
        self.assertTrue(result['passed'])
        self.assertEqual(result['signed_area_mm2'], 150)
        self.assertEqual(result['perimeter_mm'], 60)
        self.assertEqual(result['actual_vertices_mm'], POINTS)

    def test_incomplete_wrong_or_ambiguous_native_readback_never_passes(self):
        def wrong_z(s): s.GetSketchSegments[0].GetStartPoint2.Z = 1
        def wrong_x(s): s.GetSketchSegments[0].GetStartPoint2.X = .001
        mutations = [wrong_z, wrong_x,
            lambda s: s.GetSketchSegments.append(s.GetSketchSegments[0]),
            lambda s: s.GetSketchSegments.__setitem__(0, s.GetSketchSegments[1]),
            lambda s: setattr(s, 'GetSketchSegments', None),
            lambda s: setattr(s.GetSketchSegments[0], 'ConstructionGeometry', True),
            lambda s: setattr(s.GetSketchSegments[0], 'GetType', True),
            lambda s: setattr(s.GetSketchSegments[0].GetStartPoint2, 'X', math.nan),
            lambda s: setattr(s, 'GetSketchContours', []),
            lambda s: setattr(s.GetSketchContours[0], 'IsClosed', False),
            lambda s: setattr(s.GetSketchContours[0], 'IsClosed', 1),
        ]
        for mutation in mutations:
            value = sketch(); mutation(value)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                native.observe_polygon_sketch(value, validate_polygon(POINTS))

    def test_invalid_inputs_do_not_access_native_document(self):
        app, document = mock.Mock(), mock.Mock()
        for plane, points in [('front', POINTS + POINTS[:1]), ('oops', POINTS), ('top', None)]:
            result, handle = native.create_polygon_sketch_windows_with_handle(
                app=app, document=document, plane=plane, vertices_mm=points)
            self.assertFalse(result['ok']); self.assertEqual(result['error']['type'], 'InvalidArgument')
            self.assertIsNone(handle)
        self.assertEqual(app.mock_calls, []); self.assertEqual(document.mock_calls, [])

    def test_partial_line_failure_retains_handle_and_does_not_retry(self):
        feature = object(); manager = NS(AddToDB=False, CreateLine=mock.Mock(side_effect=[object(), RuntimeError('native failure')]))
        def lifecycle(**kwargs):
            try: kwargs['create_segments'](manager)
            except RuntimeError as exc: return dict(ok=False, action='sketch.polygon', error={'message':str(exc)}), feature
            raise AssertionError('failure hidden')
        with mock.patch.object(native, '_create_profile_sketch_windows_with_handle', side_effect=lifecycle):
            result, actual = native.create_polygon_sketch_windows_with_handle(
                app=object(), document=object(), plane='front', vertices_mm=POINTS)
        self.assertFalse(result['ok']); self.assertIs(actual, feature)
        self.assertEqual(manager.CreateLine.call_count, 2); self.assertIs(manager.AddToDB, False)


spec = importlib.util.spec_from_file_location('polygon_calibration', Path(__file__).resolve().parents[1] / 'scripts/ci/verify-polygon-calibration.py')
gate = importlib.util.module_from_spec(spec); spec.loader.exec_module(gate)


class PolygonCalibrationTests(unittest.TestCase):
    def test_independent_boss_and_blind_cut_oracles_reject_wrong_geometry(self):
        for shape, perimeter in [('triangle', 60), ('ell', 70)]:
            for mode in ('boss', 'cut'):
                volume, area = (1500, 300 + perimeter * 10) if mode == 'boss' else (11250, 3800 + perimeter * 5)
                valid = dict(solid_body_count=1, volume_mm3=volume, surface_area_mm2=area)
                gate.verify_geometry(valid, shape, 'front', False, mode)
                for key, value in [('solid_body_count', 2), ('volume_mm3', volume - 1), ('surface_area_mm2', area - 1), ('volume_mm3', float('nan'))]:
                    invalid = {**valid, key:value}
                    with self.subTest(shape=shape, mode=mode, key=key), self.assertRaises(RuntimeError):
                        gate.verify_geometry(invalid, shape, 'front', False, mode)


if __name__ == '__main__':
    unittest.main()
