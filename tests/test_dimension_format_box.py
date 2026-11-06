"""Fixed-box oracle rejects physical changes without rounding coordinates."""
from copy import deepcopy
import importlib.util
from itertools import product, combinations
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("dimension_box_test", ROOT / "scripts/ci/gate_support/dimension_box.py")
box = importlib.util.module_from_spec(spec); spec.loader.exec_module(box)


class DimensionBoxTests(unittest.TestCase):
    def setUp(self):
        self.vertices = list(product((-20.0, 20.0), (-15.0, 15.0), (0.0, 10.0)))
        self.edges = [(a, b) for a, b in combinations(self.vertices, 2) if sum(x != y for x, y in zip(a, b)) == 1]
        self.planes = [(-1., 0., 0., 20.), (1., 0., 0., 20.), (0., -1., 0., 15.),
                       (0., 1., 0., 15.), (0., 0., -1., 0.), (0., 0., 1., 10.)]
        self.metrics = dict(solid_body_count=1, volume_mm3=11999.999999999998,
            surface_area_mm2=3799.9999999999995, centroid_mm=dict(x=-7.058607893785837e-16, y=5.514537417020185e-16, z=5.))

    def fingerprint(self, **change):
        arguments = dict(vertices=self.vertices, edges=self.edges, planes=self.planes, metrics=self.metrics)
        return box.signature(**{**arguments, **change})

    def test_native_dispatch_observation_requires_complete_closed_planar_boundary(self):
        from types import SimpleNamespace
        vertices = {p: SimpleNamespace(GetPoint=lambda p=p: tuple(value / 1000 for value in p)) for p in self.vertices}
        native_edges = {pair: SimpleNamespace(GetCurve=lambda: SimpleNamespace(IsLine=True),
            GetStartVertex=lambda pair=pair: vertices[pair[0]], GetEndVertex=lambda pair=pair: vertices[pair[1]]) for pair in self.edges}
        faces = []
        for plane in self.planes:
            normal, offset = plane[:3], plane[3]
            axis = next(index for index, value in enumerate(normal) if value)
            coordinate = offset / normal[axis]
            boundary = tuple(edge for pair, edge in native_edges.items() if all(p[axis] == coordinate for p in pair))
            faces.append(SimpleNamespace(GetSurface=lambda: SimpleNamespace(IsPlane=True),
                Normal=normal, GetEdges=lambda boundary=boundary: boundary, GetEdgeCount=lambda: 4))
        body = SimpleNamespace(GetVertices=lambda: tuple(vertices.values()), GetVertexCount=lambda: 8,
            GetEdges=lambda: tuple(native_edges.values()), GetEdgeCount=lambda: 12,
            GetFaces=lambda: tuple(faces), GetFaceCount=lambda: 6)
        document = SimpleNamespace(GetBodies2=lambda kind, hidden: (body,) if kind == 0 else ())
        evidence = {}
        self.assertEqual(box.observe_native(document, self.metrics, evidence), self.fingerprint())
        self.assertEqual(evidence["native_counts"], dict(vertices=8, edges=12, faces=6))
        faces[0].GetEdges = lambda: ()
        with self.assertRaises(RuntimeError): box.observe_native(document, self.metrics, {})

    def test_real_no_write_centroid_jitter_does_not_change_exact_geometric_center(self):
        before = self.fingerprint()
        metrics = deepcopy(self.metrics); metrics["centroid_mm"]["y"] = 8.271806125530278e-16
        after = self.fingerprint(metrics=metrics)
        self.assertEqual(before, after)
        self.assertEqual(before["centroid_mm"], dict(x=0., y=0., z=5.))
        self.assertNotEqual(metrics["centroid_mm"], self.metrics["centroid_mm"])

    def test_traversal_and_edge_direction_do_not_define_physical_geometry(self):
        self.assertEqual(self.fingerprint(), self.fingerprint(vertices=list(reversed(self.vertices)),
            edges=[(b, a) for a, b in reversed(self.edges)], planes=list(reversed(self.planes))))

    def test_missing_duplicate_or_moved_boundaries_are_rejected(self):
        displaced = list(self.vertices); p = displaced[0]; displaced[0] = (p[0] + 1e-12, p[1], p[2])
        for change in (dict(vertices=self.vertices[:-1]), dict(vertices=self.vertices[:-1]+[self.vertices[0]]),
                       dict(vertices=displaced), dict(edges=self.edges[:-1]),
                       dict(edges=self.edges[:-1]+[self.edges[0]]), dict(planes=self.planes[:-1]),
                       dict(planes=self.planes[:-1]+[(0., 0., 1., 10.000000000001)])):
            with self.subTest(change=change), self.assertRaises(RuntimeError): self.fingerprint(**change)

    def test_exact_volume_area_remain_in_the_differential_fingerprint(self):
        for key in ("volume_mm3", "surface_area_mm2"):
            metrics = deepcopy(self.metrics); metrics[key] += 1e-10
            self.assertNotEqual(self.fingerprint(), self.fingerprint(metrics=metrics))

    def test_native_analytic_disagreement_is_not_rounded_into_a_pass(self):
        for key, bad in (("volume_mm3", 13000.), ("surface_area_mm2", 4000.)):
            metrics = deepcopy(self.metrics); metrics[key] = bad
            with self.assertRaises(RuntimeError): self.fingerprint(metrics=metrics)
        metrics = deepcopy(self.metrics); metrics["centroid_mm"]["y"] = .001
        with self.assertRaises(RuntimeError): self.fingerprint(metrics=metrics)


if __name__ == "__main__": unittest.main()
