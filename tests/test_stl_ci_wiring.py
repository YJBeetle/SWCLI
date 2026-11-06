"""Targeted calibration must never weaken normal full/native release gates."""
from pathlib import Path
import importlib.util
import math
import struct
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class StlCIWiringTests(unittest.TestCase):
    def test_manual_targeted_is_off_and_branch_scoped_with_default_gates_intact(self):
        text = (ROOT / ".github/workflows/ci.yml").read_text()
        inputs = text.split("      stl_options_targeted:", 1)[1].split("      native_full:", 1)[0]
        self.assertIn("default: false", inputs)
        native = text.split("  solidworks-e2e:", 1)[1].split("  release:", 1)[0]
        guard = native.split("runs-on:", 1)[0]
        for requirement in ("github.event_name == 'workflow_dispatch'", "needs.native-profile.outputs.profile == 'stl_options_targeted'",
                            "needs.native-profile.result == 'success'",
                            "needs.test.result == 'success'", "needs.package.result == 'success'"):
            self.assertIn(requirement, guard)
        self.assertNotIn("pull_request:", text)
        self.assertIn('python scripts/ci/validate-native-profile.py', text)
        for name in ("Prepare property fixtures for public CLI verification", "Prepare annotation fixtures for public CLI verification",
                     "Run real SOLIDWORKS modeling and export smoke test"):
            step = native.split("      - name: " + name, 1)[1].split("      - name:", 1)[0]
            self.assertIn("needs.native-profile.outputs.profile == 'full'", step)
        targeted = native.split("      - name: Calibrate isolated STL export options only", 1)[1].split("      - name:", 1)[0]
        self.assertIn("timeout-minutes: 30", targeted)
        self.assertIn("python -I scripts/ci/verify-stl-options.py", targeted)
        self.assertIn("if: always()", native.split("Upload SWCLI-generated smoke evidence", 1)[1])
        summary = native.split("Summarize public test evidence", 1)[1].split("      - name:", 1)[0]
        self.assertIn("if: always()", summary)
        self.assertIn("--scope windows-stl-options-internal-calibration", summary)
        self.assertIn("exit $LASTEXITCODE", summary)
        concurrency = native.split("    concurrency:", 1)[1].split("    env:", 1)[0]
        self.assertIn("inputs.stl_options_targeted && format('swcli-stl-options-{0}', github.ref)", concurrency)
        self.assertIn("|| 'swcli-hosted-windows-solidworks'", concurrency)
        self.assertIn("cancel-in-progress: false", concurrency)

    def test_calibration_metrics_measure_real_scale_and_curvature(self):
        spec = importlib.util.spec_from_file_location("stl_calibration", ROOT / "scripts/ci/verify-stl-options.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        def cylinder(n, unit):
            scale = {"mm": 1, "inch": 25.4}[unit]
            bottom = [(10*math.cos(i*2*math.pi/n)/scale, 10*math.sin(i*2*math.pi/n)/scale, 0) for i in range(n)]
            top = [(x,y,15/scale) for x,y,_ in bottom]
            triangles = []
            for i in range(n):
                j=(i+1)%n
                triangles.extend([(bottom[i],bottom[j],top[i]),(top[i],bottom[j],top[j]),
                                  ((0,0,0),bottom[j],bottom[i]),((0,0,15/scale),top[i],top[j])])
            return b"SWCLI analytical cylinder".ljust(80,b" ")+struct.pack("<I",len(triangles))+b"".join(
                struct.pack("<12fH",0,0,0,*a,*b,*c,0) for a,b,c in triangles)
        with tempfile.TemporaryDirectory() as folder:
            metrics = []
            for n, unit in ((12,"mm"),(120,"mm"),(120,"inch")):
                path=Path(folder)/(str(n)+unit+".stl")
                path.write_bytes(cylinder(n, unit))
                metrics.append(module.mesh_metrics(path, unit=unit, expected_encoding="binary"))
            self.assertLess(metrics[1]["max_wall_chord_error_mm"], metrics[0]["max_wall_chord_error_mm"])
            self.assertLess(metrics[1]["volume_relative_error"], metrics[0]["volume_relative_error"])
            self.assertAlmostEqual(metrics[1]["volume_mm3"],metrics[2]["volume_mm3"],places=3)
            with self.assertRaisesRegex(RuntimeError, "encoding"):
                module.mesh_metrics(path, unit="inch", expected_encoding="ascii")
            with self.assertRaisesRegex(RuntimeError, "units"):
                module.mesh_metrics(path, unit="mm", expected_encoding="binary")


class StlEvidenceAuditTests(unittest.TestCase):
    def test_missing_failed_wrong_head_and_scope_mixed_evidence_never_qualifies(self):
        import json
        spec = importlib.util.spec_from_file_location("stl_audit", ROOT / "scripts/ci/audit-stl-evidence.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaisesRegex(RuntimeError, "exactly one"):
                module.audit(root, "expected-head")
            baseline = dict(success=True, source_commit="expected-head", public_acceptance=False, full_acceptance=False,
                            native_timeout_seconds=600, group_timeout_seconds=1800, cleanup_errors=[])
            for changes, message in ((dict(success=False), "did not pass"),
                    (dict(source_commit="other-head"), "did not pass"),
                    (dict(public_acceptance=True), "must not claim"),
                    (dict(native_timeout_seconds=120), "timeout contract"),
                    (dict(cleanup_errors=[{"stage": "retained-host"}]), "cleanup errors")):
                (root / "stl-calibration.json").write_text(json.dumps({**baseline, **changes}))
                with self.subTest(changes=changes), self.assertRaisesRegex(RuntimeError, message):
                    module.audit(root, "expected-head")


class StlPublicCIWiringTests(unittest.TestCase):
    def test_public_mode_requires_manual_optin_exact_branch_and_distinct_concurrency(self):
        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        settings = workflow.split("      stl_options_public:", 1)[1].split("      stl_options_targeted:", 1)[0]
        self.assertIn("default: false", settings)
        native = workflow.split("  solidworks-e2e:", 1)[1].split("  release:", 1)[0]
        step = native.split("      - name: Verify public STL options through installed CLI SDK MCP", 1)[1].split("      - name:", 1)[0]
        for condition in ("github.event_name == 'workflow_dispatch'", "inputs.stl_options_public", "!inputs.native_full",
                          "!inputs.stl_options_targeted", "github.ref == 'refs/heads/codex/swcli-stl-export-options'"):
            self.assertIn(condition, step)
        self.assertIn("--phase public", step)
        self.assertIn("timeout-minutes: 30", step)
        self.assertIn("format('swcli-stl-options-public-{0}', github.ref)", native)
        self.assertIn("|| 'swcli-hosted-windows-solidworks'", native)
        self.assertIn("cancel-in-progress: false", native)
        self.assertIn("--scope windows-stl-options-public-isolated", native)
        source = (ROOT / "scripts/ci/verify-stl-options.py").read_text()
        self.assertIn('env.pop("SWCLI_STL_CALIBRATION", None)', source)
        self.assertIn('env["SWCLI_STL_EXCLUSIVE_RUNNER"] = "1"', source)
        for negative in ('"stale-stamp"', '"foreign-lease"', '"uncalibrated-profile"', '"read-only-source"'):
            self.assertIn(negative, source)
        self.assertIn('("sdk-fine", fine_options)', source)
        self.assertIn('("mcp-fine", fine_options)', source)


@unittest.skipUnless(importlib.util.find_spec("mcp") is not None, "optional official MCP SDK")
class StlActualMCPTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_exact_stl_options_cross_real_stdio_without_native_lifecycle_side_effects(self):
        from test_mcp import MCPStdioIntegrationTests
        from swcli.stl_calibrated_profiles import PROFILES
        fixture = MCPStdioIntegrationTests()
        daemon, captured = fixture.fake_daemon()
        self.addCleanup(daemon.server_close)
        self.addCleanup(daemon.shutdown)
        spec = importlib.util.spec_from_file_location("stl_public_transport", ROOT / "scripts/ci/verify-stl-options.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        context = dict(document_id="d-ab12cd", expected_update_stamp=161, lease_id="l-ab12cd34ef56")
        with tempfile.TemporaryDirectory() as folder:
            result, transport = await module.mcp_stdio_export("127.0.0.1:"+str(daemon.server_address[1]),
                context, PROFILES["fine"], Path(folder)/"curved.stl", Path(folder)/"mcp.stderr.log")
        self.assertTrue(result["success"])
        self.assertEqual(transport["transport"], "official-sdk-stdio")
        self.assertFalse(transport["is_error"])
        self.assertEqual(len(captured), 1)
        request = captured[0]
        self.assertEqual(request["operation"], "document.export")
        self.assertEqual(request["parameters"]["stl_options"], PROFILES["fine"])
        self.assertIs(request["parameters"]["include_content"], False)
        for field, value in context.items():
            self.assertEqual(request[field], value)
        self.assertEqual(request["session_id"], "stl-calibration")
        self.assertEqual(request["timeout_ms"], 600000)
