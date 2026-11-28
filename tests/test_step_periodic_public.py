"""Portable public periodic-face gate contracts and independent-reader routing."""
import json
from pathlib import Path
import tempfile
import unittest

from swcli.cli import _typed_operation, build_parser

from test_step_periodic_reader import FakeAPI, driver, supervisor
from test_step_periodic_evidence import synthetic
from gate_support import step_periodic_public as periodic


def request(request_id, calls):
    def row(sequence, stage, call, phase):
        return json.dumps(dict(event="swcli.native-call", request_id=request_id, operation="document.export",
                               sequence=sequence, stage=stage, call=call, phase=phase, worker_pid=91))
    lines = [row(0, "operation", "document.export", "begin")]
    for number, (stage, call) in enumerate(calls, 1):
        lines.extend((row(number, stage, call, "begin"), row(number, stage, call, "end")))
    lines.append(row(0, "operation", "document.export", "end"))
    return "\n".join(lines).encode("ascii")


class PeriodicPublicTests(unittest.TestCase):
    def test_real_cli_preserves_explicit_false_and_omitted_parameter(self):
        parser = build_parser()
        for split in (None, False, True):
            with self.subTest(split=split):
                args = parser.parse_args([
                    *periodic.export_arguments(Path("cylinder.step"), "ap214", split),
                    "--document", "d-part", "--lease", "l-lease", "--if-update-stamp", "7",
                ])
                operation, parameters = _typed_operation(args)[:2]
                self.assertEqual(operation, "document.export")
                self.assertEqual(parameters["step_geometry"], "solid-surface")
                self.assertEqual(args.expected_update_stamp, 7)
                if split is None:
                    self.assertNotIn("step_split_periodic_faces", parameters)
                else:
                    self.assertIs(parameters["step_split_periodic_faces"], split)

    def test_chinese_refusal_requires_specific_error_and_zero_preference_reads_or_save(self):
        case = dict(mode="refusal", request_id="zh")
        guard = [("read", "GetCurrentLanguage")]
        self.assertEqual(periodic.check_export_trace(request("zh", guard), case)["step_preference_call_count"], 0)
        for bad in (("step-export", "periodic-before.swStepExportSplitPeriodic"),
                    ("step-export", "ISldWorks.GetUserPreferenceIntegerValue.swStepAP"),
                    ("document-export", periodic.SAVE_CALL)):
            with self.subTest(call=bad), self.assertRaisesRegex(ValueError, "reached preference or native save"):
                periodic.check_export_trace(request("zh", guard + [bad]), case)
        with self.assertRaisesRegex(ValueError, "incomplete"):
            periodic.check_export_trace(b"\n".join(request("zh", guard).splitlines()[:-1]), case)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "kept.step"
            target.write_bytes(b"kept")
            result = dict(ok=False, error=dict(type=periodic.LANGUAGE_REFUSAL),
                          mutation=dict(attempted=False, may_have_changed=False))
            periodic.check_refusal(result, target, b"kept")
            result["error"]["type"] = "StepSplitCalibrationRequired"
            with self.assertRaisesRegex(ValueError, "dedicated language"):
                periodic.check_refusal(result, target, b"kept")

    def test_mixed_native_stderr_ignores_only_non_json_lines(self):
        case = dict(mode="refusal", request_id="zh")
        good = request("zh", [("read", "GetCurrentLanguage")])
        mixed = b"ConnectionResetError: [WinError 10054] \\xd4\\xb6\\xb3\\xcc\n" + good
        self.assertEqual(periodic.check_export_trace(mixed, case), periodic.check_export_trace(good, case))
        for bad in (
            b'  {"unrelated":"\\xb3"}\n',
            b'  {"unrelated":NaN}\n',
            b'  {"event":"other","event":"swcli.native-call"}\n',
            b'  {"truncated":\n',
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                periodic.check_export_trace(bad + good, case)

    def test_omission_requires_old_two_preference_path_and_no_language_gate(self):
        case = dict(mode="legacy", request_id="old")
        calls = [("step-export", "ISldWorks.GetUserPreferenceIntegerValue.swStepAP"),
                 ("document-export", periodic.SAVE_CALL)]
        self.assertEqual(periodic.check_export_trace(request("old", calls), case)["native_save_calls"],
                         [periodic.SAVE_CALL])
        with self.assertRaisesRegex(ValueError, "language gate"):
            periodic.check_export_trace(request("old", [("read", "GetCurrentLanguage")] + calls), case)
        with self.assertRaisesRegex(ValueError, "preference trace differs"):
            periodic.check_export_trace(request("old", calls + [("step-export", "periodic-before." + periodic.TOGGLE)]), case)

    def test_independent_reader_imports_only_the_four_verified_writer_files(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            writer = workspace / "writer"
            writer.mkdir()
            source = writer / "public-cylinder.SLDPRT"
            source.write_bytes(b"portable source fixture")
            head = "a" * 40
            trace_cases = []
            trace = []
            outputs = []
            for protocol, split in periodic.PLAN:
                case = periodic.label(protocol, split)
                target = writer / (case + ".step")
                raw = synthetic(split)
                if protocol == "ap203":
                    raw = raw.replace(b"AUTOMOTIVE_DESIGN", b"CONFIG_CONTROL_DESIGN")
                target.write_bytes(raw)
                outputs.append(dict(name=target.name, protocol=protocol, split_periodic_faces=split,
                                    sha256=periodic.digest(target), request_id=case))
                trace_cases.append(dict(mode="periodic", request_id=case))
                trace.append(request(case, [("read", "GetCurrentLanguage"),
                                           ("step-export", "periodic-before." + periodic.TOGGLE),
                                           ("document-export", periodic.SAVE_CALL)]))
            trace_bytes = b"\n".join(trace)
            trace_path = writer / "daemon.stderr.log"
            trace_path.write_bytes(trace_bytes)
            host = dict(process_id=4321, revision="33.5.0", language="english", owned_by_daemon=True,
                        visible=False, shared_interactive=False)
            manifest = writer / "report.json"
            supervisor.durable_json(manifest, dict(
                source_commit=head, evidence_scope=periodic.WRITER_SCOPE, success=True, cleanup_errors=[],
                host=host, host_after=host, owned_exit_confirmed=True, daemon_returncode=0,
                source_sha256=periodic.digest(source), outputs=outputs, trace_cases=trace_cases,
                daemon_trace_sha256=periodic.digest(trace_path),
                trace_observations=[periodic.check_export_trace(trace_bytes, row) for row in trace_cases],
            ))
            binding = dict(path=str(manifest), sha256=periodic.digest(manifest))
            output = workspace / "reader"
            output.mkdir()
            api = FakeAPI()
            code, report = driver.run(output, workspace / "swconst.tlb", head, api, public_writer=binding)
            self.assertEqual(code, 0, report.get("failure"))
            self.assertEqual(api.exports, [])
            self.assertEqual(api.imports, [str(writer / row["name"]) for row in outputs])
            self.assertEqual(len(report["artifacts"]), 4)
            self.assertTrue(all(row["success"] for row in report["cases"]))
            supervisor.durable_json(output / "worker-finished.json", dict(
                success=True, returncode=0, report_sha256=periodic.digest(output / "report.json"),
                trace_sha256=periodic.digest(output / "trace.jsonl"),
            ))
            self.assertTrue(supervisor.terminal_result(output, 0, public_writer=binding)[0])

            corrupted = writer / outputs[-1]["name"]
            corrupted.write_bytes(corrupted.read_bytes() + b"changed")
            empty = workspace / "rejected-reader"
            empty.mkdir()
            unstarted = FakeAPI()
            code, report = driver.run(empty, workspace / "swconst.tlb", head, unstarted, public_writer=binding)
            self.assertEqual(code, 1)
            self.assertIn("hash changed", report["failure"]["message"])
            self.assertEqual(unstarted.events, [])
            self.assertEqual(unstarted.imports, [])
