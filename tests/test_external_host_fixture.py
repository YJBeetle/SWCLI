import importlib.util
import sys
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import Mock, patch

script = (
    Path(__file__).resolve().parents[1] / "scripts/ci/windows/create-external-host.py"
)
spec = importlib.util.spec_from_file_location("external_host_fixture", script)
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class ComError(Exception):
    def __init__(self, hresult):
        self.hresult = hresult


class ExternalHostFixtureTests(unittest.TestCase):
    def app(self):
        return Mock(
            GetProcessID=Mock(return_value=123),
            StartupProcessCompleted=True,
            RevisionNumber="33.5.0",
            Visible=False,
            UserControl=False,
        )

    def test_ready_external_host_is_left_running(self):
        app = self.app()
        client, emit = Mock(DispatchEx=Mock(return_value=app)), Mock()
        result = fixture.create_host(client, Mock(), emit)
        self.assertEqual(result["process_id"], 123)
        self.assertTrue(result["visible"])
        self.assertTrue(result["user_control"])
        app.ExitApp.assert_not_called()
        client.DispatchEx.assert_called_once_with("SldWorks.Application")
        self.assertEqual(emit.call_args_list[0].args[0]["phase"], "host-acquired")
        self.assertEqual(emit.call_args_list[1].args[0]["phase"], "ready")

    def test_failed_startup_reports_acquired_pid_and_closes_fixture_host(self):
        app, emit = self.app(), Mock()
        app.StartupProcessCompleted = False
        with self.assertRaises(TimeoutError):
            fixture.create_host(
                Mock(DispatchEx=Mock(return_value=app)),
                Mock(),
                emit,
                clock=Mock(side_effect=[0, 121]),
                sleep=Mock(),
            )
        app.ExitApp.assert_called_once()
        emit.assert_called_once_with({"phase": "host-acquired", "process_id": 123})

    def test_native_probe_failure_closes_fixture_without_ready_event(self):
        app, emit = self.app(), Mock()
        app.RevisionNumber = Mock(side_effect=RuntimeError("disconnected"))
        with self.assertRaisesRegex(RuntimeError, "disconnected"):
            fixture.create_host(Mock(DispatchEx=Mock(return_value=app)), Mock(), emit)
        app.ExitApp.assert_called_once()
        self.assertEqual(emit.call_count, 1)

    def run_main(self, client):
        pythoncom = SimpleNamespace(
            com_error=ComError,
            CoInitialize=Mock(),
            CoUninitialize=Mock(),
            PumpWaitingMessages=Mock(),
        )
        with patch.dict(
            sys.modules,
            {
                "pythoncom": pythoncom,
                "win32com": SimpleNamespace(client=client),
                "win32com.client": client,
            },
        ):
            try:
                fixture.main()
            finally:
                pythoncom.CoUninitialize.assert_called_once()

    def test_main_refuses_existing_host_without_creating_or_closing_it(self):
        client = Mock(GetActiveObject=Mock(return_value=self.app()))
        with self.assertRaisesRegex(RuntimeError, "refuses to reuse"):
            self.run_main(client)
        client.DispatchEx.assert_not_called()

    def test_main_does_not_treat_access_failure_as_absent_host(self):
        client = Mock(GetActiveObject=Mock(side_effect=ComError(0x80070005)))
        with self.assertRaises(ComError):
            self.run_main(client)
        client.DispatchEx.assert_not_called()

    def test_main_only_activates_after_known_absent_rot_result(self):
        for hresult in (0x800401E3, 0x80040154):
            with (
                self.subTest(hresult=hresult),
                patch.object(fixture, "create_host") as create,
            ):
                client = Mock(GetActiveObject=Mock(side_effect=ComError(hresult)))
                self.run_main(client)
                self.assertIs(create.call_args.args[0], client)
