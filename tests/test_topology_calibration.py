"""Portable CI/timeout/type-library guard tests; never native proof."""

import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]

def load(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), ROOT/"scripts/ci"/(name+".py"))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

calibration = load("verify-topology-calibration")
runner = load("run-topology-targeted")


class TopologyCalibrationTests(unittest.TestCase):
    def test_official_enumerations_are_complete_and_exact(self):
        from collections import namedtuple
        descriptor = namedtuple("Descriptor", "memid value")
        enums = list(calibration.ENUMS.items())
        info = SimpleNamespace(GetTypeAttr=lambda: SimpleNamespace(typekind=0, cVars=len(enums)),
            GetVarDesc=lambda n: descriptor(n, enums[n][1]), GetDocumentation=lambda n: (enums[n][0],))
        library = SimpleNamespace(GetTypeInfoCount=lambda: 1, GetTypeInfo=lambda n: info)
        com = SimpleNamespace(TKIND_ENUM=0, LoadTypeLib=mock.Mock(return_value=library))
        self.assertEqual(calibration.read_constants(com, Path("official.tlb")), calibration.ENUMS)
        enums[0] = (enums[0][0], 999)
        with self.assertRaisesRegex(RuntimeError, "differs"):
            calibration.read_constants(com, Path("official.tlb"))

    def test_actual_typelib_signatures_are_checked_before_native_fixture_writes(self):
        wanted = [("GetPersistReference3", 1), ("GetObjectByPersistReference3", 2), ("DeleteSelection2", 1)]
        info = SimpleNamespace(GetDocumentation=lambda n: ("IModelDocExtension",),
            GetTypeAttr=lambda: SimpleNamespace(cFuncs=len(wanted)),
            GetFuncDesc=lambda n: (n, None, ["argument"] * wanted[n][1]),
            GetNames=lambda n: (wanted[n][0],))
        library = SimpleNamespace(GetTypeInfoCount=lambda: 1, GetTypeInfo=lambda n: info,
            GetDocumentation=lambda n: ("official SOLIDWORKS",), GetLibAttr=lambda: ("test-guid",))
        dispatch = SimpleNamespace(GetTypeInfo=lambda: SimpleNamespace(GetContainingTypeLib=lambda: (library, 0)))
        result = calibration.type_library_evidence(SimpleNamespace(_oleobj_=dispatch))
        self.assertEqual(set(result["methods"]), {name for name, _ in wanted})
        wanted[1] = (wanted[1][0], 1)
        with self.assertRaisesRegex(RuntimeError, "signatures differ"):
            calibration.type_library_evidence(SimpleNamespace(_oleobj_=dispatch))

    def test_internal_failure_stops_before_starting_public_host_and_preserves_receipt(self):
        import json
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)/"new"
            with mock.patch.object(runner.subprocess, "run", return_value=SimpleNamespace(returncode=9)) as run, \
                 mock.patch.object(runner.subprocess, "Popen") as start:
                result = runner.main(["--output-dir", str(output), "--swconst", "official.tlb"])
            self.assertEqual(result, 1)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.kwargs["timeout"], 1800)
            start.assert_not_called()
            receipt = json.loads((output/"targeted.json").read_text())
            self.assertFalse(receipt["success"] or receipt["full_acceptance_eligible"])
            self.assertEqual(receipt["groups"][0]["exit_code"], 9)
            self.assertEqual(receipt["native_timeout_seconds"], 600)
            self.assertTrue((output/"internal-calibration.stderr.log").is_file())

    def test_targeted_is_manual_default_off_branch_guarded_and_preserves_default_gates(self):
        text = (ROOT/".github/workflows/ci.yml").read_text()
        inputs = text.split("      native_topology_targeted:", 1)[1].split("      native_full:", 1)[0]
        self.assertIn("default: false", inputs)
        self.assertIn("type: boolean", inputs)
        native = text.split("  solidworks-e2e:", 1)[1].split("  release:", 1)[0]
        guard = native.split("    if:", 1)[1].split("    runs-on:", 1)[0]
        self.assertIn("github.event_name == 'workflow_dispatch' && inputs.native_full", guard)
        self.assertIn("inputs.native_topology_targeted && !inputs.native_full", guard)
        self.assertIn("github.ref == 'refs/heads/codex/swcli-topology-references'", guard)
        self.assertIn("needs.test.result == 'success'", guard)
        self.assertIn("needs.package.result == 'success'", guard)
        self.assertNotIn("pull_request", guard)
        concurrency = native.split("    concurrency:", 1)[1].split("    env:", 1)[0]
        self.assertIn("format('swcli-topology-targeted-{0}', github.ref)", concurrency)
        self.assertIn("|| 'swcli-hosted-windows-solidworks'", concurrency)
        self.assertIn("cancel-in-progress: false", concurrency)
        self.assertIn("windows-targeted-topology-references", native)
        targeted = native.split("      - name: Run targeted topology",1)[1].split("      - name:",1)[0]
        self.assertIn("github.event_name == 'workflow_dispatch'", targeted)
        self.assertIn("!inputs.native_full", targeted)
        self.assertIn("timeout-minutes: 65", targeted)
        self.assertIn("run-topology-targeted.py", targeted)
        release_guard = text.split("  release:", 1)[1].split("    runs-on:", 1)[0]
        self.assertIn("github.event_name == 'push'", release_guard)
        for name in ("Prepare property fixtures", "Prepare annotation fixtures", "Run real SOLIDWORKS modeling"):
            self.assertIn("if: ${{ !inputs.native_topology_targeted }}", native.split("      - name: "+name,1)[1].split("      - name:",1)[0])
