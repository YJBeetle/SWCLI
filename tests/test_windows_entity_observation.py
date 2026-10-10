"""Incomplete/changed native face reads never publish bindings or geometry."""

import json
from types import SimpleNamespace
import unittest
from unittest import mock

from swcli.hosts import windows_entity_observation as observation


class EntityObservationTests(unittest.TestCase):
    def setUp(self):
        self.body = SimpleNamespace()
        self.foreground = object()
        self.app = SimpleNamespace(
            IsSame=mock.Mock(side_effect=lambda a, b: int(a is b))
        )
        self.faces = [
            SimpleNamespace(
                GetBody=lambda: self.body,
                GetSurface=lambda: SimpleNamespace(
                    IsPlane=True,
                    IsCylinder=False,
                    PlaneParams=(1, 0, 0, 0, 0, 0),
                ),
                FaceInSurfaceSense=False,
                Normal=(1, 0, 0),
                GetArea=lambda: 0.001,
                reference=bytes((index + 1,)),
            )
            for index in range(3)
        ]
        self.body.GetFaceCount = lambda: len(self.faces)
        self.body.GetFaces = lambda: tuple(self.faces)
        self.document = SimpleNamespace(GetType=1, Extension=object())
        self.document.GetBodies2 = mock.Mock(
            side_effect=lambda kind, visible: (self.body,) if kind == 0 else None
        )
        self.before = {
            "configuration": "default",
            "update_stamp": 12,
            "modified": False,
            "editing": False,
            "foreground_present": True,
        }
        self.state = mock.patch.object(
            observation,
            "_state",
            side_effect=lambda app, document: (
                self.before.copy(),
                None,
                self.foreground,
            ),
        )
        self.state.start()
        self.addCleanup(self.state.stop)
        self.capture = mock.patch.object(
            observation,
            "capture_verified_reference",
            side_effect=lambda app, extension, face: face.reference,
        )
        self.capture_mock = self.capture.start()
        self.addCleanup(self.capture.stop)

    def read(self, **kwargs):
        return observation.observe_part_faces_with_handles(
            self.app, self.document, **kwargs
        )

    def refused(self, **kwargs):
        result, handles = self.read(**kwargs)
        self.assertFalse(result["ok"])
        self.assertIn("error", result)
        self.assertEqual(handles, [])
        self.assertNotIn("faces", result)
        self.assertNotIn("face_count", result)
        return result

    def test_complete_read_is_bounded_hidden_body_inclusive_and_private(self):
        result, handles = self.read()
        self.assertTrue(result["ok"])
        self.assertEqual((result["body_count"], result["face_count"]), (1, 3))
        self.assertTrue(result["observation"]["unchanged"])
        self.assertEqual(
            result["faces"][0],
            {
                "kind": "face",
                "surface_kind": "plane",
                "area_mm2": 1000.0,
                "area_accuracy": "approximate",
                "surface_geometry": {
                    "available": True,
                    "coordinate_system": "part-model",
                    "boundary": "untrimmed-surface",
                    "face_normal_opposes_surface": False,
                    "plane": {
                        "point_mm": [0.0, 0.0, 0.0],
                        "surface_normal": [1.0, 0.0, 0.0],
                        "outward_normal": [1.0, 0.0, 0.0],
                    },
                },
            },
        )
        self.assertIs(handles[0].face, self.faces[0])
        self.assertIs(handles[0].body, self.body)
        self.assertEqual(handles[0].reference, b"\x01")
        self.assertNotIn("reference", json.dumps(result))
        self.assertNotIn("entity_id", json.dumps(result))
        self.assertEqual(
            self.document.GetBodies2.call_args_list,
            [mock.call(0, False), mock.call(1, False)] * 2,
        )
        self.assertEqual(self.capture_mock.call_count, 3)

    def test_cylinder_and_unclassified_surfaces_are_not_invented_planes(self):
        self.faces[1].GetSurface = lambda: SimpleNamespace(
            IsPlane=False,
            IsCylinder=True,
            CylinderParams=(0, 0, 0, 0, 0, 1, 0.003),
        )
        self.faces[2].GetSurface = lambda: SimpleNamespace(
            IsPlane=False, IsCylinder=False
        )
        result, _ = self.read()
        self.assertEqual(
            [face["surface_kind"] for face in result["faces"]],
            ["plane", "cylinder", "unclassified"],
        )
        self.assertFalse(result["faces"][2]["surface_geometry"]["available"])

    def test_bad_analytic_geometry_discards_every_face_and_binding(self):
        self.faces[-1].Normal = (-1, 0, 0)
        result = self.refused()
        self.assertEqual(result["error"]["type"], "EntityGeometryUnavailable")
        self.assertTrue(result["observation"]["unchanged"])

    def test_invalid_limits_and_document_type_do_not_read_entities(self):
        for limit in (None, True, 0, 65, 1.0, "1"):
            with self.subTest(limit=limit):
                self.refused(max_faces=limit)
        for kind in (None, True, "1", 1.0, 2, 3):
            self.document.GetType = kind
            with self.subTest(kind=kind):
                self.refused()
        self.document.GetBodies2.assert_not_called()
        self.capture_mock.assert_not_called()

    def test_no_multibody_or_surface_body_is_silently_omitted(self):
        for solids, surfaces in (
            (None, None),
            ((), ()),
            ((self.body, object()), None),
            ((self.body,), (object(),)),
            ((None,), None),
            ("body", None),
        ):
            self.document.GetBodies2.side_effect = lambda kind, visible: (
                solids if kind == 0 else surfaces
            )
            with self.subTest(solids=solids, surfaces=surfaces):
                self.refused()
        self.capture_mock.assert_not_called()

    def test_count_and_complete_array_must_agree_before_reference_reads(self):
        for count in (None, True, 1.0, 0, 65, 2):
            self.body.GetFaceCount = lambda: count
            with self.subTest(count=count):
                self.refused()
        self.body.GetFaceCount = lambda: 3
        for faces in (None, (), "faces", (None, self.faces[0], self.faces[1])):
            self.body.GetFaces = lambda: faces
            with self.subTest(faces=faces):
                self.refused()
        self.refused(max_faces=2)
        self.capture_mock.assert_not_called()

    def test_foreign_body_duplicate_native_face_and_ambiguous_reference_fail(self):
        self.faces[-1].GetBody = lambda: object()
        self.refused()
        self.faces[-1].GetBody = lambda: self.body
        last = self.faces[-1]
        self.faces[-1] = self.faces[0]
        self.refused()
        self.faces[-1] = last
        self.faces[-1].reference = self.faces[0].reference
        self.refused()

    def test_unsupported_identity_never_means_different_faces(self):
        for status in (None, True, False, "1", 1.0, 2, 3):
            self.app.IsSame.side_effect = None
            self.app.IsSame.return_value = status
            with self.subTest(status=status):
                self.refused()

    def test_bad_area_or_surface_discards_earlier_successful_bindings(self):
        for area in (None, True, "1", -1, 0, float("nan"), float("inf"), 1e308):
            self.faces[-1].GetArea = lambda: area
            with self.subTest(area=area):
                self.refused()
        self.faces[-1].GetArea = lambda: 0.001
        for surface in (
            None,
            SimpleNamespace(IsPlane=True, IsCylinder=True),
            SimpleNamespace(IsPlane=1, IsCylinder=False),
            SimpleNamespace(IsPlane=False, IsCylinder=None),
        ):
            self.faces[-1].GetSurface = lambda: surface
            with self.subTest(surface=surface):
                self.refused()

    def test_reference_failure_retains_first_error_and_no_partial_faces(self):
        failure = RuntimeError("reference failed first")
        self.capture_mock.side_effect = [b"x", failure]
        result = self.refused()
        self.assertEqual(result["error"]["message"], str(failure))
        self.assertTrue(result["observation"]["unchanged"])

    def test_changed_final_body_or_count_refuses_all_records(self):
        for final_count in (None, 2, 4):
            self.body.GetFaceCount = mock.Mock(side_effect=[3, final_count])
            self.refused()
        self.body.GetFaceCount = lambda: 3
        self.document.GetBodies2.side_effect = [(self.body,), None, (object(),), None]
        self.refused()

    def test_any_snapshot_or_edit_foreground_identity_change_fails(self):
        for key, value in (
            ("configuration", "other"),
            ("update_stamp", 13),
            ("modified", True),
            ("editing", True),
            ("foreground_present", False),
        ):
            after = dict(self.before, **{key: value})
            with (
                self.subTest(key=key),
                mock.patch.object(
                    observation,
                    "_state",
                    side_effect=[
                        (self.before.copy(), None, self.foreground),
                        (after, None, self.foreground),
                    ],
                ),
            ):
                self.refused()
        for before_edit, after_edit, final_foreground in (
            (object(), object(), self.foreground),
            (None, None, object()),
        ):
            with mock.patch.object(
                observation,
                "_state",
                side_effect=[
                    (self.before.copy(), before_edit, self.foreground),
                    (self.before.copy(), after_edit, final_foreground),
                ],
            ):
                self.refused()

    def test_final_state_check_failure_cannot_replace_first_native_error(self):
        self.capture_mock.side_effect = RuntimeError("first native failure")
        with mock.patch.object(
            observation,
            "_state",
            side_effect=[
                (self.before.copy(), None, self.foreground),
                RuntimeError("later state failure"),
            ],
        ):
            result = self.refused()
        self.assertEqual(result["error"]["message"], "first native failure")
        self.assertEqual(
            result["warnings"][0]["code"], "entity-observation-state-check-failed"
        )


if __name__ == "__main__":
    unittest.main()
