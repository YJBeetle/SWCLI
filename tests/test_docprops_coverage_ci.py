"""Cross-surface outgoing contracts and adversarial evidence checks; no CAD."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from swcli.cli import build_parser, _typed_operation
from swcli.mcp import DaemonBridge
from swcli.operation_schemas import OPERATION_CATALOG, validate_operation_request
from swcli.sdk import Client

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("docprops_audit", ROOT / "scripts/ci/audit-docprops-calibration.py")
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)


class SurfaceTests(unittest.TestCase):
    def test_all_matrix_operations_preserve_values_and_context_across_cli_sdk_mcp(self):
        matrix = json.loads((ROOT / "docs/verification/docprops-capabilities-v1.json").read_text())
        for row in matrix["public_operations"]:
            with self.subTest(operation=row["operation"]):
                context = dict(document_id="d-ab12cd", expected_update_stamp=0)
                if row["write"]:
                    context["lease_id"] = "l-ab12cd34ef56"
                argv = row["cli"] + ["--document", context["document_id"], "--if-update-stamp", "0", "--json"]
                if row["write"]:
                    argv += ["--lease", context["lease_id"]]
                parsed = _typed_operation(build_parser().parse_args(argv))
                self.assertEqual(parsed, (row["operation"], row["parameters"], True,
                                          context["document_id"], 0, context.get("lease_id")))
                self.assertEqual(OPERATION_CATALOG[row["operation"]].lease_guarded, row["write"])
                validate_operation_request(row["operation"], row["parameters"], **context)
                client = Client()
                method = getattr(client.document, row["operation"].split(".")[1].replace("-", "_"))
                with patch.object(client, "_execute", return_value=Mock()) as execute:
                    method(**row["parameters"], **context)
                    self.assertEqual(execute.call_args.args, (row["operation"], row["parameters"]))
                    for key, value in context.items():
                        self.assertEqual(execute.call_args.kwargs[key], value)
                bridge = DaemonBridge(session_id="coverage")
                with patch("swcli.mcp.call_daemon", return_value={"api_version": "swcli/v1", "request_id": "coverage", "duration_ms": 0, "success": True, "result": {"ok": True}}) as wire:
                    result = bridge.call("execute", dict(operation=row["operation"], parameters=row["parameters"], **context))
                    self.assertTrue(result["success"])
                    self.assertEqual(wire.call_args.args, (row["operation"], row["parameters"]))
                    for key, value in context.items():
                        self.assertEqual(wire.call_args.kwargs[key], value)


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        native = self.root / "native"
        native.mkdir()
        self.driver = dict(source_head="a"*40, platform="win32", elapsed_seconds=30, exit_code=0, failure=None,
                           native_timeout_seconds=600, group_timeout_seconds=1800)
        self.report = dict(success=True, diagnostic_case="document-properties-calibration",
                           full_acceptance_eligible=False, cleanup_errors=[],
                           host=dict(process_id=123, revision="33.0"), cases=[])
        for kind, suffix in (("part", "SLDPRT"), ("assembly", "SLDASM")):
            path = native / ("properties." + suffix)
            path.write_bytes(kind.encode())
            self.report["cases"].append(dict(kind=kind, success=True, file_sha256=audit_module.digest(path),
                state_before={"stamp":0}, state_after={"stamp":0}, listing={"properties":[]}, reopened_properties={"properties":[]}))
        self.calls = ["acquire-owned-host", "ExitApp", "WaitForOwnedProcess", "CloseProcessHandle", "CoUninitialize"]
        self.persist()

    def persist(self):
        (self.root / "driver.json").write_text(json.dumps(self.driver))
        (self.root / "native/report.json").write_text(json.dumps(self.report))
        trace = [dict(call=call, phase=phase, time=i*2 + (phase == "end")) for i, call in enumerate(self.calls) for phase in ("begin", "end")]
        (self.root / "native/trace.jsonl").write_text("".join(json.dumps(r)+"\n" for r in trace))

    def audit(self):
        return audit_module.audit(self.root, "a"*40)

    def test_complete_internal_evidence_never_becomes_public_acceptance(self):
        result = self.audit()
        self.assertTrue(result["success"], result)
        self.assertFalse(result["full_acceptance_eligible"])
        self.assertEqual(len(result["originals"]), 5)

    def test_tampered_saved_copy_fails(self):
        (self.root / "native/properties.SLDPRT").write_bytes(b"tampered")
        self.assertFalse(self.audit()["success"])

    def test_unproven_host_exit_source_or_budget_never_passes(self):
        for target, key, value in [(self.driver,"source_head","b"*40), (self.driver,"platform","darwin"),
                                   (self.driver,"native_timeout_seconds",601), (self.report,"cleanup_errors",["failed"]),
                                   (self.report,"full_acceptance_eligible",True)]:
            with self.subTest(key=key):
                old = target[key]; target[key] = value; self.persist()
                self.assertFalse(self.audit()["success"])
                target[key] = old
        self.calls.remove("WaitForOwnedProcess"); self.persist()
        self.assertFalse(self.audit()["success"])

    def test_first_native_error_survives_cleanup_and_summary(self):
        path = self.root / "native/trace.jsonl"
        path.write_text(path.read_text().replace('"phase": "end"', '"phase": "error", "error": "first native failure"', 1))
        result = self.audit()
        self.assertFalse(result["success"])
        self.assertEqual(result["first_failure"]["error"], "first native failure")

    def test_truncated_or_missing_original_trace_fails(self):
        path = self.root / "native/trace.jsonl"
        path.write_text(path.read_text() + '{"call":')
        self.assertFalse(self.audit()["success"])
        path.unlink()
        self.assertFalse(self.audit()["success"])



class DriverTests(unittest.TestCase):
    def test_native_and_group_watchdogs_stop_one_child_without_retry(self):
        spec = importlib.util.spec_from_file_location("targeted_driver", ROOT / "scripts/ci/run-docprops-targeted.py")
        driver = importlib.util.module_from_spec(spec); spec.loader.exec_module(driver)
        for native_call, expected_time in ((True, 700), (False, 1800)):
            with self.subTest(native_call=native_call), tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp) / "evidence"
                def start(*args, **kwargs):
                    if native_call:
                        (output / "native").mkdir()
                        (output / "native/trace.jsonl").write_text(json.dumps(dict(call="native-write", phase="begin", time=0))+"\n")
                    return child
                child = Mock(); child.poll.return_value = None; child.wait.return_value = -15
                argv = ["driver", "--output", str(output), "--expected-head", "a"*40, "--swconst", "official.tlb"]
                with patch.object(driver.sys, "argv", argv), patch.object(driver.sys, "platform", "win32"), \
                     patch.object(driver.subprocess, "check_output", return_value="a"*40), \
                     patch.object(driver.subprocess, "Popen", side_effect=start) as spawn, \
                     patch.object(driver.time, "sleep"), patch.object(driver.time, "monotonic", side_effect=range(0, 3000, 100)):
                    self.assertEqual(driver.main(), 1)
                spawn.assert_called_once(); child.terminate.assert_called_once(); child.kill.assert_not_called()
                receipt = json.loads((output / "driver.json").read_text())
                self.assertEqual(receipt["failure"]["reason"], "timeout")
                self.assertGreaterEqual(receipt["elapsed_seconds"], expected_time)
                self.assertIn("unproven", receipt["failure"]["cleanup"])

    def test_workflow_limits_branch_manual_opt_in_and_skips_full_gate(self):
        text = (ROOT / ".github/workflows/ci.yml").read_text()
        targeted = text.split("  docprops-targeted:\n")[1]
        self.assertIn("github.event_name == 'workflow_dispatch'", targeted)
        self.assertIn("refs/heads/codex/docprops-coverage-ci", targeted)
        self.assertIn("inputs.docprops_targeted && !inputs.native_full", targeted)
        self.assertIn("  test:\n    if: ${{ !inputs.docprops_targeted }}", text)
        self.assertIn("  package:\n    if: ${{ !inputs.docprops_targeted }}", text)
        self.assertLess(targeted.index("Head mismatch"), targeted.index("secrets.RCLONE_CONFIG_B64"))
        self.assertIn("group: swcli-docprops-baseline-properties-${{ github.ref }}", targeted)
        self.assertIn("cancel-in-progress: false", targeted)
        self.assertNotIn("group: swcli-hosted-windows-solidworks", targeted)
        full = text.split("  solidworks-e2e:\n")[1].split("  release:\n")[0]
        release = text.split("  release:\n")[1].split("  docprops-targeted:\n")[0]
        self.assertIn("group: swcli-hosted-windows-solidworks", full)
        self.assertIn("group: swcli-release-${{ github.ref }}", release)
        template = (ROOT / "scripts/ci/templates/docprops-targeted.yml").read_text()
        self.assertIn("group: swcli-docprops-baseline-properties-${{ github.ref }}", template)
        self.assertIn("cancel-in-progress: false", template)
        self.assertNotIn("smoke-solidworks.ps1", targeted)
        self.assertNotIn("pull_request", text)


if __name__ == "__main__":
    unittest.main()
