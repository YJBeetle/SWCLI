"""Test-only equation handoff guards; no native COM runtime proof."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

path = Path(__file__).resolve().parents[1] / "scripts/ci/windows/equation-fixture-daemon.py"
spec = importlib.util.spec_from_file_location("fixture_worker_test", path)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


class WorkerFixtureTests(unittest.TestCase):
    def test_exact_session_document_and_one_shot_are_required(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            payload = {"session_id": "owner", "process_id": 123,
                       "document_descriptor": {"document_id": "d-fixture"},
                       "native_name": "D1@Sketch1@Part1"}
            (directory / "request.json").write_text(json.dumps(payload))
            result = {"ok": True, "document": {"document_id": "d-fixture"}}
            with mock.patch.object(worker.server, "execute_operation", return_value=result), \
                    mock.patch.object(worker.fixture, "add_native_equation", return_value={"equation_index": 0}) as native, \
                    mock.patch.object(worker, "_com_value", return_value=False):
                worker.install_fixture_hook(directory)
                execute = worker.server.execute_operation
                app = object()
                for operation, session, doc in (("document.list", "owner", "d-fixture"),
                                                ("document.inspect", "other", "d-fixture"),
                                                ("document.inspect", "owner", "d-other")):
                    execute(app, operation, {}, session_id=session, document_id=doc)
                    native.assert_not_called()
                    self.assertTrue((directory / "request.json").exists())
                execute(app, "document.inspect", {}, session_id="owner", document_id="d-fixture")
                native.assert_called_once_with(process_id=123, document_descriptor=payload["document_descriptor"],
                                               native_name=payload["native_name"], app=app)
                receipt = json.loads((directory / "result.json").read_text())
                self.assertTrue(receipt["success"])
                self.assertFalse(receipt["native_fixture"]["visible"])
                self.assertTrue((directory / "consumed.json").exists())
                execute(app, "document.inspect", {}, session_id="owner", document_id="d-fixture")
                native.assert_called_once()

    def test_native_failure_is_recorded_and_never_retried(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "request.json").write_text(json.dumps({"session_id": "owner", "process_id": 123,
                "document_descriptor": {"document_id": "d-fixture"}, "native_name": "D1@Sketch1@Part1"}))
            with mock.patch.object(worker.server, "execute_operation", return_value={"ok": True, "document": {"document_id": "d-fixture"}}), \
                    mock.patch.object(worker.fixture, "add_native_equation", side_effect=RuntimeError("native failure")) as native:
                worker.install_fixture_hook(directory)
                for _ in range(2):
                    worker.server.execute_operation(object(), "document.inspect", {}, session_id="owner", document_id="d-fixture")
                native.assert_called_once()
                receipt = json.loads((directory / "result.json").read_text())
                self.assertFalse(receipt["success"])
                self.assertEqual(receipt["error"]["message"], "native failure")
