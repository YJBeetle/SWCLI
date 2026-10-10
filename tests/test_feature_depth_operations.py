"""Typed depth writes retain target, lease/stamp, cleanup and result evidence."""

import contextlib
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest import mock

from jsonschema import Draft202012Validator

from swcli.cli import _typed_operation, build_parser
from swcli.daemon.documents import (
    DocumentRegistry,
    DocumentLeaseConflict,
    FeatureNotFound,
)
from swcli.daemon.feature_depth_results import feature_depth_result
from swcli.daemon.operations import DocumentUpdateConflict, execute_operation
from swcli.operation_schemas import OPERATION_CATALOG, validate_operation_request
from swcli.result_schemas import (
    OperationResultInvalid,
    operation_result_schema,
    validate_operation_result,
)
from test_feature_observation_operations import Document, Feature


def state(stamp, modified):
    return {
        "configuration": "Default",
        "update_stamp": stamp,
        "modified": modified,
        "editing": False,
        "foreground_present": True,
    }


def check(before, after):
    return {
        "ok": True,
        "selection_access": {
            key: True
            for key in (
                "attempted",
                "acquired",
                "release_attempted",
                "released",
                "state_restored",
            )
        },
        "observation": {
            "before": before,
            "after": after,
            "update_stamp_changed": before["update_stamp"] != after["update_stamp"],
        },
    }


def native_result(changed=True):
    before, ready = state(7, False), state(9, False)
    committed, final = state(10, True), state(12, True)
    definition = {
        "depth_mm": 25 if changed else 20,
        "end_condition": 0,
        "reverse_direction": False,
        "both_directions": False,
        "thin": False,
        "from_type": 0,
        "forward_draft": False,
        "reverse_draft": False,
        "merge": True,
    }
    metrics = lambda volume: {
        "solid_body_count": 1,
        "volume_mm3": volume,
        "surface_area_mm2": 16000,
        "centroid_mm": {"x": 10, "y": 20, "z": 10},
    }
    result = {
        "ok": True,
        "action": "feature.set-depth",
        "feature": {
            "name": "Boss",
            "type": "Extrusion",
            "native_type": "Extrusion",
            "kind": "boss-extrude",
        },
        "mutation": {
            key: changed
            for key in (
                "staging_attempted",
                "configuration_scope_applied",
                "commit_attempted",
                "committed",
            )
        },
        "requested_depth_mm": 25 if changed else 20,
        "before_depth_mm": 20,
        "depth_changed": changed,
        "definition_after": definition,
        "measurement_before": metrics(100000),
        "measurement_after": metrics(125000 if changed else 100000),
        "verification": {
            "passed": True,
            "method": (
                "native-blind-depth-preserved-profile-and-scope"
                if changed
                else "guarded-equal-depth"
            ),
            "absolute_tolerance_mm": 1e-6,
        },
        "final_state": final if changed else ready,
        "preflight": {
            **check(before, ready),
            "controls": {"private": object()},
            "profile": {"native": object()},
        },
    }
    if changed:
        result.update(rebuilt=True, postflight=check(committed, final))
    return result


def wire_result(changed=True):
    result = feature_depth_result(native_result(changed), "f-ab12cd")
    result["document"] = {
        "title": "A",
        "path": "",
        "type": 1,
        "modified": result["final_state"]["modified"],
        "update_stamp": result["final_state"]["update_stamp"],
    }
    return result


class FeatureDepthContractTests(unittest.TestCase):
    def test_schema_and_runtime_accept_changed_and_equal_depth(self):
        validator = Draft202012Validator(operation_result_schema("feature.set-depth"))
        for changed in (True, False):
            result = wire_result(changed)
            validator.validate(result)
            validate_operation_result("feature.set-depth", result)

    def test_projection_retains_failure_and_cleanup_without_private_pointers(self):
        native = native_result()
        native.update(
            ok=False,
            error={
                "type": "FeatureSelectionStateNotRestored",
                "message": "first failure",
            },
            modification_may_have_happened=True,
        )
        native["postflight"].update(
            ok=False,
            error=native["error"],
            warnings=[{"code": "release-error", "message": "cleanup failure"}],
        )
        native["postflight"]["selection_access"].update(
            released=False, state_restored=False
        )
        result = feature_depth_result(native, "f-ab12cd")
        validate_operation_result("feature.set-depth", result)
        self.assertEqual(result["error"], native["error"])
        self.assertEqual(
            result["selection_checks"]["postflight"]["warnings"],
            native["postflight"]["warnings"],
        )
        self.assertNotIn("profile", result["selection_checks"]["preflight"])
        self.assertNotIn("controls", result["selection_checks"]["preflight"])
        result["feature"]["name"] = "wire change"
        self.assertEqual(native["feature"]["name"], "Boss")

    def test_refusal_before_selection_access_has_small_valid_result(self):
        native = {
            "ok": False,
            "action": "feature.set-depth",
            "mutation": {key: False for key in native_result()["mutation"]},
            "error": {"type": "DocumentNotWritable", "message": "read-only part"},
            "modification_may_have_happened": False,
            "preflight": {
                "ok": False,
                "selection_access": {
                    key: False
                    for key in check(state(0, False), state(0, False))[
                        "selection_access"
                    ]
                },
                "error": {"type": "DocumentNotWritable", "message": "read-only part"},
            },
        }
        validate_operation_result(
            "feature.set-depth", feature_depth_result(native, "f-ab12cd")
        )

    def test_schema_rejects_missing_success_evidence_and_unknown_nested_fields(self):
        good = wire_result()
        for field in (
            "feature_id",
            "feature",
            "mutation",
            "document",
            "selection_checks",
            "final_state",
            "verification",
            "measurement_after",
            "before_depth_mm",
        ):
            invalid = deepcopy(good)
            del invalid[field]
            with self.subTest(field=field), self.assertRaises(OperationResultInvalid):
                validate_operation_result("feature.set-depth", invalid)
        invalid = deepcopy(good)
        invalid["selection_checks"]["preflight"]["private"] = True
        with self.assertRaises(OperationResultInvalid):
            validate_operation_result("feature.set-depth", invalid)

    def test_success_semantics_refuse_mutation_scope_target_or_state_drift(self):
        for path, value in (
            (("feature", "feature_id"), "f-zzzzzz"),
            (("mutation", "commit_attempted"), False),
            (("mutation", "committed"), False),
            (("rebuilt",), False),
            (("verification", "passed"), False),
            (("definition_after", "depth_mm"), 24),
            (("definition_after", "both_directions"), True),
            (("definition_after", "merge"), False),
            (("final_state", "update_stamp"), 13),
            (("document", "modified"), False),
            (("document", "update_stamp"), 13),
            (("selection_checks", "postflight", "ok"), False),
            (("selection_checks", "postflight", "selection_access", "released"), False),
            (
                (
                    "selection_checks",
                    "preflight",
                    "observation",
                    "update_stamp_changed",
                ),
                False,
            ),
        ):
            invalid = wire_result()
            target = invalid
            for component in path[:-1]:
                target = target[component]
            target[path[-1]] = value
            with self.subTest(path=path), self.assertRaises(OperationResultInvalid):
                validate_operation_result("feature.set-depth", invalid)

    def test_equal_depth_cannot_hide_setter_rebuild_or_geometry_changes(self):
        for field, value in (
            ("rebuilt", True),
            ("requested_depth_mm", 21),
            ("measurement_after", wire_result()["measurement_after"]),
        ):
            invalid = wire_result(False)
            invalid[field] = value
            with self.subTest(field=field), self.assertRaises(OperationResultInvalid):
                validate_operation_result("feature.set-depth", invalid)

    def test_incomplete_failed_selection_stamp_is_structured_contract_failure(self):
        result = wire_result()
        result.update(
            ok=False, error={"type": "ModelInvalid", "message": "partial failure"}
        )
        del result["selection_checks"]["postflight"]["observation"][
            "update_stamp_changed"
        ]
        with self.assertRaises(OperationResultInvalid):
            validate_operation_result("feature.set-depth", result)

    def test_request_and_cli_preserve_exact_write_context(self):
        spec = OPERATION_CATALOG["feature.set-depth"]
        self.assertTrue(
            spec.lease_guarded and spec.temporary_activation and spec.selected_document
        )
        args = build_parser().parse_args(
            [
                "--session",
                "writer",
                "feature",
                "set-depth",
                "f-ab12cd",
                "--depth-mm",
                "25",
                "--document",
                "d-ab12cd",
                "--if-update-stamp",
                "7",
                "--lease",
                "l-ab12cd34ef56",
                "--json",
            ]
        )
        self.assertEqual(
            _typed_operation(args),
            (
                "feature.set-depth",
                {"feature_id": "f-ab12cd", "depth_mm": 25},
                True,
                "d-ab12cd",
                7,
                "l-ab12cd34ef56",
            ),
        )
        for depth in (0, -1, 2e-6, True, float("nan"), float("inf"), "25"):
            with self.subTest(depth=depth), self.assertRaises(ValueError):
                validate_operation_request(
                    "feature.set-depth", {"feature_id": "f-ab12cd", "depth_mm": depth}
                )


class FeatureDepthDispatchTests(unittest.TestCase):
    def setUp(self):
        self.document, self.other = Document("A"), Document("B")
        self.document.GetUpdateStamp = lambda: 12
        self.document.GetSaveFlag = lambda: True
        self.feature = Feature(1, "Extrusion")
        self.document.features = self.feature
        self.app = SimpleNamespace(
            ActiveDoc=self.other,
            GetDocuments=lambda: (self.document, self.other),
            IsSame=lambda a, b: int(a.identity is b.identity),
        )
        self.registry = DocumentRegistry(self.app)
        self.entry = self.registry.register(self.document)
        self.other_entry = self.registry.register(self.other)
        self.registry.set_current(self.other_entry, session_id="writer")
        self.feature_id = self.registry.register_feature(self.entry, self.feature)
        self.lease = self.registry.acquire_lease(
            self.entry, session_id="writer", ttl_seconds=60
        )["lease_id"]
        self.activation_count = 0

        @contextlib.contextmanager
        def activate(entry):
            self.assertIs(entry, self.entry)
            self.activation_count += 1
            self.app.ActiveDoc = self.document
            try:
                yield []
            finally:
                self.app.ActiveDoc = self.other

        self.activation = mock.patch.object(
            self.registry, "temporarily_activate", side_effect=activate
        )
        self.activation.start()
        self.addCleanup(self.activation.stop)
        self.adapter = mock.patch(
            "swcli.hosts.windows_feature_depth_edits.set_extrusion_depth_windows",
            return_value=native_result(),
        )
        self.writer = self.adapter.start()
        self.addCleanup(self.adapter.stop)

    def call(self, **context):
        options = {
            "document_id": self.entry.document_id,
            "session_id": "writer",
            "lease_id": self.lease,
        }
        options.update(context)
        return execute_operation(
            self.app,
            "feature.set-depth",
            {"feature_id": self.feature_id, "depth_mm": 25},
            documents=self.registry,
            **options,
        )

    def test_background_write_uses_exact_object_and_restores_foreground_and_session(
        self,
    ):
        def adapter(**kwargs):
            self.assertIs(self.app.ActiveDoc, self.document)
            return native_result()

        self.writer.side_effect = adapter
        result = self.call(expected_update_stamp=12)
        validate_operation_result("feature.set-depth", result)
        self.writer.assert_called_once_with(
            app=self.app, document=self.document, feature=self.feature, depth_mm=25
        )
        self.assertEqual(result["feature_id"], self.feature_id)
        self.assertEqual(result["feature"]["feature_id"], self.feature_id)
        self.assertFalse(result["document"]["active"] or result["document"]["current"])
        self.assertIs(self.app.ActiveDoc, self.other)
        self.assertIs(
            self.registry.resolve(None, session_id="writer"), self.other_entry
        )

    def test_lease_and_stamp_refusals_precede_activation_and_native_mutation(self):
        for context, exception in (
            ({"lease_id": None}, DocumentLeaseConflict),
            ({"session_id": "intruder"}, DocumentLeaseConflict),
            ({"expected_update_stamp": 11}, DocumentUpdateConflict),
        ):
            with self.subTest(context=context), self.assertRaises(exception):
                self.call(**context)
        self.writer.assert_not_called()
        self.assertEqual(self.activation_count, 0)

    def test_unknown_or_cross_document_feature_precedes_activation(self):
        self.registry.release_lease(self.lease, session_id="writer")
        self.feature_id = "f-zzzzzz"
        with self.assertRaises(FeatureNotFound):
            self.call(lease_id=None)
        self.assertEqual(self.activation_count, 0)
        self.writer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
