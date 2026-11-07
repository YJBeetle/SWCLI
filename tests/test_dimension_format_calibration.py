"""Portable calibration watchdog and dispatch boundary checks; no CAD host."""
import importlib.util
from pathlib import Path
import unittest
from unittest import mock
import test_dimension_format as fixtures
from swcli.daemon.documents import DocumentRegistry
from swcli.daemon.operations import execute_operation

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("dimension_calibration_test", ROOT / "scripts/ci/verify-dimension-format-calibration.py")
calibration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(calibration)


class DimensionCalibrationTests(unittest.TestCase):
    def test_geometry_control_uses_saved_background_state_without_relaxing_comparisons(self):
        script = (ROOT / "scripts/ci/verify-dimension-format-calibration.py").read_text()
        self.assertLess(script.index('case["save_source"]'), script.index('geometry-saved-background-before'))
        self.assertLess(script.index('create-foreground'), script.index('geometry-saved-background-before'))
        self.assertLess(script.index('geometry-no-write-control'), script.index('internal-set-'))
        self.assertIn('case["geometry_control"] == case["geometry_before"]', script)
        self.assertIn('case["geometry_after"] == case["geometry_before"]', script)
        self.assertIn('geometry(doc, case.setdefault("geometry_native_samples", []))) == case["geometry_before"]', script)

    def test_native_save_route_keeps_the_same_document_id_and_owned_lease(self):
        fixture = fixtures.DimensionFormatTests(); fixture.setUp()
        fixture.app.ActiveDoc = fixture.document
        registry = DocumentRegistry(fixture.app)
        entry = registry.register(fixture.document)
        lease = registry.acquire_lease(entry, session_id="display-writer", ttl_seconds=600)
        def saved(output, *, document):
            document.GetPathName = lambda: output
            document.GetTitle = lambda: "saved"
            fixture.fixture.modified = False
            return dict(ok=True, action="document.save-as")
        with mock.patch("swcli.daemon.operations.save_as_native_windows", side_effect=saved) as native:
            result = calibration.save_registered_copy(fixture.app, fixture.document, registry, entry,
                lease["lease_id"], Path("/tmp/dimension-routing-only.SLDPRT"))
        self.assertTrue(result["ok"], result)
        native.assert_called_once()
        self.assertIs(registry.resolve(entry.document_id), entry)
        registry.require_lease(entry, session_id="display-writer", lease_id=lease["lease_id"])
        observed = execute_operation(fixture.app, "document.dimension-format", {}, documents=registry,
            document_id=entry.document_id, session_id="display-reader", expected_update_stamp=7)
        self.assertTrue(observed["ok"], observed)
        self.assertEqual(observed["document"]["document_id"], entry.document_id)
        self.assertTrue(observed["document"]["path"].endswith("dimension-routing-only.SLDPRT"))

    def test_watchdog_enforces_native_and_group_limits_without_restart(self):
        rows = [{"call": "setter", "phase": "begin", "time": 100}]
        self.assertIsNone(calibration.deadline_reason(rows, elapsed=600, now=700, started=0))
        self.assertIn("setter", calibration.deadline_reason(rows, elapsed=601, now=701, started=0))
        self.assertIn("1800", calibration.deadline_reason(rows, elapsed=1801, now=101, started=0))
        self.assertIn("600", calibration.deadline_reason([], elapsed=601, now=601, started=0))
        self.assertIn("helper", calibration.deadline_reason([{"phase": "end", "time": 0}], elapsed=601, now=601, started=0))

    def test_ci_is_default_off_manual_branch_only_and_has_no_full_suite_call(self):
        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        dispatch = workflow.split("      dimension_format_calibration:", 1)[1].split("      media_path:", 1)[0]
        self.assertIn("default: false", dispatch)
        job = workflow.split("  dimension-format:", 1)[1].split("  release:", 1)[0]
        for condition in ("github.event_name == 'workflow_dispatch'", "github.ref == 'refs/heads/codex/docprops-dimension-format'", "inputs.dimension_format_calibration"):
            self.assertIn(condition, job)
        self.assertNotIn("pull_request", workflow)
        self.assertNotIn("-Suite full", job)
        self.assertNotIn("-VisibleSmoke", job)
        internal = job.split("      - name: Calibrate dimension display only", 1)[1].split("      - name:", 1)[0]
        self.assertNotIn("smoke-solidworks.ps1", internal)
        self.assertIn("inputs.dimension_format_calibration && !inputs.dimension_format_public", internal)
        self.assertIn("timeout-minutes: 31", job)
        self.assertIn("verify-dimension-format-calibration.py", job)
        self.assertIn("if: always()", job)
        self.assertIn("swcli-native-smoke", job)


if __name__ == "__main__":
    unittest.main()
