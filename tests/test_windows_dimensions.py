import json
import math
import unittest
from types import SimpleNamespace
from unittest import mock

from swcli.hosts import windows_dimensions as dimensions

INVALID_METADATA = (
    ("ReadOnly", (None, 2, -2, 0.0, 1.0, "false")),
    ("DrivenState", (None, True, 2.9, "2", 3)),
    ("FullName", (None, 0, "", " ")),
    ("IsDesignTableDimension", (None, 0, 1, "false")),
)
INVALID_NATIVE_VALUES = (None, True, False, "0.016", 0, -1, math.nan, math.inf)
INVALID_CIRCLE_FLAGS = (
    ("ConstructionGeometry", (None, 0, 1, 0.0, 1.5, "false")),
    ("GetType", (None, True, False, 1.0, 1.5, "1")),
    ("IsCircle", (None, True, False, 1.0, 1.5, "1", -1, 2)),
)
INVALID_CIRCLE_NUMBERS = (None, True, False, "0.005", math.nan, math.inf, 10**1000)


class DiameterFixture:
    def setUp(self):
        self.radius = 0.005
        self.arc = SimpleNamespace(
            ConstructionGeometry=False,
            GetType=lambda: 1,
            IsCircle=lambda: 1,
            GetRadius=lambda: self.radius,
            GetCenterPoint2=lambda: SimpleNamespace(X=0.003, Y=0.004, Z=0.0),
            Select4=mock.Mock(return_value=True),
        )
        self.sketch = SimpleNamespace(
            GetSketchSegments=lambda: (self.arc,),
            GetConstrainedStatus=lambda: 2,
        )
        self.feature = SimpleNamespace(
            GetTypeName2=lambda: "ProfileFeature",
            GetSpecificFeature2=lambda: self.sketch,
            GetOwnerFeature=lambda: None,
            GetNextFeature=lambda: None,
            GetFirstSubFeature=lambda: None,
            GetNextSubFeature=lambda: None,
            GetFirstDisplayDimension=lambda: None,
            GetNextDisplayDimension=lambda display: None,
            Select2=mock.Mock(return_value=True),
        )
        self.manager = SimpleNamespace(ActiveSketch=None)
        self.manager.InsertSketch = mock.Mock(side_effect=self.exit_edit)
        self.dimension = SimpleNamespace(
            DrivenState=2,
            ReadOnly=False,
            FullName="D1@renamed-sketch@part.Part",
            GetSystemValue2=lambda name: self.radius * 2,
            SetSystemValue3=mock.Mock(side_effect=self.set_value),
            GetFeatureOwner=lambda: self.feature,
            IsDesignTableDimension=lambda: False,
        )
        self.edit_call = mock.Mock(side_effect=self.enter_edit)
        self.document = SimpleNamespace(
            GetType=lambda: 1,
            FirstFeature=lambda: self.feature,
            SketchManager=self.manager,
            ClearSelection2=mock.Mock(),
            EditSketch=lambda: self.edit_call(),
            ConfigurationManager=SimpleNamespace(
                ActiveConfiguration=SimpleNamespace(Name="Default")
            ),
            AddDiameterDimension2=mock.Mock(
                return_value=SimpleNamespace(GetDimension2=lambda index: self.dimension)
            ),
            GetEquationMgr=lambda: SimpleNamespace(GetCount=lambda: 0),
            EditRebuild3=lambda: True,
            Extension=SimpleNamespace(NeedsRebuild2=0),
            GetBodies2=lambda kind, hidden: (),
        )
        self.preference = True
        self.app = SimpleNamespace(
            IsSame=lambda a, b: int(a is b),
            GetUserPreferenceToggle=lambda flag: self.preference,
            SetUserPreferenceToggle=mock.Mock(side_effect=self.set_preference),
        )
        self.patchers = [
            mock.patch.object(
                dimensions, "_variant", side_effect=lambda kind, value: (kind, value)
            ),
            mock.patch.object(
                dimensions, "_annotation_location", return_value=(0.01, 0.02, 0.0)
            ),
        ]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def enter_edit(self):
        self.manager.ActiveSketch = self.sketch

    def exit_edit(self, update):
        self.manager.ActiveSketch = None

    def set_value(self, value, configuration, names):
        self.radius = value / 2
        return 0

    def set_preference(self, flag, value):
        self.preference = value
        return True

    def set_metadata(self, member, value):
        if member == "IsDesignTableDimension":
            setattr(self.dimension, member, lambda: value)
        else:
            setattr(self.dimension, member, value)

    def native_equations(self, count, entry=None):
        self.document.GetEquationMgr = lambda: SimpleNamespace(
            GetCount=lambda: count, Equation=lambda index: entry
        )

    def set_circle_member(self, member, value):
        if member in "XYZ":
            point = SimpleNamespace(X=0.003, Y=0.004, Z=0.0)
            setattr(point, member, value)
            self.arc.GetCenterPoint2 = lambda: point
        elif member == "ConstructionGeometry":
            setattr(self.arc, member, value)
        else:
            setattr(self.arc, member, lambda: value)

    def call(self, diameter=16):
        return dimensions.create_circle_diameter_windows_with_handle(
            app=self.app,
            document=self.document,
            sketch_feature=self.feature,
            diameter_mm=diameter,
        )


class LengthDescriptorTests(DiameterFixture, unittest.TestCase):
    def test_explicit_kind_preserves_exact_length_metadata(self):
        expected = dimensions._descriptor(self.document, self.dimension)
        self.assertEqual(expected["kind"], "diameter")
        for kind in ("diameter", "width", "height"):
            with self.subTest(kind=kind):
                actual = dimensions._descriptor(
                    self.document, self.dimension, kind=kind
                )
                self.assertEqual(actual, dict(expected, kind=kind))

    def test_unknown_kind_is_rejected_before_any_native_read(self):
        for kind in (None, True, 0, "length", "radius", "", "WIDTH"):
            with self.subTest(kind=kind):
                document, dimension = mock.Mock(), mock.Mock()
                with self.assertRaises(ValueError):
                    dimensions._descriptor(document, dimension, kind=kind)
                self.assertEqual(document.mock_calls, [])
                self.assertEqual(dimension.mock_calls, [])

    def test_linear_roles_keep_strict_native_value_and_control_readers(self):
        for kind in ("width", "height"):
            for value in INVALID_NATIVE_VALUES + (10**1000,):
                with self.subTest(kind=kind, value=str(value)[:20]):
                    self.dimension.GetSystemValue2 = lambda name: value
                    with self.assertRaises(dimensions._DimensionError) as caught:
                        dimensions._descriptor(
                            self.document, self.dimension, kind=kind
                        )
                    self.assertEqual(
                        caught.exception.code, "DimensionObservationUnavailable"
                    )
                    self.assertIn(f"native {kind} value", str(caught.exception))
        self.dimension.GetSystemValue2 = lambda name: 0.01
        for member, values in INVALID_METADATA[:3]:
            for value in values:
                with self.subTest(member=member, value=value):
                    self.set_metadata(member, value)
                    with self.assertRaises(dimensions._DimensionError):
                        dimensions._descriptor(
                            self.document, self.dimension, kind="width"
                        )
            self.setUp()


class DiameterCreationTests(DiameterFixture, unittest.TestCase):
    def test_actual_driving_value_geometry_and_exact_handle_with_cleanup(self):
        result, handle = self.call()
        self.assertTrue(result["ok"], result)
        self.assertIs(handle, self.dimension)
        self.assertEqual(result["dimension"]["value"], 16)
        self.assertEqual(result["dimension"]["configuration"], "Default")
        self.assertTrue(result["geometry_verification"]["passed"])
        self.dimension.SetSystemValue3.assert_called_once_with(
            0.016, 1, ("empty", None)
        )
        self.arc.Select4.assert_called_once_with(False, ("dispatch", None))
        self.assertTrue(self.preference)
        self.assertIsNone(self.manager.ActiveSketch)

    def test_invalid_input_does_not_select_or_edit(self):
        for value in (0, -1, True, None, "16", math.nan, math.inf, 5e-324, 10**1000):
            with self.subTest(value=str(value)[:20]):
                result, handle = self.call(value)
                self.assertEqual(result["error"]["type"], "InvalidArgument")
                self.assertIsNone(handle)
        self.document.ClearSelection2.assert_not_called()
        self.edit_call.assert_not_called()

    def test_non_part_existing_edit_and_stale_or_consumed_sketch_are_rejected(self):
        for setup, expected in (
            (
                lambda: setattr(self.document, "GetType", lambda: 2),
                "UnsupportedDocumentType",
            ),
            (
                lambda: setattr(self.manager, "ActiveSketch", object()),
                "SketchEditInProgress",
            ),
            (
                lambda: setattr(self.document, "FirstFeature", lambda: None),
                "SketchUnavailable",
            ),
            (
                lambda: setattr(self.feature, "GetOwnerFeature", lambda: object()),
                "SketchUnavailable",
            ),
        ):
            with self.subTest(expected=expected):
                self.setUp()
                setup()
                result, _ = self.call()
                self.assertEqual(result["error"]["type"], expected)
                self.document.ClearSelection2.assert_not_called()

    def test_partial_construction_multiple_or_already_dimensioned_profiles_are_rejected(
        self,
    ):
        for setup, expected in (
            (
                lambda: setattr(self.arc, "IsCircle", lambda: 0),
                "UnsupportedDimensionProfile",
            ),
            (
                lambda: setattr(self.arc, "ConstructionGeometry", True),
                "UnsupportedDimensionProfile",
            ),
            (
                lambda: setattr(
                    self.sketch, "GetSketchSegments", lambda: (self.arc, self.arc)
                ),
                "UnsupportedDimensionProfile",
            ),
            (
                lambda: setattr(
                    self.feature, "GetFirstDisplayDimension", lambda: object()
                ),
                "SketchAlreadyDimensioned",
            ),
        ):
            with self.subTest(expected=expected):
                self.setUp()
                setup()
                result, _ = self.call()
                self.assertEqual(result["error"]["type"], expected)
                self.edit_call.assert_not_called()

    def test_selection_failure_does_not_change_preference(self):
        self.arc.Select4.return_value = False
        result, handle = self.call()
        self.assertEqual(result["error"]["type"], "SketchSelectionFailed")
        self.assertIsNone(handle)
        self.assertIsNone(self.manager.ActiveSketch)
        self.app.SetUserPreferenceToggle.assert_not_called()

    def test_unknown_circle_flags_fail_before_creation_or_setting(self):
        for member, values in INVALID_CIRCLE_FLAGS:
            for value in values:
                with self.subTest(member=member, value=value):
                    self.setUp()
                    self.set_circle_member(member, value)
                    result, handle = self.call()
                    self.assertFalse(result["ok"], result)
                    self.assertEqual(
                        result["error"]["type"], "DimensionObservationUnavailable"
                    )
                    self.assertIsNone(handle)
                    self.document.AddDiameterDimension2.assert_not_called()
                    self.dimension.SetSystemValue3.assert_not_called()
                    self.document.ClearSelection2.assert_not_called()
                    self.edit_call.assert_not_called()

    def test_unknown_circle_numbers_fail_before_creation_or_setting(self):
        for member in ("GetRadius", "X", "Y", "Z"):
            for value in INVALID_CIRCLE_NUMBERS:
                with self.subTest(member=member, value=str(value)[:20]):
                    self.setUp()
                    self.set_circle_member(member, value)
                    result, handle = self.call()
                    self.assertEqual(
                        result["error"]["type"], "DimensionObservationUnavailable"
                    )
                    self.assertIsNone(handle)
                    self.document.AddDiameterDimension2.assert_not_called()
                    self.dimension.SetSystemValue3.assert_not_called()
                    self.edit_call.assert_not_called()
                    json.dumps(result, allow_nan=False)

    def test_unreadable_circle_flags_or_geometry_do_not_create_a_dimension(self):
        for member in ("ConstructionGeometry", "GetType", "IsCircle", "GetRadius", "X"):
            with self.subTest(member=member):
                self.setUp()

                def failing():
                    raise RuntimeError("native circle unavailable")

                self.set_circle_member(member, failing)
                if member not in ("ConstructionGeometry", "X"):
                    setattr(self.arc, member, failing)
                result, handle = self.call()
                self.assertEqual(result["error"]["type"], "RuntimeError")
                self.assertIsNone(handle)
                self.document.AddDiameterDimension2.assert_not_called()
                self.dimension.SetSystemValue3.assert_not_called()
                self.edit_call.assert_not_called()

    def test_unknown_post_creation_circle_retains_partial_handle_and_native_status(
        self,
    ):
        for member, values in INVALID_CIRCLE_FLAGS + tuple(
            (member, INVALID_CIRCLE_NUMBERS) for member in ("GetRadius", "X", "Y", "Z")
        ):
            for value in values:
                with self.subTest(member=member, value=str(value)[:20]):
                    self.setUp()

                    def changed_circle(native_value, configuration, names):
                        self.set_value(native_value, configuration, names)
                        self.set_circle_member(member, value)
                        return 0

                    self.dimension.SetSystemValue3.side_effect = changed_circle
                    result, handle = self.call()
                    self.assertFalse(result["ok"], result)
                    self.assertEqual(
                        result["error"]["type"], "DimensionObservationUnavailable"
                    )
                    self.assertIs(handle, self.dimension)
                    self.assertEqual(result["native_status"], 0)
                    self.assertIn(
                        "modification may have happened", result["error"]["message"]
                    )
                    self.dimension.SetSystemValue3.assert_called_once()
                    self.assertIsNone(self.manager.ActiveSketch)
                    self.assertTrue(self.preference)
                    self.assertNotIn("geometry_verification", result)
                    json.dumps(result, allow_nan=False)

    def test_failed_post_creation_circle_readback_retains_native_write_and_cleanup(
        self,
    ):
        for member in ("ConstructionGeometry", "GetType", "IsCircle", "GetRadius", "X"):
            with self.subTest(member=member):
                self.setUp()

                def changed_circle(native_value, configuration, names):
                    self.set_value(native_value, configuration, names)

                    def failing():
                        raise RuntimeError("native circle unavailable after creation")

                    self.set_circle_member(member, failing)
                    if member not in ("ConstructionGeometry", "X"):
                        setattr(self.arc, member, failing)
                    return 0

                self.dimension.SetSystemValue3.side_effect = changed_circle
                result, handle = self.call()
                self.assertFalse(result["ok"], result)
                self.assertEqual(result["error"]["type"], "RuntimeError")
                self.assertIs(handle, self.dimension)
                self.assertEqual(result["native_status"], 0)
                self.assertIn(
                    "modification may have happened", result["error"]["message"]
                )
                self.dimension.SetSystemValue3.assert_called_once()
                self.assertIsNone(self.manager.ActiveSketch)
                self.assertTrue(self.preference)

    def test_creation_failure_restores_preference_and_exits_our_edit(self):
        self.document.AddDiameterDimension2.side_effect = RuntimeError(
            "creation failed"
        )
        result, handle = self.call()
        self.assertEqual(result["error"]["type"], "RuntimeError")
        self.assertIsNone(handle)
        self.assertTrue(self.preference)
        self.assertIsNone(self.manager.ActiveSketch)

    def test_driven_or_read_only_dimension_is_not_overridden(self):
        for field, value in (("DrivenState", 1), ("ReadOnly", True)):
            with self.subTest(field=field):
                self.setUp()
                setattr(self.dimension, field, value)
                result, handle = self.call()
                self.assertEqual(result["error"]["type"], "DimensionNotDriving")
                self.assertIs(handle, self.dimension)
                self.dimension.SetSystemValue3.assert_not_called()
                self.assertIsNone(self.manager.ActiveSketch)
                self.assertTrue(self.preference)

    def test_native_set_failure_retains_partial_handle_and_native_code(self):
        self.dimension.SetSystemValue3.side_effect = None
        self.dimension.SetSystemValue3.return_value = 3
        result, handle = self.call()
        self.assertEqual(result["error"]["type"], "DimensionSetFailed")
        self.assertEqual(result["native_status"], 3)
        self.assertIs(handle, self.dimension)
        self.assertIsNone(self.manager.ActiveSketch)

    def test_false_success_value_and_geometry_are_checked_independently(self):
        self.dimension.GetSystemValue2 = lambda name: 0.020
        result, handle = self.call()
        self.assertEqual(result["error"]["type"], "DimensionVerificationFailed")
        self.assertIs(handle, self.dimension)
        self.setUp()
        self.dimension.SetSystemValue3.side_effect = lambda *args: 0
        self.dimension.GetSystemValue2 = lambda name: 0.016
        result, _ = self.call()
        self.assertEqual(result["error"]["type"], "DimensionVerificationFailed")
        self.assertFalse(result["geometry_verification"]["passed"])

    def test_nonfinite_native_value_is_not_leaked_to_wire_json(self):
        def corrupted_readback(value, configuration, names):
            self.set_value(value, configuration, names)
            self.dimension.GetSystemValue2 = lambda name: math.nan
            return 0

        self.dimension.SetSystemValue3.side_effect = corrupted_readback
        result, handle = self.call()
        self.assertEqual(result["error"]["type"], "DimensionObservationUnavailable")
        self.assertIs(handle, self.dimension)
        self.assertEqual(result["native_status"], 0)
        json.dumps(result, allow_nan=False)

    def test_unknown_creation_metadata_never_sets_but_retains_partial_handle(self):
        for member, values in INVALID_METADATA:
            for value in values:
                with self.subTest(member=member, value=value):
                    self.setUp()
                    self.set_metadata(member, value)
                    result, handle = self.call()
                    self.assertFalse(result["ok"], result)
                    self.assertEqual(
                        result["error"]["type"], "DimensionObservationUnavailable"
                    )
                    self.document.AddDiameterDimension2.assert_called_once()
                    self.dimension.SetSystemValue3.assert_not_called()
                    self.assertIs(handle, self.dimension)
                    self.assertIsNone(self.manager.ActiveSketch)
                    self.assertTrue(self.preference)
                    json.dumps(result, allow_nan=False)

    def test_creation_accepts_native_readonly_zero_but_rejects_true_encodings(self):
        for value in (0, 1, -1):
            with self.subTest(value=value):
                self.setUp()
                self.dimension.ReadOnly = value
                result, handle = self.call()
                self.assertIs(handle, self.dimension)
                if value == 0:
                    self.assertTrue(result["ok"], result)
                    self.assertIs(result["dimension"]["read_only"], False)
                    self.dimension.SetSystemValue3.assert_called_once()
                else:
                    self.assertEqual(result["error"]["type"], "DimensionNotDriving")
                    self.dimension.SetSystemValue3.assert_not_called()

    def test_invalid_creation_configuration_never_mutates(self):
        for name in (None, True, 0, "", " "):
            with self.subTest(name=name):
                self.setUp()
                self.document.ConfigurationManager.ActiveConfiguration.Name = name
                result, handle = self.call()
                self.assertEqual(
                    result["error"]["type"], "DimensionObservationUnavailable"
                )
                self.assertIsNone(handle)
                self.document.AddDiameterDimension2.assert_not_called()
                self.dimension.SetSystemValue3.assert_not_called()

    def test_invalid_created_native_value_prevents_setting_and_retains_handle(self):
        for value in INVALID_NATIVE_VALUES:
            with self.subTest(value=value):
                self.setUp()
                self.dimension.GetSystemValue2 = lambda name: value
                result, handle = self.call()
                self.assertEqual(
                    result["error"]["type"], "DimensionObservationUnavailable"
                )
                self.assertIs(handle, self.dimension)
                self.dimension.SetSystemValue3.assert_not_called()
                json.dumps(result, allow_nan=False)

    def test_creation_requires_readable_equation_and_table_control_before_setting(self):
        for count in (None, True, 0.9, "0", -1, 10001):
            with self.subTest(count=count):
                self.setUp()
                self.native_equations(count)
                result, handle = self.call()
                self.assertEqual(
                    result["error"]["type"], "DimensionObservationUnavailable"
                )
                self.assertIs(handle, self.dimension)
                self.dimension.SetSystemValue3.assert_not_called()
        for entry in (None, 0, "", " ", "invalid equation"):
            with self.subTest(entry=entry):
                self.setUp()
                self.native_equations(1, entry)
                result, handle = self.call()
                self.assertEqual(
                    result["error"]["type"], "DimensionObservationUnavailable"
                )
                self.assertIs(handle, self.dimension)
                self.dimension.SetSystemValue3.assert_not_called()
        for controlled in ("equation", "table"):
            with self.subTest(controlled=controlled):
                self.setUp()
                if controlled == "equation":
                    self.native_equations(1, '"D1@renamed-sketch" = 20')
                else:
                    self.set_metadata("IsDesignTableDimension", True)
                result, handle = self.call()
                self.assertEqual(
                    result["error"]["type"], "DimensionExternallyControlled"
                )
                self.assertIs(handle, self.dimension)
                self.dimension.SetSystemValue3.assert_not_called()

    def test_post_creation_unknown_metadata_retains_successful_native_status(self):
        for member, value in (
            ("ReadOnly", None),
            ("DrivenState", 2.9),
            ("FullName", None),
            ("IsDesignTableDimension", None),
        ):
            with self.subTest(member=member):
                self.setUp()

                def changed_metadata(value_mm, configuration, names):
                    self.set_value(value_mm, configuration, names)
                    self.set_metadata(member, value)
                    return 0

                self.dimension.SetSystemValue3.side_effect = changed_metadata
                result, handle = self.call()
                self.assertEqual(
                    result["error"]["type"], "DimensionObservationUnavailable"
                )
                self.assertEqual(result["native_status"], 0)
                self.assertIs(handle, self.dimension)
                self.dimension.SetSystemValue3.assert_called_once()
                self.assertIsNone(self.manager.ActiveSketch)
                self.assertTrue(self.preference)
                json.dumps(result, allow_nan=False)

    def test_post_creation_external_control_is_not_reported_as_success(self):
        for controlled in ("equation", "table"):
            with self.subTest(controlled=controlled):
                self.setUp()

                def externally_controlled(value, configuration, names):
                    self.set_value(value, configuration, names)
                    if controlled == "equation":
                        self.native_equations(1, '"D1@renamed-sketch" = 20')
                    else:
                        self.set_metadata("IsDesignTableDimension", True)
                    return 0

                self.dimension.SetSystemValue3.side_effect = externally_controlled
                result, handle = self.call()
                self.assertEqual(
                    result["error"]["type"], "DimensionExternallyControlled"
                )
                self.assertEqual(result["native_status"], 0)
                self.assertIs(handle, self.dimension)
                self.dimension.SetSystemValue3.assert_called_once()

    def test_preference_restoration_failure_reports_warning(self):
        def restore_failure(flag, value):
            if value:
                raise RuntimeError("cannot restore")
            self.preference = value
            return True

        self.app.SetUserPreferenceToggle.side_effect = restore_failure
        result, _ = self.call()
        self.assertTrue(result["ok"])
        self.assertEqual(
            result["warnings"][0]["code"], "dimension-preference-restore-failed"
        )

    def test_rejected_prompt_suppression_never_creates_a_modal_dimension(self):
        self.app.SetUserPreferenceToggle.side_effect = None
        self.app.SetUserPreferenceToggle.return_value = False
        result, handle = self.call()
        self.assertEqual(result["error"]["type"], "RuntimeError")
        self.assertIsNone(handle)
        self.document.AddDiameterDimension2.assert_not_called()
        self.assertIsNone(self.manager.ActiveSketch)

    def test_silent_preference_restore_failure_is_reported(self):
        def restore_rejected(flag, value):
            if value:
                return False
            self.preference = False
            return True

        self.app.SetUserPreferenceToggle.side_effect = restore_rejected
        result, _ = self.call()
        self.assertTrue(result["ok"])
        self.assertEqual(
            result["warnings"][0]["code"], "dimension-preference-restore-failed"
        )

    def test_void_native_setter_is_verified_by_preference_readback(self):
        def native_void(flag, value):
            self.preference = value

        self.app.SetUserPreferenceToggle.side_effect = native_void
        result, _ = self.call()
        self.assertTrue(result["ok"], result)
        self.assertTrue(self.preference)

    def test_cleanup_does_not_close_another_active_sketch(self):
        unrelated = object()
        self.edit_call.side_effect = lambda: setattr(
            self.manager, "ActiveSketch", unrelated
        )
        result, _ = self.call()
        self.assertFalse(result["ok"])
        self.assertIs(self.manager.ActiveSketch, unrelated)
        self.manager.InsertSketch.assert_not_called()
        self.assertTrue(result["editing"])
        self.assertEqual(result["warnings"][0]["code"], "sketch-edit-cleanup-failed")

    def test_cleanup_checks_that_the_owned_edit_really_closed(self):
        self.document.AddDiameterDimension2.side_effect = RuntimeError(
            "creation failed"
        )
        self.manager.InsertSketch.side_effect = None
        result, _ = self.call()
        self.assertTrue(result["editing"])
        self.assertIs(self.manager.ActiveSketch, self.sketch)
        self.assertTrue(self.preference)
        self.assertEqual(result["warnings"][0]["code"], "sketch-edit-cleanup-failed")


class DiameterObservationTests(DiameterFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.feature.GetFirstDisplayDimension = lambda: SimpleNamespace(
            GetDimension2=lambda index: self.dimension
        )
        patcher = mock.patch.object(
            dimensions,
            "_diagnose_features",
            return_value={
                "healthy": True,
                "issues": [],
                "issue_count": 0,
                "scanned_feature_count": 1,
                "truncated": False,
                "limit": 500,
            },
        )
        self.diagnostics = patcher.start()
        self.addCleanup(patcher.stop)

    def inspect(self):
        return dimensions.inspect_dimension_windows(
            app=self.app,
            document=self.document,
            sketch_feature=self.feature,
            dimension=self.dimension,
        )

    def set(self, value=16):
        return dimensions.set_dimension_windows(
            app=self.app,
            document=self.document,
            sketch_feature=self.feature,
            dimension=self.dimension,
            value_mm=value,
        )

    def assert_read_only(self):
        self.dimension.SetSystemValue3.assert_not_called()
        self.document.ClearSelection2.assert_not_called()
        self.feature.Select2.assert_not_called()
        self.edit_call.assert_not_called()
        self.manager.InsertSketch.assert_not_called()
        self.app.SetUserPreferenceToggle.assert_not_called()
        self.diagnostics.assert_not_called()

    def equations(self, *expressions):
        self.document.GetEquationMgr = lambda: SimpleNamespace(
            GetCount=lambda: len(expressions), Equation=lambda index: expressions[index]
        )

    def test_inspect_is_factual_read_only_even_for_existing_edit_or_driven_dimension(
        self,
    ):
        self.dimension.DrivenState = 1
        self.dimension.ReadOnly = True
        self.manager.ActiveSketch = object()
        result = self.inspect()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["action"], "dimension.inspect")
        self.assertEqual(result["dimension"]["value"], 10)
        self.assertEqual(result["dimension"]["driven_state"], 1)
        self.assertTrue(result["dimension"]["read_only"])
        self.assertTrue(result["editing"])
        self.assertTrue(result["geometry_verification"]["passed"])
        self.assertFalse(result["equation_control"]["controlled"])
        self.assert_read_only()

    def test_inspect_and_set_find_absorbed_sketch_by_native_identity(self):
        owner = SimpleNamespace(
            GetTypeName2=lambda: "Boss",
            GetNextFeature=lambda: None,
            GetFirstSubFeature=lambda: self.feature,
        )
        self.feature.GetOwnerFeature = lambda: owner
        self.document.FirstFeature = lambda: owner
        self.assertTrue(self.inspect()["ok"])
        result = self.set()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["dimension"]["value"], 16)
        self.assertEqual(result["before_value_mm"], 10)
        self.assertEqual(result["native_status"], 0)
        self.assertEqual(
            result["downstream"],
            {
                "applicable": False,
                "measurement_before": None,
                "measurement_after": None,
            },
        )
        self.dimension.SetSystemValue3.assert_called_once_with(
            0.016, 1, ("empty", None)
        )
        self.edit_call.assert_not_called()

    def test_deleted_cross_document_or_replaced_same_name_dimension_is_rejected(self):
        for setup, code in (
            (
                lambda: setattr(self.document, "FirstFeature", lambda: None),
                "SketchUnavailable",
            ),
            (
                lambda: setattr(self.dimension, "GetFeatureOwner", lambda: object()),
                "DimensionUnavailable",
            ),
            (
                lambda: setattr(self.feature, "GetFirstDisplayDimension", lambda: None),
                "DimensionUnavailable",
            ),
            (
                lambda: setattr(
                    self.feature,
                    "GetFirstDisplayDimension",
                    lambda: SimpleNamespace(
                        GetDimension2=lambda index: SimpleNamespace(
                            FullName=self.dimension.FullName
                        )
                    ),
                ),
                "DimensionUnavailable",
            ),
        ):
            with self.subTest(code=code):
                self.setUp()
                setup()
                self.assertEqual(self.inspect()["error"]["type"], code)
                self.assertEqual(self.set()["error"]["type"], code)
                self.assert_read_only()

    def test_exact_dimension_can_follow_another_display_dimension(self):
        first = SimpleNamespace(GetDimension2=lambda index: object())
        last = SimpleNamespace(GetDimension2=lambda index: self.dimension)
        self.feature.GetFirstDisplayDimension = lambda: first
        self.feature.GetNextDisplayDimension = lambda display: (
            last if display is first else None
        )
        self.assertTrue(self.inspect()["ok"])
        self.assert_read_only()

    def test_unknown_native_identity_at_each_owner_stage_blocks_inspect_and_set(self):
        for stage in (1, 2, 3):
            for value in (None, True, False, 1.0, 1.5, "1", "0", -1, 2):
                for operation in ("inspect", "set"):
                    with self.subTest(stage=stage, value=value, operation=operation):
                        self.setUp()
                        self.app.IsSame = mock.Mock(
                            side_effect=[1] * (stage - 1) + [value]
                        )
                        result = getattr(self, operation)()
                        self.assertFalse(result["ok"], result)
                        self.assertEqual(
                            result["error"]["type"], "DimensionObservationUnavailable"
                        )
                        self.assertEqual(self.app.IsSame.call_count, stage)
                        self.assertNotIn("geometry_verification", result)
                        self.assert_read_only()

    def test_unknown_document_type_does_not_become_a_part(self):
        for value in (None, True, False, 1.0, 1.5, "1"):
            with self.subTest(value=value):
                self.setUp()
                self.document.GetType = lambda: value
                self.app.IsSame = mock.Mock()
                for observe in (self.inspect, self.set):
                    result = observe()
                    self.assertFalse(result["ok"], result)
                    self.assertEqual(
                        result["error"]["type"], "DimensionObservationUnavailable"
                    )
                self.app.IsSame.assert_not_called()
                self.assert_read_only()
        for value in (-1, 0, 2, 3, 4, 99):
            with self.subTest(nonpart_enum=value):
                self.setUp()
                self.document.GetType = lambda: value
                self.assertEqual(
                    self.inspect()["error"]["type"], "UnsupportedDocumentType"
                )
                self.assertEqual(self.set()["error"]["type"], "UnsupportedDocumentType")
                self.assert_read_only()

    def test_native_identity_zero_is_not_same_and_one_remains_supported(self):
        for stage, error in (
            (1, "SketchUnavailable"),
            (2, "DimensionUnavailable"),
            (3, "DimensionUnavailable"),
        ):
            for operation in ("inspect", "set"):
                with self.subTest(stage=stage, operation=operation):
                    self.setUp()
                    self.app.IsSame = mock.Mock(side_effect=[1] * (stage - 1) + [0])
                    self.assertEqual(getattr(self, operation)()["error"]["type"], error)
                    self.assert_read_only()
        self.setUp()
        self.app.IsSame = mock.Mock(return_value=1)
        self.assertTrue(self.inspect()["ok"])
        self.assertTrue(self.set()["ok"])
        self.dimension.SetSystemValue3.assert_called_once()

    def test_unreadable_native_identity_blocks_prewrite_and_preserves_postwrite_failure(
        self,
    ):
        for stage in (1, 2, 3):
            for operation in ("inspect", "set"):
                with self.subTest(stage=stage, operation=operation):
                    self.setUp()
                    self.app.IsSame = mock.Mock(
                        side_effect=[1] * (stage - 1)
                        + [RuntimeError("native identity unavailable")]
                    )
                    result = getattr(self, operation)()
                    self.assertFalse(result["ok"], result)
                    self.assertEqual(result["error"]["type"], "RuntimeError")
                    self.assert_read_only()
            with self.subTest(postwrite_stage=stage):
                self.setUp()

                def unreadable_identity(native_value, configuration, names):
                    self.set_value(native_value, configuration, names)
                    self.app.IsSame = mock.Mock(
                        side_effect=[1] * (stage - 1)
                        + [RuntimeError("native identity unavailable")]
                    )
                    return 0

                self.dimension.SetSystemValue3.side_effect = unreadable_identity
                result = self.set()
                self.assertFalse(result["ok"], result)
                self.assertEqual(result["error"]["type"], "RuntimeError")
                self.assertEqual(result["native_status"], 0)
                self.assertEqual(result["before_value_mm"], 10)
                self.assertIn("downstream", result)
                self.assertIn(
                    "modification may have happened", result["error"]["message"]
                )
                self.dimension.SetSystemValue3.assert_called_once()

    def test_post_set_unknown_identity_retains_native_write_and_original_evidence(self):
        for stage in (1, 2, 3):
            for value in (None, True, False, 1.5, "1", -1, 2):
                with self.subTest(stage=stage, value=value):
                    self.setUp()

                    def changed_identity(native_value, configuration, names):
                        self.set_value(native_value, configuration, names)
                        self.app.IsSame = mock.Mock(
                            side_effect=[1] * (stage - 1) + [value]
                        )
                        return 0

                    self.dimension.SetSystemValue3.side_effect = changed_identity
                    result = self.set()
                    self.assertFalse(result["ok"], result)
                    self.assertEqual(
                        result["error"]["type"], "DimensionObservationUnavailable"
                    )
                    self.assertEqual(result["native_status"], 0)
                    self.assertEqual(result["before_value_mm"], 10)
                    self.assertIn("downstream", result)
                    self.assertIn(
                        "modification may have happened", result["error"]["message"]
                    )
                    self.dimension.SetSystemValue3.assert_called_once()
                    self.assertEqual(self.app.IsSame.call_count, stage)

    def test_post_set_unknown_document_type_retains_successful_native_status(self):
        for value in (None, True, False, 1.5, "1"):
            with self.subTest(value=value):
                self.setUp()

                def changed_type(native_value, configuration, names):
                    self.set_value(native_value, configuration, names)
                    self.document.GetType = lambda: value
                    return 0

                self.dimension.SetSystemValue3.side_effect = changed_type
                result = self.set()
                self.assertFalse(result["ok"], result)
                self.assertEqual(
                    result["error"]["type"], "DimensionObservationUnavailable"
                )
                self.assertEqual(result["native_status"], 0)
                self.assertEqual(result["before_value_mm"], 10)
                self.assertIn("downstream", result)
                self.assertIn(
                    "modification may have happened", result["error"]["message"]
                )
                self.dimension.SetSystemValue3.assert_called_once()

    def test_equations_are_observed_and_never_overridden_or_matched_by_rhs(self):
        self.equations('"global" = 20', '"D2@other" = "D1@renamed-sketch"')
        self.assertFalse(self.inspect()["equation_control"]["controlled"])
        for lhs in ("D1@renamed-sketch", self.dimension.FullName.upper()):
            with self.subTest(lhs=lhs):
                self.equations('"global" = 20', '"' + lhs + '" = "global"')
                result = self.inspect()
                self.assertTrue(result["ok"], result)
                self.assertEqual(
                    result["equation_control"],
                    {"controlled": True, "equation_indices": [1]},
                )
                self.assertEqual(
                    self.set()["error"]["type"], "DimensionExternallyControlled"
                )
                self.dimension.SetSystemValue3.assert_not_called()

    def test_unavailable_or_malformed_equation_observation_fails_closed(self):
        for setup in (
            lambda: setattr(self.document, "GetEquationMgr", lambda: None),
            lambda: self.equations("unparseable equation"),
            lambda: setattr(
                self.document,
                "GetEquationMgr",
                lambda: SimpleNamespace(GetCount=lambda: -1),
            ),
            lambda: setattr(
                self.document,
                "GetEquationMgr",
                lambda: SimpleNamespace(GetCount=lambda: 10001),
            ),
        ):
            with self.subTest(setup=setup):
                self.setUp()
                setup()
                self.assertEqual(
                    self.set()["error"]["type"], "DimensionObservationUnavailable"
                )
                self.assert_read_only()

    def test_external_driven_read_only_or_existing_edit_is_not_overridden(self):
        for setup, code in (
            (
                lambda: setattr(self.dimension, "IsDesignTableDimension", lambda: True),
                "DimensionExternallyControlled",
            ),
            (lambda: setattr(self.dimension, "DrivenState", 1), "DimensionNotDriving"),
            (lambda: setattr(self.dimension, "ReadOnly", True), "DimensionNotDriving"),
            (
                lambda: setattr(self.manager, "ActiveSketch", object()),
                "SketchEditInProgress",
            ),
        ):
            with self.subTest(code=code):
                self.setUp()
                setup()
                self.assertEqual(self.set()["error"]["type"], code)
                self.assert_read_only()

    def test_invalid_lengths_are_rejected_before_native_observation(self):
        self.document.SketchManager = None
        for value in (0, -1, True, None, "16", math.nan, math.inf, 5e-324, 10**1000):
            with self.subTest(value=str(value)[:20]):
                self.assertEqual(self.set(value)["error"]["type"], "InvalidArgument")
        self.dimension.SetSystemValue3.assert_not_called()

    def test_invalid_or_ambiguous_profile_is_rejected_before_setting(self):
        for setup in (
            lambda: setattr(self.arc, "ConstructionGeometry", True),
            lambda: setattr(self.arc, "IsCircle", lambda: 0),
            lambda: setattr(
                self.sketch, "GetSketchSegments", lambda: (self.arc, self.arc)
            ),
        ):
            with self.subTest(setup=setup):
                self.setUp()
                setup()
                self.assertEqual(
                    self.set()["error"]["type"], "UnsupportedDimensionProfile"
                )
                self.assert_read_only()

    def test_unknown_circle_flags_block_inspect_and_native_setting(self):
        for member, values in INVALID_CIRCLE_FLAGS:
            for value in values:
                with self.subTest(member=member, value=value):
                    self.setUp()
                    self.set_circle_member(member, value)
                    for observe in (self.inspect, self.set):
                        result = observe()
                        self.assertFalse(result["ok"], result)
                        self.assertEqual(
                            result["error"]["type"], "DimensionObservationUnavailable"
                        )
                        self.assertNotIn("geometry_verification", result)
                    self.assert_read_only()

    def test_unknown_circle_numbers_block_inspect_and_native_setting(self):
        for member in ("GetRadius", "X", "Y", "Z"):
            for value in INVALID_CIRCLE_NUMBERS:
                with self.subTest(member=member, value=str(value)[:20]):
                    self.setUp()
                    self.set_circle_member(member, value)
                    for observe in (self.inspect, self.set):
                        result = observe()
                        self.assertEqual(
                            result["error"]["type"], "DimensionObservationUnavailable"
                        )
                        json.dumps(result, allow_nan=False)
                    self.assert_read_only()

    def test_native_numeric_circle_preserves_exact_observed_center(self):
        self.radius = 1
        self.arc.GetCenterPoint2 = lambda: SimpleNamespace(X=-1, Y=1, Z=2e-10)
        result = self.inspect()
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["geometry_verification"]["passed"])
        self.assertEqual(result["geometry_verification"]["actual_radius_mm"], 1000)
        center = result["geometry_verification"]["actual_center_mm"]
        self.assertEqual((center["x"], center["y"]), (-1000, 1000))
        self.assertAlmostEqual(center["z"], 2e-7)
        self.assert_read_only()

    def test_unreadable_circle_blocks_inspect_and_setting_without_mutation(self):
        for member in ("ConstructionGeometry", "GetType", "IsCircle", "GetRadius", "X"):
            with self.subTest(member=member):
                self.setUp()

                def failing():
                    raise RuntimeError("native circle unavailable")

                self.set_circle_member(member, failing)
                if member not in ("ConstructionGeometry", "X"):
                    setattr(self.arc, member, failing)
                for observe in (self.inspect, self.set):
                    result = observe()
                    self.assertEqual(result["error"]["type"], "RuntimeError")
                self.assert_read_only()

    def test_unknown_later_circle_readback_is_not_a_successful_inspection(self):
        for member, value in (
            ("ConstructionGeometry", None),
            ("GetType", 1.5),
            ("IsCircle", True),
            ("GetRadius", "0.005"),
            ("X", False),
        ):
            with self.subTest(member=member):
                self.setUp()

                def changed_circle(configuration):
                    self.set_circle_member(member, value)
                    return self.radius * 2

                self.dimension.GetSystemValue2 = changed_circle
                result = self.inspect()
                self.assertFalse(result["ok"], result)
                self.assertEqual(
                    result["error"]["type"], "DimensionObservationUnavailable"
                )
                self.assertNotIn("geometry_verification", result)
                self.assert_read_only()

    def test_unknown_post_set_circle_preserves_successful_native_write_evidence(self):
        for member, values in INVALID_CIRCLE_FLAGS + tuple(
            (member, INVALID_CIRCLE_NUMBERS) for member in ("GetRadius", "X", "Y", "Z")
        ):
            for value in values:
                with self.subTest(member=member, value=str(value)[:20]):
                    self.setUp()

                    def changed_circle(native_value, configuration, names):
                        self.set_value(native_value, configuration, names)
                        self.set_circle_member(member, value)
                        return 0

                    self.dimension.SetSystemValue3.side_effect = changed_circle
                    result = self.set()
                    self.assertFalse(result["ok"], result)
                    self.assertEqual(
                        result["error"]["type"], "DimensionObservationUnavailable"
                    )
                    self.assertEqual(result["native_status"], 0)
                    self.assertEqual(result["before_value_mm"], 10)
                    self.assertIn("downstream", result)
                    self.assertIn(
                        "modification may have happened", result["error"]["message"]
                    )
                    self.dimension.SetSystemValue3.assert_called_once()
                    self.assertNotIn("geometry_verification", result)
                    json.dumps(result, allow_nan=False)

    def test_failed_post_set_circle_readback_retains_native_and_before_evidence(self):
        for member in ("ConstructionGeometry", "GetType", "IsCircle", "GetRadius", "X"):
            with self.subTest(member=member):
                self.setUp()

                def changed_circle(native_value, configuration, names):
                    self.set_value(native_value, configuration, names)

                    def failing():
                        raise RuntimeError("native circle unavailable after setting")

                    self.set_circle_member(member, failing)
                    if member not in ("ConstructionGeometry", "X"):
                        setattr(self.arc, member, failing)
                    return 0

                self.dimension.SetSystemValue3.side_effect = changed_circle
                result = self.set()
                self.assertFalse(result["ok"], result)
                self.assertEqual(result["error"]["type"], "RuntimeError")
                self.assertEqual(result["native_status"], 0)
                self.assertEqual(result["before_value_mm"], 10)
                self.assertIn("downstream", result)
                self.assertIn(
                    "modification may have happened", result["error"]["message"]
                )
                self.dimension.SetSystemValue3.assert_called_once()

    def test_native_set_rejection_reports_status_without_rollback(self):
        self.dimension.SetSystemValue3.side_effect = None
        self.dimension.SetSystemValue3.return_value = 3
        result = self.set()
        self.assertEqual(result["error"]["type"], "DimensionSetFailed")
        self.assertEqual(result["native_status"], 3)
        self.diagnostics.assert_not_called()
        self.dimension.SetSystemValue3.assert_called_once()

    def test_preexisting_dimension_geometry_mismatch_prevents_mutation(self):
        self.dimension.GetSystemValue2 = lambda configuration: 0.016
        result = self.inspect()
        self.assertTrue(result["ok"])
        self.assertFalse(result["geometry_verification"]["passed"])
        self.assertEqual(self.set()["error"]["type"], "DimensionVerificationFailed")
        self.assert_read_only()

    def test_final_value_geometry_center_and_configuration_are_verified_independently(
        self,
    ):
        for defect in (
            "value",
            "radius",
            "center",
            "configuration",
            "state",
            "read_only",
        ):
            with self.subTest(defect=defect):
                self.setUp()

                def false_success(value, configuration, names):
                    self.radius = 0.008
                    if defect == "value":
                        self.dimension.GetSystemValue2 = lambda name: 0.020
                    elif defect == "radius":
                        self.radius = 0.006
                        self.dimension.GetSystemValue2 = lambda name: 0.016
                    elif defect == "center":
                        self.arc.GetCenterPoint2 = lambda: SimpleNamespace(
                            X=0.006, Y=0.004, Z=0
                        )
                    elif defect == "configuration":
                        self.document.ConfigurationManager.ActiveConfiguration.Name = (
                            "Other"
                        )
                    elif defect == "state":
                        self.dimension.DrivenState = 1
                    else:
                        self.dimension.ReadOnly = True
                    return 0

                self.dimension.SetSystemValue3.side_effect = false_success
                result = self.set()
                self.assertEqual(result["error"]["type"], "DimensionVerificationFailed")
                self.assertEqual(result["native_status"], 0)
                self.dimension.SetSystemValue3.assert_called_once()

    def test_rebuild_error_pending_rebuild_warning_and_truncation_are_not_false_success(
        self,
    ):
        for defect in ("rebuild", "pending", "unhealthy", "truncated"):
            with self.subTest(defect=defect):
                self.setUp()
                if defect == "rebuild":
                    self.document.EditRebuild3 = lambda: False
                elif defect == "pending":
                    self.document.Extension.NeedsRebuild2 = 1
                else:
                    self.diagnostics.return_value = {
                        **self.diagnostics.return_value,
                        "healthy": defect != "unhealthy",
                        "truncated": defect == "truncated",
                    }
                result = self.set()
                self.assertEqual(result["error"]["type"], "ModelInvalid")
                self.assertEqual(result["dimension"]["value"], 16)

    def test_downstream_evidence_is_fresh_and_failed_measurement_blocks_success(self):
        body = SimpleNamespace(
            GetMassProperties=lambda density: (
                0,
                0,
                0,
                math.pi * self.radius**2 * 0.01,
                0.001,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
            )
        )
        self.document.GetBodies2 = lambda kind, hidden: (body,)
        result = self.set(20)
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["downstream"]["applicable"])
        self.assertAlmostEqual(
            result["downstream"]["measurement_before"]["volume_mm3"],
            math.pi * 5**2 * 10,
        )
        self.assertAlmostEqual(
            result["downstream"]["measurement_after"]["volume_mm3"],
            math.pi * 10**2 * 10,
        )
        self.setUp()
        self.document.GetBodies2 = lambda kind, hidden: (
            SimpleNamespace(GetMassProperties=lambda density: ()),
        )
        self.assertEqual(
            self.set()["error"]["type"], "DownstreamObservationUnavailable"
        )
        self.dimension.SetSystemValue3.assert_not_called()

    def test_disappearing_solid_body_or_dimension_after_rebuild_blocks_success(self):
        for defect in ("body", "dimension"):
            with self.subTest(defect=defect):
                self.setUp()
                if defect == "body":
                    body = SimpleNamespace(
                        GetMassProperties=lambda density: (
                            0,
                            0,
                            0,
                            1e-6,
                            0.001,
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                        )
                    )
                    self.document.GetBodies2 = lambda kind, hidden: (body,)

                def rebuild():
                    if defect == "body":
                        self.document.GetBodies2 = lambda kind, hidden: ()
                    else:
                        self.feature.GetFirstDisplayDimension = lambda: None
                    return True

                self.document.EditRebuild3 = rebuild
                result = self.set()
                self.assertEqual(
                    result["error"]["type"],
                    (
                        "DimensionVerificationFailed"
                        if defect == "body"
                        else "DimensionUnavailable"
                    ),
                )
                self.assertEqual(result["native_status"], 0)

    def test_nonfinite_value_never_leaks_nan_and_inspect_never_rebuilds(self):
        self.dimension.GetSystemValue2 = lambda configuration: math.nan
        result = self.inspect()
        self.assertEqual(result["error"]["type"], "DimensionObservationUnavailable")
        json.dumps(result, allow_nan=False)
        self.assert_read_only()

    def test_unknown_public_metadata_fails_inspect_and_blocks_set(self):
        for member, values in INVALID_METADATA:
            for value in values:
                with self.subTest(member=member, value=value):
                    self.setUp()
                    self.set_metadata(member, value)
                    for result in (self.inspect(), self.set()):
                        self.assertFalse(result["ok"], result)
                        self.assertEqual(
                            result["error"]["type"], "DimensionObservationUnavailable"
                        )
                        json.dumps(result, allow_nan=False)
                    self.assert_read_only()

    def test_readonly_native_integer_bindings_are_observed_without_broad_coercion(self):
        for value, expected in ((0, False), (1, True), (-1, True)):
            with self.subTest(value=value):
                self.setUp()
                self.dimension.ReadOnly = value
                inspected = self.inspect()
                self.assertTrue(inspected["ok"], inspected)
                self.assertIs(inspected["dimension"]["read_only"], expected)
                result = self.set()
                if expected:
                    self.assertEqual(result["error"]["type"], "DimensionNotDriving")
                    self.assert_read_only()
                else:
                    self.assertTrue(result["ok"], result)
                    self.dimension.SetSystemValue3.assert_called_once()

    def test_unknown_name_does_not_hide_actual_equation_control(self):
        self.equations('"D1@renamed-sketch" = 20')
        self.dimension.FullName = None
        result = self.set()
        self.assertEqual(result["error"]["type"], "DimensionObservationUnavailable")
        self.dimension.SetSystemValue3.assert_not_called()
        self.assert_read_only()

    def test_invalid_configuration_or_value_fails_before_setting(self):
        for name in (None, True, 0, "", " "):
            with self.subTest(configuration=name):
                self.setUp()
                self.document.ConfigurationManager.ActiveConfiguration.Name = name
                self.assertEqual(
                    self.inspect()["error"]["type"], "DimensionObservationUnavailable"
                )
                self.assertEqual(
                    self.set()["error"]["type"], "DimensionObservationUnavailable"
                )
                self.assert_read_only()
        for value in INVALID_NATIVE_VALUES:
            with self.subTest(value=value):
                self.setUp()
                self.dimension.GetSystemValue2 = lambda name: value
                for result in (self.inspect(), self.set()):
                    self.assertEqual(
                        result["error"]["type"], "DimensionObservationUnavailable"
                    )
                    json.dumps(result, allow_nan=False)
                self.assert_read_only()

    def test_invalid_equation_count_or_entry_is_not_coerced_to_no_control(self):
        for count in (None, True, 0.9, "0", -1, 10001):
            with self.subTest(count=count):
                self.setUp()
                self.native_equations(count)
                self.assertEqual(
                    self.inspect()["error"]["type"], "DimensionObservationUnavailable"
                )
                self.assertEqual(
                    self.set()["error"]["type"], "DimensionObservationUnavailable"
                )
                self.assert_read_only()
        for entry in (None, 0, "", " ", "invalid equation"):
            with self.subTest(entry=entry):
                self.setUp()
                self.native_equations(1, entry)
                self.assertEqual(
                    self.inspect()["error"]["type"], "DimensionObservationUnavailable"
                )
                self.assertEqual(
                    self.set()["error"]["type"], "DimensionObservationUnavailable"
                )
                self.assert_read_only()

    def test_post_set_unknown_metadata_preserves_native_and_before_evidence(self):
        for member, value in (
            ("ReadOnly", None),
            ("DrivenState", 2.9),
            ("FullName", None),
            ("IsDesignTableDimension", None),
        ):
            with self.subTest(member=member):
                self.setUp()

                def changed_metadata(value_mm, configuration, names):
                    self.set_value(value_mm, configuration, names)
                    self.set_metadata(member, value)
                    return 0

                self.dimension.SetSystemValue3.side_effect = changed_metadata
                result = self.set()
                self.assertEqual(
                    result["error"]["type"], "DimensionObservationUnavailable"
                )
                self.assertEqual(result["native_status"], 0)
                self.assertEqual(result["before_value_mm"], 10)
                self.assertIn("dimension", result)
                self.assertIn("downstream", result)
                self.dimension.SetSystemValue3.assert_called_once()
                json.dumps(result, allow_nan=False)

    def test_post_set_external_control_fails_without_hiding_completed_write(self):
        for controlled in ("equation", "table"):
            with self.subTest(controlled=controlled):
                self.setUp()

                def externally_controlled(value, configuration, names):
                    self.set_value(value, configuration, names)
                    if controlled == "equation":
                        self.equations('"D1@renamed-sketch" = 20')
                    else:
                        self.set_metadata("IsDesignTableDimension", True)
                    return 0

                self.dimension.SetSystemValue3.side_effect = externally_controlled
                result = self.set()
                self.assertEqual(
                    result["error"]["type"], "DimensionExternallyControlled"
                )
                self.assertEqual(result["native_status"], 0)
                self.assertEqual(result["before_value_mm"], 10)
                self.assertIn("downstream", result)
                self.dimension.SetSystemValue3.assert_called_once()


if __name__ == "__main__":
    unittest.main()
