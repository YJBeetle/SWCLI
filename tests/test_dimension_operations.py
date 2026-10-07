"""Dimension operations share document/session, lease and update-stamp guards."""

from contextlib import contextmanager
from types import SimpleNamespace
import unittest
from unittest import mock

from swcli.daemon import operations
from swcli.daemon.documents import (
    DimensionNotFound,
    DocumentLeaseConflict,
    DocumentRegistry,
    SketchNotFound,
)


class Document:
    def __init__(self, title):
        self.title = title
        self.stamp = 10

    def GetTitle(self):
        return self.title

    def GetPathName(self):
        return ""

    def GetType(self):
        return 1

    def GetSaveFlag(self):
        return False

    def GetUpdateStamp(self):
        return self.stamp


class App:
    def __init__(self, target, foreground):
        self.documents = (target, foreground)
        self.ActiveDoc = foreground

    def GetDocuments(self):
        return self.documents


class DimensionOperationTests(unittest.TestCase):
    def setUp(self):
        self.target, self.foreground = Document("Part1"), Document("Part2")
        self.app = App(self.target, self.foreground)
        self.registry = DocumentRegistry(self.app)
        self.entry = self.registry.register(self.target)
        self.other = self.registry.register(self.foreground)
        self.registry.set_current(self.other, session_id="writer")
        self.sketch, self.dimension = SimpleNamespace(GetID=lambda: 1), object()
        self.sketch_id = self.registry.register_sketch(self.entry, self.sketch)
        self.dimension_id = self.registry.register_dimension(
            self.entry, self.sketch_id, self.dimension
        )
        self.lease = self.registry.acquire_lease(
            self.entry, session_id="writer", ttl_seconds=60
        )["lease_id"]

    @contextmanager
    def activate(self, selected):
        self.assertIs(selected, self.entry)
        self.app.ActiveDoc = selected.document
        try:
            yield
        finally:
            self.app.ActiveDoc = self.foreground

    def call(self, operation, parameters, **context):
        return operations.execute_operation(
            self.app,
            operation,
            parameters,
            documents=self.registry,
            **{
                "session_id": "writer",
                "document_id": self.entry.document_id,
                **context,
            },
        )

    def assert_context_retained(self, result):
        self.assertFalse(result["document"]["active"])
        self.assertFalse(result["document"]["current"])
        self.assertIs(self.app.ActiveDoc, self.foreground)
        self.assertIs(self.registry.resolve(None, session_id="writer"), self.other)

    @mock.patch("swcli.daemon.operations.create_circle_diameter_windows_with_handle")
    def test_creation_guarded_before_mutation_and_retains_partial_native_handle(
        self, create
    ):
        values = {"sketch_id": self.sketch_id, "diameter_mm": 16}
        with self.assertRaises(DocumentLeaseConflict):
            self.call("sketch.dimension-diameter", values)
        with self.assertRaises(operations.DocumentUpdateConflict):
            self.call(
                "sketch.dimension-diameter",
                values,
                lease_id=self.lease,
                expected_update_stamp=9,
            )
        with self.assertRaises(SketchNotFound):
            self.call(
                "sketch.dimension-diameter",
                {**values, "sketch_id": "s-000000"},
                lease_id=self.lease,
            )
        create.assert_not_called()
        native = object()
        create.return_value = (
            {
                "ok": False,
                "action": "sketch.dimension-diameter",
                "error": {"type": "DimensionVerificationFailed", "message": "partial"},
            },
            native,
        )
        with mock.patch.object(
            self.registry, "temporarily_activate", side_effect=self.activate
        ):
            result = self.call(
                "sketch.dimension-diameter",
                values,
                lease_id=self.lease,
                expected_update_stamp=10,
            )
        create.assert_called_once_with(
            app=self.app,
            document=self.target,
            sketch_feature=self.sketch,
            diameter_mm=16.0,
        )
        self.assertEqual(result["sketch_id"], self.sketch_id)
        self.assertEqual(result["dimension"]["sketch_id"], self.sketch_id)
        self.assertIs(
            self.registry.resolve_dimension(
                self.entry, result["dimension"]["dimension_id"]
            ).dimension,
            native,
        )
        self.assert_context_retained(result)

    @mock.patch("swcli.daemon.operations.create_circle_diameter_windows_with_handle")
    def test_rejected_creation_does_not_invent_dimension_handle(self, create):
        create.return_value = (
            {
                "ok": False,
                "action": "sketch.dimension-diameter",
                "error": {"type": "SketchAlreadyDimensioned", "message": "duplicate"},
            },
            None,
        )
        with mock.patch.object(
            self.registry, "temporarily_activate", side_effect=self.activate
        ):
            result = self.call(
                "sketch.dimension-diameter",
                {"sketch_id": self.sketch_id, "diameter_mm": 16},
                lease_id=self.lease,
            )
        self.assertNotIn("dimension", result)
        self.assertEqual(len(self.entry.dimensions), 1)

    @mock.patch("swcli.daemon.operations.inspect_dimension_windows")
    def test_inspection_reads_exact_leased_background_dimension_without_activation(
        self, inspect
    ):
        inspect.return_value = {
            "ok": True,
            "action": "dimension.inspect",
            "dimension": {"value": 16},
        }
        values = {"dimension_id": self.dimension_id}
        with self.assertRaises(operations.DocumentUpdateConflict):
            self.call("dimension.inspect", values, expected_update_stamp=9)
        inspect.assert_not_called()
        with mock.patch.object(self.registry, "temporarily_activate") as activate:
            result = self.call(
                "dimension.inspect",
                values,
                session_id="observer",
                expected_update_stamp=10,
            )
        activate.assert_not_called()
        inspect.assert_called_once_with(
            app=self.app,
            document=self.target,
            sketch_feature=self.sketch,
            dimension=self.dimension,
        )
        self.assertEqual(result["dimension"]["dimension_id"], self.dimension_id)
        self.assertEqual(result["sketch_id"], self.sketch_id)
        self.assert_context_retained(result)

    @mock.patch("swcli.daemon.operations.set_dimension_windows")
    def test_value_edit_guards_lease_session_stamp_and_exact_target(self, setter):
        values = {"dimension_id": self.dimension_id, "value_mm": 20}
        for context in ({}, {"lease_id": self.lease, "session_id": "other"}):
            with self.assertRaises(DocumentLeaseConflict):
                self.call("dimension.set", values, **context)
        with self.assertRaises(operations.DocumentUpdateConflict):
            self.call(
                "dimension.set", values, lease_id=self.lease, expected_update_stamp=9
            )
        with self.assertRaises(DimensionNotFound):
            self.call(
                "dimension.set",
                {**values, "dimension_id": "m-000000"},
                lease_id=self.lease,
            )
        setter.assert_not_called()
        setter.return_value = {
            "ok": True,
            "action": "dimension.set",
            "dimension": {"value": 20},
        }
        with mock.patch.object(
            self.registry, "temporarily_activate", side_effect=self.activate
        ):
            result = self.call(
                "dimension.set", values, lease_id=self.lease, expected_update_stamp=10
            )
        setter.assert_called_once_with(
            app=self.app,
            document=self.target,
            sketch_feature=self.sketch,
            dimension=self.dimension,
            value_mm=20.0,
        )
        self.assert_context_retained(result)

    @mock.patch("swcli.daemon.operations.inspect_dimension_windows")
    def test_wrong_document_closed_handle_and_restart_never_reach_adapter(
        self, inspect
    ):
        values = {"dimension_id": self.dimension_id}
        with self.assertRaises(DimensionNotFound):
            self.call("dimension.inspect", values, document_id=self.other.document_id)
        self.registry.forget(self.entry.document_id)
        replacement = self.registry.register(self.target)
        with self.assertRaises(DimensionNotFound):
            self.call("dimension.inspect", values, document_id=replacement.document_id)
        inspect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
