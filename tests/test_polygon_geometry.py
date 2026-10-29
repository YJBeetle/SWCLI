import math
import unittest

from swcli.polygon_geometry import validate_polygon


def vertices(points):
    return [dict(x=x, y=y) for x, y in points]


class PolygonGeometryTests(unittest.TestCase):
    def test_translated_triangle_both_windings_and_cyclic_origins(self):
        original = [(7, -9), (27, -9), (7, 6)]
        for points in (original, list(reversed(original))):
            for shift in range(3):
                ordered = points[shift:] + points[:shift]
                result = validate_polygon(vertices(ordered))
                self.assertEqual(result.vertices_mm, tuple(ordered))
                self.assertEqual(abs(result.signed_area_mm2), 150)
                self.assertEqual(result.perimeter_mm, 60)
                self.assertAlmostEqual(result.centroid_mm[0], 7 + 20 / 3)
                self.assertAlmostEqual(result.centroid_mm[1], -4)

    def test_concave_l_matches_sum_of_two_rectangles(self):
        points = [(0, 0), (20, 0), (20, 5), (5, 5), (5, 15), (0, 15)]
        for sign, ordered in ((1, points), (-1, list(reversed(points)))):
            result = validate_polygon(vertices(ordered))
            self.assertEqual(result.signed_area_mm2, sign * 150)
            self.assertEqual(result.perimeter_mm, 70)
            self.assertAlmostEqual(result.centroid_mm[0], (100 * 10 + 50 * 2.5) / 150)
            self.assertAlmostEqual(result.centroid_mm[1], (100 * 2.5 + 50 * 10) / 150)

    def test_large_offset_does_not_lose_local_area(self):
        offset = 1e8
        result = validate_polygon(vertices([(offset, offset), (offset + 20, offset), (offset, offset + 15)]))
        self.assertEqual(result.signed_area_mm2, 150)

    def test_invalid_topology_is_rejected_without_normalization(self):
        invalid = [
            [(0, 0), (10, 10), (0, 10), (10, 0)],  # crossing
            [(0, 0), (10, 0), (10, 10), (0, 0)],  # explicit closure
            [(0, 0), (5, 0), (10, 0), (10, 10), (0, 10)],  # redundant corner
            [(0, 0), (10, 0), (5, 0), (5, 10)],  # adjacent backtracking
            [(0, 0), (10, 0), (10, 10), (5, 0), (0, 10)],  # touching
            [(0, 0), (10, 0), (10, 10), (5, 0.000001), (0, 10)],  # narrow gap
            [(0, 0), (0.000001, 0), (0, 10)],  # short edge
            [(0, 0), (10, 0), (5, 0.000001)],  # sliver
        ]
        for points in invalid:
            with self.subTest(points=points), self.assertRaises(ValueError):
                validate_polygon(vertices(points))

    def test_numeric_and_shape_contract(self):
        valid = vertices([(0, 0), (20, 0), (0, 15)])
        for value in (None, [], valid[:2], valid * 22, [[0, 0], [1, 0], [0, 1]]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_polygon(value)
        for value in (True, None, '1', math.nan, math.inf, -math.inf, 10**500, 1e308):
            for axis in ('x', 'y'):
                bad = [dict(p) for p in valid]; bad[0][axis] = value
                with self.subTest(value=value, axis=axis), self.assertRaises(ValueError):
                    validate_polygon(bad)
        for point in ({'x': 0}, {'x': 0, 'y': 0, 'z': 0}):
            with self.assertRaises(ValueError):
                validate_polygon([point, *valid[1:]])


if __name__ == '__main__':
    unittest.main()
