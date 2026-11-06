"""Typed SDK preferences: portable request/response and generation contracts."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

from swcli.sdk import Client
from swcli.document_display_options import DISPLAY_FIELDS
from tests import test_document_drafting_standard as drafting_fixture

ROOT = Path(__file__).resolve().parents[1]
CONTEXT = {"document_id": "d-ab12cd", "expected_update_stamp": 0, "lease_id": "l-ab12cd34ef56"}
OPS = ("document.annotation-font", "document.annotation-font-set", "document.display-options",
       "document.display-option-set", "document.drafting-standard", "document.drafting-standard-set")


def envelope(result, request_id):
    return {"api_version": "swcli/v1", "success": True, "request_id": request_id,
            "duration_ms": 1.0, "result": result}


class SDKDocumentPreferencesTests(unittest.TestCase):
    def setUp(self):
        self.client = Client(session_id="sdk-preferences")
        fixture = drafting_fixture.DocumentDraftingStandardTests()
        fixture.setUp()
        self.snapshot = fixture.expected()
        self.font_pair = self.snapshot["observed_defaults"]["annotation_font"]
        self.font = deepcopy(self.font_pair["font"])
        self.options = deepcopy(self.snapshot["observed_defaults"]["display"])
        self.document = {"title": "fixture", "path": "", "type": 1, "modified": False,
                         "update_stamp": 0, "document_id": "d-ab12cd", "current": True, "active": True}

    def method(self, operation):
        return getattr(self.client.document, operation.split(".", 1)[1].replace("-", "_"))

    def result(self, operation):
        result = {"ok": True, "action": operation, "session_id": "sdk-preferences", "document": deepcopy(self.document)}
        if "annotation-font" in operation:
            result.update(deepcopy(self.font_pair))
            if operation.endswith("-set"):
                result.update(field="typeface", before=deepcopy(self.font), native_before=deepcopy(self.font_pair["native_font"]), native_normalizations=[])
        elif "display-option" in operation:
            result["options"] = deepcopy(self.options)
            if operation.endswith("-set"):
                result.update(field="grid.display", before=deepcopy(self.options))
        else:
            result.update(deepcopy(self.snapshot))
            if operation.endswith("-set"):
                result["before"] = deepcopy(self.snapshot)
        if operation.endswith("-set"):
            result.update(changed=False, mutation={"attempted": False, "may_have_changed": False})
        return result

    def test_six_methods_validate_actual_schema_and_send_exact_context_once(self):
        requests = {
            OPS[0]: {}, OPS[1]: {"field": "typeface", "value": self.font["typeface"], "expected_font": self.font},
            OPS[2]: {}, OPS[3]: {"field": "grid.display", "value": self.options["grid.display"]["value"], "expected_value": self.options["grid.display"]["value"]},
            OPS[4]: {}, OPS[5]: {"value": "gb", "expected_snapshot": self.snapshot},
        }
        for operation, parameters in requests.items():
            with self.subTest(operation=operation):
                context = CONTEXT if operation.endswith("-set") else {key: CONTEXT[key] for key in ("document_id", "expected_update_stamp")}
                raw = self.result(operation)
                with patch("swcli.sdk.client.call_daemon", return_value=envelope(raw, "once")) as wire:
                    response = self.method(operation)(**deepcopy(parameters), **context, request_id="once")
                self.assertEqual(response.require_result(), raw)
                wire.assert_called_once()
                self.assertEqual(wire.call_args.args, (operation, parameters))
                for key, value in context.items():
                    self.assertEqual(wire.call_args.kwargs[key], value)
                self.assertEqual(wire.call_args.kwargs["request_id"], "once")
                self.assertEqual(wire.call_args.kwargs["session_id"], "sdk-preferences")

    def test_each_field_typed_request_has_one_transport_call_and_no_normalization(self):
        targets = {"typeface": "Arial", "height_mm": 4.5, "height_points": 14,
                   "bold": True, "italic": False, "underline": True, "strikeout": False}
        requests = [(OPS[1], {"field": field, "value": value, "expected_font": deepcopy(self.font)}) for field, value in targets.items()]
        for field, spec in DISPLAY_FIELDS.items():
            value = (False if spec["kind"] == "Toggle" else 25.0 if spec["kind"] == "Double"
                     else "plus" if "values" in spec else 5)
            before = self.options[field]["value"]
            requests.append((OPS[3], {"field": field, "value": value, "expected_value": before}))
        for standard in ("ansi", "iso", "din", "jis", "bsi", "gost", "gb"):
            requests.append((OPS[5], {"value": standard, "expected_snapshot": deepcopy(self.snapshot)}))
        failure = {"api_version": "swcli/v1", "success": False, "request_id": "once", "duration_ms": 0,
                   "error": {"code": "DocumentUpdateConflict", "message": "changed", "details": {"expected": 0}}}
        for operation, parameters in requests:
            with self.subTest(operation=operation, field=parameters.get("field"), value=parameters["value"]):
                with patch("swcli.sdk.client.call_daemon", return_value=deepcopy(failure)) as wire:
                    response = self.method(operation)(**deepcopy(parameters), **CONTEXT, request_id="once")
                wire.assert_called_once()
                self.assertEqual(wire.call_args.args, (operation, parameters))
                self.assertFalse(response.ok)
                self.assertEqual(response.error.details, {"expected": 0})

    def test_field_conditions_strict_cas_types_and_nonfinite_reject_before_io(self):
        invalid = [
            (OPS[1], {"field": field, "value": value, "expected_font": deepcopy(self.font)})
            for field, value in (("bold", 1), ("italic", "false"), ("height_points", 14.0),
                ("height_points", True), ("height_mm", float("nan")), ("typeface", " Arial"), ("backwards", True))]
        invalid += [(OPS[3], {"field": field, "value": value, "expected_value": expected}) for field, value, expected in
            (("grid.display", 1, True), ("grid.display", True, 0), ("grid.major_spacing_mm", 2.0, float("inf")),
             ("grid.minor_lines_per_major", 2.0, 4), ("virtual_sharp.style", "other", "plus"),
             ("plane.transparency", 101, 95), ("raw-preference-145", 3, 4))]
        missing_font = deepcopy(self.font); missing_font.pop("bold")
        invalid.append((OPS[1], {"field": "bold", "value": True, "expected_font": missing_font}))
        bad_snapshot = deepcopy(self.snapshot); bad_snapshot["observed_defaults"]["coverage"]["display"].pop()
        invalid.extend([(OPS[5], {"value": "other", "expected_snapshot": self.snapshot}),
                        (OPS[5], {"value": "iso", "expected_snapshot": bad_snapshot})])
        with patch("swcli.sdk.client.call_daemon") as wire:
            for operation, parameters in invalid:
                with self.subTest(operation=operation, parameters=parameters), self.assertRaises(ValueError):
                    self.method(operation)(**parameters, **CONTEXT)
            wire.assert_not_called()

    def test_all_three_setters_require_stamp_and_lease_before_dispatch(self):
        requests = {OPS[1]: {"field": "bold", "value": True, "expected_font": self.font},
                    OPS[3]: {"field": "grid.display", "value": False, "expected_value": True},
                    OPS[5]: {"value": "iso", "expected_snapshot": self.snapshot}}
        with patch("swcli.sdk.client.call_daemon") as wire:
            for operation, parameters in requests.items():
                for omitted in ("expected_update_stamp", "lease_id"):
                    context = {key: value for key, value in CONTEXT.items() if key != omitted}
                    with self.subTest(operation=operation, omitted=omitted), self.assertRaises(TypeError):
                        self.method(operation)(**parameters, **context)
            wire.assert_not_called()

    def test_native_partial_failure_payload_and_first_error_survive_without_retry(self):
        requests = {OPS[1]: {"field": "bold", "value": True, "expected_font": self.font},
                    OPS[3]: {"field": "grid.display", "value": False, "expected_value": True},
                    OPS[5]: {"value": "iso", "expected_snapshot": self.snapshot}}
        for operation, parameters in requests.items():
            raw = {"ok": False, "action": operation, "mutation": {"attempted": True, "may_have_changed": True},
                   "error": {"type": "NativeRefusal", "message": "first cause", "details": {"stage": "setter", "partial": True}}}
            with self.subTest(operation=operation), patch("swcli.sdk.client.call_daemon", return_value=envelope(raw, "partial")) as wire:
                response = self.method(operation)(**parameters, **CONTEXT, request_id="partial")
                self.assertEqual(response.result, raw)
                self.assertEqual(response.error.message, "first cause")
                wire.assert_called_once()

    def test_generator_recognizes_only_complete_allof_object_variants(self):
        spec = importlib.util.spec_from_file_location("sdk_preference_generator", ROOT / "scripts/dev/generate-sdk.py")
        generator = importlib.util.module_from_spec(spec); spec.loader.exec_module(generator)
        complete = {"type": "object", "additionalProperties": False, "properties": {"field": {"const": "a"}}, "required": ["field"]}
        schema = {**complete, "allOf": [{"oneOf": [complete]}]}
        self.assertEqual(generator.parameter_variants(schema), [complete])
        partial = deepcopy(schema); partial["allOf"][0]["oneOf"][0]["required"] = []
        self.assertEqual(generator.parameter_variants(partial), [])
        conditional = {**complete, "allOf": [{"if": {"properties": {"field": {"const": "a"}}}, "then": {"required": ["field"]}}]}
        self.assertEqual(generator.parameter_variants(conditional), [])
