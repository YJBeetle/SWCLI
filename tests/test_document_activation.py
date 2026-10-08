"""Foreground restoration is verified, without losing native mutation evidence."""

import io
import json
import os
from types import SimpleNamespace
import unittest
from unittest import mock

from swcli.daemon.documents import DocumentRegistry
from swcli.daemon import operations
from swcli.hosts.native_trace import trace_native_request


class Document:
    def __init__(self, title):
        self.title = title

    def GetTitle(self):
        return self.title

    def GetPathName(self):
        return ""

    def GetType(self):
        return 1

    def GetSaveFlag(self):
        return False


class ActivationTests(unittest.TestCase):
    def setUp(self):
        self.target, self.previous = Document("Part1"), Document("Part2")
        self.app = SimpleNamespace(ActiveDoc=self.previous)
        self.app.GetDocuments = lambda: (self.target, self.previous)
        self.app.IsSame = lambda first, second: int(first is second)
        self.registry = DocumentRegistry(self.app)
        self.entry = self.registry.register(self.target)
        self.other = self.registry.register(self.previous)
        self.registry.set_current(self.other, session_id="writer")
        client = SimpleNamespace(
            VARIANT=lambda kind, value: SimpleNamespace(value=value)
        )
        self.modules = mock.patch.dict(
            "sys.modules",
            {
                "pythoncom": SimpleNamespace(VT_BYREF=1, VT_I4=2),
                "win32com": SimpleNamespace(client=client),
                "win32com.client": client,
            },
        )
        self.modules.start()
        self.addCleanup(self.modules.stop)

    def activation(self, *, restore=True, null=False, raises=False):
        def activate(title, silent, rebuild, errors):
            if title == self.target.title:
                self.app.ActiveDoc = self.target
                return self.target
            if raises:
                raise RuntimeError("native restore failed")
            if restore:
                self.app.ActiveDoc = self.previous
            return None if null else self.previous

        self.app.ActivateDoc3 = activate

    def test_restoration_requires_actual_previous_identity_and_nonnull_return(self):
        for options, failed in (
            ({}, False),
            ({"restore": False}, True),
            ({"null": True}, True),
            ({"raises": True}, True),
        ):
            with self.subTest(options=options):
                self.app.ActiveDoc = self.previous
                self.activation(**options)
                with self.registry.temporarily_activate(self.entry) as warnings:
                    self.assertIs(self.app.ActiveDoc, self.target)
                    self.assertEqual(warnings, [])
                self.assertEqual(bool(warnings), failed)
                if failed:
                    self.assertEqual(
                        warnings[0]["code"], "document-foreground-restore-failed"
                    )

    @mock.patch("swcli.daemon.operations.set_dimension_windows")
    def test_completed_mutation_keeps_handle_and_reports_restore_failure(self, setter):
        sketch = self.registry.register_sketch(
            self.entry, SimpleNamespace(GetID=lambda: 1)
        )
        dimension = self.registry.register_dimension(self.entry, sketch, object())
        self.activation(restore=False)
        setter.return_value = {
            "ok": True,
            "action": "dimension.set",
            "native_status": 0,
            "dimension": {"value": 20},
        }
        result = operations.execute_operation(
            self.app,
            "dimension.set",
            {"dimension_id": dimension, "value_mm": 20},
            documents=self.registry,
            document_id=self.entry.document_id,
            session_id="writer",
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["type"], "DocumentActivationFailed")
        self.assertEqual(result["native_status"], 0)
        self.assertEqual(result["dimension"]["dimension_id"], dimension)
        self.assertEqual(result["dimension"]["value"], 20)
        self.assertTrue(result["document"]["active"])
        self.assertFalse(result["document"]["current"])
        self.assertIs(self.registry.resolve(None, session_id="writer"), self.other)

    def test_original_failure_survives_restoration_warning(self):
        self.activation(raises=True)
        with self.assertRaisesRegex(ValueError, "original"):
            with self.registry.temporarily_activate(self.entry) as warnings:
                raise ValueError("original failure")
        self.assertEqual(len(warnings), 1)

    def test_trace_separates_background_activation_and_foreground_restoration(self):
        self.activation()
        stream = io.StringIO()
        with mock.patch.dict(os.environ, {"SWCLI_TRACE_NATIVE_CALLS": "1"}), \
                mock.patch("swcli.hosts.native_trace.sys.stderr", stream):
            with trace_native_request("req-activate", "sketch.rectangle"):
                with self.registry.temporarily_activate(self.entry) as warnings:
                    self.assertIs(self.app.ActiveDoc, self.target)
                self.assertEqual(warnings, [])
        self.assertIs(self.app.ActiveDoc, self.previous)
        events = [json.loads(line) for line in stream.getvalue().splitlines()]
        activation = [e for e in events if e["call"] == "SldWorks.ActivateDoc3"]
        self.assertEqual([(e["stage"], e["phase"]) for e in activation], [
            ("document-activate", "begin"), ("document-activate", "end"),
            ("document-restore", "begin"), ("document-restore", "end"),
        ])
        self.assertTrue(all(e["request_id"] == "req-activate" for e in events))

    def test_restore_trace_error_keeps_warning_and_original_business_exception(self):
        self.activation(raises=True)
        stream = io.StringIO()
        original = ValueError("original failure")
        with mock.patch.dict(os.environ, {"SWCLI_TRACE_NATIVE_CALLS": "1"}), \
                mock.patch("swcli.hosts.native_trace.sys.stderr", stream):
            with self.assertRaises(ValueError) as caught:
                with trace_native_request("req-fail", "sketch.rectangle"):
                    with self.registry.temporarily_activate(self.entry) as warnings:
                        raise original
        self.assertIs(caught.exception, original)
        self.assertEqual(warnings[0]["code"], "document-foreground-restore-failed")
        events = [json.loads(line) for line in stream.getvalue().splitlines()]
        failed = [e for e in events if e["stage"] == "document-restore"
                  and e["phase"] == "error"]
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]["exception_type"], "RuntimeError")


if __name__ == "__main__":
    unittest.main()
