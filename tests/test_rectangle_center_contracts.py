"""Typed fixed-center contracts, exact targeting and native failure evidence."""

from contextlib import contextmanager
from copy import deepcopy
import unittest
from types import SimpleNamespace
from unittest import mock

from jsonschema import Draft202012Validator

from swcli.cli import _typed_operation, build_parser
from swcli.daemon import operations
from swcli.daemon.documents import (
    DocumentLeaseConflict,
    DocumentRegistry,
    SketchNotFound,
)
from swcli.operation_schemas import OPERATION_CATALOG, validate_operation_request
from swcli.result_schemas import OperationResultInvalid, validate_operation_result
import test_daemon as daemon_fixtures
import test_windows_rectangle_constraints as native_fixtures


class CenterFixContractTests(unittest.TestCase):
    def native_fixture(self):
        fixture = native_fixtures.RectangleCenterFixTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        return fixture

    @staticmethod
    def wire(result):
        return {
            **result,
            "action": "sketch.fix-center",
            "sketch_id": "s-ab12cd",
            "document": {
                "title": "Part1",
                "path": "",
                "type": 1,
                "modified": True,
                "update_stamp": 18,
                "document_id": "d-ab12cd",
                "current": False,
                "active": False,
            },
        }

    def test_catalog_and_cli_require_only_sketch_and_explicit_write_context(self):
        spec = OPERATION_CATALOG["sketch.fix-center"]
        self.assertEqual(spec.handler, "sketch_fix_center")
        self.assertTrue(spec.selected_document)
        self.assertTrue(spec.lease_guarded)
        self.assertTrue(spec.temporary_activation)
        self.assertEqual(
            spec.parameters["x-swcli-context"],
            {
                "document_id": "optional",
                "expected_update_stamp": "optional",
                "lease_id": "optional",
            },
        )
        parameters = {"sketch_id": "s-ab12cd"}
        self.assertEqual(
            validate_operation_request(
                "sketch.fix-center",
                parameters,
                document_id="d-ab12cd",
                expected_update_stamp=0,
                lease_id="l-ab12cd34ef56",
            ),
            parameters,
        )
        args = build_parser().parse_args(
            [
                "--session",
                "writer",
                "sketch",
                "fix-center",
                "--document",
                "d-ab12cd",
                "s-ab12cd",
                "--if-update-stamp",
                "0",
                "--lease",
                "l-ab12cd34ef56",
                "--json",
            ]
        )
        self.assertEqual(args.session, "writer")
        self.assertEqual(
            _typed_operation(args),
            (
                "sketch.fix-center",
                parameters,
                True,
                "d-ab12cd",
                0,
                "l-ab12cd34ef56",
            ),
        )
        self.assertEqual(
            _typed_operation(
                build_parser().parse_args(
                    [
                        "sketch",
                        "fix-center",
                        "s-ab12cd",
                        "--json",
                    ]
                )
            ),
            ("sketch.fix-center", parameters, True, None, None, None),
        )

    def test_no_guessed_names_coordinates_or_implicit_size_options(self):
        validator = Draft202012Validator(
            OPERATION_CATALOG["sketch.fix-center"].parameters
        )
        for parameters in (
            {},
            {"sketch_id": None},
            {"sketch_id": "Sketch1"},
            {"sketch_id": "s-ab12cd", "point_id": [0, 1]},
            {"sketch_id": "s-ab12cd", "center_x_mm": 3},
            {"sketch_id": "s-ab12cd", "width_mm": 40},
        ):
            with self.subTest(parameters=parameters):
                self.assertFalse(validator.is_valid(parameters))
                with self.assertRaises(ValueError):
                    validate_operation_request("sketch.fix-center", parameters)

    def test_native_creation_and_read_only_noop_fit_the_advertised_schema(self):
        fixture = self.native_fixture()
        result, relation = fixture.call()
        self.assertIs(relation, fixture.created)
        validate_operation_result("sketch.fix-center", self.wire(result))
        result, same_relation = fixture.call()
        self.assertIs(same_relation, relation)
        self.assertFalse(result["created"])
        validate_operation_result("sketch.fix-center", self.wire(result))
        fixture.native_manager.AddRelation.assert_called_once()

    def test_success_requires_complete_native_identity_geometry_and_closed_edit(self):
        fixture = self.native_fixture()
        result = self.wire(fixture.call()[0])
        for field in OPERATION_CATALOG["sketch.fix-center"].result["then"]["required"]:
            invalid = deepcopy(result)
            del invalid[field]
            with self.subTest(missing=field), self.assertRaises(OperationResultInvalid):
                validate_operation_result("sketch.fix-center", invalid)
        for parent, field, value in (
            (None, "editing", True),
            (None, "modification_may_have_happened", True),
            ("center", "fixed", False),
            ("center_before", "fixed", True),
            ("center", "attached_to_both_diagonals", False),
            ("center", "identity_scope", "persistent"),
            ("center", "native_diagonal_ids", [[5, 6], [5, 6]]),
            ("center", "native_point_id", [True, 1]),
            ("geometry_verification", "passed", False),
            ("geometry_verification", "center_preserved", False),
            ("geometry_verification", "size_matched", False),
        ):
            invalid = deepcopy(result)
            (invalid if parent is None else invalid[parent])[field] = value
            with (
                self.subTest(parent=parent, field=field),
                self.assertRaises(OperationResultInvalid),
            ):
                validate_operation_result("sketch.fix-center", invalid)
        invalid = deepcopy(result)
        del invalid["center_in_edit"]
        with self.assertRaises(OperationResultInvalid):
            validate_operation_result("sketch.fix-center", invalid)

    def test_matching_claims_cannot_hide_actual_center_or_size_drift(self):
        fixture = self.native_fixture()
        result = self.wire(fixture.call()[0])
        for field, value in (("width_mm", 50), ("center_mm", {"x": 4, "y": 4, "z": 0})):
            invalid = deepcopy(result)
            for center in ("center", "center_in_edit"):
                invalid[center]["geometry"][field] = value
            invalid["geometry_verification"]["actual"][field] = value
            with self.subTest(field=field), self.assertRaises(OperationResultInvalid):
                validate_operation_result("sketch.fix-center", invalid)

    def test_success_refuses_cross_field_identity_or_geometry_drift(self):
        fixture = self.native_fixture()
        result = self.wire(fixture.call()[0])
        for parent, field, value in (
            ("center", "native_point_id", [0, 2]),
            ("center_in_edit", "native_point_id", [0, 2]),
            ("geometry_verification", "expected_width_mm", 50),
            ("geometry_verification", "expected_center_mm", {"x": 4, "y": 4, "z": 0}),
        ):
            invalid = deepcopy(result)
            invalid[parent][field] = value
            with (
                self.subTest(parent=parent, field=field),
                self.assertRaises(OperationResultInvalid),
            ):
                validate_operation_result("sketch.fix-center", invalid)
        invalid = deepcopy(result)
        invalid["center"]["geometry"]["width_mm"] = 50
        with self.assertRaises(OperationResultInvalid):
            validate_operation_result("sketch.fix-center", invalid)

    def test_partial_failure_remains_error_with_mutation_and_cleanup_evidence(self):
        fixture = self.native_fixture()

        def failed(*args):
            fixture.relations.append(fixture.created)
            raise RuntimeError("native failed after mutation")

        fixture.native_manager.AddRelation.side_effect = failed
        fixture.manager.InsertSketch.side_effect = RuntimeError("cleanup failed")
        result, relation = fixture.call()
        self.assertIsNone(relation)
        self.assertFalse(result["ok"])
        self.assertTrue(result["modification_may_have_happened"])
        self.assertEqual(result["error"]["message"], "native failed after mutation")
        self.assertEqual(result["warnings"][0]["code"], "sketch-edit-cleanup-failed")
        validate_operation_result("sketch.fix-center", self.wire(result))

    @mock.patch("swcli.daemon.operations.fix_rectangle_center_windows_with_handle")
    def test_document_local_stale_stamp_and_lease_guards_precede_activation(self, fix):
        target = daemon_fixtures.DaemonProtocolTests.FakeDocument("Part1", "")
        target.GetUpdateStamp = lambda: 0
        foreground = daemon_fixtures.DaemonProtocolTests.FakeDocument("Part2", "")
        app = daemon_fixtures.DaemonProtocolTests.FakeApp(
            [target, foreground], active=foreground
        )
        registry = DocumentRegistry(app)
        entry = registry.register(target)
        other = registry.register(foreground)
        registry.set_current(other, session_id="writer")
        feature = SimpleNamespace(GetID=lambda: 17)
        sketch_id = registry.register_sketch(entry, feature)
        lease = registry.acquire_lease(entry, session_id="writer", ttl_seconds=60)[
            "lease_id"
        ]

        def call(**kwargs):
            return operations.execute_operation(
                app,
                "sketch.fix-center",
                {"sketch_id": sketch_id},
                documents=registry,
                **{"document_id": entry.document_id, "session_id": "writer", **kwargs},
            )

        with mock.patch.object(registry, "temporarily_activate") as activate:
            for kwargs, error in (
                ({"session_id": "contender"}, DocumentLeaseConflict),
                (
                    {"lease_id": lease, "expected_update_stamp": 1},
                    operations.DocumentUpdateConflict,
                ),
                ({"document_id": other.document_id}, SketchNotFound),
            ):
                with self.subTest(kwargs=kwargs), self.assertRaises(error):
                    call(**kwargs)
            fix.assert_not_called()
            activate.assert_not_called()

        @contextmanager
        def temporary(selected):
            self.assertIs(selected, entry)
            app.ActiveDoc = target
            try:
                yield []
            finally:
                app.ActiveDoc = foreground

        fix.return_value = ({"ok": True, "action": "sketch.center.fix"}, object())
        with mock.patch.object(registry, "temporarily_activate", side_effect=temporary):
            result = call(lease_id=lease, expected_update_stamp=0)
        fix.assert_called_once_with(app=app, document=target, sketch_feature=feature)
        self.assertEqual(result["action"], "sketch.fix-center")
        self.assertEqual(result["sketch_id"], sketch_id)
        self.assertFalse(result["document"]["current"])
        self.assertFalse(result["document"]["active"])
        self.assertIs(registry.resolve(None, session_id="writer"), other)
        fix.return_value = ({"ok": True, "action": "sketch.center.fix"}, None)
        with (
            mock.patch.object(registry, "temporarily_activate", side_effect=temporary),
            self.assertRaisesRegex(OperationResultInvalid, "no fixed relation"),
        ):
            call(lease_id=lease)
        registry.forget(entry.document_id)
        with self.assertRaises(SketchNotFound):
            registry.resolve_sketch(entry, sketch_id)


if __name__ == "__main__":
    unittest.main()
