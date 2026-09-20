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

    def test_non_windows_doctor_is_structured(self):
        with mock.patch.object(windows.sys, "platform", "darwin"):
            result = windows.doctor_windows_host()

        self.assertFalse(result["supported"])
        self.assertEqual(result["error"]["type"], "UnsupportedPlatform")
        self.assertIsNone(result["registration"])

    def test_com_value_accepts_property_or_method(self):
        class ComObject:
            _oleobj_ = object()

            def __call__(self):
                raise AssertionError("COM object properties must not be invoked")

        class Example:
            property_value = "property"
            object_value = ComObject()

            def method_value(self):
                return "method"

        example = Example()
        self.assertEqual(windows._com_value(example, "property_value"), "property")
        self.assertEqual(windows._com_value(example, "method_value"), "method")
        self.assertIs(windows._com_value(example, "object_value"), example.object_value)

    def test_wait_windows_host_ready_polls_until_startup_completes(self):
        class App:
            def __init__(self):
                self.values = iter((False, True))

            @property
            def StartupProcessCompleted(self):
                return next(self.values)

        with mock.patch.object(
            windows.time, "monotonic", side_effect=[10.0, 10.1, 10.2]
        ), mock.patch.object(windows.time, "sleep") as sleep:
            elapsed = windows.wait_windows_host_ready(
                App(), timeout_seconds=5.0, poll_interval_seconds=0.25
            )

        self.assertAlmostEqual(elapsed, 0.2)
        sleep.assert_called_once_with(0.25)

    def test_wait_windows_host_ready_times_out(self):
        app = mock.Mock(StartupProcessCompleted=False)

        with mock.patch.object(
            windows.time, "monotonic", side_effect=[10.0, 12.0]
        ):
            with self.assertRaisesRegex(TimeoutError, "within 1s"):
                windows.wait_windows_host_ready(app, timeout_seconds=1.0)


if __name__ == "__main__":
    unittest.main()
