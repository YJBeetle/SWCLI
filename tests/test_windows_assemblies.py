import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from jsonschema import Draft202012Validator

from swcli.cli import build_parser, _typed_operation, translate_parameter_paths
from swcli.daemon import operations
from swcli.daemon.documents import DocumentRegistry, DocumentLeaseConflict
from swcli.hosts import windows_assemblies, windows_parts
from swcli.operation_schemas import OPERATION_CATALOG, validate_operation_request
from swcli.result_schemas import validate_operation_result


def document(path="", kind=2):
    # Real ModelDoc2/AssemblyDoc surface, not a dynamic mock that can fabricate
    # GetReadOnlyState or another nonexistent native API.
    result = mock.Mock(spec_set=[
        "_oleobj_", "GetTitle", "GetPathName", "GetType", "GetSaveFlag", "GetUpdateStamp",
        "IsOpenedReadOnly", "IsOpenedViewOnly", "GetEditTarget", "GetEditTargetComponent",
        "GetComponents", "AddComponent5", "GetConfigurationByName",
        "ShowConfiguration2", "Save3", "SaveAs3",
    ])
    result.GetTitle = lambda: Path(path).name or "Assembly1"
    result.GetPathName = lambda: path
    result.GetType = lambda: kind
    result.GetSaveFlag = lambda: False
    result.GetUpdateStamp = lambda: 3
    result.IsOpenedReadOnly = lambda: False
    result.IsOpenedViewOnly = lambda: False
    result.GetEditTarget = lambda: result
    root = mock.Mock(spec_set=["_oleobj_", "IsRoot"])
    root.IsRoot = lambda: True
    result.GetEditTargetComponent = lambda: root
    return result


class AssemblyCreationTests(unittest.TestCase):
    @mock.patch.object(windows_assemblies.sys, "platform", "win32")
    def test_real_assembly_template_creates_exact_unsaved_handle(self):
        with tempfile.TemporaryDirectory() as directory:
            template = Path(directory).resolve() / "Assembly.ASMDOT"
            template.touch()
            app = mock.Mock()
            created = document()
            app.NewDocument.return_value = created
            result, handle = windows_assemblies.create_assembly_windows_with_handle(
                app=app, template=str(template)
            )
            self.assertIs(handle, created)
            self.assertTrue(result["ok"])
            self.assertEqual(result["document"]["type"], 2)
            app.NewDocument.assert_called_once_with(str(template), 0, 0.0, 0.0)
            created.Save3.assert_not_called()
            created.SaveAs3.assert_not_called()
            validate_operation_result("document.create", result)

    def test_default_preference_and_installed_discovery_use_assembly_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            template = root / "SOLIDWORKS" / "templates" / "Assembly.asmdot"
            template.parent.mkdir(parents=True)
            template.touch()
            (template.parent / "Part.prtdot").touch()
            app = mock.Mock()
            app.GetUserPreferenceStringValue.return_value = str(template)
            result = windows_parts._resolve_document_template(app, None, kind="assembly")
            self.assertEqual(result["path"], str(template))
            app.GetUserPreferenceStringValue.assert_called_once_with(9)
            app.GetUserPreferenceStringValue.return_value = ""
            with mock.patch.dict(windows_parts.os.environ, {"PROGRAMDATA": directory}, clear=True):
                result = windows_parts._resolve_document_template(app, None, kind="assembly")
            self.assertTrue(result["ok"])
            self.assertEqual(result["path"], str(template))
            self.assertEqual(result["source"], "installed-template-discovery")

    @mock.patch.object(windows_assemblies.sys, "platform", "win32")
    def test_bad_or_missing_template_never_launches_ui(self):
        app = mock.Mock()
        for path, error in (("missing.asmdot", "AssemblyTemplateUnavailable"), ("Part.prtdot", "InvalidAssemblyTemplate")):
            with self.subTest(path=path):
                result, handle = windows_assemblies.create_assembly_windows_with_handle(app=app, template=path)
                self.assertIsNone(handle)
                self.assertEqual(result["error"]["type"], error)
                app.NewDocument.assert_not_called()
                validate_operation_result("document.create", result)

    @mock.patch.object(windows_assemblies.sys, "platform", "win32")
    @mock.patch.object(windows_assemblies, "_resolve_document_template")
    def test_null_wrong_type_and_com_failure_preserve_handles(self, resolve):
        resolve.return_value = {"ok": True, "path": "Assembly.asmdot", "source": "explicit"}
        app = mock.Mock()
        for handle, code in ((None, "NewDocumentFailed"), (document(kind=1), "UnexpectedDocumentType")):
            app.NewDocument.return_value = handle
            result, actual = windows_assemblies.create_assembly_windows_with_handle(app=app)
            self.assertIs(actual, handle)
            self.assertEqual(result["error"]["type"], code)
            validate_operation_result("document.create", result)
        app.NewDocument.side_effect = RuntimeError("native failure")
        result, handle = windows_assemblies.create_assembly_windows_with_handle(app=app)
        self.assertIsNone(handle)
        self.assertEqual(result["error"]["type"], "RuntimeError")


class ComponentInsertionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name).resolve() / "saved part.SLDPRT"
        self.path.write_bytes(b"saved native part")
        self.source = document(str(self.path), 1)
        self.target = document()
        self.component = mock.Mock()
        self.component.Name2 = "saved part-1"
        self.component.GetPathName = lambda: str(self.path)
        self.component.ReferencedConfiguration = "Default"
        self.target.AddComponent5.return_value = self.component
        self.target.GetComponents.side_effect = [(), (self.component,)]
        self.app = mock.Mock()
        self.app.GetOpenDocumentByName.return_value = self.source
        self.app.IsSame.side_effect = lambda a, b: int(a is b)

    def insert(self, **keywords):
        return windows_assemblies.add_part_component_windows(
            app=self.app, document=self.target, path=str(self.path), **keywords
        )

    def test_inserts_once_with_explicit_mm_and_verifies_identity(self):
        result = self.insert(configuration="Default", x_mm=12, y_mm=-3, z_mm=0)
        self.assertTrue(result["ok"], result)
        self.target.AddComponent5.assert_called_once_with(str(self.path), 0, "", True, "Default", .012, -.003, 0)
        self.assertEqual(result["component_count_after"], 1)
        self.assertEqual(result["placement"]["unit"], "millimeter")
        validate_operation_result("assembly.add-component", result)
        self.source.Save3.assert_not_called()
        self.source.ShowConfiguration2.assert_not_called()
        self.source.SaveAs3.assert_not_called()
        self.app.OpenDoc6.assert_not_called()

    def test_default_configuration_uses_native_saved_configuration(self):
        result = self.insert()
        self.assertTrue(result["ok"])
        self.target.AddComponent5.assert_called_once_with(str(self.path), 0, "", False, "", 0, 0, 0)
        self.source.GetConfigurationByName.assert_not_called()

    def test_preconditions_reject_before_native_insertion(self):
        cases = (
            (self.target, "GetType", lambda: 1, "UnsupportedDocumentType"),
            (self.target, "IsOpenedReadOnly", lambda: True, "DocumentReadOnly"),
            (self.target, "IsOpenedViewOnly", lambda: True, "DocumentViewOnly"),
            (self.source, "GetType", lambda: 2, "UnsupportedComponentType"),
            (self.source, "GetSaveFlag", lambda: True, "ComponentModified"),
            (self.source, "GetPathName", lambda: "other.SLDPRT", "ComponentPathMismatch"),
        )
        for obj, member, value, code in cases:
            with self.subTest(code=code), mock.patch.object(obj, member, value):
                result = self.insert()
                self.assertEqual(result["error"]["type"], code)
                self.target.AddComponent5.assert_not_called()
                validate_operation_result("assembly.add-component", result)

    def test_root_component_is_not_in_context_component_editing(self):
        root = self.target.GetEditTargetComponent()
        self.assertIsNotNone(root)
        self.assertTrue(root.IsRoot())
        result = self.insert()
        self.assertTrue(result["ok"], result)
        self.target.AddComponent5.assert_called_once()

    def test_null_component_requires_proven_self_edit_target(self):
        self.target.GetEditTargetComponent = lambda: None
        result = self.insert()
        self.assertTrue(result["ok"], result)
        self.target.AddComponent5.assert_called_once()

    def test_part_or_subassembly_edit_target_blocks_insertion(self):
        for kind in (1, 2):
            with self.subTest(kind=kind), mock.patch.object(
                self.target, "GetEditTarget", lambda: document(kind=kind)
            ):
                result = self.insert()
                self.assertEqual(result["error"]["type"], "ComponentEditInProgress")
                self.target.AddComponent5.assert_not_called()
                validate_operation_result("assembly.add-component", result)
        component = mock.Mock(spec_set=["_oleobj_", "IsRoot"])
        component.IsRoot = lambda: False
        self.target.GetEditTargetComponent = lambda: component
        result = self.insert()
        self.assertEqual(result["error"]["type"], "ComponentEditInProgress")
        self.target.AddComponent5.assert_not_called()

    def test_unknown_edit_target_identity_never_means_self_editing(self):
        for value in (None, 2, -1, True, "1", mock.Mock()):
            with self.subTest(value=value), mock.patch.object(self.app, "IsSame", lambda a, b: value):
                result = self.insert()
                self.assertEqual(result["error"]["type"], "DocumentStateUnavailable")
                self.target.AddComponent5.assert_not_called()
                validate_operation_result("assembly.add-component", result)
        with mock.patch.object(self.app, "IsSame", mock.Mock(spec=lambda a, b: None, side_effect=RuntimeError("identity failed"))):
            result = self.insert()
            self.assertEqual(result["error"]["type"], "DocumentStateUnavailable")
            self.assertEqual(result["error"]["cause"]["type"], "RuntimeError")
            self.target.AddComponent5.assert_not_called()
        self.target.GetEditTarget = lambda: None
        result = self.insert()
        self.assertEqual(result["error"]["type"], "DocumentStateUnavailable")
        self.target.AddComponent5.assert_not_called()

    def test_missing_failed_or_unknown_editing_native_getter_is_fail_closed(self):
        for member in ("GetEditTarget", "GetEditTargetComponent"):
            native_getter = getattr(self.target, member)
            delattr(self.target, member)
            try:
                result = self.insert()
                self.assertEqual(result["error"]["type"], "DocumentStateUnavailable")
                self.assertEqual(result["error"]["cause"]["type"], "AttributeError")
                self.target.AddComponent5.assert_not_called()
            finally:
                setattr(self.target, member, native_getter)
            with mock.patch.object(self.target, member, mock.Mock(spec=lambda: None, side_effect=RuntimeError("COM failed"))):
                result = self.insert()
                self.assertEqual(result["error"]["type"], "DocumentStateUnavailable")
                self.target.AddComponent5.assert_not_called()
        component = mock.Mock(spec_set=["_oleobj_", "IsRoot"])
        self.target.GetEditTargetComponent = lambda: component
        for value in (None, 0, 1, "true", mock.Mock()):
            with self.subTest(value=value):
                component.IsRoot = lambda: value
                result = self.insert()
                self.assertEqual(result["error"]["type"], "DocumentStateUnavailable")
                self.target.AddComponent5.assert_not_called()
        del component.IsRoot
        result = self.insert()
        self.assertEqual(result["error"]["type"], "DocumentStateUnavailable")
        self.assertEqual(result["error"]["cause"]["type"], "AttributeError")
        self.target.AddComponent5.assert_not_called()
        component.IsRoot = mock.Mock(spec=lambda: None, side_effect=RuntimeError("root getter failed"))
        result = self.insert()
        self.assertEqual(result["error"]["type"], "DocumentStateUnavailable")
        self.target.AddComponent5.assert_not_called()

    def test_unloaded_and_unknown_configuration_do_not_mutate_source(self):
        self.app.GetOpenDocumentByName.return_value = None
        self.assertEqual(self.insert()["error"]["type"], "ComponentNotLoaded")
        self.app.GetOpenDocumentByName.return_value = self.source
        self.source.GetConfigurationByName.return_value = None
        self.assertEqual(self.insert(configuration="absent")["error"]["type"], "ConfigurationNotFound")
        self.target.AddComponent5.assert_not_called()

    def test_missing_unreadable_or_nonboolean_native_mode_is_fail_closed(self):
        self.assertFalse(hasattr(self.target, "GetReadOnlyState"))
        for member in ("IsOpenedReadOnly", "IsOpenedViewOnly"):
            for value in (None, 0, 1, -1, "false", mock.Mock()):
                with self.subTest(member=member, value=value), mock.patch.object(
                    self.target, member, lambda: value
                ):
                    result = self.insert()
                    self.assertEqual(result["error"]["type"], "DocumentStateUnavailable")
                    self.target.AddComponent5.assert_not_called()
                    validate_operation_result("assembly.add-component", result)
            native_getter = getattr(self.target, member)
            delattr(self.target, member)
            try:
                result = self.insert()
                self.assertEqual(result["error"]["type"], "DocumentStateUnavailable")
                self.assertEqual(result["error"]["cause"]["type"], "AttributeError")
                self.target.AddComponent5.assert_not_called()
            finally:
                setattr(self.target, member, native_getter)
            for exc in (AttributeError("native getter missing"), RuntimeError("COM getter failed")):
                with self.subTest(member=member, exception=exc), mock.patch.object(
                    self.target, member, mock.Mock(spec=lambda: None, side_effect=exc)
                ):
                    result = self.insert()
                    self.assertEqual(result["error"]["type"], "DocumentStateUnavailable")
                    self.assertEqual(result["error"]["cause"]["type"], type(exc).__name__)
                    self.target.AddComponent5.assert_not_called()
                    validate_operation_result("assembly.add-component", result)

    def test_invalid_file_and_nonfinite_position(self):
        for value in (float("inf"), float("nan")):
            self.assertEqual(self.insert(x_mm=value)["error"]["type"], "InvalidArgument")
        self.path.unlink()
        self.assertEqual(self.insert()["error"]["type"], "ComponentFileUnavailable")
        self.path.touch()
        self.assertEqual(self.insert()["error"]["type"], "ComponentFileUnavailable")
        self.target.AddComponent5.assert_not_called()

    def test_unreadable_source_modified_state_does_not_insert(self):
        for value in (None, 0, 1, "false", mock.Mock()):
            with self.subTest(value=value), mock.patch.object(self.source, "GetSaveFlag", lambda: value):
                result = self.insert()
                self.assertEqual(result["error"]["type"], "ComponentStateUnavailable")
                self.target.AddComponent5.assert_not_called()
                validate_operation_result("assembly.add-component", result)
        with mock.patch.object(self.source, "GetSaveFlag", mock.Mock(spec=lambda: None, side_effect=AttributeError("missing"))):
            result = self.insert()
            self.assertEqual(result["error"]["type"], "ComponentStateUnavailable")
            self.assertEqual(result["error"]["cause"]["type"], "AttributeError")
            self.target.AddComponent5.assert_not_called()

    def test_native_component_array_unknown_type_is_not_an_empty_assembly(self):
        for value in (0, "", "components", mock.Mock()):
            with self.subTest(value=value):
                self.target.GetComponents.side_effect = [value]
                result = self.insert()
                self.assertEqual(result["error"]["type"], "AssemblyObservationUnavailable")
                self.target.AddComponent5.assert_not_called()
        self.target.GetComponents.side_effect = [(), "unreadable"]
        result = self.insert()
        self.assertTrue(result["inserted"])
        self.assertEqual(result["error"]["type"], "AssemblyObservationUnavailable")
        self.target.AddComponent5.assert_called_once()
        validate_operation_result("assembly.add-component", result)

    def test_null_insertion_and_native_exception_are_not_retried(self):
        self.target.AddComponent5.return_value = None
        result = self.insert()
        self.assertEqual(result["error"]["type"], "ComponentInsertionFailed")
        self.target.AddComponent5.assert_called_once()
        self.target.AddComponent5.reset_mock(side_effect=True)
        self.target.GetComponents.side_effect = [()]
        self.target.AddComponent5.side_effect = RuntimeError("COM failed")
        self.assertEqual(self.insert()["error"]["type"], "RuntimeError")
        self.target.AddComponent5.assert_called_once()

    def test_post_mutation_verification_failures_preserve_evidence(self):
        for case in ("count", "identity", "configuration", "path", "name"):
            with self.subTest(case=case):
                self.target.GetComponents.side_effect = [(), () if case == "count" else (self.component,)]
                self.app.IsSame.side_effect = lambda a, b: 0 if case == "identity" and b is self.component else int(a is b)
                self.component.Name2 = "" if case == "name" else "saved part-1"
                self.component.ReferencedConfiguration = "other" if case == "configuration" else "Default"
                self.component.GetPathName = lambda: "other.SLDPRT" if case == "path" else str(self.path)
                result = self.insert(configuration="Default")
                self.assertTrue(result["inserted"])
                self.assertEqual(result["error"]["type"], "ComponentVerificationFailed")
                validate_operation_result("assembly.add-component", result)


class AssemblyContractTests(unittest.TestCase):
    def test_cli_maps_create_and_insertion_with_selector_context(self):
        parser = build_parser()
        creation = _typed_operation(parser.parse_args(["document", "create", "--type", "assembly", "--template", "Assembly.asmdot"]))
        self.assertEqual(creation[0:2], ("document.create", {"type": "assembly", "template": "Assembly.asmdot"}))
        request = _typed_operation(parser.parse_args(["assembly", "add-component", "part.SLDPRT", "--document", "d-ab12cd", "--lease", "l-ab12cd34ef56", "--if-update-stamp", "3", "--x-mm", "12", "--configuration", "Default", "--json"]))
        self.assertEqual(request[0], "assembly.add-component")
        self.assertEqual(request[1], {"path": "part.SLDPRT", "configuration": "Default", "x_mm": 12, "y_mm": 0, "z_mm": 0})
        self.assertEqual(request[2:], (True, "d-ab12cd", 3, "l-ab12cd34ef56"))
        with mock.patch.dict("os.environ", {"SWCLI_PATH_TRANSLATE_CMD": "winepath-helper"}), mock.patch("swcli.cli.subprocess.check_output", return_value="Z:\\part.SLDPRT\n") as translate:
            translate_parameter_paths(request[1])
        translate.assert_called_once_with(["winepath-helper", "part.SLDPRT"], text=True)

    def test_catalog_and_finite_request_contract(self):
        spec = OPERATION_CATALOG["assembly.add-component"]
        self.assertTrue(spec.selected_document and spec.lease_guarded and spec.temporary_activation)
        self.assertEqual(spec.handler, "assembly_add_component")
        Draft202012Validator.check_schema(spec.parameters)
        for values in ({}, {"path": ""}, {"path": "part", "x_mm": True}, {"path": "part", "y_mm": float("inf")}, {"path": "part", "rotation": 1}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                validate_operation_request("assembly.add-component", values)

    @mock.patch("swcli.daemon.operations.create_assembly_windows_with_handle")
    def test_creation_registers_exact_assembly_for_calling_session(self, create):
        previous, created = document("old.SLDASM"), document()
        app = mock.Mock()
        app.GetDocuments = lambda: (previous, created)
        app.ActiveDoc = previous
        registry = DocumentRegistry(app)
        registry.set_current(registry.register(previous), session_id="other")
        create.return_value = ({"ok": True, "action": "document.create", "created": True}, created)
        result = operations.execute_operation(app, "document.create", {"type": "assembly"}, documents=registry, session_id="builder")
        self.assertIs(registry.resolve(None, session_id="builder").document, created)
        self.assertIs(registry.resolve(None, session_id="other").document, previous)
        self.assertTrue(result["document"]["current"])

    @mock.patch("swcli.daemon.operations.add_part_component_windows")
    def test_target_lease_guard_and_temporary_activation_keep_current(self, insert):
        target, foreground = document("target.SLDASM"), document("part.SLDPRT", 1)
        app = mock.Mock()
        app.GetDocuments = lambda: (target, foreground)
        app.ActiveDoc = foreground
        registry = DocumentRegistry(app)
        entry = registry.register(target)
        registry.set_current(registry.register(foreground), session_id="builder")
        lease = registry.acquire_lease(entry, session_id="builder", ttl_seconds=60)
        with self.assertRaises(DocumentLeaseConflict):
            operations.execute_operation(app, "assembly.add-component", {"path": "part.SLDPRT"}, documents=registry, document_id=entry.document_id, session_id="other")
        insert.assert_not_called()
        activated = []

        @contextmanager
        def activate(selected):
            activated.append(selected)
            yield []

        insert.return_value = {"ok": False, "action": "assembly.add-component", "error": {"type": "ComponentNotLoaded", "message": "open PRT"}}
        with mock.patch.object(registry, "temporarily_activate", activate):
            result = operations.execute_operation(app, "assembly.add-component", {"path": "part.SLDPRT"}, documents=registry, document_id=entry.document_id, session_id="builder", lease_id=lease["lease_id"], expected_update_stamp=3)
        self.assertEqual(activated, [entry])
        insert.assert_called_once_with(app=app, document=target, path="part.SLDPRT")
        self.assertFalse(result["document"]["current"])
        self.assertIs(registry.resolve(None, session_id="builder").document, foreground)


if __name__ == "__main__":
    unittest.main()
