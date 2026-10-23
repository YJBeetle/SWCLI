"""Cross-document drawing writes preserve current and guard both participants."""
from contextlib import contextmanager
from types import SimpleNamespace
import unittest
from unittest import mock

from swcli.daemon.documents import DocumentRegistry, DocumentNotFound, DocumentLeaseConflict
from swcli.daemon.operations import execute_operation, DocumentUpdateConflict


class DrawingOperationTests(unittest.TestCase):
    def setUp(self):
        self.source = self.doc("Part", 1)
        self.drawing = self.doc("Drawing", 3)
        self.app = SimpleNamespace(ActiveDoc=self.source,
            IsSame=lambda a,b: int(a is b), GetDocuments=lambda: (self.source,self.drawing))
        self.registry = DocumentRegistry(self.app)
        self.s = self.registry.register(self.source)
        self.d = self.registry.register(self.drawing)
        self.registry.set_current(self.s, session_id="writer")
        self.activate = mock.patch.object(self.registry, "temporarily_activate", side_effect=self.activation).start()
        self.native = mock.patch("swcli.hosts.windows_drawings.insert_standard_views_windows",
            return_value={"ok": True, "action": "drawing.standard-views"}).start()
        self.addCleanup(mock.patch.stopall)

    @staticmethod
    def doc(title, kind):
        return SimpleNamespace(GetTitle=lambda:title, GetPathName=lambda:"", GetType=lambda:kind,
            GetSaveFlag=lambda:False, GetUpdateStamp=lambda:12)

    @contextmanager
    def activation(self, entry):
        previous = self.app.ActiveDoc
        self.app.ActiveDoc = entry.document
        try:
            yield []
        finally:
            self.app.ActiveDoc = previous

    def call(self, source_id=None, **context):
        return execute_operation(self.app, "drawing.standard-views",
            {"source_document_id": source_id or self.s.document_id, "configuration": "Default"},
            documents=self.registry, document_id=self.d.document_id, session_id="writer", **context)

    def test_exact_objects_and_current_foreground_preserved(self):
        result = self.call(expected_update_stamp=12)
        self.assertIs(self.native.call_args.kwargs["source_document"], self.source)
        self.assertIs(self.native.call_args.kwargs["document"], self.drawing)
        self.assertEqual(result["source_document_id"], self.s.document_id)
        self.assertIs(self.app.ActiveDoc, self.source)
        self.assertIs(self.registry.resolve(None, session_id="writer"), self.s)
        self.assertEqual(result["document"]["document_id"], self.d.document_id)

    def test_source_unknown_and_self_refused_before_activation(self):
        with self.assertRaises(DocumentNotFound):
            self.call("d-000000")
        with self.assertRaisesRegex(ValueError, "own source"):
            self.call(self.d.document_id)
        self.activate.assert_not_called()
        self.native.assert_not_called()

    def test_target_lease_and_cas_refused_before_activation(self):
        with self.assertRaises(DocumentUpdateConflict):
            self.call(expected_update_stamp=11)
        self.registry.acquire_lease(self.d, session_id="other", ttl_seconds=60)
        with self.assertRaises(DocumentLeaseConflict):
            self.call()
        self.activate.assert_not_called()
        self.native.assert_not_called()

    def test_source_other_owner_lease_refused_before_activation(self):
        self.registry.acquire_lease(self.s, session_id="other", ttl_seconds=60)
        with self.assertRaisesRegex(DocumentLeaseConflict, "source model"):
            self.call()
        self.activate.assert_not_called()
        self.native.assert_not_called()

    def test_owned_source_lease_does_not_authorize_target_lease_bypass(self):
        self.registry.acquire_lease(self.s, session_id="writer", ttl_seconds=60)
        target = self.registry.acquire_lease(self.d, session_id="writer", ttl_seconds=60)
        with self.assertRaises(DocumentLeaseConflict):
            self.call()
        self.call(lease_id=target["lease_id"])
        self.native.assert_called_once()

    def test_native_failure_retains_partial_evidence_and_restores_foreground(self):
        self.native.return_value = {"ok":False, "action":"drawing.standard-views",
            "mutation":{"attempted":True,"may_have_changed":True},
            "views":[{"name":"partial"}], "error":{"type":"FirstFailure","message":"insertion"}}
        result = self.call()
        self.assertEqual(result["error"]["type"], "FirstFailure")
        self.assertTrue(result["mutation"]["may_have_changed"])
        self.assertEqual(len(result["views"]), 1)
        self.assertIs(self.app.ActiveDoc, self.source)

    def test_created_exact_drawing_is_registered_even_after_postcondition_failure(self):
        failure = {"ok":False,"action":"document.create","created":True,
                   "error":{"type":"ProjectionFailed","message":"readback"}}
        with mock.patch("swcli.hosts.windows_drawings.create_drawing_windows_with_handle",
                        return_value=(failure, self.drawing)) as create:
            result = execute_operation(self.app, "document.create",
                {"type":"drawing","template":"C:/templates/a4.drwdot","projection":"third-angle"},
                documents=self.registry, session_id="writer")
        self.assertFalse(result["ok"])
        self.assertIs(self.registry.resolve(None, session_id="writer"), self.d)
        self.assertEqual(result["document"]["document_id"], self.d.document_id)
        self.assertEqual(create.call_args.kwargs["projection"], "third-angle")
