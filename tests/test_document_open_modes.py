import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from jsonschema import Draft202012Validator

from swcli.cli import _typed_operation, build_parser
from swcli.hosts import windows_open_modes as native
from swcli.operation_schemas import OPERATION_SCHEMAS, validate_operation_request
from swcli.result_schemas import validate_operation_result


class DocumentOpenModeTests(unittest.TestCase):
    def test_file_type_and_combination_validation(self):
        schema = Draft202012Validator(OPERATION_SCHEMAS["document.open"])
        for path, mode in [
            ("C:\\Workspace\\model.SLDASM", "large-design-review"),
            ("drawing.SLDDRW", "lightweight"), ("drawing.SLDDRW", "detailing"),
            ("part.SLDPRT", "quick-view"), ("part.SLDPRT", "resolved"),
        ]:
            with self.subTest(path=path, mode=mode):
                parameters = {"path": path, "mode": mode}
                validate_operation_request("document.open", parameters)
                schema.validate(parameters)
        for params in [
            {"path": "part.sldprt", "mode": "lightweight"},
            {"path": "drawing.slddrw", "mode": "resolved", "use_speedpak": False},
            {"path": "asm.sldasm", "mode": "large-design-review", "load_hidden_components": True},
            {"path": "asm.sldasm", "use_large_assembly_settings": False},
            {"path": "drawing.slddrw", "mode": "resolved", "configuration": "Default"},
        ]:
            with self.subTest(params=params):
                with self.assertRaises(ValueError):
                    validate_operation_request("document.open", params)
                self.assertFalse(schema.is_valid(params))

    def test_cli_preserves_omission_and_explicit_false(self):
        parser = build_parser()
        default = _typed_operation(parser.parse_args(["document", "open", "asm.sldasm"]))[1]
        self.assertEqual(default, {"path": "asm.sldasm", "read_only": False, "configuration": ""})
        explicit = _typed_operation(parser.parse_args([
            "document", "open", "asm.sldasm", "--mode", "resolved",
            "--no-load-hidden-components", "--use-speedpak", "--no-use-large-assembly-settings",
        ]))[1]
        self.assertEqual(explicit, {
            **default, "mode": "resolved", "load_hidden_components": False,
            "use_speedpak": True, "use_large_assembly_settings": False,
        })

    def open_assembly(self, component_states, options, *, ldr=0, mode="lightweight", restore_error=False):
        components = [
            SimpleNamespace(GetSuppression2=state, IsSpeedPak=state == 2)
            for state in component_states
        ]
        document = SimpleNamespace(
            GetLargeDesignReviewState=ldr, GetComponents=mock.Mock(return_value=components),
            IsOpenedViewOnly=bool(ldr), IsOpenedReadOnly=True, HasUnloadedComponents=True,
        )
        spec = SimpleNamespace(Error=0, Warning=2)
        app = mock.Mock()
        app.GetOpenDocumentByName.return_value = None
        app.GetOpenDocSpec.return_value = spec
        app.OpenDoc7.return_value = document
        app.GetUserPreferenceToggle.side_effect = [False, True, restore_error, False]
        app.SetUserPreferenceToggle.return_value = None
        result = {}

        with native.open_modes_host_scope(True), mock.patch.object(native, "_large_settings_key", return_value=42):
            self.assertIs(native.open_explicit_document(
                app, Path("model.SLDASM"), 2, mode, options, True, "", result), document)
        return app, spec, result

    def test_observed_mode_is_not_requested_mode(self):
        app, spec, result = self.open_assembly(
            [1, 2, 0], {"load_hidden_components": False, "use_speedpak": True,
                         "use_large_assembly_settings": True})
        self.assertIs(spec.IgnoreHiddenComponents, False)
        self.assertIs(spec.UseSpeedPak, True)
        self.assertIs(spec.LightWeight, True)
        self.assertIs(spec.UseLightWeightDefault, False)
        self.assertEqual(result["open_mode"], {
            "requested": "lightweight", "actual": "mixed", "matches_request": False,
            "options": {"load_hidden_components": False, "use_speedpak": True,
                        "use_large_assembly_settings": True},
            "view_only": False, "actual_read_only": True, "large_design_review_state": 0,
            "lightweight_count": 1, "resolved_count": 1, "suppressed_count": 1,
            "speedpak_count": 1, "has_unloaded_components": True,
            "large_assembly_settings": {"before": False, "during_open": True,
                                        "after_open": False, "restored": True},
        })
        self.assertEqual(app.SetUserPreferenceToggle.call_args_list, [mock.call(42, True), mock.call(42, False)])

        validate_operation_result("document.open", {
            **result, "ok": True, "action": "document.open", "path": "model.SLDASM",
            "configuration": None, "read_only": True,
            "document": {"path": "model.SLDASM", "modified": False, "title": "model", "type": 2, "update_stamp": 1},
        })

    def test_ldr_stops_before_component_access(self):
        _, spec, result = self.open_assembly([], {}, ldr=1, mode="large-design-review")
        self.assertIs(spec.ViewOnly, True)
        self.assertEqual(result["open_mode"]["actual"], "large-design-review")
        self.assertNotIn("resolved_count", result["open_mode"])

    def test_restore_failure_is_reported(self):
        _, _, result = self.open_assembly([1], {"use_large_assembly_settings": True}, restore_error=True)
        self.assertIs(result["open_mode"]["large_assembly_settings"]["restored"], False)
        self.assertIn("preference_restore_errors", result)

    def test_existing_document_does_not_attempt_native_open(self):
        app = mock.Mock()
        with self.assertRaisesRegex(native.OpenModeError, "close the document"):
            native.open_explicit_document(app, Path("model.SLDPRT"), 1, "resolved", {}, False, "", {})
        app.GetOpenDocSpec.assert_not_called()
        app.OpenDoc7.assert_not_called()

    def test_drawing_observes_each_sheet_and_checks_model_presence(self):
        loaded = SimpleNamespace(IsLightweight=False, IsModelLoaded=True)
        lightweight = SimpleNamespace(IsLightweight=True, IsModelLoaded=False)
        unloaded = SimpleNamespace(IsLightweight=False, IsModelLoaded=False)
        observed = {"view_only": False}
        document = SimpleNamespace(IsDetailingMode=False, GetViews=[
            (object(), loaded, lightweight),
            (object(), unloaded),
        ])
        with mock.patch.object(native, "_dispatch", side_effect=lambda view: view) as dispatch:
            self.assertEqual(native._observe_drawing(document, observed), "unknown")
        self.assertEqual(dispatch.call_args_list, [mock.call(loaded), mock.call(lightweight), mock.call(unloaded)])
        self.assertEqual(observed, {
            "view_only": False, "detailing_mode": False, "lightweight_count": 1,
            "resolved_count": 1, "unloaded_count": 1,
        })

    def test_part_quick_view_passes_both_native_flags(self):
        spec = SimpleNamespace(Error=0, Warning=0)
        document = SimpleNamespace(IsOpenedViewOnly=True, IsOpenedReadOnly=False)
        app = mock.Mock()
        app.GetOpenDocumentByName.return_value = None
        app.GetOpenDocSpec.return_value = spec
        app.OpenDoc7.return_value = document
        result = {}

        native.open_explicit_document(
            app, Path("part.SLDPRT"), 1, "quick-view", {}, False, "Current", result,
        )

        self.assertIs(spec.ViewOnly, True)
        self.assertIs(spec.Selective, True)
        self.assertEqual(spec.ConfigurationName, "Current")
        self.assertEqual(result["open_mode"]["actual"], "quick-view")

    def test_attach_existing_cannot_change_global_settings(self):
        app = mock.Mock()
        app.GetOpenDocumentByName.return_value = None
        with self.assertRaisesRegex(native.OpenModeError, "daemon-owned"):
            native.open_explicit_document(
                app, Path("assembly.SLDASM"), 2, "resolved",
                {"use_large_assembly_settings": False}, False, "", {},
            )
        app.SetUserPreferenceToggle.assert_not_called()
        app.OpenDoc7.assert_not_called()
