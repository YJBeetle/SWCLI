"""The hosted table gate sequences synthetic receipts without starting SOLIDWORKS."""

import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "_hosted_table_fonts", ROOT / "scripts/ci/run-font-scopes-hosted-tables.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
HEAD = "a" * 40


class HostedTableFontTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name).resolve()

    def receipt(self, phase, **values):
        destination = self.root / phase
        (destination / "native").mkdir(parents=True, exist_ok=True)
        watchdog = dict(success=True, supervision_verified=True, source_head=HEAD,
                        requested_scope="tables", profile="next-fixture", **values)
        (destination / "watchdog.json").write_text(json.dumps(watchdog), encoding="utf-8")
        return destination / "native"

    def report(self, directory, cases):
        report = dict(success=True, cleanup_errors=[], cases=cases)
        (directory / "report.json").write_text(json.dumps(report), encoding="utf-8")

    def prepare_fixture(self):
        native = self.receipt("fixture", supervision_probe=False)
        drawing = native / "font-tables-fixture.SLDDRW"
        drawing.write_bytes(b"synthetic fixture")
        digest = gate.file_digest(drawing)
        self.report(native, [dict(success=True, scope="tables", source_head=HEAD,
                                  source_kind="generated-GB-table", save_verified=True,
                                  reopen={"read_only": True}, path=str(drawing), file_sha256=digest)])
        return drawing, digest

    def run_phase(self, phase):
        return gate.run_phase(phase, self.root, HEAD, Path("swconst.tlb"), Path("gb.drwdot"))

    def test_context_denies_nonmanual_untrusted_or_nonhosted_execution(self):
        allowed = dict(GITHUB_ACTIONS="true", GITHUB_EVENT_NAME="workflow_dispatch",
                       GITHUB_REPOSITORY=gate.REPOSITORY, GITHUB_REF=gate.REF, GITHUB_SHA=HEAD,
                       GITHUB_WORKFLOW_REF=gate.REPOSITORY + "/.github/workflows/ci.yml@" + gate.REF,
                       RUNNER_ENVIRONMENT="github-hosted")
        self.assertEqual(gate.source_head(allowed), HEAD)
        for key, value in (("GITHUB_EVENT_NAME", "pull_request"), ("GITHUB_REF", "refs/heads/main"),
                           ("GITHUB_REPOSITORY", "fork/SWCLI"), ("GITHUB_SHA", "a"),
                           ("GITHUB_WORKFLOW_REF", "other-workflow"), ("RUNNER_ENVIRONMENT", "self-hosted")):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                gate.source_head(dict(allowed, **{key: value}))

    def test_only_a_successful_probe_allows_fixture_generation(self):
        with patch.object(gate.subprocess, "run") as process:
            with self.assertRaises(OSError):
                self.run_phase("fixture")
            process.assert_not_called()
            native = self.receipt("probe", supervision_probe=True, native_executed=False)
            self.report(native, [])
            with self.assertRaisesRegex(RuntimeError, "without COM"):
                self.run_phase("fixture")
            process.assert_not_called()

    def test_inheritance_only_uses_hash_pinned_generated_drawing(self):
        self.receipt("probe", supervision_probe=True, native_executed=False)
        drawing, digest = self.prepare_fixture()
        native = self.receipt("inheritance", inheritance_fixture_sha256=digest)
        watchdog = native.parent / "watchdog.json"
        watchdog.write_text(json.dumps({**json.loads(watchdog.read_text(encoding="utf-8")), "profile": "internal"}),
                            encoding="utf-8")
        case = dict(success=True, selected_scopes=["tables"])
        self.report(native, [dict(case, kind="part"), dict(case, kind="assembly"), dict(
            case, kind="drawing", fixture={"input_sha256": digest},
            inheritance_witness={"scope": "tables", "success": True})])
        with patch.object(gate.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as process:
            self.assertEqual(self.run_phase("inheritance"), 0)
            command = process.call_args.args[0]
            self.assertEqual(command[3:7], ["--scope", "tables", "--profile", "internal"])
            self.assertEqual(command[-4:], ["--inheritance-drawing", str(drawing), "--inheritance-sha256", digest])
            drawing.write_bytes(b"changed")
            process.reset_mock()
            with self.assertRaisesRegex(RuntimeError, "SHA-256 differs"):
                self.run_phase("inheritance")
            process.assert_not_called()

    def test_failed_worker_is_not_retried_or_replaced_by_a_missing_report_error(self):
        self.receipt("probe", supervision_probe=True, native_executed=False)
        with patch.object(gate.subprocess, "run", return_value=SimpleNamespace(returncode=7)) as process, \
                patch.object(gate, "qualified_fixture") as verify:
            self.assertEqual(self.run_phase("fixture"), 7)
            process.assert_called_once()
            verify.assert_not_called()

    def test_hosted_workflow_probes_before_private_install_and_stops_on_first_failure(self):
        import yaml

        workflow = yaml.safe_load((ROOT / ".github/workflows/font-scopes-calibration.yml").read_text())
        job = workflow["jobs"]["native"]
        steps = job["steps"]

        def find(fragment):
            return next(index for index, step in enumerate(steps) if fragment in step.get("run", ""))

        probe = find("run-font-scopes-hosted-tables.py probe")
        transfer = next(index for index, step in enumerate(steps) if step.get("env", {}).get("RCLONE_CONFIG_B64"))
        fixture = find("run-font-scopes-hosted-tables.py fixture")
        inheritance = find("run-font-scopes-hosted-tables.py inheritance")
        cleanup = find("-PrivateInputsOnly")
        self.assertLess(probe, transfer)
        self.assertLess(transfer, fixture)
        self.assertLess(fixture, inheritance)
        self.assertLess(inheritance, cleanup)
        self.assertEqual([steps[index]["timeout-minutes"] for index in (probe, fixture, inheritance)], [2, 31, 31])
        for index in (probe, fixture, inheritance):
            self.assertIn("inputs.font_scopes_profile == 'next-tables'", steps[index]["if"])
            self.assertNotIn("always()", steps[index]["if"])
            self.assertNotIn("continue-on-error", steps[index])
        upload = steps[-1]
        self.assertEqual(upload["if"], "always()")
        self.assertIn("font-scopes-next-tables/", upload["with"]["path"])
        self.assertNotIn("swcli-private-runtime", upload["with"]["path"])
        self.assertNotIn("next-tables", workflow[True]["workflow_dispatch"]["inputs"]["font_scopes_profile"]["options"])
