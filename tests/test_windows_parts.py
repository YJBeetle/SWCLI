import math
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from swcli.hosts import windows_parts


class WindowsPartTests(unittest.TestCase):
    def test_explicit_part_template_takes_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            template = Path(directory) / "Custom.PRTDOT"
            template.touch()
            app = mock.Mock()

            result = windows_parts._resolve_part_template(app, str(template))

        self.assertTrue(result["ok"])
        self.assertEqual(result["source"], "explicit")
        app.GetUserPreferenceStringValue.assert_not_called()

    def test_configured_part_template_is_used_when_available(self):
        with tempfile.TemporaryDirectory() as directory:
            template = Path(directory) / "Part.prtdot"
            template.touch()
            app = mock.Mock()
            app.GetUserPreferenceStringValue.return_value = str(template)

            result = windows_parts._resolve_part_template(app, None)

        self.assertTrue(result["ok"])
        self.assertEqual(result["source"], "solidworks-default")
        app.GetUserPreferenceStringValue.assert_called_once_with(8)

    def test_missing_explicit_part_template_fails_without_ui(self):
        result = windows_parts._resolve_part_template(
            mock.Mock(), "missing-template.prtdot"
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["type"], "PartTemplateUnavailable")

    def test_installed_part_template_is_discovered_when_default_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            template = Path(directory) / "SOLIDWORKS" / "templates" / "Part.prtdot"
            template.parent.mkdir(parents=True)
            template.touch()
            app = mock.Mock()
            app.GetUserPreferenceStringValue.return_value = ""
            with mock.patch.dict(
                windows_parts.os.environ,
                {"PROGRAMDATA": directory, "ProgramFiles": "", "ProgramFiles(x86)": ""},
            ):
                result = windows_parts._resolve_part_template(app, None)

        self.assertTrue(result["ok"])
        self.assertEqual(result["source"], "installed-template-discovery")
        self.assertEqual(result["path"], str(template.resolve()))

    def test_box_arguments_require_sldprt_output(self):
        result = windows_parts._validate_box_arguments("box.step", 10, 20, 30)
        self.assertEqual(result["error"]["type"], "InvalidArgument")

    def test_box_arguments_require_positive_finite_dimensions(self):
        for value in (0, -1, math.inf, math.nan):
            with self.subTest(value=value):
                result = windows_parts._validate_box_arguments(
                    "box.SLDPRT", value, 20, 30
                )
                self.assertEqual(result["error"]["type"], "InvalidArgument")

    def test_box_operation_is_rejected_off_windows(self):
        with mock.patch.object(windows_parts.sys, "platform", "darwin"):
            result = windows_parts.create_box_part_windows(
                "box.SLDPRT", width_mm=10, height_mm=20, depth_mm=30
            )

        self.assertEqual(result["error"]["type"], "UnsupportedPlatform")

    def test_box_geometry_verification_accepts_small_body_box_error(self):
        bodies = {
            "items": [
                {
                    "type": {"name": "solid"},
                    "approximate_bounding_box": {
                        "size_mm": {"x": 100.02, "y": 49.98, "z": 20.01}
                    },
                }
            ]
        }

        verification = windows_parts._verify_box_geometry(bodies, 100, 50, 20)

        self.assertTrue(verification["passed"])
        self.assertEqual(verification["method"], "axis-aligned-approximate-body-box")

    def test_box_geometry_verification_rejects_wrong_dimensions(self):
        bodies = {
            "items": [
                {
                    "type": {"name": "solid"},
                    "approximate_bounding_box": {
                        "size_mm": {"x": 100.0, "y": 50.0, "z": 19.0}
                    },
                }
            ]
        }

        verification = windows_parts._verify_box_geometry(bodies, 100, 50, 20)

        self.assertFalse(verification["passed"])


if __name__ == "__main__":
    unittest.main()
