"""Portable checks of the TEST-ONLY equation gate, not native COM proof."""

import importlib.util
import io
import json
import math
from pathlib import Path
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest import mock

script = (
    Path(__file__).resolve().parents[1]
    / "scripts/ci/windows/verify-equation-dimension.py"
)
spec = importlib.util.spec_from_file_location("equation_smoke", script)
equation_smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(equation_smoke)


class FakeDaemon:
    def __init__(self):
        self.owned = False
        self.stamp = 1
        self.controlled = False
        self.create_partial_failure = False
        self.modify_rejected = False
        self.modify_inspect = False
        self.bad_volume = False
        self.bad_identity = False
        self.bad_control = False
        self.bad_error = False
        self.close_fails = False
        self.replaced_host = False
        self.health_calls = 0
        self.calls = []

    def descriptor(self):
        return {
            "document_id": "d-000001",
            "title": "零件1",
            "path": "",
            "active": True,
            "update_stamp": self.stamp,
        }

    def call(self, operation, parameters=None, **context):
        self.calls.append((operation, parameters, context))
        values = parameters or {}
        if operation == "daemon.health":
            self.health_calls += 1
            pid = 999 if self.replaced_host and self.health_calls > 1 else 123
            return {
                "success": True,
                "result": {
                    "host_connected": True,
                    "host": {"process_id": pid},
                    "operations": [
                        "sketch.dimension-diameter",
                        "dimension.inspect",
                        "dimension.set",
                    ],
                },
            }
        if operation == "document.create":
            self.owned = True
            result = {"ok": True, "document": self.descriptor()}
            if self.create_partial_failure:
                return {
                    "success": False,
                    "error": {
                        "code": "PartialCreate",
                        "message": "created then failed",
                    },
                    "result": result,
                }
            return {"success": True, "result": result}
        if context["document_id"] != "d-000001":
            raise AssertionError("gate touched a document it did not create")
        result = {"ok": True, "document": self.descriptor()}
        if operation == "document.inspect":
            pass
        elif operation == "sketch.circle":
            result["sketch"] = {"sketch_id": "s-000001"}
            self.stamp += 1
        elif operation in ("sketch.dimension-diameter", "dimension.inspect"):
            result["dimension"] = {
                "dimension_id": "m-000001",
                "sketch_id": "s-000001",
                "kind": "diameter",
                "unit": "millimeter",
                "value": 16,
                "native_name": "D1@草图1@零件1",
            }
            if operation == "sketch.dimension-diameter":
                self.stamp += 1
            else:
                if self.bad_identity:
                    result["dimension"]["dimension_id"] = "m-other1"
                result["editing"] = False
                result["equation_control"] = {
                    "controlled": self.controlled and not self.bad_control,
                    "equation_indices": [0],
                }
                if self.modify_inspect:
                    self.stamp += 1
        elif operation == "feature.extrude":
            self.stamp += 1
        elif operation == "sketch.inspect":
            result.update(
                geometry_complete=True,
                editing=False,
                coordinate_system="sketch-local",
                profile_segment_count=1,
                segment_count=1,
                sketch={"absorbed": True},
                segments=[
                    {
                        "construction": False,
                        "geometry": {
                            "kind": "arc",
                            "complete_circle": True,
                            "radius_mm": 8,
                            "center_mm": {"x": 3, "y": 4, "z": 0},
                        },
                    }
                ],
            )
        elif operation == "document.measure":
            result["metrics"] = {
                "solid_body_count": 1,
                "volume_mm3": math.pi * 8**2 * 10 + int(self.bad_volume),
                "surface_area_mm2": 2 * math.pi * 8 * 18,
            }
        elif operation == "dimension.set":
            if self.modify_rejected:
                self.stamp += 1
            return {
                "success": False,
                "error": {
                    "code": (
                        "DimensionSetFailed"
                        if self.bad_error
                        else "DimensionExternallyControlled"
                    ),
                    "message": "controlled",
                },
            }
        elif operation == "document.close":
            if self.close_fails:
                return {
                    "success": False,
                    "error": {"code": "CloseFailed", "message": "close failed"},
                }
            self.owned = False
        else:
            raise AssertionError(operation)
        return {"success": True, "result": result}

    def fixture(self, **context):
        self.fixture_context = context
        self.controlled = True
        self.stamp += 1
        return {"equation_index": 0, "equation": '"D1@草图1" = 16mm'}


class EquationGateTests(unittest.TestCase):
    def setUp(self):
        self.daemon = FakeDaemon()
        patcher = mock.patch.object(
            equation_smoke, "call_daemon", side_effect=self.daemon.call
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_gate(self, **options):
        return equation_smoke.run_gate(
            endpoint="127.0.0.1:18495",
            session_id="fixture",
            fixture=self.daemon.fixture,
            **options,
        )

    def test_complete_gate_verifies_control_and_unchanged_model_then_closes_only_owned_doc(
        self,
    ):
        record = self.run_gate()
        self.assertTrue(record["success"], record)
        self.assertFalse(self.daemon.owned)
        self.assertEqual(record["update_stamp_before"], record["update_stamp_after"])
        self.assertEqual(self.daemon.fixture_context["process_id"], 123)
        self.assertEqual(
            self.daemon.fixture_context["document_descriptor"]["title"], "零件1"
        )
        self.assertEqual(self.daemon.fixture_context["native_name"], "D1@草图1@零件1")
        self.assertEqual(self.daemon.calls[-1][0], "document.close")
        self.assertEqual(self.daemon.calls[-1][1], {"discard": True})
        self.assertEqual(self.daemon.calls[-1][2]["document_id"], "d-000001")
        self.assertFalse(
            any(
                operation.startswith("daemon.") and operation != "daemon.health"
                for operation, _, _ in self.daemon.calls
            )
        )

    def test_changed_stamp_wrong_identity_geometry_or_control_fails_and_still_cleans_up(
        self,
    ):
        for defect in (
            "modify_rejected",
            "modify_inspect",
            "bad_volume",
            "bad_identity",
            "bad_control",
            "bad_error",
            "replaced_host",
        ):
            with self.subTest(defect=defect):
                self.daemon = FakeDaemon()
                setattr(self.daemon, defect, True)
                with mock.patch.object(
                    equation_smoke, "call_daemon", side_effect=self.daemon.call
                ):
                    record = self.run_gate()
                self.assertFalse(record["success"])
                self.assertIn("failure", record)
                self.assertFalse(self.daemon.owned)
                self.assertEqual(record["cleanup_errors"], [])

    def test_partial_native_document_creation_is_cleaned_even_when_rpc_failed(self):
        self.daemon.create_partial_failure = True
        record = self.run_gate()
        self.assertFalse(record["success"])
        self.assertFalse(self.daemon.owned)
        self.assertIn("PartialCreate", record["failure"]["message"])
        self.assertEqual(
            [operation for operation, _, _ in self.daemon.calls],
            ["daemon.health", "document.create", "document.close"],
        )

    def test_fixture_failure_and_cleanup_failure_are_both_retained(self):
        self.daemon.close_fails = True
        record = equation_smoke.run_gate(
            endpoint="endpoint",
            session_id="fixture",
            fixture=mock.Mock(side_effect=RuntimeError("native fixture failed")),
        )
        self.assertFalse(record["success"])
        self.assertEqual(record["failure"]["message"], "native fixture failed")
        self.assertIn("close failed", record["cleanup_errors"][0]["message"])
        self.assertEqual(record["cleanup_errors"][0]["document_id"], "d-000001")

    def test_cleanup_failure_alone_is_not_a_pass(self):
        self.daemon.close_fails = True
        record = self.run_gate()
        self.assertFalse(record["success"])
        self.assertNotIn("failure", record)
        self.assertTrue(record["cleanup_errors"])

    def test_optional_evidence_is_utf8_and_no_stdout_output_dir_is_required(self):
        with tempfile.TemporaryDirectory() as directory:
            record = self.run_gate(output_dir=directory)
            raw = (Path(directory) / "equation-dimension-result.json").read_bytes()
        self.assertIn("零件1".encode("utf-8"), raw)
        self.assertEqual(json.loads(raw), record)

    def test_existing_evidence_is_preserved_without_any_daemon_call(self):
        with tempfile.TemporaryDirectory() as directory:
            record_path = Path(directory) / "equation-dimension-result.json"
            record_path.write_text("previous native proof", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                self.run_gate(output_dir=directory)
            self.assertEqual(
                record_path.read_text(encoding="utf-8"), "previous native proof"
            )
        self.assertEqual(self.daemon.calls, [])

    def test_unwritable_destination_and_failed_initial_write_never_touch_daemon(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(
                Path, "open", side_effect=PermissionError("unwritable proof")
            ):
                with self.assertRaisesRegex(PermissionError, "unwritable proof"):
                    self.run_gate(output_dir=directory)
            with mock.patch.object(
                equation_smoke,
                "_write_record",
                side_effect=OSError("initial write failed"),
            ):
                with self.assertRaisesRegex(OSError, "initial write failed"):
                    self.run_gate(output_dir=directory)
        self.assertEqual(self.daemon.calls, [])

    def test_provisional_evidence_is_flushed_before_the_first_daemon_call(self):
        with tempfile.TemporaryDirectory() as directory:
            record_path = Path(directory) / "equation-dimension-result.json"

            def call_after_reservation(*args, **kwargs):
                provisional = json.loads(record_path.read_text(encoding="utf-8"))
                self.assertFalse(provisional["success"])
                self.assertEqual(provisional["status"], "running")
                return self.daemon.call(*args, **kwargs)

            with mock.patch.object(
                equation_smoke, "call_daemon", side_effect=call_after_reservation
            ):
                result = self.run_gate(output_dir=directory)
            self.assertTrue(result["success"], result)
            final = json.loads(record_path.read_text(encoding="utf-8"))
            self.assertTrue(final["success"])
            self.assertNotIn("status", final)

    def test_final_evidence_write_failure_never_hides_cleanup_or_original_failure(self):
        write_record = equation_smoke._write_record
        for failure in (False, True):
            with (
                self.subTest(original_failure=failure),
                tempfile.TemporaryDirectory() as directory,
            ):
                self.daemon = FakeDaemon()
                self.daemon.bad_control = failure
                writes = 0

                def write_then_fail(stream, record):
                    nonlocal writes
                    writes += 1
                    if writes == 2:
                        raise OSError("final proof write failed")
                    write_record(stream, record)

                with (
                    mock.patch.object(
                        equation_smoke, "call_daemon", side_effect=self.daemon.call
                    ),
                    mock.patch.object(
                        equation_smoke, "_write_record", side_effect=write_then_fail
                    ),
                ):
                    record = self.run_gate(output_dir=directory)
                self.assertFalse(record["success"])
                self.assertFalse(self.daemon.owned)
                self.assertEqual(record["cleanup_errors"], [])
                self.assertEqual(
                    record["evidence_errors"],
                    [{"type": "OSError", "message": "final proof write failed"}],
                )
                self.assertEqual(
                    record["failure"]["type"],
                    "RuntimeError" if failure else "EvidenceWriteFailed",
                )
                provisional = json.loads(
                    (Path(directory) / "equation-dimension-result.json").read_text(
                        encoding="utf-8"
                    )
                )
                self.assertFalse(provisional["success"])

    def test_evidence_stream_close_failure_is_not_reported_as_a_pass(self):
        stream = io.StringIO()
        with (
            tempfile.TemporaryDirectory() as directory,
            mock.patch.object(Path, "open", return_value=stream),
            mock.patch.object(
                stream, "close", side_effect=OSError("proof close failed")
            ),
        ):
            record = self.run_gate(output_dir=directory)
        self.assertFalse(record["success"])
        self.assertFalse(self.daemon.owned)
        self.assertEqual(record["failure"]["type"], "EvidenceWriteFailed")
        self.assertEqual(record["evidence_errors"][0]["message"], "proof close failed")
        stream.close()

    def test_main_prints_only_compact_summary_and_handles_preflight_failure(self):
        full_record = {
            "success": True,
            "cleanup_errors": [],
            "evidence_path": "proof.json",
            "events": [{"host": "x" * 100000}],
        }
        with (
            mock.patch.object(equation_smoke, "run_gate", return_value=full_record),
            mock.patch("sys.stdout", new_callable=io.StringIO) as stdout,
        ):
            self.assertEqual(equation_smoke.main([]), 0)
            summary = json.loads(stdout.getvalue())
            self.assertEqual(
                summary,
                {
                    "success": True,
                    "failure": None,
                    "cleanup_errors": [],
                    "evidence_path": "proof.json",
                },
            )
            self.assertLess(len(stdout.getvalue()), 300)
        with (
            mock.patch.object(
                equation_smoke, "run_gate", side_effect=FileExistsError("proof exists")
            ),
            mock.patch("sys.stdout", new_callable=io.StringIO) as stdout,
        ):
            self.assertEqual(equation_smoke.main(["--output-dir", "proof"]), 1)
            summary = json.loads(stdout.getvalue())
            self.assertFalse(summary["success"])
            self.assertEqual(summary["failure"]["type"], "FileExistsError")
            self.assertEqual(summary["cleanup_errors"], [])
            self.assertTrue(
                summary["evidence_path"].endswith("equation-dimension-result.json")
            )

    def test_main_propagates_failure_exit_status_and_structured_record(self):
        with (
            mock.patch.object(
                equation_smoke, "run_gate", return_value={"success": False}
            ),
            mock.patch("sys.stdout", new_callable=io.StringIO) as stdout,
        ):
            self.assertEqual(
                equation_smoke.main(["--session", "test", "--endpoint", "host:1"]), 1
            )
            self.assertFalse(json.loads(stdout.getvalue())["success"])


class NativeFixtureBindingTests(unittest.TestCase):
    def setUp(self):
        self.equations = []
        self.document = SimpleNamespace(
            GetTitle=lambda: "零件1",
            GetPathName=lambda: "",
            GetType=lambda: 1,
            GetConfigurationNames=lambda: ("默认",),
            SketchManager=SimpleNamespace(ActiveSketch=None),
            ConfigurationManager=SimpleNamespace(
                ActiveConfiguration=SimpleNamespace(Name="默认")
            ),
            EditRebuild3=lambda: True,
        )
        self.add_call = mock.Mock(side_effect=self.add)
        self.equation_call = mock.Mock(side_effect=lambda index: self.equations[index])
        self.manager = SimpleNamespace(
            GetCount=lambda: len(self.equations),
            Add2=self.add_call,
            Equation=self.equation_call,
        )
        self.document.GetEquationMgr = lambda: self.manager
        self.app = SimpleNamespace(GetProcessID=lambda: 123, ActiveDoc=self.document)
        self.pythoncom = ModuleType("pythoncom")
        self.pythoncom.CoInitialize = mock.Mock()
        self.pythoncom.CoUninitialize = mock.Mock()
        self.win32com = ModuleType("win32com")
        self.win32com.__path__ = []
        self.client = ModuleType("win32com.client")
        self.client.GetActiveObject = mock.Mock(return_value=self.app)
        self.win32com.client = self.client
        patcher = mock.patch.dict(
            "sys.modules",
            {
                "pythoncom": self.pythoncom,
                "win32com": self.win32com,
                "win32com.client": self.client,
            },
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def add(self, index, expression, solve):
        self.equations.append(expression)
        return len(self.equations) - 1

    def call(self, **changes):
        return equation_smoke.add_native_equation(
            **{
                "process_id": 123,
                "document_descriptor": {"title": "零件1", "path": ""},
                "native_name": "D1@草图1@零件1",
                **changes,
            }
        )

    def test_getactiveobject_pid_document_and_configuration_guard_then_indexed_property_read(
        self,
    ):
        result = self.call()
        self.client.GetActiveObject.assert_called_once_with("SldWorks.Application")
        self.add_call.assert_called_once_with(-1, '"D1@草图1" = 16mm', True)
        self.equation_call.assert_called_once_with(0)
        self.assertEqual(result["count_before"], 0)
        self.assertEqual(result["count_after"], 1)
        self.assertEqual(result["equation_index"], 0)
        self.assertEqual(result["configuration"], "默认")
        self.pythoncom.CoInitialize.assert_called_once()
        self.pythoncom.CoUninitialize.assert_called_once()
        self.assertFalse(hasattr(self.client, "Dispatch"))

    def test_wrong_pid_or_active_document_never_mutates_and_balances_com(self):
        for setup in (
            lambda: setattr(self.app, "GetProcessID", lambda: 999),
            lambda: setattr(self.app, "ActiveDoc", None),
            lambda: setattr(self.document, "GetTitle", lambda: "user model"),
            lambda: setattr(
                self.document, "GetPathName", lambda: r"C:\Workspace\user.SLDPRT"
            ),
            lambda: setattr(
                self.document, "GetConfigurationNames", lambda: ("Default", "Other")
            ),
            lambda: setattr(self.document.SketchManager, "ActiveSketch", object()),
        ):
            with self.subTest(setup=setup):
                self.setUp()
                setup()
                with self.assertRaises(RuntimeError):
                    self.call()
                self.add_call.assert_not_called()
                self.pythoncom.CoUninitialize.assert_called_once()

    def test_missing_rot_host_never_dispatches_a_replacement(self):
        self.client.GetActiveObject.side_effect = RuntimeError("no host")
        with self.assertRaisesRegex(RuntimeError, "no host"):
            self.call()
        self.add_call.assert_not_called()
        self.pythoncom.CoUninitialize.assert_called_once()

    def test_invalid_name_or_pid_is_rejected_before_attaching(self):
        for changes in (
            {"process_id": True},
            {"process_id": 0},
            {"native_name": "D1@Sketch"},
            {"native_name": 'D1@injected"@Part'},
            {"native_name": "D1@line\n@Part"},
        ):
            with self.subTest(changes=changes), self.assertRaises(RuntimeError):
                self.call(**changes)
        self.client.GetActiveObject.assert_not_called()
        self.pythoncom.CoInitialize.assert_not_called()

    def test_native_add_rebuild_or_indexed_getter_failure_is_never_a_pass(self):
        for defect in ("existing", "add", "rebuild", "getter"):
            with self.subTest(defect=defect):
                self.setUp()
                if defect == "existing":
                    self.equations.append('"user" = 1')
                elif defect == "add":
                    self.add_call.side_effect = lambda *args: -1
                elif defect == "rebuild":
                    self.document.EditRebuild3 = lambda: False
                else:
                    self.equation_call.side_effect = RuntimeError(
                        "indexed getter unavailable"
                    )
                with self.assertRaises(RuntimeError):
                    self.call()
                self.pythoncom.CoUninitialize.assert_called_once()


if __name__ == "__main__":
    unittest.main()
