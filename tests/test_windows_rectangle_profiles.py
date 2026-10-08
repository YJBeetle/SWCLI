import itertools
import math
from types import SimpleNamespace
import unittest
from unittest import mock

from swcli.hosts.windows_rectangle_profiles import (
    RectangleObservationError,
    observe_rectangle_profile,
)


def point(x, y, z=0):
    return SimpleNamespace(X=x / 1000, Y=y / 1000, Z=z / 1000)


def line(start, end, construction=False):
    return SimpleNamespace(
        ConstructionGeometry=construction,
        GetType=lambda: 0,
        GetStartPoint2=lambda: start,
        GetEndPoint2=lambda: end,
        Select4=mock.Mock(),
    )


class RectangleProfileTests(unittest.TestCase):
    def setUp(self):
        self.corners = [point(-17, -11), point(23, -11),
                        point(23, 19), point(-17, 19)]
        self.edges = [line(self.corners[i], self.corners[(i + 1) % 4])
                      for i in range(4)]
        self.diagonals = [line(self.corners[0], self.corners[2], True),
                          line(self.corners[1], self.corners[3], True)]
        self.segments = self.edges + self.diagonals
        self.sketch = SimpleNamespace(GetSketchSegments=lambda: self.segments)

    def assert_error(self, code):
        with self.assertRaises(RectangleObservationError) as caught:
            observe_rectangle_profile(self.sketch)
        self.assertEqual(caught.exception.code, code)

    def test_observes_exact_edges_sizes_center_and_construction_count(self):
        observed = observe_rectangle_profile(self.sketch)
        self.assertAlmostEqual(observed.width_mm, 40)
        self.assertAlmostEqual(observed.height_mm, 30)
        self.assertEqual(observed.center_mm, (3, 4))
        self.assertEqual(observed.bounds_mm, (-17, -11, 23, 19))
        self.assertIs(observed.bottom_edge, self.edges[0])
        self.assertIs(observed.left_edge, self.edges[3])
        self.assertEqual(observed.native_segment_count, 6)
        self.assertEqual(observed.construction_segment_count, 2)
        self.assertEqual(observed.max_abs_z_mm, 0)
        for edge in self.segments:
            edge.Select4.assert_not_called()

    def test_all_orders_and_reversed_endpoints_keep_geometric_identity(self):
        for order in itertools.permutations(range(4)):
            for mask in range(16):
                edges = [line(self.corners[(i + 1) % 4], self.corners[i])
                         if mask & (1 << i) else self.edges[i] for i in range(4)]
                self.segments = [edges[i] for i in order] + self.diagonals
                observed = observe_rectangle_profile(self.sketch)
                self.assertIs(observed.bottom_edge, edges[0])
                self.assertIs(observed.left_edge, edges[3])

    def test_construction_edges_are_not_required_or_selected(self):
        self.segments = self.edges
        self.assertEqual(observe_rectangle_profile(self.sketch).construction_segment_count, 0)

    def test_absence_and_invalid_collection_are_not_coerced(self):
        for value in (None, False, 0, '', {}, 'edges', iter(self.edges)):
            with self.subTest(value=value):
                self.segments = value
                self.assert_error('DimensionObservationUnavailable')

    def test_segment_limit(self):
        self.segments = self.edges + self.diagonals * 31
        self.assert_error('DimensionObservationUnavailable')

    def test_construction_flags_must_be_native_booleans(self):
        for value in (None, 0, 1, -1, 0.0, 'false'):
            with self.subTest(value=value):
                self.edges[0].ConstructionGeometry = value
                self.assert_error('DimensionObservationUnavailable')

    def test_profile_types_must_be_native_integers(self):
        for value in (None, True, False, 0.0, '0'):
            with self.subTest(value=value):
                self.edges[0].GetType = lambda: value
                self.assert_error('DimensionObservationUnavailable')

    def test_curves_and_extra_or_missing_profile_edges_are_refused(self):
        self.edges[0].GetType = lambda: 1
        self.assert_error('UnsupportedDimensionProfile')
        self.edges[0].GetType = lambda: 0
        for edges in ([], self.edges[:3], self.edges + [self.edges[0]]):
            self.segments = edges
            self.assert_error('UnsupportedDimensionProfile')

    def test_missing_points_and_native_failures_are_not_silently_repaired(self):
        self.edges[0].GetStartPoint2 = lambda: None
        self.assert_error('DimensionObservationUnavailable')
        failure = RuntimeError('native point access failed')
        self.edges[0].GetStartPoint2 = mock.Mock(spec=(), side_effect=failure)
        with self.assertRaises(RuntimeError) as caught:
            observe_rectangle_profile(self.sketch)
        self.assertIs(caught.exception, failure)

    def test_coordinates_are_finite_numbers_not_coerced_strings_or_booleans(self):
        for value in (None, True, False, '0', math.nan, math.inf, -math.inf, 10**1000, 1e308):
            for axis in 'XYZ':
                with self.subTest(value=value, axis=axis):
                    self.setUp()
                    setattr(self.corners[0], axis, value)
                    self.assert_error('DimensionObservationUnavailable')

    def test_coordinate_precision_must_resolve_absolute_tolerance(self):
        self.corners[0].X = 1e20
        self.assert_error('DimensionObservationUnavailable')

    def test_nonplanar_profile_is_refused(self):
        self.corners[0].Z = 0.000001
        self.assert_error('UnsupportedDimensionProfile')

    def test_duplicate_sides_with_correct_bounding_box_are_refused(self):
        self.segments = [self.edges[0], self.edges[1], self.edges[2], self.edges[0]]
        self.assert_error('UnsupportedDimensionProfile')

    def test_diagonals_cannot_replace_sides_even_with_correct_bounds(self):
        self.segments = [self.edges[0], self.edges[2],
                         line(self.corners[0], self.corners[2]),
                         line(self.corners[1], self.corners[3])]
        self.assert_error('UnsupportedDimensionProfile')

    def test_disconnected_corner_interior_or_zero_length_side_is_refused(self):
        for replacement in (line(point(-16, -11), self.corners[1]),
                            line(point(0, -11), self.corners[1]),
                            line(self.corners[0], self.corners[0])):
            self.segments = [replacement] + self.edges[1:]
            self.assert_error('UnsupportedDimensionProfile')

    def test_rotated_rectangle_is_outside_initial_axis_aligned_scope(self):
        corners = [point(0, 0), point(1, 1), point(0, 2), point(-1, 1)]
        self.segments = [line(corners[i], corners[(i + 1) % 4]) for i in range(4)]
        self.assert_error('UnsupportedDimensionProfile')

    def test_degenerate_or_tolerance_ambiguous_corners_are_refused(self):
        for width in (0, 1e-6, 2e-6):
            corners = [point(0, 0), point(width, 0), point(width, 1), point(0, 1)]
            self.segments = [line(corners[i], corners[(i + 1) % 4]) for i in range(4)]
            self.assert_error('UnsupportedDimensionProfile')

    def test_small_native_roundoff_is_reported_without_relative_tolerance(self):
        self.corners[0].Z = 0.5e-9
        observed = observe_rectangle_profile(self.sketch)
        self.assertTrue(math.isclose(observed.max_abs_z_mm, 0.5e-6, rel_tol=1e-15))
        self.corners[0].X += 0.01
        self.assert_error('UnsupportedDimensionProfile')


if __name__ == '__main__':
    unittest.main()
