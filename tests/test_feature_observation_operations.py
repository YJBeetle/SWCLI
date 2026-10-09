"""Public feature reads bind exact native objects without becoming edit authority."""

import contextlib
from copy import deepcopy
import io
from types import SimpleNamespace
import unittest
from unittest import mock

from jsonschema import Draft202012Validator

from swcli.cli import _typed_operation, build_parser
from swcli.daemon.documents import DocumentRegistry, FeatureNotFound
from swcli.daemon.operations import DocumentUpdateConflict, execute_operation
from swcli.operation_schemas import OPERATION_CATALOG, validate_operation_request
from swcli.result_schemas import OperationResultInvalid, validate_operation_result


class Feature:
    def __init__(self, native_id, kind, *, identity=None):
        self.identity = object() if identity is None else identity
        self.native_id = native_id
        self.kind = kind
        self.Name = "native feature"
        self.next = None
        self.definition = SimpleNamespace(
            GetDepth=lambda direction: 0.02,
            GetEndCondition=lambda direction: 0,
            ReverseDirection=False,
            BothDirections=False,
            IsThinFeature=lambda: False,
            FromType=0,
            GetDraftWhileExtruding=lambda direction: False,
            Merge=True,
            FeatureScope=True,
        )

    def GetID(self):
        return self.native_id

    def GetTypeName2(self):
        return self.kind

    def GetDefinition(self):
        return self.definition

    def GetNextFeature(self):
        return self.next

    def GetFirstSubFeature(self):
        return None

    def GetNextSubFeature(self):
        return None


class Document:
    def __init__(self, title):
        self.identity = object()
        self.title = title
        self.features = None
        self.ConfigurationManager = SimpleNamespace(
            ActiveConfiguration=SimpleNamespace(Name="Default")
        )
        self.SketchManager = SimpleNamespace(ActiveSketch=None)

    def GetTitle(self):
        return self.title

    def GetPathName(self):
        return ""

    def GetType(self):
        return 1

    def GetSaveFlag(self):
        return False

    def GetUpdateStamp(self):
        return 0

    def FirstFeature(self):
        return self.features


class FeatureObservationOperationTests(unittest.TestCase):
    def setUp(self):
        self.document, self.other = Document("A"), Document("B")
        self.boss, self.cut = Feature(1, "Extrusion"), Feature(2, "Cut")
        self.boss.next = self.cut
        self.document.features = self.boss
        self.app = SimpleNamespace(
            ActiveDoc=self.other,
            GetDocuments=lambda: (self.document, self.other),
            IsSame=lambda a, b: int(a.identity is b.identity),
            ActivateDoc3=mock.Mock(),
        )
        self.registry = DocumentRegistry(self.app)
        self.entry = self.registry.register(self.document)
        self.other_entry = self.registry.register(self.other)
        self.registry.set_current(self.other_entry, session_id="reader")
        self.registry.acquire_lease(self.entry, session_id="writer", ttl_seconds=60)

    def call(self, operation="feature.list", parameters=None, **context):
        return execute_operation(
            self.app,
            operation,
            {} if parameters is None else parameters,
            documents=self.registry,
            session_id="reader",
            document_id=self.entry.document_id,
            **context,
        )

    def test_complete_background_read_ignores_write_lease_and_retains_session_current(
        self,
    ):
        with mock.patch.object(self.registry, "temporarily_activate") as activate:
            result = self.call(expected_update_stamp=0)
        validate_operation_result("feature.list", result)
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["scope"], "part-extrusions")
        self.assertFalse(result["document"]["active"] or result["document"]["current"])
        for descriptor, native in zip(result["features"], (self.boss, self.cut)):
            self.assertIs(
                self.registry.resolve_feature(self.entry, descriptor["feature_id"]),
                native,
            )
        activate.assert_not_called()
        self.app.ActivateDoc3.assert_not_called()
        self.assertIs(self.app.ActiveDoc, self.other)
        self.assertIs(
            self.registry.resolve(None, session_id="reader"), self.other_entry
        )

    def test_inspect_uses_exact_registered_object_with_native_definition(self):
        listed = self.call()
        for descriptor in listed["features"]:
            feature_id = descriptor["feature_id"]
            result = self.call("feature.inspect", {"feature_id": feature_id})
            validate_operation_result("feature.inspect", result)
            self.assertEqual(result["feature"], descriptor)
            self.assertEqual(result["definition"]["depth_mm"], 20)
            self.assertEqual(
                "feature_scope" in result["definition"],
                descriptor["kind"] == "cut-extrude",
            )
            self.assertTrue(result["observation"]["unchanged"])
        self.app.ActivateDoc3.assert_not_called()

    def test_repeat_and_renamed_wrappers_reuse_exact_live_ids(self):
        first = self.call()
        replacement = Feature(1, "Extrusion", identity=self.boss.identity)
        replacement.Name = "renamed"
        replacement.next = self.cut
        self.document.features = replacement
        second = self.call()
        self.assertEqual(
            [f["feature_id"] for f in first["features"]],
            [f["feature_id"] for f in second["features"]],
        )
        self.assertEqual(second["features"][0]["name"], "renamed")
        self.assertEqual(len(self.entry.features), 2)

    def test_unknown_closed_and_cross_document_handles_fail_before_native_inspection(
        self,
    ):
        feature_id = self.call()["features"][0]["feature_id"]
        with mock.patch(
            "swcli.hosts.windows_feature_inspection.inspect_extrusion_feature_windows"
        ) as inspect:
            for value in ("f-zzzzzz",):
                with self.assertRaises(FeatureNotFound):
                    self.call("feature.inspect", {"feature_id": value})
            with self.assertRaises(FeatureNotFound):
                execute_operation(
                    self.app,
                    "feature.inspect",
                    {"feature_id": feature_id},
                    documents=self.registry,
                    document_id=self.other_entry.document_id,
                )
            self.registry.forget(self.entry.document_id)
            self.entry = self.registry.register(self.document)
            with self.assertRaises(FeatureNotFound):
                self.call("feature.inspect", {"feature_id": feature_id})
        inspect.assert_not_called()

    def test_stale_update_stamp_and_request_errors_do_not_observe_or_register(self):
        with mock.patch(
            "swcli.hosts.windows_feature_inspection.list_extrusion_features_windows_with_handles"
        ) as observe:
            with self.assertRaises(DocumentUpdateConflict):
                self.call(expected_update_stamp=1)
            for parameters in (
                {"max_features": 0},
                {"max_features": True},
                {"max_features": 1.5},
            ):
                with self.subTest(parameters=parameters), self.assertRaises(ValueError):
                    self.call(parameters=parameters)
        observe.assert_not_called()
        self.assertEqual(self.entry.features, {})

    def test_incomplete_or_invalid_adapter_payload_never_registers_handles(self):
        good = self.call()
        self.entry.features.clear()
        self.entry.feature_ids_by_native_id.clear()
        for feature in good["features"]:
            del feature["feature_id"]
        for mutate in (
            lambda r: r.update(count=1),
            lambda r: r["observation"].update(unchanged=False),
            lambda r: r["observation"]["after"].update(update_stamp=1),
            lambda r: r["features"][0].update(kind="cut-extrude"),
            lambda r: r["features"][0].update(name=" "),
            lambda r: r["features"][0].update(feature_id="f-ab12cd"),
        ):
            invalid = deepcopy(good)
            mutate(invalid)
            with (
                mock.patch(
                    "swcli.hosts.windows_feature_inspection.list_extrusion_features_windows_with_handles",
                    return_value=(invalid, [self.boss, self.cut]),
                ),
                self.assertRaises(OperationResultInvalid),
            ):
                self.call()
            self.assertEqual(self.entry.features, {})

    def test_missing_or_mismatched_exact_adapter_handles_never_registers(self):
        good = self.call()
        self.entry.features.clear()
        self.entry.feature_ids_by_native_id.clear()
        for descriptor in good["features"]:
            del descriptor["feature_id"]
        for handles in ([self.boss], [self.boss, None]):
            with (
                mock.patch(
                    "swcli.hosts.windows_feature_inspection.list_extrusion_features_windows_with_handles",
                    return_value=(deepcopy(good), handles),
                ),
                self.assertRaises(OperationResultInvalid),
            ):
                self.call()
            self.assertEqual(self.entry.features, {})

    def test_empty_supported_scope_is_valid_and_failed_reads_expose_no_payload(self):
        self.document.features = None
        result = self.call()
        validate_operation_result("feature.list", result)
        self.assertEqual(result["features"], [])
        self.document.GetUpdateStamp = lambda: None
        failure = self.call()
        validate_operation_result("feature.list", failure)
        self.assertFalse(failure["ok"])
        self.assertNotIn("features", failure)
        self.assertEqual(self.entry.features, {})

    def test_public_results_reject_wrong_depth_state_and_branch_semantics(self):
        feature_id = self.call()["features"][0]["feature_id"]
        good = self.call("feature.inspect", {"feature_id": feature_id})
        for mutate in (
            lambda r: r["definition"].update(depth_mm=float("nan")),
            lambda r: r["definition"].update(depth_mm=-1),
            lambda r: r["definition"].update(reverse_direction=1),
            lambda r: r["observation"].pop("after"),
            lambda r: r["observation"].update(unchanged=False),
            lambda r: r["document"].update(modified=True),
            lambda r: r["feature"].update(
                native_type="Cut", kind="cut-extrude", type="Cut"
            ),
            lambda r: r["feature"].pop("feature_id"),
        ):
            invalid = deepcopy(good)
            mutate(invalid)
            with (
                self.subTest(invalid=invalid),
                self.assertRaises(OperationResultInvalid),
            ):
                validate_operation_result("feature.inspect", invalid)
        failed = {
            "ok": False,
            "action": "feature.inspect",
            "error": {"type": "FeatureUnavailable", "message": "absent"},
            "feature": good["feature"],
        }
        with self.assertRaises(OperationResultInvalid):
            validate_operation_result("feature.inspect", failed)

    def test_public_request_schema_and_policy_are_read_only(self):
        for operation, parameters in (
            ("feature.list", {"max_features": 12}),
            ("feature.inspect", {"feature_id": "f-ab12cd"}),
        ):
            spec = OPERATION_CATALOG[operation]
            Draft202012Validator.check_schema(spec.parameters)
            Draft202012Validator.check_schema(spec.result)
            self.assertTrue(spec.selected_document)
            self.assertFalse(spec.lease_guarded or spec.temporary_activation)
            self.assertEqual(
                validate_operation_request(
                    operation,
                    parameters,
                    document_id="active",
                    expected_update_stamp=0,
                ),
                parameters,
            )
            with self.assertRaises(ValueError):
                validate_operation_request(
                    operation, parameters, lease_id="l-ab12cd34ef56"
                )
        for values in (
            {},
            {"feature_id": "Boss1"},
            {"feature_id": "s-ab12cd"},
            {"feature_id": "f-ab12cd", "depth_mm": 10},
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                validate_operation_request("feature.inspect", values)

    def test_cli_maps_read_context_without_lease_or_edit_options(self):
        parser = build_parser()
        for words, operation, values in (
            (
                ["feature", "list", "--max-features", "12"],
                "feature.list",
                {"max_features": 12},
            ),
            (
                ["feature", "inspect", "f-ab12cd"],
                "feature.inspect",
                {"feature_id": "f-ab12cd"},
            ),
        ):
            args = parser.parse_args(
                [
                    "--session",
                    "reader",
                    *words,
                    "--document",
                    "d-ab12cd",
                    "--if-update-stamp",
                    "0",
                    "--json",
                ]
            )
            self.assertEqual(args.session, "reader")
            self.assertEqual(
                _typed_operation(args), (operation, values, True, "d-ab12cd", 0, None)
            )
            for extra in (["--lease", "l-ab12cd34ef56"], ["--depth-mm", "10"]):
                with (
                    contextlib.redirect_stderr(io.StringIO()),
                    self.assertRaises(SystemExit),
                ):
                    parser.parse_args([*words, *extra])
        self.assertEqual(
            _typed_operation(parser.parse_args(["feature", "list"])),
            ("feature.list", {"max_features": 1000}, False, None, None, None),
        )


if __name__ == "__main__":
    unittest.main()
