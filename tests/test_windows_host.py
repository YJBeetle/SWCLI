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


if __name__ == "__main__":
    unittest.main()
