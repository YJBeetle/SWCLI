"""Reporting must preserve public first failures and distinguish missing proof."""
import copy
import importlib.util
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("test_summary", ROOT / "scripts/ci/summarize-tests.py")
summary = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(summary)
SOURCE = {"commit": "a" * 40, "client_version": "0.1.0a17", "host": "windows", "scope": "full", "run_url": None}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def passed(**changes):
    return {"state": "completed", "success": True, "cleanup_errors": [], **changes}


def sets(rows=None, **changes):
    return {"completed": True, "success": True, "suite": "full", "coverage_scope": "full-plan",
            "expected_sets": list(summary.FULL_SET_NAMES),
            "sets": rows if rows is not None else [{"name": name, "success": True, "cleanup_errors": [], "seconds": 0}
                                                    for name in summary.FULL_SET_NAMES], "cleanup_errors": [], **changes}


class PublicSummaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def summarize(self, stages=()):
        report = summary.Summary(self.root, SOURCE)
        for stage in stages:
            report.stage(summary.parse_stage(stage))
        report.scan()
        return report.result()

    def test_expected_negative_commands_do_not_override_public_gate_pass(self):
        for name in ("properties.json", "visible.json", "attach-refusal.json"):
            write(self.root / name, passed(events=[{"returncode": 1, "result": {"success": False,
                  "error": {"code": "ExistingHostNotFound"}}}], commands=[{"exit_code": 23}]))
        value = self.summarize()
        self.assertEqual(value["totals"]["pass"], 3)
        self.assertIsNone(value["first_failure"])
        self.assertEqual(value["cleanup_errors"], [])

    def test_business_failure_wins_over_parent_stage_and_cleanup(self):
        write(self.root / "hidden/native-model/modeling.json", passed(success=False,
            error={"type": "NativeCallFailed", "message": "first API failed"}, cleanup_errors=["close failed"]))
        value = self.summarize(["functional-tests=failure", "cleanup=failure"])
        self.assertEqual(value["first_failure"]["code"], "NativeCallFailed")
        self.assertEqual(value["first_failure"]["message"], "first API failed")
        self.assertEqual(len(value["cleanup_errors"]), 2)
        self.assertNotIn(str(self.root), json.dumps(value))

    def test_partial_full_plan_lists_all_unexecuted_groups_as_skip(self):
        rows = [{"name": "native-model", "success": True, "cleanup_errors": [], "seconds": 0},
                {"name": "assemblies", "success": False, "error": {"type": "NativeFailure", "message": "assembly failed"},
                 "cleanup_errors": ["stop failed"], "seconds": 12.5}]
        write(self.root / "hidden/runtime-sets.json", sets(rows, completed=False, success=False))
        value = self.summarize(["functional-tests=failure"])
        groups = [row for row in value["phases"] if "/runtime-sets/" in row["name"]]
        self.assertEqual(len(groups), 19)
        self.assertEqual(sum(row["status"] == "SKIP" for row in groups), 17)
        by_name = {row["name"].rsplit("/", 1)[-1]: row for row in groups}
        self.assertEqual(by_name["native-model"]["seconds"], 0)
        self.assertEqual(by_name["assemblies"]["seconds"], 12.5)
        self.assertTrue(all(row["seconds"] is None for row in groups if row["status"] == "SKIP"))
        self.assertEqual(value["first_failure"]["code"], "NativeFailure")

    def test_successful_full_report_cannot_hide_missing_groups(self):
        write(self.root / "runtime-sets.json", sets([]))
        value = self.summarize()
        self.assertEqual(value["totals"]["skip"], 19)
        self.assertEqual(value["totals"]["fail"], 1)
        self.assertEqual(value["first_failure"]["code"], "IncompleteEvidence")

    def test_cleanup_only_failure_does_not_fabricate_a_business_first_failure(self):
        write(self.root / "properties.json", passed(success=False, cleanup_errors=["close failed"]))
        value = self.summarize()
        self.assertEqual(value["totals"]["fail"], 1)
        self.assertIsNone(value["first_failure"])
        self.assertEqual(value["cleanup_errors"][0]["message"], "close failed")
        (self.root / "properties.json").unlink()
        rows = [{"name": "native-model", "success": False, "cleanup_errors": ["host exit failed"]}]
        write(self.root / "runtime-sets.json", sets(rows, success=False, completed=False))
        self.assertIsNone(self.summarize()["first_failure"])

    def test_malformed_cleanup_types_never_create_a_pass_or_string_none(self):
        for malformed in (None, {"message": "bad shape"}, "not-an-array"):
            with self.subTest(value=malformed):
                write(self.root / "properties.json", passed(cleanup_errors=malformed))
                value = self.summarize()
                self.assertEqual(value["totals"]["pass"], 0)
                self.assertEqual(value["totals"]["fail"], 1)
                self.assertEqual(value["cleanup_errors"][0]["code"], "InvalidEvidence")
                self.assertNotEqual(value["cleanup_errors"][0]["message"], "None")

    def test_missing_and_corrupt_evidence_do_not_count_as_pass(self):
        missing = summary.Summary(self.root / "missing", SOURCE)
        missing.scan()
        self.assertEqual(missing.result()["phases"][0]["status"], "SKIP")
        (self.root / "properties.json").write_text("{broken JSON")
        value = self.summarize(["install=failure"])
        self.assertEqual(value["totals"]["pass"], 0)
        self.assertEqual(value["totals"]["fail"], 2)
        self.assertEqual(value["first_failure"]["phase"], "install")

    def test_no_private_or_calibration_read_and_no_original_mutation(self):
        for directory in ("private-inputs", "properties-calibration", "licensing"):
            path = self.root / directory / "properties.json"
            path.parent.mkdir()
            path.write_text("{sensitive invalid JSON")
        write(self.root / "properties.json", passed())
        ds_store = self.root / ".DS_Store"
        ds_store.write_bytes(b"retain user metadata")
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        value = self.summarize()
        self.assertEqual(value["totals"], {"phases": 1, "pass": 1, "fail": 0, "skip": 0})
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_diagnostic_selected_sets_cannot_be_full_pass(self):
        write(self.root / "runtime-sets.json", sets(diagnostic_set="native-model", coverage_scope="selected-set"))
        value = self.summarize()
        self.assertEqual(value["totals"]["pass"], 0)
        self.assertEqual(value["totals"]["skip"], 1)
        self.assertIsNone(value["first_failure"])

    def test_equation_boolean_gate_and_missing_duration(self):
        write(self.root / "equation-dimension-result.json", {"success": True, "cleanup_errors": [], "events": [{"returncode": 1}]})
        value = self.summarize()
        self.assertEqual(value["phases"][0]["status"], "PASS")
        self.assertIsNone(value["phases"][0]["seconds"])
        write(self.root / "equation-dimension-result.json", {"success": False, "failure": {"type": "FixtureError", "message": "fixture failed"}, "cleanup_errors": []})
        self.assertEqual(self.summarize()["first_failure"]["code"], "FixtureError")

    def test_mac_outer_receipt_has_no_success_boolean_and_uses_embedded_shared_proof(self):
        write(self.root / "hidden-full/runtime.json", {"completed": True, "phase": "completed", "profile": "hidden-full",
              "full_acceptance_eligible": True, "functional_sets": {"hidden": sets()}})
        value = self.summarize()
        self.assertEqual(value["totals"]["fail"], 0)
        self.assertEqual(value["totals"]["pass"], 21)
        write(self.root / "visible-smoke/runtime.json", {"completed": True, "phase": "completed", "profile": "visible-smoke",
              "full_acceptance_eligible": False, "visible_smoke": passed(), "server_exit_code": 0, "host_process_exited": True})
        self.assertEqual(self.summarize()["totals"]["pass"], 22)

    def test_markdown_injection_is_escaped_and_only_current_run_artifacts_are_linked(self):
        write(self.root / "properties.json", passed(success=False, error={"type": "NativeError", "message": '<script>[bad](javascript:alert(1))`|\n## injected'}))
        source = dict(SOURCE, scope='<b>[scope](https://evil.invalid)</b>', run_url="https://github.com/owner/repo/actions/runs/123")
        reporter = summary.Summary(self.root, source)
        reporter.scan()
        text = summary.render(reporter.result())
        self.assertIn('[Run artifacts](https://github.com/owner/repo/actions/runs/123#artifacts)', text)
        self.assertNotIn('<script>', text)
        self.assertNotIn('[bad](javascript:', text)
        self.assertNotIn('[scope](https://evil', text)
        self.assertNotIn(str(self.root), text)
        self.assertNotIn('\n## injected', text)

    def test_stage_empty_and_cancelled_are_explicit_skip(self):
        value = self.summarize(["unit=success", "native=", "later=cancelled"])
        self.assertEqual([p["status"] for p in value["phases"][:3]], ["PASS", "SKIP", "SKIP"])
        self.assertEqual(value["phases"][1]["detail"], "not-executed")
        with self.assertRaises(Exception):
            summary.parse_stage("phase=unrecognized")

    def test_cli_writes_two_files_and_appends_step_summary_even_on_failure(self):
        output = self.root / "summary-output"
        web = self.root / "web.md"
        web.write_text("earlier content\n")
        args = ["--evidence-root", str(self.root / "missing"), "--output-dir", str(output), "--host", "linux-wine",
                "--scope", "shared-full", "--source-commit", "a" * 40, "--client-version", "0.1.0a17", "--stage", "startup=failure"]
        with patch.dict(summary.os.environ, {"GITHUB_STEP_SUMMARY": str(web)}, clear=True):
            self.assertEqual(summary.main(args), 0)
        value = json.loads((output / "summary.json").read_text())
        self.assertEqual(value["schema_version"], 1)
        self.assertEqual(value["first_failure"]["phase"], "startup")
        self.assertTrue(web.read_text().startswith("earlier content\n## Test summary"))
        self.assertEqual(web.read_text().split("earlier content\n", 1)[1], (output / "summary.md").read_text())

    def test_malformed_runtime_children_and_untrusted_run_url_do_not_break_report(self):
        write(self.root / "runtime-sets.json", sets(None))
        raw = json.loads((self.root / "runtime-sets.json").read_text())
        raw["sets"] = None
        write(self.root / "runtime-sets.json", raw)
        value = self.summarize()
        self.assertEqual(value["totals"]["pass"], 0)
        self.assertEqual(value["totals"]["skip"], 19)
        for server in ("javascript:alert(1)", "https://github.com)[x](evil", "https://[invalid"):
            self.assertIsNone(summary.run_url({"GITHUB_SERVER_URL": server, "GITHUB_REPOSITORY": "owner/repo", "GITHUB_RUN_ID": "123"}))
        self.assertEqual(summary.run_url({"GITHUB_REPOSITORY": "owner/repo", "GITHUB_RUN_ID": "123"}),
                         "https://github.com/owner/repo/actions/runs/123")

    def test_generated_output_symlinks_cannot_overwrite_original_receipts(self):
        receipt = self.root / "properties.json"
        write(receipt, passed())
        original = receipt.read_bytes()
        output = self.root / "output"
        output.mkdir()
        (output / "summary.json").symlink_to(receipt)
        (output / "summary.md").symlink_to(receipt)
        args = ["--evidence-root", str(self.root), "--output-dir", str(output), "--host", "windows",
                "--scope", "full", "--source-commit", "a" * 40, "--client-version", "test"]
        with patch.dict(summary.os.environ, {}, clear=True):
            summary.main(args)
        self.assertEqual(receipt.read_bytes(), original)
        self.assertFalse((output / "summary.json").is_symlink())
        self.assertFalse((output / "summary.md").is_symlink())
        with patch.dict(summary.os.environ, {}, clear=True), self.assertRaisesRegex(ValueError, "original test receipt"):
            summary.main(args + ["--step-summary", str(receipt)])
        self.assertEqual(receipt.read_bytes(), original)

    def test_phase_identifiers_use_posix_separators_on_both_path_flavors(self):
        for path_type in (PurePosixPath, PureWindowsPath):
            with self.subTest(path_type=path_type.__name__):
                reporter = summary.Summary(self.root, SOURCE)
                with patch.object(summary, "Path", path_type):
                    reporter.runtime_sets(sets(), "hidden/runtime-sets.json")
                names = [row["name"] for row in reporter.result()["phases"]]
                self.assertEqual(names[0], "hidden/runtime-sets")
                self.assertEqual(names[1:], ["hidden/runtime-sets/" + name for name in summary.FULL_SET_NAMES])
                self.assertFalse(any("\\" in name for name in names))

    def test_literal_server_authority_is_checked_before_version_dependent_parser(self):
        for server in ("https://github.com)[x](evil", "https://github.com\t", "https://github.com/evil", "https://github.com@evil"):
            with self.subTest(server=server), patch.object(summary, "urlsplit") as parse:
                self.assertIsNone(summary.run_url({"GITHUB_SERVER_URL": server,
                    "GITHUB_REPOSITORY": "owner/repo", "GITHUB_RUN_ID": "123"}))
                parse.assert_not_called()
        self.assertEqual(summary.run_url({"GITHUB_SERVER_URL": "https://github.example:8443",
            "GITHUB_REPOSITORY": "owner/repo", "GITHUB_RUN_ID": "123"}),
            "https://github.example:8443/owner/repo/actions/runs/123")

    def test_units_and_annotations_use_public_completion_not_expected_negative_events(self):
        for filename in ("document-units.json", "document-annotations.json"):
            write(self.root / "hidden" / filename, passed(evidence_kind="installed-public-cli-gate",
                  events=[{"returncode": 1, "result": {"ok": False, "error": {"type": "DocumentUpdateConflict"}}}]))
        report = self.summarize()
        self.assertEqual(report["totals"]["pass"], 2)
        self.assertIsNone(report["first_failure"])
        for filename in ("document-units.json", "document-annotations.json"):
            write(self.root / "hidden" / filename, {"success": True, "cleanup_errors": []})
        report = self.summarize()
        self.assertEqual(report["totals"]["pass"], 0)
        self.assertEqual(report["totals"]["fail"], 2)

    def test_annotation_business_error_is_preserved_before_cleanup_and_stage(self):
        write(self.root / "document-annotations.json", passed(success=False,
              error={"type": "NativeReadbackMismatch", "message": "annotation native readback changed"},
              cleanup_errors=["close failed"]))
        report = self.summarize(["functional-tests=failure", "cleanup=failure"])
        self.assertEqual(report["first_failure"]["code"], "NativeReadbackMismatch")
        self.assertEqual(report["first_failure"]["evidence"], ["document-annotations.json"])
        self.assertEqual(len(report["cleanup_errors"]), 2)

    def test_full_group_names_match_shared_public_plan(self):
        ci = str(ROOT / "scripts/ci")
        with patch.object(sys, "path", [ci] + sys.path):
            from gate_support.runtime_plan import runtime_plan
        self.assertEqual(summary.FULL_SET_NAMES, tuple(item.name for item in runtime_plan("full")))

    def test_workflow_summaries_do_not_change_original_artifact_or_native_policy(self):
        text = (ROOT / ".github/workflows/ci.yml").read_text()
        package = text.split("  package:", 1)[1].split("  solidworks-e2e:", 1)[0]
        upload = package.split("- name: Upload distributions", 1)[1].split("- name:", 1)[0]
        self.assertIn("path: dist/", upload)
        self.assertNotIn("summary", upload)
        self.assertIn("Upload package summary separately", package)
        native = text.split("  solidworks-e2e:", 1)[1].split("  release:", 1)[0]
        self.assertLess(native.index("- name: Remove private test inputs"), native.index("- name: Summarize public"))
        self.assertLess(native.index("- name: Summarize public"), native.index("- name: Upload SWCLI-generated"))
        report_step = native.split("- name: Summarize public", 1)[1].split("- name:", 1)[0]
        self.assertIn("if: always()", report_step)
        self.assertIn("continue-on-error: true", report_step)
        self.assertIn('evidence-root "$env:RUNNER_TEMP\\swcli-native-smoke"', report_step)
        self.assertNotIn('evidence-root "$env:PRIVATE_ROOT', report_step)
        self.assertIn("timeout-minutes: 120", native)


if __name__ == "__main__":
    unittest.main()
