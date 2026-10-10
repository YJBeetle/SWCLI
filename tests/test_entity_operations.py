"""Typed face reads preserve background/current state and never rebind stale IDs."""

from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest import mock

from jsonschema import Draft202012Validator

from swcli.cli import build_parser, _typed_operation
from swcli.daemon.documents import DocumentRegistry
from swcli.daemon.entities import (
    EntityNotFound,
    EntityReferenceStale,
    EntityBindingConflict,
)
from swcli.daemon.operations import execute_operation, DocumentUpdateConflict
from swcli.hosts.windows_entity_observation import FaceBinding
from swcli.operation_schemas import OPERATION_CATALOG, validate_operation_request
from swcli.result_schemas import OperationResultInvalid, validate_operation_result

from test_entity_result_schemas import face_result


class EntityOperationTests(unittest.TestCase):
    def setUp(self):
        self.doc = self.document("A")
        self.other = self.document("B")
        self.app = SimpleNamespace(
            ActiveDoc=self.other,
            GetDocuments=lambda: (self.doc, self.other),
            IsSame=lambda a, b: int(a is b),
            ActivateDoc3=mock.Mock(),
        )
        self.registry = DocumentRegistry(self.app)
        self.entry = self.registry.register(self.doc)
        self.other_entry = self.registry.register(self.other)
        self.registry.set_current(self.other_entry, session_id="reader")
        self.registry.acquire_lease(self.entry, session_id="writer", ttl_seconds=60)
        self.bindings = [FaceBinding(object(), object(), b"private-reference")]
        self.native = face_result(public=False)
        self.native.pop("document")
        self.native.pop("scope")
        self.native["action"] = "entity.observe-faces"
        self.native["faces"] = self.native.pop("entities")
        self.observer_patch = mock.patch(
            "swcli.hosts.windows_entity_observation.observe_part_faces_with_handles",
            side_effect=lambda *args, **kwargs: (
                deepcopy(self.native),
                self.bindings.copy(),
            ),
        )
        self.observer = self.observer_patch.start()
        self.addCleanup(self.observer_patch.stop)

    @staticmethod
    def document(title):
        return SimpleNamespace(
            GetTitle=lambda: title,
            GetPathName=lambda: "",
            GetType=lambda: 1,
            GetSaveFlag=lambda: False,
            GetUpdateStamp=lambda: 12,
            ConfigurationManager=SimpleNamespace(
                ActiveConfiguration=SimpleNamespace(Name="Default")
            ),
            SketchManager=SimpleNamespace(ActiveSketch=None),
        )

    def call(self, name="entity.list", values=None, **context):
        return execute_operation(
            self.app,
            name,
            values or {},
            documents=self.registry,
            session_id="reader",
            document_id=self.entry.document_id,
            **context,
        )

    def test_background_read_ignores_write_lease_and_preserves_current_foreground(self):
        with mock.patch.object(self.registry, "temporarily_activate") as activate:
            result = self.call(expected_update_stamp=12)
        validate_operation_result("entity.list", result)
        self.assertFalse(result["document"]["current"] or result["document"]["active"])
        self.assertIs(self.app.ActiveDoc, self.other)
        self.assertIs(
            self.registry.resolve(None, session_id="reader"), self.other_entry
        )
        activate.assert_not_called()
        self.app.ActivateDoc3.assert_not_called()
        self.assertEqual(result["face_count"], 1)

    def test_repeat_and_inspect_reuse_exact_entity_with_fresh_scope(self):
        first = self.call()
        second = self.call()
        self.assertEqual(first["entities"], second["entities"])
        token = first["entities"][0]["entity_id"]
        inspected = self.call("entity.inspect", {"entity_id": token})
        validate_operation_result("entity.inspect", inspected)
        self.assertEqual(inspected["entity"], first["entities"][0])
        self.assertNotIn("entities", inspected)

    def test_unknown_cross_document_and_closed_handles_fail_before_traversal(self):
        token = self.call()["entities"][0]["entity_id"]
        self.observer.reset_mock()
        for bad in ("e-000000",):
            with self.assertRaises(EntityNotFound):
                self.call("entity.inspect", {"entity_id": bad})
        self.registry.set_current(self.other_entry, session_id="default")
        with self.assertRaises(EntityNotFound):
            execute_operation(
                self.app,
                "entity.inspect",
                {"entity_id": token},
                documents=self.registry,
            )
        self.observer.assert_not_called()
        self.registry.forget(self.entry.document_id)
        with self.assertRaises(EntityNotFound):
            self.entry.entities.resolve(token, configuration="Default", update_stamp=12)

    def test_changed_scope_retires_ids_before_any_implicit_rediscovery(self):
        token = self.call()["entities"][0]["entity_id"]
        self.doc.GetUpdateStamp = lambda: 13
        self.observer.reset_mock()
        with self.assertRaises(EntityReferenceStale):
            self.call("entity.inspect", {"entity_id": token})
        self.observer.assert_not_called()
        self.doc.GetUpdateStamp = lambda: 12
        with self.assertRaises(EntityReferenceStale):
            self.call("entity.inspect", {"entity_id": token})

    def test_list_rediscovery_after_scope_change_has_fresh_not_rebound_ids(self):
        first = self.call()["entities"][0]["entity_id"]
        self.doc.GetUpdateStamp = lambda: 13
        for state in ("before", "after"):
            self.native["observation"][state]["update_stamp"] = 13
        second = self.call()["entities"][0]["entity_id"]
        self.assertNotEqual(first, second)
        with self.assertRaises(EntityReferenceStale):
            self.call("entity.inspect", {"entity_id": first})

    def test_cas_rejection_does_not_traverse_or_allocate(self):
        with self.assertRaises(DocumentUpdateConflict):
            self.call(expected_update_stamp=11)
        self.observer.assert_not_called()
        self.assertEqual(self.registry._issued_entity_ids, set())

    def test_native_failure_returns_structured_error_without_allocating_handles(self):
        self.native = {
            "ok": False,
            "action": "entity.observe-faces",
            "error": {"type": "EntityObservationUnavailable", "message": "first error"},
        }
        self.bindings = []
        result = self.call()
        validate_operation_result("entity.list", result)
        self.assertEqual(result["error"]["message"], "first error")
        self.assertEqual(self.registry._issued_entity_ids, set())

    def test_failed_list_retires_observed_scope_without_revival_or_new_handles(self):
        token = self.call()["entities"][0]["entity_id"]
        issued = self.registry._issued_entity_ids.copy()
        original = deepcopy(self.native)
        observation = deepcopy(self.native["observation"])
        for state in ("before", "after"):
            observation[state]["configuration"] = "Other"
        self.native = {
            "ok": False,
            "action": "entity.observe-faces",
            "error": {"type": "EntityObservationUnavailable", "message": "first error"},
            "observation": observation,
        }
        self.bindings = []
        self.doc.ConfigurationManager.ActiveConfiguration.Name = "Other"
        result = self.call()
        validate_operation_result("entity.list", result)
        self.assertEqual(result["error"]["message"], "first error")
        self.assertNotIn("entities", result)
        self.assertEqual(self.registry._issued_entity_ids, issued)
        self.doc.ConfigurationManager.ActiveConfiguration.Name = "Default"
        self.native = original
        self.observer.reset_mock()
        with self.assertRaises(EntityReferenceStale):
            self.call("entity.inspect", {"entity_id": token})
        self.observer.assert_not_called()

    def test_failed_list_retires_after_scope_even_when_before_matches_old_scope(self):
        token = self.call()["entities"][0]["entity_id"]
        observation = deepcopy(self.native["observation"])
        observation["after"]["update_stamp"] = 13
        observation["unchanged"] = False
        self.native = {
            "ok": False,
            "action": "entity.observe-faces",
            "error": {"type": "EntityObservationUnavailable", "message": "state changed"},
            "observation": observation,
        }
        self.bindings = []
        result = self.call()
        validate_operation_result("entity.list", result)
        self.assertEqual(result["error"]["message"], "state changed")
        with self.assertRaises(EntityReferenceStale):
            self.call("entity.inspect", {"entity_id": token})

    def test_failed_geometry_in_unchanged_scope_preserves_existing_exact_handles(self):
        token = self.call()["entities"][0]["entity_id"]
        original = deepcopy(self.native)
        bindings = self.bindings.copy()
        self.native = {
            "ok": False,
            "action": "entity.observe-faces",
            "error": {"type": "EntityObservationUnavailable", "message": "first error"},
            "observation": deepcopy(original["observation"]),
        }
        self.bindings = []
        self.assertFalse(self.call()["ok"])
        self.native, self.bindings = original, bindings
        result = self.call("entity.inspect", {"entity_id": token})
        self.assertEqual(result["entity"]["entity_id"], token)

    def test_bad_native_shape_state_and_binding_counts_never_issue_tokens(self):
        original = deepcopy(self.native)
        for mutate in (
            lambda: self.native.update(face_count=2),
            lambda: self.native["observation"]["after"].update(modified=True),
            lambda: self.native["faces"][0].update(entity_id="e-ab12cd"),
            lambda: self.bindings.clear(),
        ):
            self.native = deepcopy(original)
            self.bindings = [FaceBinding(object(), object(), b"private")]
            mutate()
            with self.assertRaises(OperationResultInvalid):
                self.call()
            self.assertEqual(self.registry._issued_entity_ids, set())

    def test_same_scope_native_face_replacement_is_not_nearest_geometry_rebinding(self):
        token = self.call()["entities"][0]["entity_id"]
        self.bindings = [FaceBinding(object(), object(), b"new-private")]
        with self.assertRaises(EntityBindingConflict):
            self.call("entity.inspect", {"entity_id": token})

    def test_catalog_requests_and_cli_use_read_only_document_context(self):
        for name in ("entity.list", "entity.inspect"):
            spec = OPERATION_CATALOG[name]
            self.assertTrue(spec.selected_document)
            self.assertFalse(spec.lease_guarded or spec.temporary_activation)
            self.assertEqual(
                spec.parameters["x-swcli-context"]["lease_id"], "forbidden"
            )
        for args, operation, values in (
            (["entity", "list", "--max-faces", "8"], "entity.list", {"max_faces": 8}),
            (
                ["entity", "inspect", "e-ab12cd"],
                "entity.inspect",
                {"entity_id": "e-ab12cd"},
            ),
        ):
            parsed = build_parser().parse_args(
                [*args, "--document", "d-ab12cd", "--json"]
            )
            typed = _typed_operation(parsed)
            self.assertEqual(typed, (operation, values, True, "d-ab12cd", None, None))
            self.assertEqual(validate_operation_request(operation, values), values)
            self.assertTrue(
                Draft202012Validator(OPERATION_CATALOG[operation].parameters).is_valid(
                    values
                )
            )
        for name, values in (
            ("entity.list", {"max_faces": 65}),
            ("entity.list", {"max_faces": True}),
            ("entity.inspect", {}),
            ("entity.inspect", {"entity_id": "Face1"}),
            ("entity.inspect", {"entity_id": "e-ab12cd", "index": 1}),
        ):
            with self.assertRaises(ValueError):
                validate_operation_request(name, values)


if __name__ == "__main__":
    unittest.main()
