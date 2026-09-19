import math
import unittest
from unittest import mock

from swcli.hosts import windows_parts


class WindowsPartTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
