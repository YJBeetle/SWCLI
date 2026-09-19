import unittest
from unittest import mock

from swcli.hosts import windows


class WindowsHostTests(unittest.TestCase):
    def test_command_executable_handles_quoted_server(self):
        command = '"C:\\Program Files\\SOLIDWORKS Corp\\SOLIDWORKS\\SLDWORKS.exe" /Automation'
        self.assertEqual(
            windows._command_executable(command),
            r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\SLDWORKS.exe",
        )

    def test_command_executable_handles_unquoted_server(self):
        command = r"C:\SOLIDWORKS\SLDWORKS.exe /Automation"
        self.assertEqual(
            windows._command_executable(command), r"C:\SOLIDWORKS\SLDWORKS.exe"
        )

    def test_non_windows_probe_is_structured(self):
        with mock.patch.object(windows.sys, "platform", "darwin"):
            result = windows.probe_windows_host()

        self.assertFalse(result["supported"])
        self.assertEqual(result["error"]["type"], "UnsupportedPlatform")
        self.assertIsNone(result["registration"])

    def test_com_value_accepts_property_or_method(self):
        class Example:
            property_value = "property"

            def method_value(self):
                return "method"

        example = Example()
        self.assertEqual(windows._com_value(example, "property_value"), "property")
        self.assertEqual(windows._com_value(example, "method_value"), "method")

    def test_lifecycle_is_rejected_off_windows(self):
        with mock.patch.object(windows.sys, "platform", "darwin"):
            start = windows.start_windows_host()
            stop = windows.stop_windows_host()

        self.assertFalse(start["ok"])
        self.assertFalse(stop["ok"])
        self.assertEqual(start["error"]["type"], "UnsupportedPlatform")


if __name__ == "__main__":
    unittest.main()
