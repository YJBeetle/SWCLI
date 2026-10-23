"""Fillet targeting uses existing document leases, scope and exact bindings."""

from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest import mock

from swcli.daemon.documents import DocumentRegistry, DocumentLeaseConflict
from swcli.daemon.entities import EntityNotFound, EntityReferenceStale
from swcli.daemon.operations import execute_operation, DocumentUpdateConflict
from swcli.hosts.windows_edge_observation import EdgeBinding
from swcli.hosts.windows_entity_observation import FaceBinding


class FilletOperationTests(unittest.TestCase):
    def setUp(self):
        self.stamp = 12
        self.doc = self.document("A")
        self.other = self.document("B")
        self.app = SimpleNamespace(ActiveDoc=self.other,
            GetDocuments=lambda: (self.doc, self.other), IsSame=lambda a, b: int(a is b))
        self.documents = DocumentRegistry(self.app)
        self.entry = self.documents.register(self.doc)
        self.other_entry = self.documents.register(self.other)
        self.documents.set_current(self.other_entry, session_id="writer")
        self.binding = EdgeBinding(object(), object(), b"reference")
        self.token = self.entry.entities.register_edges([self.binding],
            configuration="Default", update_stamp=12)[0]
        self.feature = SimpleNamespace(GetID=lambda: 77)
        self.native = {"ok": True, "action": "feature.fillet", "radius_mm": 2,
            "mutation": {"attempted": True, "creation_returned": True, "may_have_changed": True},
            "feature": {"name": "Fillet1", "type": "Fillet"}, "cleanup_errors": []}
        self.state = {"configuration": "Default", "update_stamp": 12}
        self.observation = {"ok": True, "observation": {"after": self.state}, "edge_count": 1}
        self.observe = mock.patch("swcli.daemon.operations._observe_entities",
            side_effect=lambda *args: (deepcopy(self.observation), [self.binding])).start()
        self.adapter = mock.patch("swcli.hosts.windows_fillets.create_edge_fillet_windows_with_handle",
            side_effect=lambda **kwargs: (deepcopy(self.native), self.feature)).start()
        self.activate = mock.patch.object(self.documents, "temporarily_activate",
            side_effect=self.activation).start()
        self.addCleanup(mock.patch.stopall)

    def document(self, title):
        return SimpleNamespace(GetTitle=lambda: title, GetPathName=lambda: "", GetType=lambda: 1,
            GetSaveFlag=lambda: False, GetUpdateStamp=lambda: self.stamp,
            ConfigurationManager=SimpleNamespace(ActiveConfiguration=SimpleNamespace(Name="Default")),
            SketchManager=SimpleNamespace(ActiveSketch=None))

    @contextmanager
    def activation(self, entry):
        previous = self.app.ActiveDoc
        self.app.ActiveDoc = entry.document
        try:
            yield []
        finally:
            self.app.ActiveDoc = previous

    def call(self, token=None, **context):
        return execute_operation(self.app, "feature.fillet",
            {"entity_id": token or self.token, "radius_mm": 2}, documents=self.documents,
            document_id=self.entry.document_id, session_id="writer", **context)

    def test_complete_binding_and_returned_feature_preserve_current_and_foreground(self):
        result = self.call()
        self.assertIs(self.adapter.call_args.kwargs["binding"], self.binding)
        self.assertIs(self.documents.resolve_feature(self.entry, result["feature"]["feature_id"]), self.feature)
        self.assertIs(self.app.ActiveDoc, self.other)
        self.assertIs(self.documents.resolve(None, session_id="writer"), self.other_entry)
        self.assertEqual(result["entity_id"], self.token)
        with self.assertRaises(EntityReferenceStale):
            self.call()

    def test_unknown_cross_document_and_face_targets_fail_before_activation(self):
        foreign = self.other_entry.entities.register_edges([self.binding],
            configuration="Default", update_stamp=12)[0]
        face = self.entry.entities.register_faces([FaceBinding(object(), self.binding.body, b"face")],
            configuration="Default", update_stamp=12)[0]
        for token in ("e-abcdef", foreign, face):
            with self.subTest(token=token), self.assertRaises(EntityNotFound):
                self.call(token)
        self.activate.assert_not_called()
        self.adapter.assert_not_called()
        self.observe.assert_not_called()

    def test_stale_scope_and_stamp_conflict_fail_before_activation(self):
        self.stamp = 13
        with self.assertRaises(DocumentUpdateConflict):
            self.call(expected_update_stamp=12)
        with self.assertRaises(EntityReferenceStale):
            self.call()
        self.activate.assert_not_called()
        self.adapter.assert_not_called()

    def test_other_owner_lease_fails_before_observation_or_activation(self):
        self.documents.acquire_lease(self.entry, session_id="other", ttl_seconds=60)
        with self.assertRaises(DocumentLeaseConflict):
            self.call()
        self.activate.assert_not_called()
        self.observe.assert_not_called()

    def test_failed_complete_observation_does_not_create_or_retire_current_scope(self):
        self.observation.update(ok=False, error={"type": "ObservationFailed", "message": "missing edge"})
        result = self.call()
        self.assertFalse(result["ok"])
        self.assertFalse(result["mutation"]["may_have_changed"])
        self.assertEqual(result["error"]["type"], "ObservationFailed")
        self.adapter.assert_not_called()
        self.entry.entities.resolve(self.token, kind="edge", configuration="Default", update_stamp=12)

    def test_partial_creation_failure_retains_feature_and_retires_face_and_edge(self):
        face = self.entry.entities.register_faces([FaceBinding(object(), self.binding.body, b"face")],
            configuration="Default", update_stamp=12)[0]
        self.native.update(ok=False, error={"type": "VerificationFailed", "message": "bad radius"})
        result = self.call()
        self.assertFalse(result["ok"])
        self.assertIn("feature_id", result["feature"])
        for token, kind in ((self.token, "edge"), (face, "face")):
            with self.assertRaises(EntityReferenceStale):
                self.entry.entities.resolve(token, kind=kind, configuration="Default", update_stamp=12)
        new = self.entry.entities.register_edges([self.binding], configuration="Default", update_stamp=12)[0]
        self.assertNotEqual(new, self.token)

    def test_unexpected_adapter_exception_retires_scope_and_restores_foreground(self):
        self.adapter.side_effect = RuntimeError("unknown native write boundary")
        with self.assertRaisesRegex(RuntimeError, "write boundary"):
            self.call()
        self.assertIs(self.app.ActiveDoc, self.other)
        with self.assertRaises(EntityReferenceStale):
            self.call()

    def test_precreation_failure_keeps_scope(self):
        self.native.update(ok=False, mutation={"attempted": False, "creation_returned": False,
            "may_have_changed": False}, error={"type": "SelectionNotEmpty", "message": "busy"})
        self.adapter.side_effect = lambda **kwargs: (deepcopy(self.native), None)
        self.call()
        self.entry.entities.resolve(self.token, kind="edge", configuration="Default", update_stamp=12)

    def test_failed_feature_registration_does_not_erase_mutation_or_first_error(self):
        self.native.update(ok=False, error={"type": "FirstFailure", "message": "native verification"})
        with mock.patch.object(self.documents, "register_feature", side_effect=RuntimeError("native ID unavailable")):
            result = self.call()
        self.assertFalse(result["ok"])
        self.assertTrue(result["mutation"]["creation_returned"])
        self.assertEqual(result["error"]["type"], "FirstFailure")
        self.assertEqual(result["cleanup_errors"][0]["stage"], "register-created-feature")
        with self.assertRaises(EntityReferenceStale):
            self.call()


if __name__ == "__main__":
    unittest.main()
