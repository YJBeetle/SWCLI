"""Daemon/MCP preference routing and guards using real registry, without COM."""
from copy import deepcopy
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

from swcli import PROTOCOL_VERSION
from swcli.daemon import operations
from swcli.daemon.documents import DocumentLeaseConflict, DocumentNotFound, DocumentRegistry
from swcli.daemon.operations import DocumentUpdateConflict, OperationContext, execute_operation
from swcli.daemon.server import WorkerManager
from swcli.mcp import DaemonBridge
from swcli.operation_schemas import OPERATION_CATALOG, validate_operation_request
from swcli.result_schemas import validate_operation_result


HOST_FUNCTIONS = {
    "document.annotation-font": "read_document_annotation_font_windows",
    "document.annotation-font-set": "set_document_annotation_font_windows",
    "document.display-options": "read_document_display_options_windows",
    "document.display-option-set": "set_document_display_option_windows",
    "document.drafting-standard": "read_document_drafting_standard_windows",
    "document.drafting-standard-set": "set_document_drafting_standard_windows",
}
READS = tuple(name for name in HOST_FUNCTIONS if not name.endswith("-set"))
WRITES = tuple(name for name in HOST_FUNCTIONS if name.endswith("-set"))


class DocumentPreferenceOperationTests(unittest.TestCase):
    def setUp(self):
        # Compose actual fixed-reader values from the existing native-object
        # fixture; no successful preference payload is synthesized by hand.
        path = Path(__file__).with_name("test_document_drafting_standard.py")
        spec = importlib.util.spec_from_file_location("_preference_operation_fixture", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.fixture = module.DocumentDraftingStandardTests()
        self.fixture.setUp()
        self.snapshot = self.fixture.expected()
        self.font = deepcopy(self.snapshot["observed_defaults"]["annotation_font"]["font"])
        self.native_font = deepcopy(self.snapshot["observed_defaults"]["annotation_font"]["native_font"])
        self.options = deepcopy(self.snapshot["observed_defaults"]["display"])
        self.stamp = 19
        self.document = self.fixture.document
        self.document.GetTitle = lambda: "Preference Background"
        self.document.GetPathName = lambda: ""
        self.document.GetUpdateStamp = lambda: self.stamp
        self.foreground = SimpleNamespace(
            GetTitle=lambda: "Preference Foreground", GetPathName=lambda: "",
            GetType=lambda: 1, GetSaveFlag=lambda: False, GetUpdateStamp=lambda: 8)
        self.app = self.fixture.app
        self.app.ActiveDoc = self.foreground
        self.app.GetDocuments = lambda: (self.document, self.foreground)
        self.documents = DocumentRegistry(self.app)
        self.entry = self.documents.register(self.document)
        self.front_entry = self.documents.register(self.foreground)
        for session in ("reader", "writer"):
            self.documents.set_current(self.front_entry, session_id=session)
        self.lease = self.documents.acquire_lease(self.entry, session_id="writer", ttl_seconds=600)
        self.front_lease = self.documents.acquire_lease(self.front_entry, session_id="writer", ttl_seconds=600)

    def parameters(self, name):
        if name in READS:
            return {}
        if name == "document.annotation-font-set":
            return {"field": "bold", "value": True, "expected_font": deepcopy(self.font)}
        if name == "document.display-option-set":
            old = self.options["grid.display"]["value"]
            return {"field": "grid.display", "value": not old, "expected_value": old}
        return {"value": "iso", "expected_snapshot": deepcopy(self.snapshot)}

    def success(self, name, *, document=None):
        result = {"ok": True, "action": name}
        if name.startswith("document.annotation-font"):
            result.update(font=deepcopy(self.font), native_font=deepcopy(self.native_font))
            if name in WRITES:
                result.update(field="bold", before=deepcopy(self.font),
                              native_before=deepcopy(self.native_font), changed=True,
                              mutation={"attempted": True, "may_have_changed": True},
                              native_normalizations=[])
                result["font"]["bold"] = result["native_font"]["Bold"] = True
                result["observed_font"] = deepcopy(result["font"])
                result["observed_native_font"] = deepcopy(result["native_font"])
        elif name.startswith("document.display-"):
            result["options"] = deepcopy(self.options)
            if name in WRITES:
                result.update(field="grid.display", before=deepcopy(self.options), changed=True,
                              mutation={"attempted": True, "may_have_changed": True})
                target = not self.options["grid.display"]["value"]
                result["options"]["grid.display"] = {"value": target, "native_value": target}
                result["observed_options"] = deepcopy(result["options"])
        else:
            after = deepcopy(self.snapshot)
            if name in WRITES:
                after["standard"] = {"value": "iso", "native_value": 2}
                result.update(before=deepcopy(self.snapshot), after=deepcopy(after),
                              final=deepcopy(after), observed_defaults_changed=False,
                              changed=True, mutation={"attempted": True, "may_have_changed": True})
            result.update(after)
        if name in WRITES:
            entry = self.documents.register(self.document if document is None else document)
            result["document"] = self.documents.describe(entry, session_id="writer")
            result["document"]["modified"] = True
        return result

    def call(self, name, *, parameters=None, session="writer", selector=None,
             stamp=19, lease=None):
        return execute_operation(
            self.app, name, self.parameters(name) if parameters is None else parameters,
            documents=self.documents, session_id=session,
            document_id=self.entry.document_id if selector is None else selector,
            expected_update_stamp=stamp,
            lease_id=lease)

    def assert_adapter_call(self, adapter, name, parameters, document):
        adapter.assert_called_once_with(app=self.app, document=document, **parameters)

    def assert_selection(self, result, entry, session, *, current, active):
        self.assertEqual(result["session_id"], session)
        self.assertEqual(result["document"]["document_id"], entry.document_id)
        self.assertIs(result["document"]["current"], current)
        self.assertIs(result["document"]["active"], active)
        self.assertIs(self.app.ActiveDoc, self.foreground)
        self.app.ActivateDoc3.assert_not_called()

    def test_three_reads_select_background_and_preserve_session_current(self):
        for name in READS:
            with self.subTest(operation=name), mock.patch.object(
                    operations, HOST_FUNCTIONS[name], return_value=self.success(name)) as adapter:
                result = self.call(name, session="reader")
                self.assert_adapter_call(adapter, name, {}, self.document)
                self.assert_selection(result, self.entry, "reader", current=False, active=False)
                self.assertIs(self.documents.resolve(None, session_id="reader"), self.front_entry)
                validate_operation_result(name, result)

    def test_three_writes_forward_exact_cas_and_selected_background_context(self):
        for name in WRITES:
            with self.subTest(operation=name):
                parameters = self.parameters(name)
                with mock.patch.object(operations, HOST_FUNCTIONS[name], return_value=self.success(name)) as adapter:
                    result = self.call(name, parameters=parameters, lease=self.lease["lease_id"])
                self.assert_adapter_call(adapter, name, parameters, self.document)
                self.assert_selection(result, self.entry, "writer", current=False, active=False)
                self.assertIs(self.documents.resolve(None, session_id="writer"), self.front_entry)
                validate_operation_result(name, result)

    def test_all_six_resolve_session_current_and_active_without_activation(self):
        self.documents.set_current(self.entry, session_id="writer")
        for name in HOST_FUNCTIONS:
            for selector in (None, "active"):
                with self.subTest(operation=name, selector=selector):
                    target = self.entry if selector is None else self.front_entry
                    parameters = self.parameters(name)
                    with mock.patch.object(operations, HOST_FUNCTIONS[name], return_value=self.success(name, document=target.document)) as adapter:
                        result = execute_operation(
                            self.app, name, parameters, documents=self.documents,
                            session_id="writer", document_id=selector,
                            expected_update_stamp=19 if target is self.entry else 8,
                            lease_id=(self.lease if target is self.entry else self.front_lease)["lease_id"] if name in WRITES else None)
                    self.assert_adapter_call(adapter, name, parameters, target.document)
                    self.assert_selection(result, target, "writer",
                                          current=target is self.entry, active=target is self.front_entry)
                    self.assertIs(self.documents.resolve(None, session_id="writer"), self.entry)

    def test_write_lease_conflicts_are_rejected_before_any_adapter(self):
        for name in WRITES:
            for session, lease in (("other", self.lease["lease_id"]),
                                   ("writer", self.front_lease["lease_id"])):
                with self.subTest(operation=name, session=session, lease=lease), mock.patch.object(
                        operations, HOST_FUNCTIONS[name]) as adapter:
                    with self.assertRaises(DocumentLeaseConflict):
                        execute_operation(self.app, name, self.parameters(name),
                            documents=self.documents, session_id=session, document_id=self.entry.document_id,
                            expected_update_stamp=self.stamp, lease_id=lease)
                    adapter.assert_not_called()
                    self.app.ActivateDoc3.assert_not_called()

    def test_stamp_conflicts_and_unknown_document_precede_all_six_adapters(self):
        for name in HOST_FUNCTIONS:
            with self.subTest(operation=name), mock.patch.object(operations, HOST_FUNCTIONS[name]) as adapter:
                with self.assertRaises(DocumentUpdateConflict):
                    self.call(name, stamp=0, lease=self.lease["lease_id"] if name in WRITES else None)
                with self.assertRaises(DocumentNotFound):
                    self.call(name, selector="d-000000", lease=self.lease["lease_id"] if name in WRITES else None)
                adapter.assert_not_called()
                self.app.ActivateDoc3.assert_not_called()

    def test_zero_stamp_is_valid_and_not_treated_as_missing(self):
        self.stamp = 0
        for name in HOST_FUNCTIONS:
            with self.subTest(operation=name), mock.patch.object(
                    operations, HOST_FUNCTIONS[name], return_value=self.success(name)) as adapter:
                result = self.call(name, stamp=0, lease=self.lease["lease_id"] if name in WRITES else None)
                self.assertTrue(result["ok"])
                adapter.assert_called_once()

    def test_write_required_context_and_private_injections_refused_before_adapter(self):
        for name in WRITES:
            with self.subTest(operation=name), mock.patch.object(operations, HOST_FUNCTIONS[name]) as adapter:
                with self.assertRaises(ValueError):
                    self.call(name, stamp=None, lease=self.lease["lease_id"])
                for key in ("snapshot_reader", "_preference_ids", "native_preference", "option"):
                    parameters = {**self.parameters(name), key: {}}
                    with self.assertRaises(ValueError):
                        self.call(name, parameters=parameters, lease=self.lease["lease_id"])
                adapter.assert_not_called()
        # Required tokens apply even when the registry has no active lease;
        # missing-lease rejection must happen before reaching any host adapter.
        for active in (True, False):
            if not active:
                self.documents.release_lease(self.lease["lease_id"], session_id="writer")
            for name in WRITES:
                with self.subTest(operation=name, active_lease=active), mock.patch.object(
                        operations, HOST_FUNCTIONS[name]) as adapter:
                    with self.assertRaisesRegex(ValueError, "requires lease_id"):
                        self.call(name, lease=None)
                    adapter.assert_not_called()
                    self.app.ActivateDoc3.assert_not_called()

    def test_partial_host_failure_and_native_metadata_are_not_rewritten(self):
        for name in WRITES:
            with self.subTest(operation=name):
                partial = {
                    "ok": False, "action": name,
                    "error": {"type": "NativePreferenceFailure", "message": "first cause"},
                    "mutation": {"attempted": True, "may_have_changed": True},
                    "document": {"title": "native partial title", "path": "", "type": 1,
                                 "modified": True, "update_stamp": 23, "current": True, "active": True},
                }
                with mock.patch.object(operations, HOST_FUNCTIONS[name], return_value=partial) as adapter:
                    result = self.call(name, lease=self.lease["lease_id"])
                self.assertIs(result, partial)
                self.assertFalse(result["ok"])
                self.assertEqual(result["error"]["message"], "first cause")
                self.assertEqual(result["mutation"], {"attempted": True, "may_have_changed": True})
                self.assertEqual(result["document"]["title"], "native partial title")
                self.assertTrue(result["document"]["modified"])
                self.assertEqual(result["document"]["update_stamp"], 23)
                self.assert_selection(result, self.entry, "writer", current=False, active=False)
                self.assertEqual(adapter.call_count, 1)
                validate_operation_result(name, result)

    def test_missing_registry_or_entry_is_refused_without_falling_back_to_active_doc(self):
        for name in HOST_FUNCTIONS:
            for documents, entry in ((None, None), (self.documents, None)):
                with self.subTest(operation=name, registry=documents is not None), mock.patch.object(
                        operations, HOST_FUNCTIONS[name]) as adapter:
                    context = OperationContext(self.app, name, documents, "writer",
                                               self.entry.document_id, self.lease["lease_id"], entry)
                    with self.assertRaisesRegex(RuntimeError, "registry"):
                        getattr(operations, OPERATION_CATALOG[name].handler)(context, self.parameters(name))
                    adapter.assert_not_called()

    def test_catalog_capabilities_and_generic_mcp_execute_reach_same_six_handlers(self):
        # Construct only the metadata capability shell, never WorkerManager.__init__
        # (which launches a worker). This remains an in-process routing test.
        worker = WorkerManager.__new__(WorkerManager)
        worker.health = mock.Mock(return_value={"worker_alive": True, "host_connected": True, "host": {}})
        with mock.patch("swcli.mcp.DaemonManager") as manager_class:
            bridge = DaemonBridge(session_id="unused-default")
            manager = manager_class.return_value
            def transport(name, parameters, **context):
                if name == "daemon.capabilities":
                    payload = worker.capabilities(**parameters)
                else:
                    payload = execute_operation(
                        self.app, name, parameters, documents=self.documents,
                        session_id=context["session_id"], document_id=context["document_id"],
                        expected_update_stamp=context["expected_update_stamp"], lease_id=context.get("lease_id"))
                return {"api_version": PROTOCOL_VERSION, "request_id": context["request_id"],
                        "success": True, "duration_ms": 0, "result": payload}
            with mock.patch("swcli.mcp.call_daemon", side_effect=transport):
                for name in HOST_FUNCTIONS:
                    with self.subTest(operation=name):
                        spec = OPERATION_CATALOG[name]
                        self.assertTrue(spec.selected_document)
                        self.assertEqual(spec.lease_guarded, name in WRITES)
                        self.assertFalse(spec.temporary_activation)
                        capability = bridge.call("capabilities", {"operation": name})
                        self.assertTrue(capability["success"], capability)
                        self.assertEqual(capability["result"]["operations"], [name])
                        self.assertEqual(capability["result"]["operation_schemas"][name], spec.parameters)
                        parameters = self.parameters(name)
                        arguments = {"operation": name, "parameters": parameters,
                                     "session_id": "writer", "document_id": self.entry.document_id,
                                     "expected_update_stamp": 19, "request_id": "preference-route"}
                        if name in WRITES:
                            arguments["lease_id"] = self.lease["lease_id"]
                        with mock.patch.object(operations, HOST_FUNCTIONS[name], return_value=self.success(name)) as adapter:
                            response = bridge.call("execute", arguments)
                        self.assertTrue(response["success"], response)
                        self.assert_adapter_call(adapter, name, parameters, self.document)
                        self.assert_selection(response["result"], self.entry, "writer", current=False, active=False)
                        validate_operation_result(name, response["result"])
            manager.start.assert_not_called()
            manager.stop.assert_not_called()


if __name__ == "__main__":
    unittest.main()
