"""Typed edge reads use exact mixed-kind scope, never foreground or coercion."""

from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest import mock

from jsonschema import Draft202012Validator

from swcli.cli import build_parser, _typed_operation, _capabilities_mismatch
from swcli.daemon.documents import DocumentRegistry
from swcli.daemon.entities import EntityNotFound, EntityReferenceStale, EntityBindingConflict
from swcli.daemon.operations import execute_operation, DocumentUpdateConflict
from swcli.daemon.server import WorkerManager
from swcli.hosts.windows_edge_observation import EdgeBinding
from swcli.hosts.windows_entity_observation import FaceBinding
from swcli.operation_schemas import OPERATION_CATALOG, validate_operation_request
from swcli.result_schemas import OperationResultInvalid, validate_operation_result
from test_edge_result_schemas import edge_result
from test_entity_result_schemas import face_result


class EdgeOperationTests(unittest.TestCase):
    def setUp(self):
        self.doc, self.other = self.document("A"), self.document("B")
        self.app = SimpleNamespace(ActiveDoc=self.other, GetDocuments=lambda: (self.doc, self.other),
                                   IsSame=lambda a, b: int(a is b), ActivateDoc3=mock.Mock())
        self.registry = DocumentRegistry(self.app)
        self.entry, self.other_entry = self.registry.register(self.doc), self.registry.register(self.other)
        self.registry.set_current(self.other_entry, session_id="reader")
        self.registry.acquire_lease(self.entry, session_id="writer", ttl_seconds=60)
        self.body = object()
        self.edges = [EdgeBinding(object(), self.body, b"private-edge")]
        self.faces = [FaceBinding(object(), self.body, b"private-face")]
        self.native = self.native_result(edge_result(public=False), "edge")
        self.face_native = self.native_result(face_result(public=False), "face")
        self.edge_observer = self.patch("windows_edge_observation.observe_part_edges_with_handles", "native", "edges")
        self.face_observer = self.patch("windows_entity_observation.observe_part_faces_with_handles", "face_native", "faces")

    @staticmethod
    def native_result(result, kind):
        result.pop("document")
        result.pop("scope")
        result["action"] = f"entity.observe-{kind}s"
        result[f"{kind}s"] = result.pop("entities")
        return result

    def patch(self, name, native, bindings):
        patch = mock.patch(f"swcli.hosts.{name}", side_effect=lambda *a, **kw: (
            deepcopy(getattr(self, native)), getattr(self, bindings).copy()))
        observer = patch.start()
        self.addCleanup(patch.stop)
        return observer

    @staticmethod
    def document(title):
        return SimpleNamespace(GetTitle=lambda: title, GetPathName=lambda: "", GetType=lambda: 1,
                               GetSaveFlag=lambda: False, GetUpdateStamp=lambda: 12,
                               ConfigurationManager=SimpleNamespace(ActiveConfiguration=SimpleNamespace(Name="Default")),
                               SketchManager=SimpleNamespace(ActiveSketch=None))

    def call(self, name="entity.list", values=None, *, kind="edge", **context):
        return execute_operation(self.app, name, {"kind": kind, **(values or {})},
                                 documents=self.registry, session_id="reader", document_id=self.entry.document_id, **context)

    def test_background_read_uses_edge_observer_without_activation_or_write_lease(self):
        with mock.patch.object(self.registry, "temporarily_activate") as activate:
            result = self.call("entity.list", {"max_edges": 8}, expected_update_stamp=12)
        validate_operation_result("entity.list", result)
        self.assertEqual(result["edge_count"], 1)
        self.assertEqual(result["scope"], "single-solid-part-edges")
        self.edge_observer.assert_called_once_with(self.app, self.doc, max_edges=8)
        self.face_observer.assert_not_called()
        activate.assert_not_called()
        self.app.ActivateDoc3.assert_not_called()
        self.assertIs(self.app.ActiveDoc, self.other)
        self.assertIs(self.registry.resolve(None, session_id="reader"), self.other_entry)

    def test_faces_edges_repeat_and_inspect_without_removing_other_kind(self):
        face = self.call(kind="face")["entities"][0]
        edge = self.call()["entities"][0]
        self.assertNotEqual(face["entity_id"], edge["entity_id"])
        for kind, entity in (("face", face), ("edge", edge)):
            repeated = self.call(kind=kind)
            inspected = self.call("entity.inspect", {"entity_id": entity["entity_id"]}, kind=kind)
            validate_operation_result("entity.inspect", inspected)
            self.assertEqual(repeated["entities"][0], entity)
            self.assertEqual(inspected["entity"], entity)

    def test_unknown_wrong_kind_and_cross_document_fail_before_any_traversal(self):
        edge, face = self.call()["entities"][0], self.call(kind="face")["entities"][0]
        self.edge_observer.reset_mock()
        self.face_observer.reset_mock()
        for token, kind in (("e-000000", "edge"), (face["entity_id"], "edge"), (edge["entity_id"], "face")):
            with self.assertRaises(EntityNotFound):
                self.call("entity.inspect", {"entity_id": token}, kind=kind)
        with self.assertRaises(EntityNotFound):
            execute_operation(self.app, "entity.inspect", {"entity_id": edge["entity_id"], "kind": "edge"},
                              documents=self.registry, document_id=self.other_entry.document_id)
        # Omission deliberately retains the default face resolver, not inferred kind.
        with self.assertRaises(EntityNotFound):
            execute_operation(self.app, "entity.inspect", {"entity_id": edge["entity_id"]},
                              documents=self.registry, document_id=self.entry.document_id)
        self.edge_observer.assert_not_called()
        self.face_observer.assert_not_called()

    def test_cas_rejection_precedes_traversal_and_token_allocation(self):
        with self.assertRaises(DocumentUpdateConflict):
            self.call(expected_update_stamp=11)
        self.edge_observer.assert_not_called()
        self.assertEqual(self.registry._issued_entity_ids, set())

    def test_scope_seen_by_failed_edge_read_retires_both_without_new_ids(self):
        face, edge = self.call(kind="face")["entities"][0], self.call()["entities"][0]
        issued = self.registry._issued_entity_ids.copy()
        observation = deepcopy(self.native["observation"])
        observation["after"]["update_stamp"] = 13
        observation["unchanged"] = False
        self.native = {"ok": False, "action": "entity.observe-edges", "observation": observation,
                       "error": {"type": "EntityObservationUnavailable", "message": "first native failure"}}
        self.edges = []
        result = self.call()
        validate_operation_result("entity.list", result)
        self.assertEqual(result["error"]["message"], "first native failure")
        self.assertEqual(self.registry._issued_entity_ids, issued)
        for kind, entity in (("face", face), ("edge", edge)):
            with self.assertRaises(EntityReferenceStale):
                self.call("entity.inspect", {"entity_id": entity["entity_id"]}, kind=kind)

    def test_failed_same_scope_edge_geometry_preserves_exact_face_and_edge_ids(self):
        face, edge = self.call(kind="face")["entities"][0], self.call()["entities"][0]
        original, bindings = deepcopy(self.native), self.edges.copy()
        self.native = {"ok": False, "action": "entity.observe-edges", "observation": original["observation"],
                       "error": {"type": "NativeError", "message": "first"}}
        self.edges = []
        self.assertFalse(self.call()["ok"])
        self.native, self.edges = original, bindings
        for kind, entity in (("face", face), ("edge", edge)):
            self.assertEqual(self.call("entity.inspect", {"entity_id": entity["entity_id"]}, kind=kind)["entity"], entity)

    def test_malformed_private_geometry_or_binding_count_cannot_issue_ids(self):
        original = deepcopy(self.native)
        for mutate in (
            lambda: self.native.update(edge_count=2),
            lambda: self.native["edges"][0]["parameter_data"].update(u_max_native=0),
            lambda: self.native["edges"][0].update(entity_id="e-ab12cd"),
            lambda: self.edges.clear(),
        ):
            self.native, self.edges = deepcopy(original), [EdgeBinding(object(), self.body, b"edge")]
            mutate()
            with self.assertRaises(OperationResultInvalid):
                self.call()
            self.assertEqual(self.registry._issued_entity_ids, set())

    def test_same_scope_native_edge_replacement_never_rebinds_geometry(self):
        token = self.call()["entities"][0]["entity_id"]
        self.edges = [EdgeBinding(object(), self.body, b"new-private")]
        with self.assertRaises(EntityBindingConflict):
            self.call("entity.inspect", {"entity_id": token})

    def test_kind_specific_request_limits_match_schema_and_cli(self):
        cases = (
            (["list", "--kind", "edge", "--max-edges", "8"], {"kind": "edge", "max_edges": 8}),
            (["list", "--kind", "edge"], {"kind": "edge", "max_edges": 64}),
            (["inspect", "e-ab12cd", "--kind", "edge"], {"entity_id": "e-ab12cd", "kind": "edge"}),
            (["list"], {"max_faces": 64}),
        )
        for args, values in cases:
            parsed = build_parser().parse_args(["entity", *args, "--document", "d-ab12cd", "--json"])
            name = f"entity.{args[0]}"
            self.assertEqual(_typed_operation(parsed), (name, values, True, "d-ab12cd", None, None))
            self.assertEqual(validate_operation_request(name, values), values)
            self.assertTrue(Draft202012Validator(OPERATION_CATALOG[name].parameters).is_valid(values))
        invalid = ({"max_edges": 8}, {"kind": "face", "max_edges": 8},
                   {"kind": "edge", "max_faces": 8}, {"kind": "edge", "max_edges": True},
                   {"kind": "edge", "max_edges": 65}, {"kind": "edge", "max_edges": 0},
                   {"kind": "vertex"}, {"kind": "edge", "max_edges": 8, "max_faces": 8})
        for values in invalid:
            with self.subTest(values=values):
                self.assertFalse(Draft202012Validator(OPERATION_CATALOG["entity.list"].parameters).is_valid(values))
                with self.assertRaises(ValueError):
                    validate_operation_request("entity.list", values)
        for values in ({"entity_id": "e-ab12cd", "kind": "vertex"},
                       {"entity_id": "e-ab12cd", "kind": "edge", "max_edges": 8}):
            with self.assertRaises(ValueError):
                validate_operation_request("entity.inspect", values)

    def test_conditional_parameter_schema_is_valid_capability_not_unchecked_escape(self):
        with mock.patch.object(WorkerManager, "_start_worker"):
            payload = WorkerManager().health()
        validate_operation_result("daemon.health", payload)
        self.assertIsNone(_capabilities_mismatch(payload))
        for conditions in ([], "unchecked", [{"if": {"type": "bogus-type"}}]):
            changed = deepcopy(payload)
            changed["operation_schemas"]["entity.list"]["allOf"] = conditions
            with self.subTest(conditions=conditions):
                self.assertIsNotNone(_capabilities_mismatch(changed))


if __name__ == "__main__":
    unittest.main()
