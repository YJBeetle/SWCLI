import copy
import math
import unittest
from types import SimpleNamespace
from unittest import mock

from swcli.hosts import windows_sketches as sketches
from swcli.result_schemas import OperationResultInvalid, validate_operation_result

TRANSFORMS = {
    "front": (1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0),
    "top": (1, 0, 0, 0, 0, -1, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0),
    "right": (0, 0, -1, 0, 1, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0),
}


class Segment:
    def __init__(self, start, end, construction=False):
        self.start, self.end = start, end
        self.ConstructionGeometry = construction

    def GetType(self):
        return 0

    def GetStartPoint2(self):
        return SimpleNamespace(X=self.start[0], Y=self.start[1], Z=self.start[2])

    def GetEndPoint2(self):
        return SimpleNamespace(X=self.end[0], Y=self.end[1], Z=self.end[2])


class Sketch:
    ModelToSketchTransform = SimpleNamespace(ArrayData=TRANSFORMS["front"])

    def __init__(self):
        self.segments = []

    def GetSketchSegments(self):
        return self.segments

    def GetConstrainedStatus(self):
        return 2


class Feature:
    def __init__(self, document, name, kind, specific):
        self.document, self.Name, self.kind, self.specific = (
            document,
            name,
            kind,
            specific,
        )
        self.Select2 = mock.Mock(return_value=True)

    def GetTypeName2(self):
        return self.kind

    def GetSpecificFeature2(self):
        return self.specific

    def GetNextFeature(self):
        index = self.document.features.index(self) + 1
        return (
            self.document.features[index]
            if index < len(self.document.features)
            else None
        )


class Document:
    def __init__(self):
        self.features = [
            Feature(
                self,
                "renamed-" + name,
                "RefPlane",
                SimpleNamespace(Transform=SimpleNamespace(ArrayData=transform)),
            )
            for name, transform in TRANSFORMS.items()
        ]
        self.SketchManager = Manager(self)
        self.ClearSelection2 = mock.Mock()

    def GetType(self):
        return 1

    def FirstFeature(self):
        return self.features[0] if self.features else None


class Manager:
    def __init__(self, document):
        self.document, self.ActiveSketch = document, None
        self.AddToDB = False
        self.InsertSketch = mock.Mock(side_effect=self.toggle)
        self.CreateCenterRectangle = mock.Mock(side_effect=self.rectangle)
        self.on_close = lambda: None

    def toggle(self, update):
        if self.ActiveSketch is None:
            self.ActiveSketch = Sketch()
            self.document.features.append(
                Feature(
                    self.document, "new-sketch", "ProfileFeature", self.ActiveSketch
                )
            )
        else:
            self.on_close()
            self.ActiveSketch = None

    def rectangle(self, x, y, z, xmax, ymax, zmax):
        xmin, ymin = 2 * x - xmax, 2 * y - ymax
        corners = [(xmin, ymin, 0), (xmax, ymin, 0), (xmax, ymax, 0), (xmin, ymax, 0)]
        self.ActiveSketch.segments = [
            Segment(corners[i], corners[(i + 1) % 4]) for i in range(4)
        ] + [
            Segment(corners[0], corners[2], True),
            Segment(corners[1], corners[3], True),
        ]
        return self.ActiveSketch.segments


class CircleSegment:
    ConstructionGeometry = False

    def __init__(self, x, y, z, radius):
        self.center = SimpleNamespace(X=x, Y=y, Z=z)
        self.radius = radius
        self.complete = 1

    def GetType(self):
        return 1

    def IsCircle(self):
        return self.complete

    def GetRadius(self):
        return self.radius

    def GetCenterPoint2(self):
        return self.center


class WindowsCircleTests(unittest.TestCase):
    def setUp(self):
        self.document = Document()
        self.app = SimpleNamespace(IsSame=lambda a, b: int(a is b))
        manager = self.document.SketchManager

        def circle(x, y, z, radius):
            segment = CircleSegment(x, y, z, radius)
            manager.ActiveSketch.segments = [segment]
            return segment

        manager.CreateCircleByRadius = mock.Mock(side_effect=circle)

    def create(self, **arguments):
        values = dict(plane="front", radius_mm=8, center_x_mm=10, center_y_mm=20)
        values.update(arguments)
        return sketches.create_circle_sketch_windows_with_handle(
            app=self.app, document=self.document, **values
        )

    def test_three_planes_create_full_circle_and_read_actual_local_geometry(self):
        for plane, index in (("front", 0), ("top", 1), ("right", 2)):
            self.setUp()
            result, feature = self.create(plane=plane)
            self.assertTrue(result["ok"], result)
            self.assertIs(feature, self.document.features[-1])
            self.document.features[index].Select2.assert_called_once_with(False, 0)
            self.document.SketchManager.CreateCircleByRadius.assert_called_once_with(
                0.01, 0.02, 0, 0.008
            )
            self.assertEqual(result["geometry_verification"]["actual_radius_mm"], 8)
            self.assertEqual(
                result["geometry_verification"]["actual_center_mm"],
                {"x": 10, "y": 20, "z": 0},
            )
            self.assertIsNone(self.document.SketchManager.ActiveSketch)
            self.assertFalse(result["editing"])

    def test_bad_radius_center_plane_and_underflow_do_not_enter_sketch(self):
        for changed in (
            {"radius_mm": 0},
            {"radius_mm": -1},
            {"radius_mm": math.inf},
            {"radius_mm": 5e-324},
            {"radius_mm": 1e308},
            {"center_x_mm": math.nan},
            {"center_x_mm": 1e100},
            {"plane": "other"},
        ):
            with self.subTest(changed=changed):
                self.setUp()
                result, feature = self.create(**changed)
                self.assertEqual(result["error"]["type"], "InvalidArgument")
                self.assertIsNone(feature)
                self.document.SketchManager.InsertSketch.assert_not_called()

    def test_existing_edit_and_non_part_are_not_modified(self):
        existing = Sketch()
        self.document.SketchManager.ActiveSketch = existing
        self.assertEqual(self.create()[0]["error"]["type"], "SketchEditInProgress")
        self.assertIs(self.document.SketchManager.ActiveSketch, existing)
        self.document.GetType = lambda: 2
        self.assertEqual(self.create()[0]["error"]["type"], "UnsupportedDocumentType")
        self.document.SketchManager.InsertSketch.assert_not_called()

    def test_solving_modified_arc_or_extra_profiles_cannot_pass_verification(self):
        def wrong_radius(sketch):
            sketch.segments[0].radius = 0.009

        def wrong_center(sketch):
            sketch.segments[0].center.Z = 0.001

        def arc(sketch):
            sketch.segments[0].complete = 0

        def nonfinite(sketch):
            sketch.segments[0].radius = math.nan

        def extra(sketch):
            sketch.segments.append(sketch.segments[0])

        for change in (wrong_radius, wrong_center, arc, nonfinite, extra):
            self.setUp()
            self.document.SketchManager.on_close = lambda: change(
                self.document.SketchManager.ActiveSketch
            )
            result, feature = self.create()
            self.assertEqual(result["error"]["type"], "SketchVerificationFailed")
            self.assertIsNotNone(feature)
            self.assertFalse(result["editing"])
            validate_operation_result("sketch.circle", result)

    def test_native_circle_float_noise_uses_the_declared_absolute_tolerance(self):
        def float_noise():
            arc = self.document.SketchManager.ActiveSketch.segments[0]
            arc.radius = 0.008000000000000012
            arc.center.X += 1e-12

        self.document.SketchManager.on_close = float_noise
        result, _ = self.create()
        self.assertTrue(result["ok"], result)
        self.assertNotEqual(result["geometry_verification"]["actual_radius_mm"], 8)

    def test_creation_failure_exits_owned_edit_and_preserves_partial_feature(self):
        manager = self.document.SketchManager
        manager.CreateCircleByRadius.side_effect = None
        manager.CreateCircleByRadius.return_value = None
        result, feature = self.create()
        self.assertEqual(result["error"]["type"], "SketchCreationFailed")
        self.assertIsNotNone(feature)
        self.assertIsNone(manager.ActiveSketch)

    def test_direct_creation_prevents_the_ci_origin_snap_without_changing_expected_geometry(
        self,
    ):
        manager = self.document.SketchManager
        create_circle = manager.CreateCircleByRadius.side_effect

        def infer_or_create(x, y, z, radius):
            # The native UI path can snap X=3mm to the origin and preserve the
            # requested endpoint X=8mm, changing radius5 to radius8. This fake
            # models that documented inference, not a replacement native proof.
            if not manager.AddToDB:
                x, radius = 0, x + radius
            return create_circle(x, y, z, radius)

        manager.CreateCircleByRadius.side_effect = infer_or_create
        result, feature = self.create(radius_mm=5, center_x_mm=3, center_y_mm=4)
        self.assertTrue(result["ok"], result)
        self.assertIsNotNone(feature)
        self.assertEqual(result["geometry_verification"]["actual_radius_mm"], 5)
        self.assertEqual(
            result["geometry_verification"]["actual_center_mm"],
            {"x": 3, "y": 4, "z": 0},
        )
        self.assertFalse(manager.AddToDB)

    def test_original_creation_mode_is_restored_before_closing_the_sketch(self):
        for original in (False, True):
            with self.subTest(original=original):
                self.setUp()
                manager = self.document.SketchManager
                manager.AddToDB = original
                manager.DisplayWhenAdded = False
                manager.AutoSolve = True
                create_circle = manager.CreateCircleByRadius.side_effect

                def create_direct(*arguments):
                    self.assertTrue(manager.AddToDB)
                    return create_circle(*arguments)

                manager.CreateCircleByRadius.side_effect = create_direct
                manager.on_close = lambda: self.assertEqual(manager.AddToDB, original)
                result, _ = self.create()
                self.assertTrue(result["ok"], result)
                self.assertEqual(manager.AddToDB, original)
                self.assertFalse(manager.DisplayWhenAdded)
                self.assertTrue(manager.AutoSolve)

    def test_native_creation_exception_restores_mode_and_preserves_original_failure(
        self,
    ):
        manager = self.document.SketchManager
        manager.CreateCircleByRadius.side_effect = RuntimeError(
            "native creation failed"
        )
        result, feature = self.create()
        self.assertEqual(
            result["error"],
            {"type": "RuntimeError", "message": "native creation failed"},
        )
        self.assertIsNotNone(feature)
        self.assertFalse(manager.AddToDB)
        self.assertIsNone(manager.ActiveSketch)

    def test_unavailable_or_rejected_direct_mode_does_not_create_ui_geometry(self):
        manager = self.document.SketchManager
        del manager.AddToDB
        result, _ = self.create()
        self.assertEqual(result["error"]["type"], "AttributeError")
        manager.CreateCircleByRadius.assert_not_called()
        self.assertIsNone(manager.ActiveSketch)
        self.setUp()
        manager = self.document.SketchManager
        with mock.patch.object(
            Manager,
            "AddToDB",
            new_callable=mock.PropertyMock,
            create=True,
            return_value=False,
        ):
            result, _ = self.create()
            self.assertFalse(result["ok"])
            self.assertIn(
                "could not enable direct circle creation", result["error"]["message"]
            )
            manager.CreateCircleByRadius.assert_not_called()
            self.assertIsNone(manager.ActiveSketch)

    def test_invalid_mode_observation_and_failed_enable_never_create_circle(self):
        for original in (None, "false", 2):
            with self.subTest(original=original):
                self.setUp()
                manager = self.document.SketchManager
                manager.AddToDB = original
                result, _ = self.create()
                self.assertFalse(result["ok"])
                self.assertIn("invalid AddToDB mode", result["error"]["message"])
                self.assertEqual(manager.AddToDB, original)
                manager.CreateCircleByRadius.assert_not_called()
        for effects in (
            [False, RuntimeError("enable failed"), None, False],
            [False, None, RuntimeError("readback failed"), None, False],
        ):
            with self.subTest(effects=effects):
                self.setUp()
                with mock.patch.object(
                    Manager,
                    "AddToDB",
                    new_callable=mock.PropertyMock,
                    create=True,
                    side_effect=effects,
                ) as mode:
                    result, _ = self.create()
                self.assertFalse(result["ok"])
                self.document.SketchManager.CreateCircleByRadius.assert_not_called()
                self.assertEqual(mode.call_args_list[-2], mock.call(False))
                self.assertNotIn("warnings", result)

    def test_silent_mode_restoration_failure_is_fail_closed_with_partial_geometry_evidence(
        self,
    ):
        with mock.patch.object(
            Manager,
            "AddToDB",
            new_callable=mock.PropertyMock,
            create=True,
            side_effect=[False, None, True, None, True],
        ):
            result, feature = self.create()
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["type"], "SketchStateRestoreFailed")
        self.assertTrue(result["geometry_verification"]["passed"])
        self.assertIsNotNone(feature)
        self.assertFalse(result["editing"])
        self.assertEqual(
            result["warnings"][0]["code"], "sketch-creation-mode-restore-failed"
        )
        validate_operation_result("sketch.circle", result)

    def test_thrown_restore_failure_does_not_hide_an_existing_creation_error(self):
        manager = self.document.SketchManager
        manager.CreateCircleByRadius.side_effect = RuntimeError("create failed")
        with mock.patch.object(
            Manager,
            "AddToDB",
            new_callable=mock.PropertyMock,
            create=True,
            side_effect=[False, None, True, RuntimeError("restore failed")],
        ):
            result, feature = self.create()
        self.assertEqual(
            result["error"], {"type": "RuntimeError", "message": "create failed"}
        )
        self.assertEqual(
            result["warnings"][0],
            {
                "code": "sketch-creation-mode-restore-failed",
                "message": "restore failed",
            },
        )
        self.assertIsNotNone(feature)
        self.assertIsNone(manager.ActiveSketch)

    def test_success_contract_requires_handle_closed_edit_and_actual_complete_circle(
        self,
    ):
        result, _ = self.create()
        result["sketch"]["sketch_id"] = "s-ab12cd"
        result["document"] = {
            "title": "Part1",
            "path": "",
            "type": 1,
            "modified": True,
            "update_stamp": 0,
        }
        validate_operation_result("sketch.circle", result)
        for key, value in (
            ("complete_circle", False),
            ("actual_radius_mm", None),
            ("actual_center_mm", None),
            ("profile_segment_count", 2),
        ):
            invalid = copy.deepcopy(result)
            invalid["geometry_verification"][key] = value
            with self.assertRaises(OperationResultInvalid):
                validate_operation_result("sketch.circle", invalid)


class WindowsSketchTests(unittest.TestCase):
    def setUp(self):
        self.document = Document()
        self.app = SimpleNamespace(IsSame=lambda a, b: int(a is b))

    def create(self, **arguments):
        values = dict(
            plane="front", width_mm=100, height_mm=50, center_x_mm=10, center_y_mm=20
        )
        values.update(arguments)
        return sketches.create_rectangle_sketch_windows_with_handle(
            app=self.app, document=self.document, **values
        )

    def test_three_planes_are_selected_by_geometry_not_translated_names(self):
        for plane, index in (("front", 0), ("top", 1), ("right", 2)):
            with self.subTest(plane=plane):
                self.setUp()
                result, feature = self.create(plane=plane)
                self.assertTrue(result["ok"], result)
                self.assertIs(feature, self.document.features[-1])
                self.document.features[index].Select2.assert_called_once_with(False, 0)
                self.document.SketchManager.CreateCenterRectangle.assert_called_once_with(
                    0.01, 0.02, 0.0, 0.06, 0.045, 0.0
                )
                self.assertEqual(
                    result["geometry_verification"]["profile_segment_count"], 4
                )
                self.assertEqual(result["geometry_verification"]["segment_count"], 6)
                self.assertFalse(result["editing"])
                self.assertFalse(result["sketch"]["dimensions_created"])
                self.assertIsNone(self.document.SketchManager.ActiveSketch)

    def test_success_contract_requires_verified_closed_sketch_and_registered_id(self):
        result, _ = self.create()
        result["sketch"]["sketch_id"] = "s-ab12cd"
        result["document"] = {
            "title": "Part1",
            "path": "",
            "type": 1,
            "modified": True,
            "update_stamp": 0,
            "document_id": "d-ab12cd",
            "current": True,
            "active": True,
        }
        validate_operation_result("sketch.rectangle", result)
        for change in ("id", "editing", "verification", "transform"):
            with self.subTest(change=change):
                invalid = copy.deepcopy(result)
                if change == "id":
                    del invalid["sketch"]["sketch_id"]
                elif change == "editing":
                    invalid["editing"] = True
                elif change == "verification":
                    invalid["geometry_verification"]["passed"] = False
                else:
                    invalid["model_to_sketch_transform"] = [1, 2]
                with self.assertRaises(OperationResultInvalid):
                    validate_operation_result("sketch.rectangle", invalid)

    def test_standard_plane_resolution_skips_offset_and_invalid_planes(self):
        offset = list(TRANSFORMS["front"])
        offset[11] = 0.001
        self.document.features[0].specific.Transform.ArrayData = offset
        result, _ = self.create()
        self.assertEqual(result["error"]["type"], "StandardPlaneUnavailable")
        self.document.SketchManager.InsertSketch.assert_not_called()

    def test_bad_size_center_or_precision_is_rejected_before_com_mutation(self):
        for values in (
            {"width_mm": 0},
            {"width_mm": -1},
            {"height_mm": math.inf},
            {"center_x_mm": math.nan},
            {"plane": "other"},
            {"center_x_mm": 1e100, "width_mm": 1},
            {"width_mm": 5e-324},
        ):
            with self.subTest(values=values):
                result, feature = self.create(**values)
                self.assertEqual(result["error"]["type"], "InvalidArgument")
                self.assertIsNone(feature)
                self.document.SketchManager.InsertSketch.assert_not_called()

    def test_existing_sketch_edit_is_not_closed_or_modified(self):
        existing = Sketch()
        self.document.SketchManager.ActiveSketch = existing
        result, _ = self.create()
        self.assertEqual(result["error"]["type"], "SketchEditInProgress")
        self.assertIs(self.document.SketchManager.ActiveSketch, existing)
        self.document.SketchManager.InsertSketch.assert_not_called()

    def test_assembly_and_failed_plane_selection_do_not_enter_editing(self):
        self.document.GetType = lambda: 2
        result, _ = self.create()
        self.assertEqual(result["error"]["type"], "UnsupportedDocumentType")
        self.document.GetType = lambda: 1
        self.document.features[0].Select2.return_value = False
        result, _ = self.create()
        self.assertEqual(result["error"]["type"], "PlaneSelectionFailed")
        self.document.SketchManager.InsertSketch.assert_not_called()

    def test_null_segments_and_com_exception_exit_owned_sketch_edit(self):
        for failure in (None, RuntimeError("creation failed")):
            with self.subTest(failure=failure):
                self.setUp()
                manager = self.document.SketchManager
                if failure is None:
                    manager.CreateCenterRectangle.side_effect = None
                    manager.CreateCenterRectangle.return_value = None
                else:
                    manager.CreateCenterRectangle.side_effect = failure
                result, feature = self.create()
                self.assertFalse(result["ok"])
                self.assertIsNotNone(feature)
                self.assertIsNone(manager.ActiveSketch)
                self.assertFalse(result["editing"])
                validate_operation_result("sketch.rectangle", result)

    def test_native_identity_must_match_instead_of_using_last_feature(self):
        self.app.IsSame = lambda a, b: 0
        result, feature = self.create()
        self.assertFalse(result["ok"])
        self.assertIsNone(feature)
        self.assertIsNone(self.document.SketchManager.ActiveSketch)

    def test_final_geometry_is_checked_after_close_triggers_solving(self):
        def change_geometry():
            self.document.SketchManager.ActiveSketch.segments[0].start = (0.5, 0.5, 0)

        self.document.SketchManager.on_close = change_geometry
        result, feature = self.create()
        self.assertFalse(result["ok"])
        self.assertIsNotNone(feature)
        self.assertEqual(result["error"]["type"], "SketchVerificationFailed")
        self.assertFalse(result["editing"])
        validate_operation_result("sketch.rectangle", result)

    def test_duplicate_or_diagonal_edges_cannot_pass_only_a_bounding_box_check(self):
        def duplicate_edge():
            sketch = self.document.SketchManager.ActiveSketch
            sketch.segments[1] = sketch.segments[0]

        self.document.SketchManager.on_close = duplicate_edge
        result, _ = self.create()
        self.assertFalse(result["geometry_verification"]["passed"])

    def test_cleanup_failure_reports_editing_state_and_warning(self):
        manager = self.document.SketchManager

        def fail_exit(update):
            if manager.ActiveSketch is None:
                manager.toggle(update)
            else:
                raise RuntimeError("cannot exit sketch")

        manager.InsertSketch.side_effect = fail_exit
        result, _ = self.create()
        self.assertFalse(result["ok"])
        self.assertTrue(result["editing"])
        self.assertEqual(result["warnings"][0]["code"], "sketch-cleanup-failed")
        validate_operation_result("sketch.rectangle", result)


if __name__ == "__main__":
    unittest.main()
