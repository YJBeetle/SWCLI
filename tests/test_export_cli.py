import unittest
from unittest import mock

from swcli.utils import export


class ExportCliTests(unittest.TestCase):
    @mock.patch("swcli.cli.main")
    def test_utility_entry_point_delegates_to_batch_export(self, swcli_main):
        swcli_main.return_value = 0

        exit_code = export.main(
            ["--list", "files.txt", "--workspace", "workspace"]
        )

        self.assertEqual(exit_code, 0)
        swcli_main.assert_called_once_with(
            [
                "batch",
                "export",
                "--list",
                "files.txt",
                "--workspace",
                "workspace",
            ]
        )


if __name__ == "__main__":
    unittest.main()
