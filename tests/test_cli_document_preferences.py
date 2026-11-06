"""CLI parsing/forwarding only; no daemon or native SOLIDWORKS execution."""

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import importlib.util
from io import StringIO
import json
from pathlib import Path
import unittest
from unittest import mock

from swcli.cli import _typed_operation, build_parser, main
from swcli.document_drafting_standard import NAMED_DRAFTING_STANDARDS


class CLIDocumentPreferencesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = build_parser()
        path = Path(__file__).with_name("test_document_drafting_standard.py")
        spec = importlib.util.spec_from_file_location("_cli_drafting_fixture", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        fixture = module.DocumentDraftingStandardTests()
        fixture.setUp()
        cls.baseline = fixture.expected()

    def setUp(self):
        self.snapshot = deepcopy(self.baseline)
        self.font = deepcopy(self.snapshot["observed_defaults"]["annotation_font"]["font"])
        self.guards = ["--document", "d-cli-test", "--if-update-stamp", "144", "--lease", "l-cli-test", "--json"]

    def font_command(self, field="bold", value="true", *, font=None):
        return ["document", "annotation-font-set", field, value, "--if-font",
                json.dumps(self.font if font is None else font)]

    def standard_command(self, value="iso", *, snapshot=None):
        return ["document", "drafting-standard-set", value, "--if-snapshot",
                json.dumps(self.snapshot if snapshot is None else snapshot)]

    def mapped(self, command):
        return _typed_operation(self.parser.parse_args(command))

    def reject(self, command, message=None):
        with mock.patch("swcli.cli.call_daemon") as call:
            error = StringIO()
            with redirect_stderr(error), self.assertRaises(SystemExit) as exited:
                main(command)
            self.assertEqual(exited.exception.code, 2)
            self.assertNotIn("Traceback", error.getvalue())
            if message is not None:
                self.assertIn(message, error.getvalue())
            call.assert_not_called()

    def test_three_read_commands_preserve_optional_document_and_stamp_selectors(self):
        for command in ("annotation-font", "display-options", "drafting-standard"):
            with self.subTest(command=command):
                self.assertEqual(self.mapped(["document", command, "--json"]),
                                 ("document." + command, {}, True, None, None, None))
                self.assertEqual(self.mapped(["document", command, "--document", "active", "--if-update-stamp", "0"]),
                                 ("document." + command, {}, False, "active", 0, None))

    def test_all_seven_font_fields_map_exact_types_and_complete_snapshot(self):
        for field, text, value in (("typeface", "Arial Unicode MS", "Arial Unicode MS"),
                                   ("height_mm", "4.5", 4.5), ("height_points", "14", 14),
                                   ("bold", "true", True), ("italic", "false", False),
                                   ("underline", "true", True), ("strikeout", "false", False)):
            with self.subTest(field=field):
                mapped = self.mapped(self.font_command(field, text) + self.guards)
                self.assertEqual(mapped, ("document.annotation-font-set",
                    {"field": field, "value": value, "expected_font": self.font},
                    True, "d-cli-test", 144, "l-cli-test"))
                self.assertIs(type(mapped[1]["value"]), type(value))

    def test_all_ten_display_fields_map_both_typed_scalars(self):
        cases = (("grid.display", "true", "false", True, False),
                 ("grid.major_spacing_mm", "10", "100", 10.0, 100.0),
                 ("grid.minor_lines_per_major", "10", "4", 10, 4),
                 ("grid.snap_points_per_minor", "5", "1", 5, 1),
                 ("virtual_sharp.style", "dot", "witness", "dot", "witness"),
                 ("plane.front_face_color", "1193046", "33023", 1193046, 33023),
                 ("plane.back_face_color", "1193046", "16512", 1193046, 16512),
                 ("plane.intersection_line_color", "1193046", "0", 1193046, 0),
                 ("plane.transparency", "25", "95", 25, 95),
                 ("plane.show_intersections", "false", "true", False, True))
        for field, text, previous, value, expected in cases:
            with self.subTest(field=field):
                mapped = self.mapped(["document", "display-option-set", field, text, "--if-value", previous] + self.guards)
                self.assertEqual(mapped, ("document.display-option-set",
                    {"field": field, "value": value, "expected_value": expected},
                    True, "d-cli-test", 144, "l-cli-test"))
                self.assertIs(type(mapped[1]["value"]), type(value))
                self.assertIs(type(mapped[1]["expected_value"]), type(expected))

    def test_display_signed_raw_cas_prevalue_does_not_become_a_writable_target(self):
        mapped = self.mapped(["document", "display-option-set", "plane.front_face_color", "0",
                              "--if-value", "-1"] + self.guards)
        self.assertEqual(mapped[1], {"field": "plane.front_face_color", "value": 0, "expected_value": -1})
        self.reject(["document", "display-option-set", "plane.front_face_color", "-1",
                     "--if-value", "0"] + self.guards)

    def test_named_standard_values_use_the_exact_complete_fixed_snapshot(self):
        for name in NAMED_DRAFTING_STANDARDS:
            with self.subTest(name=name):
                self.assertEqual(self.mapped(self.standard_command(name) + self.guards),
                    ("document.drafting-standard-set", {"value": name, "expected_snapshot": self.snapshot},
                     True, "d-cli-test", 144, "l-cli-test"))

    def test_setters_require_stamp_lease_and_their_previous_observation(self):
        commands = (self.font_command(), self.standard_command(),
                    ["document", "display-option-set", "grid.display", "true", "--if-value", "false"])
        for command in commands:
            for guards in ([], ["--lease", "l-cli-test"], ["--if-update-stamp", "144"]):
                with self.subTest(command=command[:2], guards=guards):
                    self.reject(command + guards)
        for command in (["document", "annotation-font-set", "bold", "true"],
                        ["document", "display-option-set", "grid.display", "true"],
                        ["document", "drafting-standard-set", "iso"]):
            with self.subTest(missing_observation=command):
                self.reject(command + self.guards)

    def test_empty_or_whitespace_lease_tokens_are_rejected_before_daemon(self):
        for token in ("", " ", " l-cli-test", "l-cli-test "):
            with self.subTest(token=token):
                self.reject(self.font_command() + ["--if-update-stamp", "144", "--lease", token])

    def test_main_forwards_context_and_structured_parameters_without_native_paths(self):
        cases = ((self.font_command(), "document.annotation-font-set"),
                 (self.standard_command(), "document.drafting-standard-set"),
                 (["document", "display-option-set", "grid.display", "false", "--if-value", "true"],
                  "document.display-option-set"))
        for command, operation in cases:
            with self.subTest(operation=operation):
                expected = self.mapped(command + self.guards)[1]
                response = {"success": True, "request_id": "cli-review", "result": {"ok": True, "action": operation}}
                with mock.patch("swcli.cli.call_daemon", return_value=response) as call, redirect_stdout(StringIO()):
                    code = main(["--session", "review-session", "--request-id", "cli-review"] + command + self.guards)
                self.assertEqual(code, 0)
                call.assert_called_once()
                self.assertEqual(call.call_args.args, (operation, expected))
                self.assertEqual(call.call_args.kwargs["document_id"], "d-cli-test")
                self.assertEqual(call.call_args.kwargs["expected_update_stamp"], 144)
                self.assertEqual(call.call_args.kwargs["lease_id"], "l-cli-test")
                self.assertEqual(call.call_args.kwargs["session_id"], "review-session")
                self.assertEqual(call.call_args.kwargs["request_id"], "cli-review")
                self.assertFalse({"path", "preference", "option", "snapshot_reader"}.intersection(expected))

    def test_duplicate_json_keys_reject_at_top_level_and_at_any_nested_level(self):
        command = self.font_command()
        command[-1] = command[-1][:-1] + ', "bold": true}'
        self.reject(command + self.guards, "duplicate JSON key")
        command = self.standard_command()
        command[-1] = command[-1].replace('"value": "gb"', '"value": "gb", "value": "iso"', 1)
        self.reject(command + self.guards, "duplicate JSON key")
        command = self.standard_command()
        command[-1] = '{"nested": [{"same": 1, "same": 2}]}'
        self.reject(command + self.guards, "duplicate JSON key")

    def test_nonfinite_json_literals_and_overflow_are_rejected_before_daemon(self):
        for token in ("NaN", "Infinity", "-Infinity", "1e999"):
            for command in (self.font_command(), self.standard_command()):
                with self.subTest(token=token, command=command[:2]):
                    command[-1] = command[-1].replace('"height_mm": 3.5', '"height_mm": ' + token, 1)
                    self.reject(command + self.guards)

    def test_json_requires_an_object_and_malformed_input_never_connects(self):
        for text in ("[]", "null", "true", "14", '"filename.json"', '{"bold":', "@/tmp/font.json"):
            for command in (self.font_command(), self.standard_command()):
                with self.subTest(text=text, command=command[:2]):
                    command[-1] = text
                    self.reject(command + self.guards)

    def test_font_snapshot_rejects_missing_extra_wrongly_typed_and_nested_values(self):
        missing = dict(self.font)
        missing.pop("line_length")
        for font in (missing, {**self.font, "preference": 19}, {**self.font, "bold": 1},
                     {**self.font, "height_points": 12.0}, {**self.font, "height_mm": True},
                     {**self.font, "bold": {"value": False}}):
            with self.subTest(font=font):
                self.reject(self.font_command(font=font) + self.guards)

    def test_standard_snapshot_rejects_nested_scope_shape_and_semantic_mismatch(self):
        cases = []
        changed = deepcopy(self.snapshot)
        changed["observed_defaults"]["profile"] = "caller-profile"
        cases.append(changed)
        changed = deepcopy(self.snapshot)
        changed["observed_defaults"]["coverage"]["display"].pop()
        cases.append(changed)
        changed = deepcopy(self.snapshot)
        changed["observed_defaults"]["annotation_font"]["font"]["bold"] = True
        cases.append(changed)
        changed = deepcopy(self.snapshot)
        changed["observed_defaults"]["length_units"]["native_units"]["significant_digits"] = 4
        cases.append(changed)
        changed = deepcopy(self.snapshot)
        changed["snapshot_reader"] = "/tmp/injected.py"
        cases.append(changed)
        for snapshot in cases:
            with self.subTest(snapshot=snapshot):
                self.reject(self.standard_command(snapshot=snapshot) + self.guards)

    def test_font_and_display_scalar_domains_reject_malformed_values_before_daemon(self):
        for field, value in (("bold", "True"), ("bold", "0"), ("height_points", "14.0"),
                             ("height_points", "true"), ("height_mm", "NaN"), ("height_mm", "1e999"),
                             ("height_mm", "0"), ("height_mm", "5e-324"), ("typeface", " Arial")):
            with self.subTest(field=field, value=value):
                self.reject(self.font_command(field, value) + self.guards)
        for field, value, previous in (("grid.display", "1", "false"),
                                      ("grid.major_spacing_mm", "inf", "100"),
                                      ("grid.major_spacing_mm", "10", "NaN"),
                                      ("grid.minor_lines_per_major", "4.5", "4"),
                                      ("plane.transparency", "101", "95"),
                                      ("virtual_sharp.style", "999", "witness"),
                                      ("virtual_sharp.style", "dot", "other")):
            with self.subTest(field=field, value=value):
                self.reject(["document", "display-option-set", field, value, "--if-value", previous] + self.guards)

    def test_native_ids_paths_and_callables_have_no_cli_escape_hatch(self):
        for flags in (["--preference", "57"], ["--option", "0"], ["--path", "/tmp/a"],
                      ["--snapshot-reader", "callable"], ["--preference-ids", '{"swGridDisplay":57}']):
            with self.subTest(flags=flags):
                self.reject(["document", "display-options"] + flags)
        for command in (self.font_command("height_mode", "points"),
                        ["document", "display-option-set", "swGridDisplay", "true", "--if-value", "false"],
                        self.standard_command("custom")):
            with self.subTest(command=command[:4]):
                self.reject(command + self.guards)


if __name__ == "__main__":
    unittest.main()
