"""Analytic face evidence has strict units, arrays and outward-normal semantics."""

import json
from types import SimpleNamespace
import unittest
from unittest import mock

from swcli.hosts.windows_entity_geometry import (
    EntityGeometryUnavailable,
    observe_surface_geometry,
)


class EntityGeometryTests(unittest.TestCase):
    def setUp(self):
        self.face = SimpleNamespace(FaceInSurfaceSense=True, Normal=(-1, 0, 0))
        self.surface = SimpleNamespace(
            PlaneParams=(1, 0, 0, 0.01, -0.02, 0.03),
            CylinderParams=(0.01, 0.02, 0.005, 0, 0, -1, 0.003),
        )

    def read(self, kind="plane"):
        return observe_surface_geometry(self.face, self.surface, kind)

    def test_plane_is_untrimmed_part_geometry_with_verified_outward_normal(self):
        result = self.read()
        self.assertEqual(
            result,
            {
                "available": True,
                "coordinate_system": "part-model",
                "boundary": "untrimmed-surface",
                "face_normal_opposes_surface": True,
                "plane": {
                    "point_mm": [10.0, -20.0, 30.0],
                    "surface_normal": [1.0, 0.0, 0.0],
                    "outward_normal": [-1.0, 0.0, 0.0],
                },
            },
        )
        json.dumps(result, allow_nan=False)

    def test_same_sense_and_list_containers_are_supported_without_sign_guessing(self):
        self.face.FaceInSurfaceSense = False
        self.face.Normal = [1.0, 0.0, 0.0]
        self.surface.PlaneParams = list(self.surface.PlaneParams)
        self.assertEqual(self.read()["plane"]["outward_normal"], [1.0, 0.0, 0.0])

    def test_cylinder_reports_axis_radius_not_constant_outward_normal(self):
        del self.face.Normal
        result = self.read("cylinder")
        self.assertEqual(
            result["cylinder"],
            {
                "axis_point_mm": [10.0, 20.0, 5.0],
                "axis_direction": [0.0, 0.0, -1.0],
                "radius_mm": 3.0,
            },
        )
        self.assertNotIn("outward_normal", json.dumps(result))
        self.assertEqual(result["boundary"], "untrimmed-surface")

    def test_unknown_surface_is_explicitly_unavailable_without_native_reads(self):
        self.assertEqual(
            observe_surface_geometry(object(), object(), "unclassified"),
            {"available": False, "reason": "unsupported-surface-kind"},
        )

    def test_supported_arrays_reject_missing_extra_or_arbitrary_buffers(self):
        for kind, member, length in (
            ("plane", "PlaneParams", 6),
            ("plane", "Normal", 3),
            ("cylinder", "CylinderParams", 7),
        ):
            owner = self.face if member == "Normal" else self.surface
            for value in (
                None,
                (),
                [1] * (length - 1),
                [1] * (length + 1),
                "1" * length,
                b"1" * length,
                memoryview(b"1" * length),
            ):
                with self.subTest(member=member, value=value):
                    with mock.patch.object(owner, member, value):
                        with self.assertRaises(EntityGeometryUnavailable):
                            self.read(kind)

    def test_arrays_reject_boolean_strings_nonfinite_and_overflow(self):
        for bad in (
            True,
            False,
            None,
            "0",
            float("nan"),
            float("inf"),
            -float("inf"),
            10**1000,
        ):
            for kind, member in (
                ("plane", "PlaneParams"),
                ("cylinder", "CylinderParams"),
            ):
                values = list(getattr(self.surface, member))
                values[0] = bad
                with self.subTest(member=member, bad=str(bad)):
                    with mock.patch.object(self.surface, member, values):
                        with self.assertRaises(EntityGeometryUnavailable):
                            self.read(kind)

    def test_directions_are_not_repaired_or_normalized(self):
        for vector in ((0, 0, 0), (2, 0, 0), (1, 1, 0), (1e308, 0, 0)):
            with self.subTest(vector=vector):
                with mock.patch.object(self.surface, "PlaneParams", (*vector, 0, 0, 0)):
                    with self.assertRaises(EntityGeometryUnavailable):
                        self.read()
                with mock.patch.object(self.face, "Normal", vector):
                    with self.assertRaises(EntityGeometryUnavailable):
                        self.read()
                with mock.patch.object(
                    self.surface, "CylinderParams", (0, 0, 0, *vector, 0.003)
                ):
                    with self.assertRaises(EntityGeometryUnavailable):
                        self.read("cylinder")

    def test_boolean_sense_and_independent_face_normal_must_agree(self):
        for sense in (None, 0, 1, "true", 1.0):
            with (
                self.subTest(sense=sense),
                mock.patch.object(self.face, "FaceInSurfaceSense", sense),
            ):
                for kind in ("plane", "cylinder"):
                    with self.assertRaises(EntityGeometryUnavailable):
                        self.read(kind)
        for normal in ((1, 0, 0), (0, 1, 0)):
            with mock.patch.object(self.face, "Normal", normal):
                with self.assertRaisesRegex(EntityGeometryUnavailable, "disagrees"):
                    self.read()

    def test_length_conversions_and_positive_radius_fail_closed(self):
        for kind, member, index in (
            ("plane", "PlaneParams", 3),
            ("cylinder", "CylinderParams", 0),
            ("cylinder", "CylinderParams", 6),
        ):
            values = list(getattr(self.surface, member))
            values[index] = 1e308
            with mock.patch.object(self.surface, member, values):
                with self.assertRaises(EntityGeometryUnavailable):
                    self.read(kind)
        for radius in (0, -0.003):
            with mock.patch.object(
                self.surface, "CylinderParams", (0, 0, 0, 0, 0, 1, radius)
            ):
                with self.assertRaises(EntityGeometryUnavailable):
                    self.read("cylinder")

    def test_native_failure_is_not_downgraded_to_unavailable_optional_geometry(self):
        class FailedSurface:
            @property
            def PlaneParams(self):
                raise RuntimeError("native failed")

        self.surface = FailedSurface()
        with self.assertRaisesRegex(RuntimeError, "native failed"):
            self.read()


if __name__ == "__main__":
    unittest.main()
