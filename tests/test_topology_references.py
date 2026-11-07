"""Persistent references are scoped read-only proofs, never nearest rebinding."""

import base64
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from swcli.cli import build_parser, _typed_operation
from swcli.daemon.documents import DocumentRegistry
from swcli.daemon.operations import execute_operation, DocumentUpdateConflict
from swcli.hosts.windows_topology_references import verify_reference, PersistentReferenceTopologyChanged
from swcli.operation_schemas import OPERATION_CATALOG, validate_operation_request
from swcli.result_schemas import validate_operation_result, OperationResultInvalid
from swcli.sdk import Client
from swcli.mcp import DaemonBridge
from swcli.topology_references import encode_reference, decode_reference, document_path, MAX_TOKEN_CHARS
import test_edge_operations as edge_tests


class ReferenceOperationTests(unittest.TestCase):
    native_result = staticmethod(edge_tests.EdgeOperationTests.native_result)
    patch = edge_tests.EdgeOperationTests.patch
    call = edge_tests.EdgeOperationTests.call

    @staticmethod
    def document(title):
        doc = edge_tests.EdgeOperationTests.document(title)
        if title == "A":
            doc.GetPathName = lambda: r"C:\models\part.SLDPRT"
        return doc
    # Reuse exact mock observers/registry, not the inherited edge test methods.
    def call_reference(self, action, values, **kwargs):
        result = execute_operation(self.app, action, values, documents=self.registry,
            session_id="reader", document_id=self.entry.document_id, **kwargs)
        validate_operation_result(action, result)
        return result

    def setUp(self):
        edge_tests.EdgeOperationTests.setUp(self)
        self.extension = object()
        self.doc.Extension = self.extension
        self.native_resolution = mock.patch(
            "swcli.hosts.windows_topology_references._resolve_native",
            side_effect=lambda ext, ref: ({b"private-face": self.faces[0].face,
                                         b"private-edge": self.edges[0].edge}[ref], 0))
        self.resolve_native = self.native_resolution.start()
        self.addCleanup(self.native_resolution.stop)

    def capture(self, kind="face"):
        listed = self.call(kind=kind)
        token = listed["entities"][0]["entity_id"]
        return self.call_reference("entity.reference-create", {"entity_id": token, "kind": kind})

    def resolve(self, captured, **kwargs):
        return self.call_reference("entity.reference-resolve", {"reference": captured["reference"]}, **kwargs)

    def test_capture_resolve_both_kinds_background_lease_and_unchanged_scope(self):
        for kind in ("face", "edge"):
            captured = self.capture(kind)
            payload = decode_reference(captured["reference"])
            self.assertEqual(payload["document_path"], r"c:\models\part.sldprt")
            self.assertEqual(payload["configuration"], "Default")
            with mock.patch.object(self.registry, "temporarily_activate") as activate:
                resolved = self.resolve(captured, expected_update_stamp=12)
            self.assertTrue(resolved["ok"])
            self.assertEqual(resolved["entity"]["entity_id"], captured["entity_id"])
            self.assertEqual(resolved["native_status"], 0)
            self.assertFalse(resolved["document"]["active"] or resolved["document"]["current"])
            self.assertIs(self.app.ActiveDoc, self.other)
            activate.assert_not_called()
        self.app.ActivateDoc3.assert_not_called()

    def test_rebuild_new_stamp_resolves_explicitly_without_reviving_old_short_id(self):
        captured = self.capture()
        self.doc.GetUpdateStamp = lambda: 13
        for native in (self.native, self.face_native):
            for boundary in ("before", "after"):
                native["observation"][boundary]["update_stamp"] = 13
        resolved = self.resolve(captured)
        self.assertTrue(resolved["ok"])
        self.assertEqual(resolved["captured_update_stamp"], 12)
        self.assertEqual(resolved["document"]["update_stamp"], 13)
        self.assertNotEqual(resolved["entity"]["entity_id"], captured["entity_id"])
        from swcli.daemon.entities import EntityReferenceStale
        with self.assertRaises(EntityReferenceStale):
            self.entry.entities.resolve(captured["entity_id"], configuration="Default", update_stamp=13)

    def test_close_reopen_new_registry_accepts_portable_reference_not_old_short_id(self):
        captured = self.capture("edge")
        self.registry.forget(self.entry.document_id)
        self.entry = self.registry.register(self.doc)
        self.registry.set_current(self.other_entry, session_id="reader")
        result = self.resolve(captured)
        self.assertTrue(result["ok"])
        self.assertNotEqual(result["entity"]["entity_id"], captured["entity_id"])

    def test_wrong_saved_path_or_configuration_fails_before_native_topology(self):
        captured = self.capture()
        self.face_observer.reset_mock(); self.edge_observer.reset_mock()
        for attr, value in (("GetPathName", lambda: r"C:\models\copy.SLDPRT"),):
            old = getattr(self.doc, attr); setattr(self.doc, attr, value)
            self.entry = self.registry.register(self.doc)
            result = self.resolve(captured)
            self.assertFalse(result["ok"])
            self.assertEqual(result["error"]["type"], "PersistentReferenceScopeMismatch")
            setattr(self.doc, attr, old)
            self.entry = self.registry.register(self.doc)
        self.doc.ConfigurationManager.ActiveConfiguration.Name = "Other"
        self.assertFalse(self.resolve(captured)["ok"])
        self.resolve_native.assert_not_called()
        self.face_observer.assert_not_called(); self.edge_observer.assert_not_called()

    def test_unsaved_capture_unknown_target_and_cas_allocate_nothing(self):
        captured = self.capture()
        issued = self.registry._issued_entity_ids.copy()
        self.resolve_native.reset_mock()
        with self.assertRaises(DocumentUpdateConflict):
            self.resolve(captured, expected_update_stamp=11)
        self.doc.GetPathName = lambda: ""
        self.entry = self.registry.register(self.doc)
        result = self.call_reference("entity.reference-create", {"entity_id": captured["entity_id"]})
        self.assertFalse(result["ok"])
        self.assertNotIn("reference", result)
        self.assertEqual(issued, self.registry._issued_entity_ids)
        self.resolve_native.assert_not_called()

    def test_deleted_suppressed_invalid_unknown_and_unwritten_native_status_never_bind(self):
        captured = self.capture()
        issued = self.registry._issued_entity_ids.copy()
        for status in (1, 2, 4, 3, 7, 8, -1, 2147483647, None, True, "0", 0.0):
            self.resolve_native.side_effect = None
            self.resolve_native.return_value = (self.faces[0].face, status)
            self.resolve_native.reset_mock()
            result = self.resolve(captured)
            self.assertFalse(result["ok"], status)
            self.assertEqual(result["error"]["type"], "PersistentReferenceNativeState")
            if type(status) is int:
                self.assertEqual(result["native_status"], status)
            self.assertNotIn("entity", result)
            self.assertEqual(issued, self.registry._issued_entity_ids)
            self.assertEqual(self.resolve_native.call_count, 1)

    def test_null_success_native_exception_and_other_body_entity_preserve_failure(self):
        captured = self.capture()
        for native, message in (((None, 0), "state"), ((object(), 0), "membership")):
            self.resolve_native.side_effect = None
            self.resolve_native.return_value = native
            result = self.resolve(captured)
            self.assertFalse(result["ok"])
            self.assertIn(message, result["error"]["message"])
        self.resolve_native.side_effect = RuntimeError("first disconnected native call")
        self.resolve_native.reset_mock()
        result = self.resolve(captured)
        self.assertEqual(result["error"]["message"], "first disconnected native call")
        self.assertEqual(self.resolve_native.call_count, 1)

    def test_partial_observation_and_final_state_failure_never_publish_reference_or_handle(self):
        captured = self.capture()
        original = deepcopy(self.native)
        self.native = {"ok": False, "action": "entity.observe-edges",
                       "error": {"type": "NativeFailure", "message": "original edge failure"}}
        self.edges = []
        result = self.resolve(captured)
        self.assertEqual(result["error"]["message"], "original edge failure")
        self.assertIn("document", result)
        self.assertNotIn("entity", result)
        self.resolve_native.assert_not_called()
        self.native = original

    def test_final_stamp_change_discards_reference_without_issuing_handles(self):
        from swcli.hosts import windows_feature_inspection as native_state
        captured = self.capture()
        issued = self.registry._issued_entity_ids.copy()
        original = native_state._state
        calls = 0
        def state(app, document):
            nonlocal calls
            calls += 1
            result, edit, front = original(app, document)
            if calls == 2:
                result["update_stamp"] = 13
            return result, edit, front
        with mock.patch("swcli.daemon.topology_references._state", side_effect=state):
            result = self.resolve(captured)
        self.assertFalse(result["ok"])
        self.assertFalse(result["observation"]["unchanged"])
        self.assertNotIn("entity", result)
        self.assertEqual(issued, self.registry._issued_entity_ids)

    def test_first_native_failure_is_not_replaced_by_final_state_error(self):
        captured = self.capture()
        self.resolve_native.side_effect = RuntimeError("first native failure")
        from swcli.hosts.windows_feature_inspection import _state
        with mock.patch("swcli.daemon.topology_references._state",
                        side_effect=[_state(self.app, self.doc), RuntimeError("secondary state failure")]):
            result = self.resolve(captured)
        self.assertEqual(result["error"]["message"], "first native failure")
        self.assertEqual(result["warnings"][0]["message"], "secondary state failure")
        self.assertNotIn("entity", result)

    def test_first_native_error_survives_unavailable_document_description(self):
        captured = self.capture()
        self.resolve_native.side_effect = RuntimeError("first native failure")
        from swcli.daemon.operations import _with_document
        def descriptor(result, *args, **kwargs):
            if result["action"] == "entity.reference-resolve":
                raise RuntimeError("descriptor unavailable")
            return _with_document(result, *args, **kwargs)
        with mock.patch("swcli.daemon.operations._with_document", side_effect=descriptor):
            result = self.resolve(captured)
        self.assertEqual(result["error"]["message"], "first native failure")
        self.assertEqual(result["warnings"][0]["message"], "descriptor unavailable")
        self.assertNotIn("entity", result)

    def test_result_scope_token_and_kind_inconsistency_rejected(self):
        captured = self.capture()
        resolved = self.resolve(captured)
        for source, key, value in ((captured, "kind", "edge"),
                                   (captured, "captured_update_stamp", 99),
                                   (captured, "face_count", 2),
                                   (resolved, "native_status", 4),
                                   (resolved, "kind", "edge")):
            broken = deepcopy(source); broken[key] = value
            with self.assertRaises(OperationResultInvalid):
                validate_operation_result(broken["action"], broken)
        broken = deepcopy(resolved); broken["ok"] = False
        broken["error"] = {"type": "NativeFailure", "message": "failed"}
        with self.assertRaises(OperationResultInvalid):
            validate_operation_result(broken["action"], broken)


class ReferenceEnvelopeTests(unittest.TestCase):
    def payload(self):
        return dict(version=1, document_path=r"c:\models\part.sldprt", configuration="Default",
                    captured_update_stamp=12, kind="face", target_index=0,
                    faces=["ZmFjZQ"], edges=["ZWRnZQ"])

    def test_paths_are_explicit_windows_saved_scope(self):
        self.assertEqual(document_path(r"C:/models/./part.SLDPRT"), r"c:\models\part.sldprt")
        self.assertEqual(document_path(r"\\server\share\part.SLDPRT"), r"\\server\share\part.sldprt")
        for path in ("", "part.SLDPRT", "C:part.SLDPRT", "/part.SLDPRT", r"C:\part.SLDASM", None):
            with self.assertRaises(ValueError): document_path(path)

    def test_malformed_oversized_duplicate_and_wrong_target_envelopes_fail_before_io(self):
        good = self.payload()
        for field, value in (("version", True), ("faces", []), ("edges", ["ZmFjZQ"]),
                             ("target_index", True), ("target_index", 1), ("kind", "vertex"),
                             ("configuration", " "), ("faces", ["?bad"]), ("faces", ["ZmFjZQ=="]),
                             ("faces", ["ZmFjZQ"] * 65), ("document_path", "part.sldprt")):
            payload = {**good, field: value}
            with self.assertRaises((ValueError, TypeError)):
                encode_reference(payload)
        for raw in (None, "swref1.bad", "other", "swref1." + "a" * MAX_TOKEN_CHARS):
            with self.assertRaises(ValueError): decode_reference(raw)
        self.assertEqual(decode_reference(encode_reference(good)), good)

    def test_complete_census_rejects_split_merge_duplicate_and_nonunique_native_mapping(self):
        from swcli.hosts.windows_entity_observation import FaceBinding
        from swcli.hosts.windows_edge_observation import EdgeBinding
        from types import SimpleNamespace
        body, f1, f2, e1 = object(), object(), object(), object()
        faces = [FaceBinding(f1, body, b"face")]
        edges = [EdgeBinding(e1, body, b"edge")]
        app = SimpleNamespace(IsSame=lambda a, b: int(a is b))
        payload = self.payload()
        with mock.patch("swcli.hosts.windows_topology_references._resolve_native", return_value=(f1, 0)):
            for changed in (faces + [FaceBinding(f2, body, b"new")],
                            [FaceBinding(f1, body, b"face"), FaceBinding(f1, body, b"duplicate")]):
                with self.assertRaises(PersistentReferenceTopologyChanged):
                    verify_reference(app, object(), payload, faces=changed, edges=edges)
        # Counts stay the same but two old faces resolve to one current face.
        payload["faces"].append("b3RoZXI")
        faces.append(FaceBinding(f2, body, b"other"))
        with mock.patch("swcli.hosts.windows_topology_references._resolve_native", return_value=(f1, 0)) as native:
            with self.assertRaises(PersistentReferenceTopologyChanged):
                verify_reference(app, object(), payload, faces=faces, edges=edges)
            self.assertEqual(native.call_count, 2)

    def test_cli_sdk_and_mcp_share_same_reference_contract_and_context(self):
        reference = encode_reference(self.payload())
        for action in ("entity.reference-create", "entity.reference-resolve"):
            spec = OPERATION_CATALOG[action]
            self.assertTrue(spec.selected_document)
            self.assertFalse(spec.lease_guarded or spec.temporary_activation)
        parsed = build_parser().parse_args(["entity", "reference-create", "e-ab12cd", "--kind", "edge",
                                            "--document", "d-ab12cd", "--if-update-stamp", "12", "--json"])
        self.assertEqual(_typed_operation(parsed), ("entity.reference-create", {"entity_id": "e-ab12cd", "kind": "edge"},
                                                   True, "d-ab12cd", 12, None))
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/"reference.json"
            path.write_text(json.dumps({"reference": reference}))
            parsed = build_parser().parse_args(["entity", "reference-resolve", "--reference-file", str(path), "--json"])
            self.assertEqual(_typed_operation(parsed)[1], {"reference": reference})
        with mock.patch("swcli.sdk.client.call_daemon", return_value={"api_version": "swcli/v1", "success": False,
                "request_id": "id", "duration_ms": 1, "error": {"code": "NativeFailure", "message": "original"}}) as wire:
            response = Client(session_id="reader").entity.reference_resolve(reference=reference, document_id="d-ab12cd",
                                                                            expected_update_stamp=12, request_id="id")
            self.assertFalse(response.ok)
            self.assertEqual(wire.call_args.args[:2], ("entity.reference-resolve", {"reference": reference}))
            self.assertEqual(wire.call_args.kwargs["expected_update_stamp"], 12)
        with mock.patch("swcli.mcp.call_daemon", return_value={"api_version": "swcli/v1", "success": False,
                "request_id": "mcp-id", "duration_ms": 1, "error": {"code": "NativeFailure", "message": "original"}}) as wire:
            DaemonBridge(session_id="reader").call("execute", {"operation": "entity.reference-resolve",
                "parameters": {"reference": reference}, "document_id": "d-ab12cd", "expected_update_stamp": 12})
            self.assertEqual(wire.call_args.args[:2], ("entity.reference-resolve", {"reference": reference}))
        with self.assertRaises(ValueError):
            validate_operation_request("entity.reference-resolve", {"reference": reference}, lease_id="l-ab12cd34ef56")
