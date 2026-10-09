"""Public rectangle dimensions preserve exact bindings and partial evidence."""

from copy import deepcopy
import unittest
from unittest import mock

from jsonschema import Draft202012Validator

from swcli.cli import _typed_operation, build_parser
from swcli.daemon import operations
from swcli.daemon.documents import DocumentLeaseConflict, SketchNotFound
from swcli.operation_schemas import OPERATION_CATALOG, validate_operation_request
from swcli.result_schemas import OperationResultInvalid, validate_operation_result
import test_dimension_operations as operation_fixtures
import test_windows_rectangle_dimensions as native_fixtures


class RectangleCreationContractTests(unittest.TestCase):
    def native_fixture(self):
        fixture = native_fixtures.RectangleDimensionTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
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
                "update_stamp": 18,
                "document_id": "d-ab12cd",
                "current": False,
                "active": False,
            },
        )
        if result["ok"]:
            for kind, token in (("width", "m-ab12cd"), ("height", "m-ab12ce")):
                result["dimensions"][kind].update(
                    dimension_id=token, sketch_id="s-ab12cd"
                )
        return result

    def test_catalog_cli_and_write_guards_preserve_selector_before_position(self):
        spec = OPERATION_CATALOG["sketch.dimension-rectangle"]
        self.assertTrue(
            spec.selected_document and spec.lease_guarded and spec.temporary_activation
        )
        args = build_parser().parse_args(
            [
                "--session",
                "writer",
                "sketch",
                "dimension-rectangle",
                "--document",
                "d-ab12cd",
                "s-ab12cd",
                "--width-mm",
                "40",
                "--height-mm",
                "30",
                "--lease",
                "l-ab12cd34ef56",
                "--if-update-stamp",
                "0",
                "--json",
            ]
        )
        values = {"sketch_id": "s-ab12cd", "width_mm": 40, "height_mm": 30}
        self.assertEqual(
            _typed_operation(args),
            (
                "sketch.dimension-rectangle",
                values,
                True,
                "d-ab12cd",
                0,
                "l-ab12cd34ef56",
            ),
        )
        self.assertEqual(args.session, "writer")
        self.assertEqual(
            validate_operation_request("sketch.dimension-rectangle", values), values
        )

    def test_request_refuses_guessed_names_invalid_sizes_and_implicit_position(self):
        valid = {"sketch_id": "s-ab12cd", "width_mm": 40, "height_mm": 30}
        validator = Draft202012Validator(
            OPERATION_CATALOG["sketch.dimension-rectangle"].parameters
        )
        invalid = [
            {},
            {**valid, "sketch_id": "Sketch1"},
            {**valid, "fix_center": True},
            {**valid, "center_x_mm": 3},
        ]
        invalid.extend(
            {**valid, axis: value}
            for axis in ("width_mm", "height_mm")
            for value in (None, True, 0, -1, "40")
        )
        for values in invalid:
            with self.subTest(values=values):
                self.assertFalse(validator.is_valid(values))
                with self.assertRaises(ValueError):
                    validate_operation_request("sketch.dimension-rectangle", values)
        for value in (float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                validate_operation_request(
                    "sketch.dimension-rectangle", {**valid, "width_mm": value}
                )

    def test_real_adapter_shape_requires_verified_pair_steps_and_closed_edit(self):
        result = self.wire(self.native_fixture().call()[0])
        validate_operation_result("sketch.dimension-rectangle", result)
        for parent, field, value in (
            ("dimensions", "height", None),
            ("native_status", "height", 1),
            ("steps", "height", None),
            ("geometry_verification", "center_preserved", False),
        ):
            invalid = deepcopy(result)
            invalid[parent][field] = value
            with (
                self.subTest(parent=parent, field=field),
                self.assertRaises(OperationResultInvalid),
            ):
                validate_operation_result("sketch.dimension-rectangle", invalid)
        for key, value in (("editing", True), ("modification_may_have_happened", True)):
            invalid = {**result, key: value}
            with self.assertRaises(OperationResultInvalid):
                validate_operation_result("sketch.dimension-rectangle", invalid)
        for kind in ("width", "height"):
            invalid = deepcopy(result)
            invalid["dimensions"][kind]["kind"] = "diameter"
            with self.assertRaises(OperationResultInvalid):
                validate_operation_result("sketch.dimension-rectangle", invalid)

    def test_boolean_success_cannot_hide_inconsistent_geometry_or_parameter(self):
        result = self.wire(self.native_fixture().call()[0])
        invalid = deepcopy(result)
        invalid["steps"]["width"]["actual"]["center_mm"]["x"] += 1
        with self.assertRaises(OperationResultInvalid):
            validate_operation_result("sketch.dimension-rectangle", invalid)
        for kind, field, value in (
            ("width", "value", 51),
            ("height", "configuration", "Other"),
            ("height", "sketch_id", "s-ab12ce"),
        ):
            invalid = deepcopy(result)
            invalid["dimensions"][kind][field] = value
            with (
                self.subTest(kind=kind, field=field),
                self.assertRaises(OperationResultInvalid),
            ):
                validate_operation_result("sketch.dimension-rectangle", invalid)

    def test_native_partial_failure_fits_schema_without_verified_handles(self):
        fixture = self.native_fixture()
        fixture.document.AddVerticalDimension2.side_effect = RuntimeError(
            "height failed"
        )
        fixture.manager.InsertSketch.side_effect = RuntimeError("cleanup failed")
        result, handles = fixture.call()
        self.assertEqual(set(handles), {"width"})
        self.assertTrue(result["modification_may_have_happened"])
        self.assertEqual(result["error"]["message"], "height failed")
        result = self.wire(result)
        validate_operation_result("sketch.dimension-rectangle", result)
        result["dimensions"]["width"]["dimension_id"] = "m-ab12cd"
        with self.assertRaises(OperationResultInvalid):
            validate_operation_result("sketch.dimension-rectangle", result)


class RectangleCreationOperationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = operation_fixtures.DimensionOperationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        native = native_fixtures.RectangleDimensionTests()
        native.setUp()
        self.addCleanup(native.doCleanups)
        self.native_result, self.handles = native.call()
        self.values = {
            "sketch_id": self.fixture.sketch_id,
            "width_mm": 50,
            "height_mm": 35,
        }

    def call(self, **context):
        return self.fixture.call("sketch.dimension-rectangle", self.values, **context)

    @mock.patch.object(operations, "create_rectangle_dimensions_windows_with_handles")
    def test_guards_before_activation_and_exact_background_pair_registration(
        self, create
    ):
        f = self.fixture
        create.return_value = (deepcopy(self.native_result), self.handles)
        with mock.patch.object(f.registry, "temporarily_activate") as activate:
            for context, error in (
                ({}, DocumentLeaseConflict),
                ({"lease_id": f.lease, "session_id": "other"}, DocumentLeaseConflict),
                (
                    {"lease_id": f.lease, "expected_update_stamp": 9},
                    operations.DocumentUpdateConflict,
                ),
                ({"document_id": f.other.document_id}, SketchNotFound),
            ):
                with self.subTest(context=context), self.assertRaises(error):
                    self.call(**context)
            create.assert_not_called()
            activate.assert_not_called()
        with mock.patch.object(
            f.registry, "temporarily_activate", side_effect=f.activate
        ):
            result = self.call(lease_id=f.lease, expected_update_stamp=10)
        create.assert_called_once_with(
            app=f.app,
            document=f.target,
            sketch_feature=f.sketch,
            width_mm=50.0,
            height_mm=35.0,
        )
        f.assert_context_retained(result)
        validate_operation_result("sketch.dimension-rectangle", result)
        self.assertEqual(len(f.entry.dimensions), 3)
        for kind in ("width", "height"):
            binding = f.registry.resolve_dimension(
                f.entry, result["dimensions"][kind]["dimension_id"]
            )
            self.assertIs(binding.dimension, self.handles[kind])
            self.assertEqual((binding.kind, binding.profile_kind), (kind, "rectangle"))

    @mock.patch.object(operations, "create_rectangle_dimensions_windows_with_handles")
    def test_invalid_native_success_and_missing_handles_never_publish_binding(
        self, create
    ):
        f = self.fixture
        invalid = deepcopy(self.native_result)
        invalid["dimensions"]["height"]["value"] = 36
        for result, handles in (
            (invalid, self.handles),
            (self.native_result, {"width": self.handles["width"]}),
        ):
            create.return_value = (deepcopy(result), handles)
            with (
                mock.patch.object(
                    f.registry, "temporarily_activate", side_effect=f.activate
                ),
                self.assertRaises(OperationResultInvalid),
            ):
                self.call(lease_id=f.lease)
            self.assertEqual(len(f.entry.dimensions), 1)
            self.assertIs(f.app.ActiveDoc, f.foreground)

    @mock.patch.object(operations, "create_rectangle_dimensions_windows_with_handles")
    def test_failed_creation_keeps_evidence_but_never_registers_partial_handles(
        self, create
    ):
        f = self.fixture
        result = deepcopy(self.native_result)
        result.update(
            ok=False,
            error={"type": "DimensionCleanupFailed", "message": "partial"},
            modification_may_have_happened=True,
        )
        result["dimensions"]["width"].update(
            dimension_id="m-ab12cd", sketch_id="s-ab12cd"
        )
        create.return_value = (result, self.handles)
        with mock.patch.object(
            f.registry, "temporarily_activate", side_effect=f.activate
        ):
            result = self.call(lease_id=f.lease)
        validate_operation_result("sketch.dimension-rectangle", result)
        self.assertNotIn("dimension_id", result["dimensions"]["width"])
        self.assertEqual(len(f.entry.dimensions), 1)
        self.assertTrue(result["modification_may_have_happened"])
        f.assert_context_retained(result)


if __name__ == "__main__":
    unittest.main()
