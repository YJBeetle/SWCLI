"""CLI lazy startup remains explicit and excludes discovery/lifecycle commands."""

import contextlib
import io
import unittest
from unittest import mock

from swcli.cli import main


class CLIAutoStartTests(unittest.TestCase):
    def invoke(self, arguments):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            return main(arguments)

    def test_typed_commands_only_start_when_explicitly_enabled(self):
        for flags in ([], ["--auto-start"]):
            with self.subTest(flags=flags), mock.patch("swcli.client_startup.ensure_local_daemon") as start, \
                    mock.patch("swcli.cli.call_daemon", return_value={"success": True, "result": {"ok": True, "documents": [], "count": 0}}) as call:
                self.assertEqual(self.invoke([*flags, "document", "list", "--json"]), 0)
            self.assertEqual(start.call_count, bool(flags))
            call.assert_called_once()
            if flags:
                start.assert_called_once_with(endpoint="127.0.0.1:18495", connect_timeout_seconds=3)

    def test_version_protocol_status_and_capabilities_do_not_trigger_lazy_start(self):
        for command in (["version", "--json"], ["protocol", "show", "request"],
                        ["daemon", "status", "--json"], ["capabilities", "--json"]):
            with self.subTest(command=command), mock.patch("swcli.client_startup.ensure_local_daemon") as start, \
                    mock.patch("swcli.cli.call_daemon", side_effect=ConnectionRefusedError("offline")), \
                    mock.patch("swcli.daemon.main.call_daemon", side_effect=ConnectionRefusedError("offline")):
                self.invoke(["--auto-start", *command])
            start.assert_not_called()

    def test_startup_failure_never_submits_the_requested_cad_operation(self):
        with mock.patch("swcli.client_startup.ensure_local_daemon", side_effect=RuntimeError("ExistingHostRequiresAttach")), \
                mock.patch("swcli.cli.call_daemon") as call:
            self.assertEqual(self.invoke(["--auto-start", "document", "list", "--json"]), 1)
        call.assert_not_called()

    def test_native_failure_is_not_retried_or_recovered(self):
        with mock.patch("swcli.client_startup.ensure_local_daemon") as start, \
                mock.patch("swcli.cli.call_daemon", return_value={"success": False, "error": {"code": "HostDisconnected", "message": "recover explicitly"}}) as call:
            self.assertEqual(self.invoke(["--auto-start", "document", "list", "--json"]), 1)
        start.assert_called_once()
        call.assert_called_once()
