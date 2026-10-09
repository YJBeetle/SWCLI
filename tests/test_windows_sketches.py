import copy
from contextlib import nullcontext
import io
import json
import math
import os
import unittest
from types import SimpleNamespace
from unittest import mock

from swcli.hosts import windows_sketches as sketches
from swcli.hosts.native_trace import trace_native_request
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

    def test_com_failures_report_the_precise_stage_and_preserve_native_error(self):
        native_type = type("com_error", (Exception,), {})
        native = native_type(-2147023898, "No access to memory location", None, None)
        native.hresult = -2147023898
        expected_error = {"type": "com_error", "message": str(native)}
        cases = (
            ("plane-resolve", "GetSpecificFeature2"),
            ("plane-select", "Select2"),
            ("sketch-enter", "InsertSketch"),
            ("exact-feature", "IsSame"),
            ("transform", "ModelToSketchTransform"),
            ("create", "CreateCircleByRadius"),
            ("close", "InsertSketch"),
            ("verify", "GetRadius"),
        )
        for stage, member in cases:
            with self.subTest(stage=stage, member=member):
                self.setUp()
                manager = self.document.SketchManager
                patcher = None

                def raise_native(*arguments):
                    raise native

                if stage == "plane-resolve":
                    self.document.features[0].GetSpecificFeature2 = raise_native
                elif stage == "plane-select":
                    self.document.features[0].Select2.side_effect = native
                elif stage == "sketch-enter":
                    manager.InsertSketch.side_effect = native
                elif stage == "exact-feature":
                    self.app.IsSame = mock.Mock(side_effect=native)
                elif stage == "transform":
                    patcher = mock.patch.object(
                        Sketch, "ModelToSketchTransform", new_callable=mock.PropertyMock,
                        side_effect=native,
                    )
                elif stage == "create":
                    manager.CreateCircleByRadius.side_effect = native
                elif stage == "close":
                    calls = 0

                    def close_failure(update):
                        nonlocal calls
                        calls += 1
                        if calls == 2:
                            raise native
                        manager.toggle(update)

                    manager.InsertSketch.side_effect = close_failure
                elif stage == "verify":
                    patcher = mock.patch.object(CircleSegment, "GetRadius", new=raise_native)
                with patcher if patcher is not None else nullcontext():
                    result, feature = self.create()
                self.assertFalse(result["ok"])
                self.assertEqual(result["error"], expected_error)
                warning = result["warnings"][0]
                self.assertEqual(warning["code"], "sketch-com-call-failed")
                self.assertEqual((warning["stage"], warning["call"]), (stage, member))
                self.assertEqual(warning["native_error"], {
                    **expected_error, "hresult": -2147023898, "hresult_hex": "0x800703E6",
                })
                self.assertIsNone(manager.ActiveSketch)
                self.assertFalse(manager.AddToDB)
                if stage in ("plane-resolve", "plane-select", "sketch-enter", "exact-feature"):
                    self.assertIsNone(feature)
                    manager.CreateCircleByRadius.assert_not_called()
                else:
                    self.assertIsNotNone(feature)
                if stage in ("create", "close", "verify"):
                    self.assertEqual(manager.CreateCircleByRadius.call_count, 1)
                validate_operation_result("sketch.circle", result)

    def test_com_creation_mode_failure_keeps_failed_enable_not_restore_as_its_call(self):
        native_type = type("com_error", (Exception,), {})
        native = native_type(-2147023898, "No access to memory location")
        with mock.patch.object(
            Manager, "AddToDB", new_callable=mock.PropertyMock, create=True,
            side_effect=[False, native, None, False],
        ):
            result, _ = self.create()
        warning = result["warnings"][0]
        self.assertEqual((warning["stage"], warning["call"]), ("create", "AddToDB.set(True)"))
        self.assertEqual(result["error"], {"type": "com_error", "message": str(native)})
        self.assertEqual(warning["native_error"]["hresult"], -2147023898)
        self.document.SketchManager.CreateCircleByRadius.assert_not_called()
        self.assertIsNone(self.document.SketchManager.ActiveSketch)
        validate_operation_result("sketch.circle", result)

    def test_com_failure_context_is_not_overwritten_by_failed_cleanup(self):
        native_type = type("com_error", (Exception,), {})
        creation_error = native_type(-2147023898, "creation memory error")
        cleanup_error = native_type(-2147417848, "cleanup disconnect")
        manager = self.document.SketchManager
        manager.CreateCircleByRadius.side_effect = creation_error

        def fail_cleanup(update):
            if manager.ActiveSketch is None:
                manager.toggle(update)
            else:
                raise cleanup_error

        manager.InsertSketch.side_effect = fail_cleanup
        result, feature = self.create()
        self.assertIsNotNone(feature)
        self.assertEqual(result["error"], {"type": "com_error", "message": str(creation_error)})
        self.assertEqual(result["warnings"][0]["stage"], "create")
        self.assertEqual(result["warnings"][0]["call"], "CreateCircleByRadius")
        self.assertEqual(result["warnings"][1]["code"], "sketch-cleanup-failed")
        self.assertIn("cleanup disconnect", result["warnings"][1]["message"])
        self.assertTrue(result["editing"])
        validate_operation_result("sketch.circle", result)

    def test_success_and_domain_failures_do_not_emit_com_failure_context(self):
        result, _ = self.create()
        self.assertNotIn("warnings", result)
        self.setUp()
        result, _ = self.create(radius_mm=0)
        self.assertNotIn("warnings", result)
        self.assertEqual(result["error"]["type"], "InvalidArgument")

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
        self.inference = True

        def set_inference(flag, value):
            self.assertEqual(flag, 249)
            self.inference = value
            return True

        self.app = SimpleNamespace(
            IsSame=lambda a, b: int(a is b),
            GetUserPreferenceToggle=mock.Mock(side_effect=lambda flag: self.inference),
            SetUserPreferenceToggle=mock.Mock(side_effect=set_inference),
        )

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

    def test_direct_rectangle_creation_preserves_the_ci_requested_center_and_width(self):
        manager = self.document.SketchManager
        create_rectangle = manager.CreateCenterRectangle.side_effect

        def infer_or_create(x, y, z, xmax, ymax, zmax):
            # Native Windows and Wine still snap this composite tool with
            # AddToDB=True when application sketch inference remains enabled.
            if not manager.AddToDB or self.inference:
                x = 0  # UI snapping produces the CI's [-23,23] instead of [-17,23].
            return create_rectangle(x, y, z, xmax, ymax, zmax)

        manager.CreateCenterRectangle.side_effect = infer_or_create
        result, feature = self.create(width_mm=40, height_mm=30,
                                      center_x_mm=3, center_y_mm=4)
        self.assertTrue(result["ok"], result)
        self.assertIsNotNone(feature)
        self.assertEqual(result["geometry_verification"]["actual_bounds_mm"],
                         {"min_x": -17, "max_x": 23, "min_y": -11, "max_y": 19})
        manager.CreateCenterRectangle.assert_called_once_with(.003, .004, 0, .023, .019, 0)
        self.assertFalse(manager.AddToDB)
        self.assertTrue(self.inference)

    def test_rectangle_inference_is_scoped_and_restored_before_close(self):
        for original in (False, True):
            with self.subTest(original=original):
                self.setUp()
                self.inference = original
                manager = self.document.SketchManager
                create_rectangle = manager.CreateCenterRectangle.side_effect

                def create(*arguments):
                    self.assertFalse(self.inference)
                    return create_rectangle(*arguments)

                manager.CreateCenterRectangle.side_effect = create
                manager.on_close = lambda: self.assertEqual(self.inference, original)
                result, _ = self.create()
                self.assertTrue(result["ok"], result)
                self.app.SetUserPreferenceToggle.assert_has_calls(
                    [mock.call(249, False), mock.call(249, original)]
                )
                self.assertEqual(self.inference, original)

    def test_rectangle_refuses_unknown_or_unchanged_inference_without_geometry(self):
        for observed in (None, 1, "false", True):
            with self.subTest(observed=observed):
                self.setUp()
                self.app.GetUserPreferenceToggle.side_effect = lambda flag: observed
                result, _ = self.create()
                self.assertFalse(result["ok"])
                self.document.SketchManager.CreateCenterRectangle.assert_not_called()
                self.assertIsNone(self.document.SketchManager.ActiveSketch)

    def test_rectangle_native_failure_restores_inference_without_retry(self):
        self.document.SketchManager.CreateCenterRectangle.side_effect = RuntimeError("native")
        result, _ = self.create()
        self.assertEqual(result["error"], {"type": "RuntimeError", "message": "native"})
        self.assertTrue(self.inference)
        self.document.SketchManager.CreateCenterRectangle.assert_called_once()

    def test_rectangle_failed_inference_restore_is_not_success(self):
        for rejected in (False, True):
            with self.subTest(rejected=rejected):
                self.setUp()
                setter = self.app.SetUserPreferenceToggle.side_effect

                def fail_restore(flag, value):
                    if value:
                        if rejected:
                            return False
                        raise RuntimeError("restore failure")
                    return setter(flag, value)

                self.app.SetUserPreferenceToggle.side_effect = fail_restore
                result, feature = self.create()
                self.assertIsNotNone(feature)
                self.assertFalse(result["ok"])
                self.assertEqual(result["error"]["type"], "SketchStateRestoreFailed")
                self.assertEqual(result["warnings"][0]["code"], "sketch-inference-restore-failed")
                self.assertTrue(result["geometry_verification"]["passed"])
                self.assertFalse(result["editing"])
                validate_operation_result("sketch.rectangle", result)

    def test_rectangle_creation_mode_is_restored_without_display_or_solver_changes(self):
        for original in (False, True):
            with self.subTest(original=original):
                self.setUp()
                manager = self.document.SketchManager
                manager.AddToDB = original
                manager.DisplayWhenAdded = True
                manager.AutoSolve = True
                create_rectangle = manager.CreateCenterRectangle.side_effect

                def direct(*arguments):
                    self.assertTrue(manager.AddToDB)
                    return create_rectangle(*arguments)

                manager.CreateCenterRectangle.side_effect = direct
                manager.on_close = lambda: self.assertEqual(manager.AddToDB, original)
                result, _ = self.create()
                self.assertTrue(result["ok"], result)
                self.assertEqual(manager.AddToDB, original)
                self.assertTrue(manager.DisplayWhenAdded)
                self.assertTrue(manager.AutoSolve)

    def test_failed_rectangle_creation_restores_mode_and_preserves_native_error(self):
        manager = self.document.SketchManager
        manager.CreateCenterRectangle.side_effect = RuntimeError("native rectangle failed")
        result, _ = self.create()
        self.assertEqual(result["error"], {"type": "RuntimeError", "message": "native rectangle failed"})
        manager.CreateCenterRectangle.assert_called_once()
        self.assertFalse(manager.AddToDB)
        self.assertIsNone(manager.ActiveSketch)

    def test_rectangle_creation_refuses_failed_enable_before_creating_geometry(self):
        with mock.patch.object(Manager, "AddToDB", new_callable=mock.PropertyMock,
                               create=True, side_effect=[False, None, False, None, False]):
            result, _ = self.create()
        self.assertFalse(result["ok"])
        self.document.SketchManager.CreateCenterRectangle.assert_not_called()
        self.assertIsNone(self.document.SketchManager.ActiveSketch)

    def test_failed_rectangle_mode_restore_is_not_reported_as_success(self):
        with mock.patch.object(Manager, "AddToDB", new_callable=mock.PropertyMock,
                               create=True, side_effect=[False, None, True, RuntimeError("restore failed")]):
            result, feature = self.create()
        self.assertIsNotNone(feature)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["type"], "SketchStateRestoreFailed")
        self.assertEqual(result["warnings"][0]["code"], "sketch-creation-mode-restore-failed")
        self.assertTrue(result["geometry_verification"]["passed"])
        self.assertFalse(result["editing"])
        validate_operation_result("sketch.rectangle", result)

    def test_rectangle_trace_covers_native_edit_create_close_and_verification(self):
        stream = io.StringIO()
        with mock.patch.dict(os.environ, {"SWCLI_TRACE_NATIVE_CALLS": "1"}), \
                mock.patch("swcli.hosts.native_trace.sys.stderr", stream):
            with trace_native_request("req-rectangle", "sketch.rectangle"):
                result, feature = self.create()
        self.assertTrue(result["ok"], result)
        self.assertIs(feature, self.document.features[-1])
        self.assertIsNone(self.document.SketchManager.ActiveSketch)
        events = [json.loads(line) for line in stream.getvalue().splitlines()]
        beginnings = {e["sequence"]: e for e in events if e["phase"] == "begin"}
        endings = {e["sequence"]: e for e in events if e["phase"] == "end"}
        self.assertEqual(set(beginnings), set(endings))
        self.assertTrue(all(e["request_id"] == "req-rectangle" for e in events))
        boundaries = {(e["stage"], e["call"]) for e in beginnings.values()}
        self.assertTrue({
            ("plane-select", "Select2"),
            ("sketch-enter", "SketchManager.InsertSketch"),
            ("create", "SketchManager.CreateCenterRectangle"),
            ("sketch-close", "SketchManager.InsertSketch"),
            ("verify", "profile-geometry"),
        }.issubset(boundaries))
        self.document.SketchManager.CreateCenterRectangle.assert_called_once()
        self.assertEqual(self.document.SketchManager.InsertSketch.call_count, 2)

    def test_rectangle_trace_keeps_native_failure_and_owned_edit_cleanup_without_retry(self):
        manager = self.document.SketchManager
        manager.CreateCenterRectangle.side_effect = RuntimeError("native creation failed")
        stream = io.StringIO()
        with mock.patch.dict(os.environ, {"SWCLI_TRACE_NATIVE_CALLS": "1"}), \
                mock.patch("swcli.hosts.native_trace.sys.stderr", stream):
            with trace_native_request("req-fail", "sketch.rectangle"):
                result, _ = self.create()
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["type"], "RuntimeError")
        self.assertEqual(result["error"]["message"], "native creation failed")
        self.assertFalse(result["editing"])
        self.assertIsNone(manager.ActiveSketch)
        manager.CreateCenterRectangle.assert_called_once()
        self.assertEqual(manager.InsertSketch.call_count, 2)
        events = [json.loads(line) for line in stream.getvalue().splitlines()]
        self.assertTrue(any(e["call"] == "SketchManager.CreateCenterRectangle"
                            and e["phase"] == "error" for e in events))
        self.assertTrue(any(e["stage"] == "cleanup"
                            and e["call"] == "SketchManager.InsertSketch"
                            and e["phase"] == "end" for e in events))

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
