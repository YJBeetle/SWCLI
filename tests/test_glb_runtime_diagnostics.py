"""Specific regressions for opt-in GLB observation without a second save."""
from contextlib import ExitStack
import hashlib
import io
import json
import os
import struct
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

from swcli.hosts import glb_runtime_diagnostics as diagnostics
from swcli.hosts.native_trace import trace_native_request
from test_export_validation import glb


class GlbDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.dict(os.environ, SWCLI_GLB_RUNTIME_DIAGNOSTICS="1"))
        self.stack.enter_context(mock.patch.object(diagnostics.sys, "stderr", io.StringIO()))
        self.modules = self.stack.enter_context(mock.patch.object(diagnostics, "_modules", return_value={"status":"complete", "modules":[]}))
        self.preferences = self.stack.enter_context(mock.patch.object(diagnostics, "_preferences", return_value={"status":"complete", "matches":[]}))

    def test_disabled_flag_and_non_glb_do_not_probe_or_write(self):
        for toggle, enabled in (("",True),("0",True),("true",True),("1",False)):
            with self.subTest(toggle=toggle, enabled=enabled), mock.patch.dict(os.environ, SWCLI_GLB_RUNTIME_DIAGNOSTICS=toggle), \
                    mock.patch.object(diagnostics, "_Evidence") as evidence:
                with diagnostics.glb_runtime_evidence(object(), Path("stage"), Path("output"), {}, enabled=enabled):
                    pass
                evidence.assert_not_called()
        self.modules.assert_not_called()
        self.preferences.assert_not_called()

    def test_hidden_same_prefix_files_are_copied_with_hashes_and_unrelated_files_excluded(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            staging = root / ".fixture.unique.swcli.GLB"
            sidecar = staging.with_suffix(".bin")
            unrelated = root / ".fixture.other.swcli.bin"
            unrelated.write_bytes(b"must stay outside evidence")
            app = SimpleNamespace(GetProcessID=lambda: 3424)
            receipt = {}
            self.stack.enter_context(mock.patch.dict(os.environ, SWCLI_TRACE_NATIVE_CALLS="1"))
            with trace_native_request("glb-request", "document.export"), \
                    diagnostics.glb_runtime_evidence(app, staging, root / "fixture.GLB", receipt, enabled=True):
                staging.write_bytes(b"native glb")
                sidecar.write_bytes(b"native hidden binary")
                receipt.update(api_saved=True, save_errors=0, save_warnings=0, save_attempted=True)
            directory, = root.glob("swcli-glb-diagnostics-*")
            report = json.loads((directory/"manifest.json").read_text())
            self.assertEqual(report["request_id"], "glb-request")
            self.assertEqual(report["solidworks_pid"], 3424)
            self.assertEqual(report["staging_path"], str(staging))
            self.assertEqual(report["phases"]["before"]["files"], [])
            files = report["phases"]["after"]["files"]
            self.assertEqual({row["name"] for row in files}, {staging.name,sidecar.name})
            for row in files:
                data = (root/row["name"]).read_bytes()
                self.assertEqual((directory/row["copy"]).read_bytes(), data)
                self.assertEqual(row["sha256"], hashlib.sha256(data).hexdigest())
                self.assertTrue(row["stable_while_reading"])
                self.assertFalse(row["copy"].startswith("."))
            self.assertEqual(report["file_access_monitor"]["status"], "unknown")
            self.assertEqual(report["phases"]["after"]["save_receipt"],receipt)
            self.assertEqual(self.modules.call_args_list,[mock.call(3424),mock.call(3424)])
            self.preferences.assert_called_once_with(app)

    def test_windows_cached_direntry_zero_ids_do_not_reject_the_real_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            staging = root / ".fixture.uuid.GLB"
            staging.write_bytes(b"original native bytes")
            actual = os.stat(staging, follow_symlinks=False)
            cached = SimpleNamespace(st_mode=actual.st_mode, st_size=actual.st_size,
                st_mtime_ns=actual.st_mtime_ns, st_file_attributes=0, st_dev=0, st_ino=0)
            entry = SimpleNamespace(name=staging.name, path=str(staging),
                stat=mock.Mock(return_value=cached), is_symlink=lambda: False)
            evidence = diagnostics._Evidence(object(), staging, root / "final.GLB")
            with mock.patch.object(diagnostics.os, "scandir") as scan:
                scan.return_value.__enter__.return_value = [entry]
                row, = evidence._files("after")
            self.assertEqual(row["status"], "copied", row)
            self.assertEqual((evidence.directory / row["copy"]).read_bytes(), staging.read_bytes())
            self.assertEqual(row["sha256"], hashlib.sha256(staging.read_bytes()).hexdigest())
            entry.stat.assert_not_called()

    def test_true_source_identity_change_never_creates_an_empty_copy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            staging = root / ".fixture.uuid.GLB"
            staging.write_bytes(b"native bytes")
            actual = os.stat(staging, follow_symlinks=False)
            changed = SimpleNamespace(st_mode=actual.st_mode, st_size=actual.st_size,
                st_mtime_ns=actual.st_mtime_ns, st_file_attributes=0,
                st_dev=actual.st_dev, st_ino=actual.st_ino + 1)
            evidence = diagnostics._Evidence(object(), staging, root / "final.GLB")
            with mock.patch.object(diagnostics.os, "stat", return_value=changed):
                row, = evidence._files("after")
            self.assertEqual(row["status"], "unknown")
            self.assertIn("source identity changed", row["error"]["message"])
            self.assertEqual(list(evidence.directory.glob("*.bin")), [])

    def test_symlinks_and_copy_budget_are_recorded_without_reading_external_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            stage=root/".fixture.uuid.GLB"
            external=root/"unrelated"
            external.write_bytes(b"secret")
            (root/".fixture.uuid.bin").symlink_to(external)
            stage.write_bytes(b"larger than limit")
            evidence=diagnostics._Evidence(object(),stage,root/"final.GLB")
            with mock.patch.object(diagnostics,"MAX_BYTES",4):
                rows=evidence._files("after")
            self.assertEqual({r["status"] for r in rows},{"unknown-nonregular-or-reparse","unknown"})
            self.assertEqual(list(evidence.directory.glob("*.bin")),[])
            self.assertEqual(external.read_bytes(),b"secret")

    def test_count_bound_retains_copied_rows_and_explicit_incomplete_marker(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            stage=root/".fixture.uuid.GLB"
            for extension in ("GLB","bin","png"):
                stage.with_suffix("."+extension).write_bytes(b"x")
            evidence=diagnostics._Evidence(object(),stage,root/"final.GLB")
            with mock.patch.object(diagnostics,"MAX_FILES",1):
                rows=evidence._files("after")
            self.assertEqual(rows[0]["status"],"copied")
            self.assertEqual(rows[1]["status"],"incomplete")

    def test_manifest_and_log_failure_preserve_original_exception(self):
        original=ValueError("first native failure")
        with tempfile.TemporaryDirectory() as temporary, \
                mock.patch.object(diagnostics._Evidence,"_write_manifest",side_effect=OSError("disk failure")), \
                mock.patch.object(diagnostics.sys,"stderr") as stream:
            stream.write.side_effect=OSError("log failure")
            stage=Path(temporary)/".fixture.uuid.GLB"
            with self.assertRaises(ValueError) as caught:
                with diagnostics.glb_runtime_evidence(SimpleNamespace(GetProcessID=lambda:1),stage,
                        stage.with_name("fixture.GLB"),{},enabled=True):
                    raise original
            self.assertIs(caught.exception,original)

    def test_export_entry_keeps_single_save_staging_case_and_first_failure(self):
        from test_windows_mesh_exports import WindowsMeshExportTests
        empty_bin = bytearray(glb()[:-36])
        struct.pack_into("<I", empty_bin, 8, len(empty_bin))
        struct.pack_into("<I", empty_bin, len(empty_bin) - 8, 0)
        for native_failure, payload in ((False,glb()),(False,b"invalid"),(False,bytes(empty_bin)),(True,b"unused")):
            with self.subTest(native_failure=native_failure):
                case=WindowsMeshExportTests()
                result=case.export("GLB",payload,runtime_diagnostics=True,native_failure=native_failure)
                self.assertEqual(len(case.saved),1)
                self.assertTrue(case.saved[0].name.startswith(".fixture."))
                self.assertTrue(case.saved[0].name.endswith(".swcli.GLB"))
                self.assertEqual(case.preference_writes,[])
                self.assertEqual(len(case.runtime_evidence),1)
                proof=case.runtime_evidence[0]
                if native_failure:
                    self.assertEqual(result["error"]["type"],"RuntimeError")
                    self.assertEqual(proof["report"]["phases"]["after"]["save_receipt"]["error"]["type"],"RuntimeError")
                elif not result["ok"]:
                    self.assertEqual(result["error"]["type"],"ExportVerificationFailed")
                    self.assertEqual(case.output,b"previous valid artifact")
                    self.assertEqual(list(proof["copies"].values()),[payload])
                else:
                    self.assertTrue(result["ok"])
                    self.assertTrue(result["output"].endswith("fixture.GLB"))

    def test_export_entry_logging_failure_keeps_success_and_original_target_behavior(self):
        from test_windows_mesh_exports import WindowsMeshExportTests
        with mock.patch.object(diagnostics._Evidence,"_write_manifest",side_effect=OSError("cannot log")):
            case=WindowsMeshExportTests()
            result=case.export("GLB",glb(),runtime_diagnostics=True)
        self.assertTrue(result["ok"])
        self.assertEqual(len(case.saved),1)


class GlbNativeObservationTests(unittest.TestCase):
    def test_module_inventory_uses_only_observed_pid_and_reports_actual_version(self):
        handle=SimpleNamespace(Close=mock.Mock())
        api=SimpleNamespace(OpenProcess=mock.Mock(return_value=handle),
            GetFileVersionInfo=mock.Mock(return_value={"FileVersionMS":(33<<16)|5,"FileVersionLS":53,
                "ProductVersionMS":(33<<16)|5,"ProductVersionLS":53}))
        process=SimpleNamespace(EnumProcessModules=mock.Mock(return_value=[1,2]),
            GetModuleFileNameEx=mock.Mock(side_effect=[r"C:\SOLIDWORKS\sldgltfu.dll",r"C:\Windows\kernel32.dll"]))
        with mock.patch.dict("sys.modules",win32api=api,win32process=process,
                win32con=SimpleNamespace(PROCESS_QUERY_INFORMATION=1024,PROCESS_VM_READ=16)):
            result=diagnostics._modules(3424)
        api.OpenProcess.assert_called_once_with(1040,False,3424)
        self.assertEqual(len(result["modules"]),1)
        self.assertEqual(result["modules"][0]["file_version"],[33,5,0,53])
        handle.Close.assert_called_once()

    def test_actual_typelib_names_select_only_known_readonly_preference_getters(self):
        members=[("swGLTFUseDraco",91),("swExportGLBScene",92),("swSTLBinaryFormat",69)]
        info=SimpleNamespace(GetTypeAttr=lambda:SimpleNamespace(typekind=0,cVars=len(members)),
            GetDocumentation=lambda i:(members[i][0],))
        class Desc:
            def __init__(self,index):self.value=members[index][1];self.index=index
            def __getitem__(self,index):return self.index
        info.GetVarDesc=lambda i:Desc(i)
        library=SimpleNamespace(GetLibAttr=lambda:("GUID",0,3,33,0),GetTypeInfoCount=lambda:1,
            GetTypeInfo=lambda i:info,GetDocumentation=lambda i:("swUserPreferenceToggle_e",))
        app=mock.Mock()
        app.GetUserPreferenceToggle.side_effect=[True,RuntimeError("getter unavailable")]
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/"swconst.tlb";path.write_bytes(b"actual typelib fixture")
            com=SimpleNamespace(TKIND_ENUM=0,LoadTypeLib=mock.Mock(return_value=library))
            with mock.patch.dict("sys.modules",pythoncom=com),mock.patch.dict(os.environ,SWCLI_GLB_DIAGNOSTICS_SWCONST=str(path)):
                result=diagnostics._preferences(app)
        self.assertEqual(app.GetUserPreferenceToggle.call_args_list,[mock.call(91),mock.call(92)])
        self.assertEqual([row["read_status"] for row in result["matches"]],["observed","unknown"])
        self.assertFalse(any('Set' in call[0] for call in app.mock_calls))
        self.assertFalse(diagnostics._related("swMaximumRadius"))

    def test_combined_full_precedes_glb_with_both_getter_and_stl_proofs(self):
        workflow = Path('.github/workflows/ci.yml').read_text()
        ids = ('modern_api_contract', 'getter_two_configurations',
               'stl_configuration_observation', 'native_tests')
        positions = [workflow.index('        id: ' + step) for step in ids]
        self.assertEqual(positions, sorted(positions))
        for step, script in (('getter_two_configurations', 'verify-native-getter-configurations.py'),
                             ('stl_configuration_observation', 'verify-stl-options.py')):
            block = workflow.split('        id: ' + step, 1)[1].split('      - name:', 1)[0]
            self.assertIn("needs.native-profile.outputs.profile == 'full' && github.ref == 'refs/heads/codex/glb-export-repair'", block)
            self.assertIn('timeout-minutes: 31', block)
            self.assertIn(script, block)
            self.assertIn('if ($LASTEXITCODE -ne 0) { throw', block)
            self.assertNotIn('always()', block)
        stl = workflow.split('        id: stl_configuration_observation', 1)[1].split('      - name:', 1)[0]
        self.assertIn('--phase public', stl)
        self.assertLess(stl.index('python -m pip install'), stl.index('python -I'))
        self.assertIn('stl-configuration-observation', stl)

    def test_ci_enables_observation_only_on_glb_branch_without_a_new_input(self):
        workflow=Path('.github/workflows/ci.yml').read_text()
        self.assertIn("SWCLI_GLB_RUNTIME_DIAGNOSTICS: ${{ github.ref == 'refs/heads/codex/glb-export-repair' && '1' || '' }}",workflow)
        self.assertIn("format('swcli-glb-export-repair-{0}', github.ref)",workflow)
        inputs=workflow.split('  workflow_dispatch:',1)[1].split('\npermissions:',1)[0]
        self.assertNotIn("      glb_",inputs)
