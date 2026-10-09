"""Linear inspect/set are role-specific, read-only or guarded, never diameters."""

from copy import deepcopy
import unittest
from unittest import mock

from swcli.daemon import operations
from swcli.daemon.documents import DimensionNotFound, DocumentLeaseConflict
from swcli.result_schemas import OperationResultInvalid, validate_operation_result
import test_dimension_operations as operation_fixtures
import test_windows_linear_dimensions as native_fixtures


class LinearDimensionContractTests(unittest.TestCase):
    def fixture(self, kind="width"):
        fixture = native_fixtures.RectangleSetTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.axis = kind
        fixture.parameters[kind].SetSystemValue3 = fixture.setter
        fixture._diagnose_features.side_effect = lambda document, limit: {
            "healthy": True,
            "truncated": False,
            "issues": [],
            "issue_count": 0,
            "scanned_feature_count": 10,
            "limit": 500,
        }
        return fixture

    @staticmethod
    def wire(result):
        result = deepcopy(result)
        result.update(
            sketch_id="s-ab12cd",
            document={
                "title": "Part1",
                "path": "",
                "type": 1,
                "modified": True,
                "update_stamp": result.get("observation", {})
                .get("after", {})
                .get("update_stamp", 11),
                "document_id": "d-ab12cd",
                "current": False,
                "active": False,
            },
        )
        result.setdefault("dimension", {"kind": "width"}).update(
            dimension_id="m-ab12cd", sketch_id="s-ab12cd"
        )
        return result

    def test_native_read_and_edit_shapes_match_strict_role_branches(self):
        for kind in ("width", "height"):
            fixture = self.fixture(kind)
            read = self.wire(fixture.call(kind))
            validate_operation_result("dimension.inspect", read)
            changed = self.wire(fixture.set_call(50))
            validate_operation_result("dimension.set", changed)
            self.assertEqual(changed["dimension"]["kind"], kind)
            self.assertEqual(
                changed["geometry_verification"]["expected_center_mm"],
                {"x": 3, "y": 4, "z": 0},
            )

    def test_read_observes_controls_edit_and_geometry_mismatch_without_mutation(self):
        fixture = self.fixture()
        fixture.parameters["width"].DrivenState = 1
        fixture.parameters["width"].ReadOnly = 1
        fixture.parameters["width"].value = 0.041
        fixture.manager.ActiveSketch = fixture.sketch
        result = self.wire(fixture.call())
        self.assertFalse(result["geometry_verification"]["passed"])
        self.assertTrue(result["editing"])
        validate_operation_result("dimension.inspect", result)
        fixture.setter.assert_not_called()

    def test_success_rejects_metadata_role_state_and_geometry_contradictions(self):
        read = self.wire(self.fixture().call())
        for parent, field, value in (
            ("dimension", "kind", "diameter"),
            ("dimension", "kind", "height"),
            ("dimension", "configuration", "Other"),
            ("dimension", "value", 41),
            ("geometry_verification", "passed", False),
            ("observation", "unchanged", False),
        ):
            invalid = deepcopy(read)
            invalid[parent][field] = value
            with (
                self.subTest(parent=parent, field=field),
                self.assertRaises(OperationResultInvalid),
            ):
                validate_operation_result("dimension.inspect", invalid)
        invalid = deepcopy(read)
        invalid["observation"]["after"]["update_stamp"] += 1
        with self.assertRaises(OperationResultInvalid):
            validate_operation_result("dimension.inspect", invalid)
        invalid = deepcopy(read)
        invalid["document"]["update_stamp"] += 1
        with self.assertRaises(OperationResultInvalid):
            validate_operation_result("dimension.inspect", invalid)

    def test_edit_success_requires_complete_native_snapshots_and_preserved_other_axis(
        self,
    ):
        result = self.wire(self.fixture().set_call())
        for parent, field, value in (
            ("final_state", "update_stamp", 99),
            ("dimension", "value", 51),
            ("geometry_verification", "expected_height_mm", 31),
            ("geometry_verification", "expected_center_mm", {"x": 4, "y": 4, "z": 0}),
            ("before", "ok", False),
            ("after", "ok", False),
        ):
            invalid = deepcopy(result)
            invalid[parent][field] = value
            with (
                self.subTest(parent=parent, field=field),
                self.assertRaises(OperationResultInvalid),
            ):
                validate_operation_result("dimension.set", invalid)
        for field in ("before", "after", "final_state"):
            invalid = deepcopy(result)
            del invalid[field]
            with self.assertRaises(OperationResultInvalid):
                validate_operation_result("dimension.set", invalid)

    def test_preflight_and_failed_mutation_preserve_the_original_error(self):
        fixture = self.fixture()
        fixture.manager.ActiveSketch = fixture.sketch
        result = self.wire(fixture.set_call())
        validate_operation_result("dimension.set", result)
        fixture.setter.assert_not_called()
        fixture.manager.ActiveSketch = None
        fixture.drift = True
        result = self.wire(fixture.set_call())
        self.assertFalse(result["ok"])
        self.assertTrue(result["modification_may_have_happened"])
        self.assertEqual(result["error"]["type"], "DimensionVerificationFailed")
        validate_operation_result("dimension.set", result)


class LinearDimensionOperationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = operation_fixtures.DimensionOperationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def register(self, kind):
        f = self.fixture
        native = object()
        handle = f.registry.register_dimension(
            f.entry, f.sketch_id, native, kind=kind, profile_kind="rectangle"
        )
        return native, handle

    def test_exact_leased_background_read_never_activates_or_calls_diameter(self):
        f = self.fixture
        for kind in ("width", "height"):
            native, handle = self.register(kind)
            with (
                mock.patch.object(
                    operations,
                    "inspect_rectangle_dimension_windows",
                    return_value={
                        "ok": False,
                        "action": "dimension.inspect",
                        "error": {
                            "type": "DimensionUnavailable",
                            "message": "native gone",
                        },
                    },
                ) as read,
                mock.patch.object(operations, "inspect_dimension_windows") as diameter,
                mock.patch.object(f.registry, "temporarily_activate") as activate,
            ):
                result = f.call(
                    "dimension.inspect",
                    {"dimension_id": handle},
                    session_id="observer",
                    expected_update_stamp=10,
                )
                read.assert_called_once_with(
                    app=f.app,
                    document=f.target,
                    sketch_feature=f.sketch,
                    dimension=native,
                    kind=kind,
                )
                diameter.assert_not_called()
                activate.assert_not_called()
                f.assert_context_retained(result)
                self.assertEqual(
                    result["dimension"],
                    {"kind": kind, "dimension_id": handle, "sketch_id": f.sketch_id},
                )
                validate_operation_result("dimension.inspect", result)

    def test_edit_guard_activation_exact_role_and_failure_discriminator(self):
        f = self.fixture
        for kind in ("width", "height"):
            native, handle = self.register(kind)
            values = {"dimension_id": handle, "value_mm": 50}
            with (
                mock.patch.object(
                    operations,
                    "set_rectangle_dimension_windows",
                    return_value={
                        "ok": False,
                        "action": "dimension.set",
                        "error": {
                            "type": "SketchEditInProgress",
                            "message": "finish edit",
                        },
                    },
                ) as setter,
                mock.patch.object(operations, "set_dimension_windows") as diameter,
            ):
                with self.assertRaises(DocumentLeaseConflict):
                    f.call("dimension.set", values)
                with self.assertRaises(operations.DocumentUpdateConflict):
                    f.call(
                        "dimension.set",
                        values,
                        lease_id=f.lease,
                        expected_update_stamp=9,
                    )
                with self.assertRaises(DimensionNotFound):
                    f.call("dimension.set", values, document_id=f.other.document_id)
                setter.assert_not_called()
                with mock.patch.object(
                    f.registry, "temporarily_activate", side_effect=f.activate
                ):
                    result = f.call(
                        "dimension.set",
                        values,
                        lease_id=f.lease,
                        expected_update_stamp=10,
                    )
                setter.assert_called_once_with(
                    app=f.app,
                    document=f.target,
                    sketch_feature=f.sketch,
                    dimension=native,
                    kind=kind,
                    value_mm=50.0,
                )
                diameter.assert_not_called()
                f.assert_context_retained(result)
                validate_operation_result("dimension.set", result)


if __name__ == "__main__":
    unittest.main()
