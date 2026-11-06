"""Portable image-quality safety/contracts; these mocks are not native evidence."""
from copy import deepcopy
import json
import math
import os
from types import SimpleNamespace
import unittest
from unittest import mock

from swcli.cli import _typed_operation, build_parser
from swcli.daemon.documents import DocumentLeaseConflict, DocumentRegistry
from swcli.daemon.operations import DocumentUpdateConflict, execute_operation
from swcli.document_image_quality import quality_snapshot, validate_quality
from swcli.hosts import windows_document_image_quality as adapter
from swcli.operation_schemas import OPERATION_CATALOG, validate_operation_request
from swcli.result_schemas import validate_operation_result


def snapshot():
    return quality_snapshot(dict(shaded_mode=3, shaded_deviation_m=0.0002,
        optimize_edge_length=False, save_tessellation=True, apply_to_referenced_parts=False),
        dict(status=0, bounds_m=[0.00001, 0.001]))


class ImageQualityTests(unittest.TestCase):
    def setUp(self):
        env = mock.patch.dict(os.environ, SWCLI_IMAGE_QUALITY_CALIBRATION="1")
        env.start(); self.addCleanup(env.stop)
        self.native = {44: 3, 32: 0.0002, 210: False, 255: True, 158: False}
        self.modified = False
        self.configuration = SimpleNamespace(Name="Default")
        self.extension = SimpleNamespace()
        for kind in ("Integer", "Double", "Toggle"):
            setattr(self.extension, "GetUserPreference" + kind, mock.Mock(side_effect=lambda p, o: self.native[p]))
            setattr(self.extension, "SetUserPreference" + kind, mock.Mock(side_effect=self.apply))
        self.document = SimpleNamespace(GetType=lambda: 1, GetUpdateStamp=lambda: 7,
            GetSaveFlag=lambda: self.modified, GetActiveConfiguration=lambda: self.configuration,
            GetPathName=lambda: "", GetTitle=lambda: "Background", IsOpenedReadOnly=lambda: False,
            IsOpenedViewOnly=lambda: False, SketchManager=SimpleNamespace(ActiveSketch=None),
            Extension=self.extension, SetSaveFlag=mock.Mock(side_effect=lambda: setattr(self, "modified", True)))
        self.foreground = SimpleNamespace(GetType=lambda: 1, GetSaveFlag=lambda: False,
            GetUpdateStamp=lambda: 8, GetTitle=lambda: "Foreground", GetPathName=lambda: "",
            GetActiveConfiguration=lambda: SimpleNamespace(Name="ForegroundDefault"),
            IsOpenedReadOnly=lambda: False, IsOpenedViewOnly=lambda: False)
        self.app = SimpleNamespace(ActiveDoc=self.foreground, GetDocuments=lambda: (self.document, self.foreground),
            IsSame=lambda a,b: int(a is b), ActivateDoc3=mock.Mock())
        self.registry = DocumentRegistry(self.app)
        self.entry = self.registry.register(self.document)
        foreground = self.registry.register(self.foreground)
        self.registry.set_current(foreground, session_id="reader")
        self.lease = self.registry.acquire_lease(self.entry, session_id="writer", ttl_seconds=60)["lease_id"]
        ranges = mock.patch.object(adapter, "_range", side_effect=lambda extension: (0, self.native[32], 0.00001, 0.001))
        self.ranges = ranges.start(); self.addCleanup(ranges.stop)

    def apply(self, preference, option, value):
        self.native[preference] = value
        if preference == 32:
            self.native[44] = 3
        return True

    def operation(self, name, params=None, **context):
        return execute_operation(self.app, name, params or {}, documents=self.registry,
            document_id=self.entry.document_id, session_id=context.get("session", "writer"),
            expected_update_stamp=context.get("stamp", 7), lease_id=context.get("lease", self.lease) if name.endswith("-set") else None)

    def edit(self, field="optimize_edge_length", value=True, expected=None, **context):
        return self.operation("document.image-quality-set", dict(field=field, value=value,
            expected_quality=snapshot() if expected is None else expected), **context)

    def assert_no_mutation(self):
        for kind in ("Integer", "Double", "Toggle"):
            getattr(self.extension, "SetUserPreference" + kind).assert_not_called()
        self.document.SetSaveFlag.assert_not_called()
        self.app.ActivateDoc3.assert_not_called()

    def test_read_background_complete_raw_snapshot_under_other_session(self):
        result = self.operation("document.image-quality", session="reader")
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["quality"], snapshot())
        validate_operation_result("document.image-quality", result)
        self.assertFalse(result["document"]["active"] or result["document"]["current"])
        self.assert_no_mutation()

    def test_writes_are_closed_by_default_before_native_access(self):
        with mock.patch.dict(os.environ, SWCLI_IMAGE_QUALITY_CALIBRATION=""):
            result = self.edit()
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["type"], "DocumentImageQualityUnsupported")
        self.extension.GetUserPreferenceInteger.assert_not_called()
        validate_operation_result("document.image-quality-set", result)
        self.assert_no_mutation()

    def test_three_fields_single_document_setter_exact_native_mapping(self):
        for field, value, kind, preference, native in (
            ("shaded_mode", "fine", "Integer", 44, 2),
            ("shaded_deviation_mm", 0.4, "Double", 32, 0.0004),
            ("optimize_edge_length", True, "Toggle", 210, True)):
            with self.subTest(field=field):
                self.setUp()
                result = self.edit(field, value)
                self.assertTrue(result["ok"], result)
                validate_operation_result("document.image-quality-set", result)
                getattr(self.extension, "SetUserPreference" + kind).assert_called_once_with(preference, 0, native)
                self.document.SetSaveFlag.assert_called_once_with()
                self.assertTrue(result["changed"] and result["document"]["modified"])
                self.assertEqual(result["quality"][field], value)
                self.app.ActivateDoc3.assert_not_called()

    def test_same_value_has_zero_setters_and_zero_dirty_mark(self):
        for field in ("shaded_deviation_mm", "optimize_edge_length"):
            result = self.edit(field, snapshot()[field])
            self.assertTrue(result["ok"], result)
            self.assertFalse(result["changed"])
            validate_operation_result("document.image-quality-set", result)
        self.native[44] = 2
        expected = quality_snapshot({**snapshot()["native"], "shaded_mode": 2}, snapshot()["deviation_range"])
        result = self.edit("shaded_mode", "fine", expected)
        self.assertTrue(result["ok"], result)
        self.assertFalse(result["changed"])
        self.assert_no_mutation()

    def test_exact_complete_cas_rejects_nextafter_and_unrequested_member_drift(self):
        for key in ("shaded_deviation_m", "save_tessellation"):
            expected = snapshot()
            expected["native"][key] = math.nextafter(expected["native"][key], math.inf) if key.endswith("_m") else False
            expected = quality_snapshot(expected["native"], expected["deviation_range"])
            result = self.edit(expected=expected)
            self.assertEqual(result["error"]["type"], "DocumentImageQualityConflict")
            self.assert_no_mutation()

    def test_lease_and_stamp_protect_before_native(self):
        with self.assertRaises(DocumentLeaseConflict): self.edit(session="reader")
        with self.assertRaises(DocumentUpdateConflict): self.edit(stamp=6)
        self.extension.GetUserPreferenceInteger.assert_not_called()
        self.assert_no_mutation()

    def test_invalid_profile_context_and_ranges_refuse_without_setter(self):
        defects = [lambda: setattr(self.document, "IsOpenedReadOnly", lambda: True),
            lambda: setattr(self.document, "IsOpenedViewOnly", lambda: True),
            lambda: setattr(self.document.SketchManager, "ActiveSketch", object()),
            lambda: self.native.update({158: True}), lambda: self.native.update({44: 88})]
        for defect in defects:
            with self.subTest(defect=defect):
                self.setUp(); defect()
                result = self.edit()
                self.assertFalse(result["ok"], result); self.assert_no_mutation()
        self.setUp()
        self.document.GetType = lambda: 2
        result = adapter.set_document_image_quality_windows(app=self.app, document=self.document,
            field="optimize_edge_length", value=True, expected_quality=snapshot())
        self.assertFalse(result["ok"]); self.assert_no_mutation()
        self.setUp(); self.native[44] = 1
        result = self.edit("shaded_deviation_mm", 0.4, quality_snapshot({**snapshot()["native"], "shaded_mode":1}, snapshot()["deviation_range"]))
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["quality"]["shaded_mode"], "custom")
        self.assertEqual(result["linked_changes"], [dict(field="shaded_mode", before="coarse", after="custom", reason="shaded-deviation-coupling")])
        self.extension.SetUserPreferenceDouble.assert_called_once_with(32, 0, 0.0004)
        self.extension.SetUserPreferenceInteger.assert_not_called()
        validate_operation_result("document.image-quality-set", result)
        self.setUp()
        self.assertFalse(self.edit("shaded_deviation_mm", 2)["ok"]); self.assert_no_mutation()
        self.ranges.side_effect = lambda e: (1, self.native[32], float("nan"), float("nan"))
        expected = quality_snapshot(snapshot()["native"], dict(status=1, bounds_m=[]))
        self.assertFalse(self.edit("shaded_deviation_mm", 0.4, expected)["ok"]); self.assert_no_mutation()

    def test_false_exception_and_unexpected_native_return_keep_first_failure_single_attempt(self):
        for returned in (False, None, 1, "wrong", object(), float("nan"), RuntimeError("original")):
            with self.subTest(returned=returned):
                self.setUp()
                def setter(*args):
                    self.native[210] = True
                    if isinstance(returned, Exception): raise returned
                    return returned
                self.extension.SetUserPreferenceToggle.side_effect = setter
                result = self.edit()
                self.assertFalse(result["ok"], result)
                self.assertTrue(result["mutation"]["may_have_changed"])
                self.assertIn("original" if isinstance(returned, Exception) else "no retry", result["error"]["message"])
                validate_operation_result("document.image-quality-set", result)
                json.dumps(result, allow_nan=False)
                self.extension.SetUserPreferenceToggle.assert_called_once()
                self.document.SetSaveFlag.assert_not_called()

    def test_context_access_and_state_drift_in_each_read_phase_stop_without_repair(self):
        for phase in (1, 2, 3):
            for defect in (lambda: setattr(self.configuration, "Name", "Other"),
                lambda: setattr(self.app, "ActiveDoc", self.document),
                lambda: setattr(self.document.SketchManager, "ActiveSketch", object()),
                lambda: setattr(self.document, "GetPathName", lambda: "different.SLDPRT"),
                lambda: setattr(self.document, "IsOpenedReadOnly", lambda: True),
                lambda: setattr(self.document, "GetUpdateStamp", lambda: 9)):
                with self.subTest(phase=phase, defect=defect):
                    self.setUp(); count = 0
                    def read(preference, option):
                        nonlocal count
                        if preference == 255:
                            count += 1
                            if count == phase: defect()
                        return self.native[preference]
                    self.extension.GetUserPreferenceToggle.side_effect = read
                    result = self.edit()
                    self.assertFalse(result["ok"], result)
                    self.assertEqual(result["mutation"]["attempted"], phase > 1)
                    self.assertEqual(self.extension.SetUserPreferenceToggle.call_count, int(phase > 1))
                    self.assertEqual(self.document.SetSaveFlag.call_count, int(phase == 3))

    def test_setter_configuration_drift_and_unrequested_changes_are_partial_failures(self):
        for defect in (lambda: setattr(self.configuration, "Name", "Other"),
                       lambda: self.native.update({255: False}),
                       lambda: setattr(self.document, "IsOpenedReadOnly", lambda: True)):
            with self.subTest(defect=defect):
                self.setUp()
                def setter(*args): self.apply(*args); defect(); return True
                self.extension.SetUserPreferenceToggle.side_effect = setter
                result = self.edit()
                self.assertFalse(result["ok"], result)
                self.assertTrue(result["mutation"]["may_have_changed"])
                self.document.SetSaveFlag.assert_not_called()

    def test_unverified_range_coupling_is_rejected_and_deviation_coupling_is_explicit(self):
        def setter(*args): self.apply(*args); self.native[32] = 0.0003; return True
        self.extension.SetUserPreferenceInteger.side_effect = setter
        result = self.edit("shaded_mode", "fine")
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["linked_changes"], [dict(field="shaded_deviation_mm", before=0.2, after=0.3, reason="shaded-mode-coupling")])
        self.setUp()
        def setter(*args):
            self.apply(*args)
            self.ranges.side_effect = lambda e: (0, self.native[32], 0.00002, 0.001)
            return True
        self.extension.SetUserPreferenceInteger.side_effect = setter
        result = self.edit("shaded_mode", "fine")
        self.assertFalse(result["ok"], result)
        self.document.SetSaveFlag.assert_not_called()

    def test_native_invalid_range_or_preference_stops_observation_without_mutation(self):
        for returned in ((-1, 0.0002, 0, 1), (True, 0.0002, 0, 1),
                         (0, 0.0003, 0, 1), (0, 0.0002, float("nan"), 1),
                         (0, 0.0002, 1, 0)):
            with self.subTest(returned=returned):
                self.setUp(); self.ranges.side_effect = None; self.ranges.return_value = returned
                result = self.operation("document.image-quality")
                self.assertFalse(result["ok"], result)
                self.ranges.assert_called_once(); self.assert_no_mutation()
        for preference, value in ((44, True), (32, float("inf")), (210, 0), (255, None)):
            with self.subTest(preference=preference):
                self.setUp(); self.native[preference] = value
                result = self.operation("document.image-quality")
                self.assertFalse(result["ok"], result); self.assert_no_mutation()

    def test_dirty_mutation_identity_drift_or_failure_is_not_repaired(self):
        for defect in (lambda: setattr(self.document, "GetPathName", lambda: "changed.SLDPRT"),
                       lambda: setattr(self.document, "IsOpenedReadOnly", lambda: True),
                       lambda: setattr(self, "modified", False)):
            with self.subTest(defect=defect):
                self.setUp()
                def mark(): self.modified = True; defect()
                self.document.SetSaveFlag.side_effect = mark
                result = self.edit()
                self.assertFalse(result["ok"], result)
                self.assertTrue(result["mutation"]["may_have_changed"])
                self.document.SetSaveFlag.assert_called_once()
                self.extension.SetUserPreferenceToggle.assert_called_once()
                validate_operation_result("document.image-quality-set", result)

    def test_custom_integer_is_rejected_before_native_and_double_requires_custom_readback(self):
        with self.assertRaises(ValueError):
            self.edit("shaded_mode", "custom")
        self.assert_no_mutation()
        self.extension.GetUserPreferenceInteger.assert_not_called()
        self.native[44] = 2
        expected = quality_snapshot({**snapshot()["native"], "shaded_mode": 2}, snapshot()["deviation_range"])
        def ignores_mode(preference, option, value): self.native[preference] = value; return True
        self.extension.SetUserPreferenceDouble.side_effect = ignores_mode
        result = self.edit("shaded_deviation_mm", 0.4, expected)
        self.assertFalse(result["ok"], result)
        self.assertTrue(result["mutation"]["may_have_changed"])
        self.extension.SetUserPreferenceDouble.assert_called_once()
        self.extension.SetUserPreferenceInteger.assert_not_called()
        self.document.SetSaveFlag.assert_not_called()

    def test_foreground_same_handle_state_drift_is_partial_failure_in_every_phase(self):
        defects = {
            "stamp": ("GetUpdateStamp", lambda: 99),
            "dirty": ("GetSaveFlag", lambda: True),
            "title": ("GetTitle", lambda: "Changed"),
            "path": ("GetPathName", lambda: "Changed.SLDPRT"),
            "configuration": ("GetActiveConfiguration", lambda: SimpleNamespace(Name="Changed")),
            "read-only": ("IsOpenedReadOnly", lambda: True),
            "view-only": ("IsOpenedViewOnly", lambda: True),
        }
        for phase in ("before", "setter", "readback", "dirty"):
            for name, (attribute, replacement) in defects.items():
                with self.subTest(phase=phase, defect=name):
                    self.setUp()
                    def defect(): setattr(self.foreground, attribute, replacement)
                    if phase == "setter":
                        def setter(*args): self.apply(*args); defect(); return True
                        self.extension.SetUserPreferenceToggle.side_effect = setter
                    elif phase == "dirty":
                        def dirty(): self.modified = True; defect()
                        self.document.SetSaveFlag.side_effect = dirty
                    else:
                        count = 0
                        def read(preference, option):
                            nonlocal count
                            if preference == 255:
                                count += 1
                                if count == (1 if phase == "before" else 2): defect()
                            return self.native[preference]
                        self.extension.GetUserPreferenceToggle.side_effect = read
                    result = self.edit()
                    self.assertFalse(result["ok"], result)
                    self.assertIn("foreground", result["error"]["message"])
                    self.assertEqual(result["mutation"], dict(attempted=phase != "before", may_have_changed=phase != "before"))
                    self.assertEqual(self.extension.SetUserPreferenceToggle.call_count, int(phase != "before"))
                    self.assertEqual(self.document.SetSaveFlag.call_count, int(phase == "dirty"))
                    self.assertIs(self.app.ActiveDoc, self.foreground)
                    self.assertIs(getattr(self.foreground, attribute), replacement)
                    self.app.ActivateDoc3.assert_not_called()
                    validate_operation_result("document.image-quality-set", result)

    def test_target_as_foreground_allows_its_expected_dirty_change(self):
        self.app.ActiveDoc = self.document
        result = self.edit()
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["document"]["modified"])
        self.extension.SetUserPreferenceToggle.assert_called_once()
        self.document.SetSaveFlag.assert_called_once()

    def test_handler_finalization_preserves_success_and_first_business_failure_receipts(self):
        from swcli.daemon import operations
        context = SimpleNamespace(app=self.app, documents=self.registry, entry=self.entry, session_id="writer")
        for business_error in (None, dict(type="NativeFirstFailure", message="original setter failure")):
            with self.subTest(business_error=business_error):
                receipt = dict(ok=business_error is None, action="mock", changed=True,
                    mutation=dict(attempted=True, may_have_changed=True))
                if business_error: receipt["error"] = business_error
                with mock.patch.object(operations, "set_document_image_quality_windows", return_value=receipt) as setter, \
                        mock.patch.object(self.registry, "describe", side_effect=RuntimeError("descriptor finalization")) as describe:
                    result = operations.document_image_quality_set(context, {})
                self.assertFalse(result["ok"], result)
                self.assertEqual(result["mutation"], receipt["mutation"])
                self.assertEqual(result["error"], business_error or dict(type="DocumentImageQualityFinalizationFailed", message="descriptor finalization"))
                self.assertEqual(result["finalization_error"]["message"], "descriptor finalization")
                self.assertNotIn("document", result)
                setter.assert_called_once(); describe.assert_called_once()
                validate_operation_result("document.image-quality-set", result)
                self.assertEqual(receipt["action"], "mock")

    def run_quality_worker(self, *, native_failure=False, restore_failure=False):
        from contextlib import contextmanager
        from swcli.daemon import server
        from swcli.hosts.native_sequence import NativeCommandRestoreFailed
        self.app.GetProcessID = lambda: 1234
        self.app.RevisionNumber = "33.5.0"
        request = dict(request_id="quality-once", operation="document.image-quality-set",
            parameters=dict(field="optimize_edge_length", value=True, expected_quality=snapshot()),
            document_id=self.entry.document_id, expected_update_stamp=7, lease_id=self.lease, session_id="writer")
        def setter(*args):
            self.apply(*args)
            if native_failure: raise RuntimeError("native first failure")
            return True
        self.extension.SetUserPreferenceToggle.side_effect = setter
        original_describe = self.registry.describe
        def describe(*args, **kwargs):
            if self.native[210] and not restore_failure: raise RuntimeError("descriptor finalization")
            return original_describe(*args, **kwargs)
        @contextmanager
        def sequence(*args, **kwargs):
            yield
            raise NativeCommandRestoreFailed(RuntimeError("restore finalization"), None)
        pythoncom, com_client = mock.Mock(), mock.Mock()
        responses, lifecycle = mock.Mock(), mock.Mock()
        with mock.patch.dict("sys.modules", {"pythoncom": pythoncom,
                "win32com": mock.Mock(client=com_client), "win32com.client": com_client}), \
                mock.patch.object(server, "acquire_resident_app", return_value=(self.app, False)), \
                mock.patch.object(server, "wait_windows_host_ready", return_value=0), \
                mock.patch.object(server, "DocumentRegistry", return_value=self.registry), \
                mock.patch.object(server, "_describe_app", return_value={"process_id":1234}), \
                mock.patch.object(server, "_wait_for_worker_request", side_effect=[request, None]), \
                mock.patch.object(self.registry, "describe", side_effect=describe):
            if restore_failure:
                with mock.patch.object(server, "native_api_sequence", sequence):
                    server._worker_main(mock.Mock(), responses, lifecycle, False, 120, True)
            else:
                server._worker_main(mock.Mock(), responses, lifecycle, False, 120, True)
        pythoncom.CoUninitialize.assert_called_once()
        responses.put.assert_called_once()
        return responses.put.call_args.args[0], lifecycle

    def test_real_worker_handler_and_adapter_preserve_receipt_after_describe_failure(self):
        for native_failure in (False, True):
            with self.subTest(native_failure=native_failure):
                self.setUp()
                response, _ = self.run_quality_worker(native_failure=native_failure)
                self.assertFalse(response["success"], response)
                result = response["result"]
                self.assertEqual(result["mutation"], dict(attempted=True, may_have_changed=True))
                self.assertEqual(result["error"]["message"], "native first failure" if native_failure else "descriptor finalization")
                self.assertEqual(result["finalization_error"]["message"], "descriptor finalization")
                self.assertEqual(response["error"]["code"], result["error"]["type"])
                validate_operation_result("document.image-quality-set", result)
                self.extension.SetUserPreferenceToggle.assert_called_once()
                self.assertEqual(self.document.SetSaveFlag.call_count, int(not native_failure))
                self.app.ActivateDoc3.assert_not_called()

    def test_worker_late_command_restore_failure_preserves_receipt_and_stops_host(self):
        for native_failure in (False, True):
            with self.subTest(native_failure=native_failure):
                self.setUp()
                response, lifecycle = self.run_quality_worker(native_failure=native_failure, restore_failure=True)
                self.assertFalse(response["success"], response)
                self.assertEqual(response["error"]["code"], "NativeCommandRestoreFailed")
                result = response["result"]
                self.assertEqual(result["mutation"], dict(attempted=True, may_have_changed=True))
                self.assertEqual(result["finalization_error"]["type"], "NativeCommandRestoreFailed")
                if native_failure: self.assertEqual(result["error"]["message"], "native first failure")
                validate_operation_result("document.image-quality-set", result)
                self.assertEqual(lifecycle.put.call_args.args[0]["event"], "host-disconnected")
                self.extension.SetUserPreferenceToggle.assert_called_once()

    def test_request_schema_and_cli_reject_invalid_typed_and_nested_json(self):
        parameters = dict(field="optimize_edge_length", value=True, expected_quality=snapshot())
        spec = OPERATION_CATALOG["document.image-quality-set"]
        self.assertTrue(spec.lease_guarded)
        self.assertEqual(spec.parameters["x-swcli-context"]["lease_id"], "required")
        for field, value in (("optimize_edge_length", 1), ("shaded_mode", 2), ("shaded_deviation_mm", True),
                             ("shaded_deviation_mm", float("inf")), ("shaded_deviation_mm", 0)):
            with self.subTest(field=field,value=value), self.assertRaises(ValueError):
                validate_operation_request("document.image-quality-set", {**parameters,"field":field,"value":value})
        for bad in (None, {}, {**snapshot(), "extra":0}, {**snapshot(), "optimize_edge_length":1}):
            with self.assertRaises((ValueError, TypeError)): validate_quality(bad)
        base = ["document", "image-quality-set", "optimize_edge_length", "false", "--if-update-stamp", "7", "--lease", "l-ab12cd34ef56", "--if-quality"]
        operation = _typed_operation(build_parser().parse_args(base + [json.dumps(snapshot())]))
        self.assertEqual(operation[1]["value"], False)
        malformed = [json.dumps(snapshot()).replace('"status": 0', '"status": 0, "status": 0'),
                     json.dumps(snapshot()).replace('0.0002', 'NaN'), 'null']
        for value in malformed:
            with self.assertRaises((ValueError, TypeError)):
                _typed_operation(build_parser().parse_args(base + [value]))


class ImageQualityWireTests(unittest.TestCase):
    def test_sdk_forwards_exact_typed_payload_context_once_and_preserves_partial_failure(self):
        from swcli.sdk import Client, TransportError
        from tests.test_sdk import envelope, document
        result = dict(ok=False, action="document.image-quality-set", session_id="quality",
            document=document(), mutation=dict(attempted=True, may_have_changed=True), native_return=None,
            error=dict(type="RuntimeError", message="native first failure"))
        client = Client(session_id="quality")
        with mock.patch("swcli.sdk.client.call_daemon", return_value=envelope(result, request_id="once")) as wire:
            reply = client.document.image_quality_set(field="optimize_edge_length", value=False,
                expected_quality=snapshot(), expected_update_stamp=0, lease_id="l-ab12cd34ef56",
                document_id="d-ab12cd", request_id="once")
            self.assertEqual(reply.raw["result"], result)
            wire.assert_called_once()
            self.assertEqual(wire.call_args.args, ("document.image-quality-set",
                dict(field="optimize_edge_length", value=False, expected_quality=snapshot())))
            for key, value in dict(session_id="quality", document_id="d-ab12cd", expected_update_stamp=0,
                lease_id="l-ab12cd34ef56", request_id="once").items(): self.assertEqual(wire.call_args.kwargs[key], value)
        with mock.patch("swcli.sdk.client.call_daemon", side_effect=ConnectionError("lost")) as wire:
            with self.assertRaises(TransportError):
                client.document.image_quality_set(field="optimize_edge_length", value=True,
                    expected_quality=snapshot(), expected_update_stamp=0, lease_id="l-ab12cd34ef56")
            wire.assert_called_once()
        with mock.patch("swcli.sdk.client.call_daemon") as wire:
            for params in (dict(field="shaded_mode", value="custom"), dict(value=1), dict(expected_quality={}), dict(expected_update_stamp=None), dict(lease_id=None)):
                arguments = dict(field="optimize_edge_length", value=True, expected_quality=snapshot(),
                    expected_update_stamp=0, lease_id="l-ab12cd34ef56")
                arguments.update(params)
                with self.assertRaises(Exception): client.document.image_quality_set(**arguments)
            wire.assert_not_called()

    def test_mcp_discovery_and_single_send_preserve_session_snapshot_cas_and_lease(self):
        from swcli.mcp import DaemonBridge
        from swcli.operation_schemas import operation_schemas
        from tests.test_mcp import response
        schema = operation_schemas()["document.image-quality-set"]
        self.assertEqual(schema["x-swcli-context"]["expected_update_stamp"], "required")
        with mock.patch("swcli.mcp.call_daemon", return_value=response()) as wire, \
                mock.patch("swcli.mcp.DaemonManager") as manager:
            bridge = DaemonBridge(session_id="quality")
            params = dict(field="optimize_edge_length", value=False, expected_quality=snapshot())
            bridge.call("execute", dict(operation="document.image-quality-set", parameters=params,
                session_id="quality", document_id="d-ab12cd", expected_update_stamp=0,
                lease_id="l-ab12cd34ef56", request_id="quality-once"))
            wire.assert_called_once()
            self.assertEqual(wire.call_args.args, ("document.image-quality-set", params))
            self.assertEqual(wire.call_args.kwargs["expected_update_stamp"], 0)
            self.assertEqual(wire.call_args.kwargs["lease_id"], "l-ab12cd34ef56")
            self.assertEqual(wire.call_args.kwargs["session_id"], "quality")
            manager.return_value.start.assert_not_called()


if __name__ == "__main__": unittest.main()
