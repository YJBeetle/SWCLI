"""Public rectangle discovery publishes only a complete verified live pair."""

from copy import deepcopy
import unittest
from unittest import mock

from swcli.cli import _typed_operation, build_parser
from swcli.daemon import operations
from swcli.daemon.documents import SketchNotFound
from swcli.operation_schemas import OPERATION_CATALOG, validate_operation_request
from swcli.result_schemas import OperationResultInvalid, validate_operation_result
import test_dimension_operations as operation_fixtures
import test_windows_rectangle_dimension_discovery as native_fixtures


class RectangleDiscoveryContractTests(unittest.TestCase):
    def fixture(self):
        fixture = native_fixtures.RectangleDiscoveryTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        return fixture

    @staticmethod
    def wire(result):
        result = deepcopy(result)
        result.update(
            action="dimension.discover-rectangle",
            sketch_id="s-ab12cd",
            document={
                "title": "Part1",
                "path": "",
                "type": 1,
                "modified": False,
                "update_stamp": 10,
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

    def test_read_policy_cli_and_selector_before_position(self):
        spec = OPERATION_CATALOG["dimension.discover-rectangle"]
        self.assertTrue(spec.selected_document)
        self.assertFalse(spec.lease_guarded or spec.temporary_activation)
        args = build_parser().parse_args(
            [
                "--session",
                "observer",
                "dimension",
                "discover-rectangle",
                "--document",
                "d-ab12cd",
                "s-ab12cd",
                "--if-update-stamp",
                "0",
                "--json",
            ]
        )
        self.assertEqual(
            _typed_operation(args),
            (
                "dimension.discover-rectangle",
                {"sketch_id": "s-ab12cd"},
                True,
                "d-ab12cd",
                0,
                None,
            ),
        )
        with self.assertRaises(SystemExit), mock.patch("sys.stderr"):
            build_parser().parse_args(
                [
                    "dimension",
                    "discover-rectangle",
                    "s-ab12cd",
                    "--lease",
                    "l-ab12cd34ef56",
                ]
            )
        for values in (
            {},
            {"sketch_id": "Sketch1"},
            {"sketch_id": "s-ab12cd", "kind": "width"},
        ):
            with self.assertRaises(ValueError):
                validate_operation_request("dimension.discover-rectangle", values)
        with self.assertRaises(ValueError):
            validate_operation_request(
                "dimension.discover-rectangle",
                {"sketch_id": "s-ab12cd"},
                lease_id="l-ab12cd34ef56",
            )

    def test_native_pair_shapes_and_read_only_external_controls_fit_contract(self):
        fixture = self.fixture()
        fixture.parameters["width"].DrivenState = 1
        fixture.parameters["width"].ReadOnly = 1
        fixture.parameters["width"].IsDesignTableDimension = lambda: True
        result, _ = fixture.call()
        result = self.wire(result)
        validate_operation_result("dimension.discover-rectangle", result)
        self.assertTrue(result["inspections"]["width"]["dimension"]["read_only"])
        self.assertNotIn("dimension_id", result["inspections"]["width"]["dimension"])

    def test_pair_snapshot_state_and_geometry_contradictions_never_validate(self):
        result = self.wire(self.fixture().call()[0])
        for kind, field, value in (
            ("width", "kind", "height"),
            ("width", "value", 41),
            ("height", "configuration", "Other"),
            ("height", "sketch_id", "s-ab12ce"),
            ("height", "dimension_id", "m-ab12cd"),
        ):
            invalid = deepcopy(result)
            invalid["dimensions"][kind][field] = value
            with self.subTest(field=field), self.assertRaises(OperationResultInvalid):
                validate_operation_result("dimension.discover-rectangle", invalid)
        for fault in (
            "stamp",
            "center",
            "size",
            "native-value",
            "native-id",
            "state",
            "constraint",
            "empty",
        ):
            invalid = deepcopy(result)
            if fault == "stamp":
                invalid["document"]["update_stamp"] += 1
            elif fault == "center":
                invalid["geometry_verification"]["actual"]["center_mm"]["x"] += 1
            elif fault == "size":
                invalid["geometry_verification"]["expected_height_mm"] += 1
            elif fault == "native-value":
                invalid["inspections"]["height"]["dimension"]["value"] += 1
            elif fault == "native-id":
                invalid["inspections"]["height"]["dimension"][
                    "dimension_id"
                ] = "m-ab12ce"
            elif fault == "state":
                invalid["observation"]["after"]["editing"] = True
            elif fault == "constraint":
                invalid["inspections"]["height"]["constraint_status"] = 2
            else:
                del invalid["inspections"]["height"]
            with self.subTest(fault=fault), self.assertRaises(OperationResultInvalid):
                validate_operation_result("dimension.discover-rectangle", invalid)

    def test_partial_failure_has_diagnostic_evidence_not_wire_handles(self):
        fixture = self.fixture()
        fixture.parameters["height"].value = 0.031
        result = self.wire(fixture.call()[0])
        validate_operation_result("dimension.discover-rectangle", result)
        result["dimensions"]["width"]["dimension_id"] = "m-ab12cd"
        with self.assertRaises(OperationResultInvalid):
            validate_operation_result("dimension.discover-rectangle", result)


class RectangleDiscoveryOperationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = operation_fixtures.DimensionOperationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        native = native_fixtures.RectangleDiscoveryTests()
        native.setUp()
        self.addCleanup(native.doCleanups)
        self.native_result, self.handles = native.call()
        self.values = {"sketch_id": self.fixture.sketch_id}

    def call(self, **context):
        return self.fixture.call("dimension.discover-rectangle", self.values, **context)

    @mock.patch.object(operations, "discover_rectangle_dimensions_windows_with_handles")
    def test_observer_reads_leased_background_and_reuses_exact_pair_without_activation(
        self, discover
    ):
        f = self.fixture
        f.registry.set_current(f.other, session_id="observer")
        discover.side_effect = lambda **kwargs: (
            deepcopy(self.native_result),
            self.handles,
        )
        with mock.patch.object(f.registry, "temporarily_activate") as activate:
            first = self.call(session_id="observer", expected_update_stamp=10)
            second = self.call(session_id="observer", expected_update_stamp=10)
            activate.assert_not_called()
        self.assertEqual(first["dimensions"], second["dimensions"])
        self.assertEqual(len(f.entry.dimensions), 3)
        validate_operation_result("dimension.discover-rectangle", first)
        for kind in ("width", "height"):
            binding = f.registry.resolve_dimension(
                f.entry, first["dimensions"][kind]["dimension_id"]
            )
            self.assertIs(binding.dimension, self.handles[kind])
            self.assertEqual((binding.kind, binding.profile_kind), (kind, "rectangle"))
        self.assertIs(f.app.ActiveDoc, f.foreground)
        self.assertIs(f.registry.resolve(None, session_id="observer"), f.other)

    @mock.patch.object(operations, "discover_rectangle_dimensions_windows_with_handles")
    def test_target_and_stamp_guards_precede_native_reads(self, discover):
        for context, error in (
            ({"expected_update_stamp": 9}, operations.DocumentUpdateConflict),
            ({"document_id": self.fixture.other.document_id}, SketchNotFound),
        ):
            with self.subTest(context=context), self.assertRaises(error):
                self.call(**context)
        discover.assert_not_called()

    @mock.patch.object(operations, "discover_rectangle_dimensions_windows_with_handles")
    def test_unverified_partial_or_missing_handles_never_enter_registry(self, discover):
        failed = deepcopy(self.native_result)
        failed.update(
            ok=False,
            error={"type": "DimensionObservationUnavailable", "message": "partial"},
        )
        discover.return_value = (failed, self.handles)
        result = self.call()
        validate_operation_result("dimension.discover-rectangle", result)
        self.assertEqual(len(self.fixture.entry.dimensions), 1)
        invalid = deepcopy(self.native_result)
        invalid["dimensions"]["width"]["value"] += 1
        for result, handles in (
            (invalid, self.handles),
            (self.native_result, {"width": self.handles["width"]}),
        ):
            discover.return_value = (deepcopy(result), handles)
            with self.assertRaises(OperationResultInvalid):
                self.call()
            self.assertEqual(len(self.fixture.entry.dimensions), 1)


if __name__ == "__main__":
    unittest.main()
