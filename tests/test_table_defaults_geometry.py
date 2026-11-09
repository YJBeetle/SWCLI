"""The explicit table-only centroid bound does not relax other geometry fields."""

from copy import deepcopy
import importlib.util
import math
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('table_geometry_rule_test',
    Path(__file__).resolve().parents[1] / 'scripts/ci/gate_support/table_defaults_geometry.py')
geometry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(geometry)


class TableGeometryTests(unittest.TestCase):
    def metrics(self):
        return dict(solid_body_count=1, volume_mm3=12000.0, surface_area_mm2=3800.0,
                    centroid_mm=dict(x=0.0, y=0.0, z=0.0))

    def test_each_axis_accepts_inside_and_inclusive_boundary_but_rejects_next_float(self):
        bound = 1e-12
        for axis in ('x', 'y', 'z'):
            for delta in (0.0, bound / 2, bound, -bound, math.nextafter(bound, math.inf), -math.nextafter(bound, math.inf)):
                with self.subTest(axis=axis, delta=delta):
                    before, after = self.metrics(), self.metrics()
                    after['centroid_mm'][axis] = delta
                    original = deepcopy(after)
                    result = geometry.compare_table_geometry(before, after)
                    self.assertIs(result['passed'], abs(delta) <= bound)
                    self.assertEqual(result['centroid_delta_mm'][axis], delta)
                    self.assertEqual(result['after_hex']['centroid_mm.' + axis], delta.hex())
                    self.assertEqual(after, original)

    def test_volume_area_single_ulp_body_count_and_other_shapes_remain_strict(self):
        for field in ('volume_mm3', 'surface_area_mm2', 'solid_body_count', 'extra'):
            with self.subTest(field=field):
                before, after = self.metrics(), self.metrics()
                if field == 'extra':
                    after['unexpected'] = 0
                elif field == 'solid_body_count':
                    after[field] = 2
                else:
                    after[field] = math.nextafter(after[field], math.inf)
                self.assertFalse(geometry.compare_table_geometry(before, after)['passed'])

    def test_nonfinite_and_boolean_geometry_are_rejected_on_both_sides(self):
        for value in (math.nan, math.inf, -math.inf, True):
            for side in ('before', 'after'):
                for field in ('centroid', 'volume_mm3', 'surface_area_mm2'):
                    with self.subTest(value=value, side=side, field=field):
                        before, after = self.metrics(), self.metrics()
                        target = before if side == 'before' else after
                        if field == 'centroid': target['centroid_mm']['x'] = value
                        else: target[field] = value
                        self.assertFalse(geometry.compare_table_geometry(before, after)['passed'])

    def test_finite_input_delta_overflow_is_rejected_and_diagnostics_remain_json(self):
        import json
        before, after = self.metrics(), self.metrics()
        before['centroid_mm']['x'], after['centroid_mm']['x'] = -1e308, 1e308
        result = geometry.compare_table_geometry(before, after)
        self.assertFalse(result['passed'])
        self.assertFalse(result['finite'])
        self.assertEqual(result['centroid_delta_hex']['x'], 'inf')
        json.dumps(result, allow_nan=False)
