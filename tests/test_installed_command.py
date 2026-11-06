"""The distribution's one console command is swcli; no legacy alias or daemon entrypoint."""
import contextlib
import importlib.metadata
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from swcli import __version__
from swcli.cli import build_parser, main

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("verify_installed_command", ROOT / "scripts/ci/verify-installed.py")
installed = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installed)


def distribution(*names):
    return SimpleNamespace(entry_points=[importlib.metadata.EntryPoint(name=name, value="swcli.cli:main",
        group="console_scripts") for name in names])


class CommandContractTests(unittest.TestCase):
    def test_client_help_identifies_swcli_and_mcp_is_a_client_subcommand(self):
        parser = build_parser()
        self.assertEqual(parser.prog, "swcli")
        self.assertIn("usage: swcli", parser.format_help())
        self.assertNotIn("sw-cli", parser.format_help())
        self.assertEqual(parser.parse_args(["mcp", "serve"]).command, "mcp")
        output = io.StringIO()
        with contextlib.redirect_stdout(output), mock.patch("swcli.cli.call_daemon") as call:
            self.assertEqual(main(["version", "--json"]), 0)
        self.assertEqual(json.loads(output.getvalue())["client_version"], __version__)
        call.assert_not_called()

    def test_distribution_has_exactly_one_console_command_and_generated_script(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "swcli"
            executable.write_text("#!/bin/sh\nexit 0\n")
            executable.chmod(0o755)
            with mock.patch.object(installed.sys, "platform", "linux"):
                self.assertEqual(installed.console_entrypoint(distribution("swcli"), directory), executable)
            self.assertFalse((Path(directory) / "sw-cli").exists())
            for names in (("sw-cli",), ("swcli", "sw-cli"), ("swcli", "swclid"), (), ("swcli", "swcli")):
                with self.subTest(names=names), self.assertRaisesRegex(RuntimeError, "only the swcli"):
                    installed.console_entrypoint(distribution(*names), directory)
            executable.unlink()
            with self.assertRaisesRegex(RuntimeError, "executable is missing"):
                installed.console_entrypoint(distribution("swcli"), directory)

    def test_windows_generated_console_uses_swcli_exe(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "swcli.exe"
            executable.write_text("fixture executable")
            executable.chmod(0o755)
            with mock.patch.object(installed.sys, "platform", "win32"):
                self.assertEqual(installed.console_entrypoint(distribution("swcli"), directory), executable)

    def test_console_probe_invokes_new_executable_and_rejects_wrong_distribution(self):
        response = SimpleNamespace(stdout=json.dumps({"client_version": __version__}))
        with mock.patch.object(installed.subprocess, "run", return_value=response) as run:
            installed.verify_console_version(Path("/tool path/swcli"), __version__)
        self.assertEqual(run.call_args.args[0], ["/tool path/swcli", "version", "--json"])
        response.stdout = json.dumps({"client_version": "older"})
        with mock.patch.object(installed.subprocess, "run", return_value=response), \
                self.assertRaisesRegex(RuntimeError, "installed distribution"):
            installed.verify_console_version(Path("/tool path/swcli"), __version__)


if __name__ == "__main__":
    unittest.main()
