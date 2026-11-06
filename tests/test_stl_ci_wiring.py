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
        for requirement in ("github.event_name == 'workflow_dispatch'", "inputs.stl_options_targeted",
                            "!inputs.native_full", "github.ref == 'refs/heads/codex/swcli-stl-export-options'",
                            "needs.test.result == 'success'", "needs.package.result == 'success'"):
            self.assertIn(requirement, guard)
        self.assertNotIn("pull_request:", text)
        self.assertIn("Require one explicit native mode", native)
        for name in ("Prepare property fixtures for public CLI verification", "Prepare annotation fixtures for public CLI verification",
                     "Run real SOLIDWORKS modeling and export smoke test"):
            step = native.split("      - name: " + name, 1)[1].split("      - name:", 1)[0]
            self.assertIn("!inputs.stl_options_targeted", step)
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
