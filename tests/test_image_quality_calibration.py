"""Portable adversarial calibration-control tests; no native acceptance claims."""
from copy import deepcopy
import importlib.util
import io
import json
import math
from pathlib import Path, PureWindowsPath
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from swcli import __version__
from swcli.cli import _typed_operation
from swcli.document_image_quality import exact_snapshot, quality_snapshot, linked_changes
from tests.test_document_image_quality import snapshot
from tests.test_modeling_smoke import FakeCLI, mesh_fixture

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("_quality_calibration_test", ROOT/"scripts/ci/verify-image-quality.py")
gate = importlib.util.module_from_spec(spec); spec.loader.exec_module(gate)


class QualityCLI(FakeCLI):
    def __init__(self, directory, trace):
        super().__init__(directory); self.trace=trace; self.quality_defect=None; self.setters=0
        self.native_calls=[]

    def run(self, command, **kwargs):
        self.native_calls=[]
        completed=super().run(command, **kwargs)
        args=self.calls[-1]
        if args.command == "document" and args.document_command.startswith("image-quality"):
            response=json.loads(completed.stdout); operation="document."+args.document_command
            records=[]
            # Real _com_value and native_sequence tracing surrounds the six
            # property getters. Include that independent evidence in the fake.
            calls=["CommandInProgress", "SldWorks.CommandInProgress.enter", "GetDocuments", *self.native_calls, "GetUpdateStamp", "SldWorks.CommandInProgress.restore"]
            if self.quality_defect == "global-setter": calls.insert(3,"ISldWorks.SetUserPreferenceDoubleValue")
            if self.quality_defect == "reordered-preferences": calls[3],calls[4]=calls[4],calls[3]
            for sequence, name in enumerate([operation,*calls]):
                if sequence == 0: records.append(dict(sequence=0,call=operation,phase="begin"))
                else: records.extend(dict(sequence=sequence,call=name,phase=phase) for phase in ("begin","end"))
            records.append(dict(sequence=0,call=operation,phase="end"))
            if self.quality_defect == "missing-trace": records=[]
            if self.quality_defect == "missing-native-getter": records=[r for r in records if r["call"] != "IModelDocExtension.GetUserPreferenceDoubleValueRange"]
            with self.trace.open("a") as stream:
                for record in records:
                    stream.write(json.dumps(dict(event="swcli.native-call",request_id=response["request_id"],
                        operation=operation,worker_pid=99,**record))+"\n")
        return completed

    def getters(self):
        self.native_calls += ["IModelDocExtension.GetUserPreference"+kind for kind in ("Integer","Double","Toggle","Toggle","Toggle")]
        self.native_calls.append("IModelDocExtension.GetUserPreferenceDoubleValueRange")

    def dispatch(self, args):
        action=args.command; sub=getattr(args, action+"_command", None)
        if action == "document" and sub.startswith("image-quality"):
            document=self.documents[args.document_id]; quality=document["quality"]
            base=dict(ok=True,action="document."+sub,session_id=args.session,document=self.descriptor(document,args.session))
            self.getters()
            if sub == "image-quality": return dict(base,quality=deepcopy(quality))
            _,values,*_=_typed_operation(args)
            field,value=values["field"],values["value"]
            if not exact_snapshot(quality,values["expected_quality"]):
                return self.failure("DocumentImageQualityConflict",mutation=dict(attempted=False,may_have_changed=False))
            before=deepcopy(quality); changed=quality[field] != value
            if changed:
                self.setters += 1
                if self.quality_defect == "native-first-failure":
                    return self.failure("RuntimeError", mutation=dict(attempted=True,may_have_changed=True))
                raw=quality["native"]
                if field == "shaded_mode":
                    raw[field]={"coarse":1,"fine":2,"custom":3}[value]
                    raw["shaded_deviation_m"]={"coarse":0.0005,"fine":0.0001}[value]
                elif field == "shaded_deviation_mm":
                    raw["shaded_deviation_m"]=value/1000
                    if self.quality_defect=="quantize-unobserved-deviation" and value != snapshot()["shaded_deviation_mm"]:
                        raw["shaded_deviation_m"]=0.0003
                    raw["shaded_mode"]=3
                else: raw[field]=value
                document["quality"]=quality=quality_snapshot(raw,quality["deviation_range"])
                document["modified"]=True
                self.native_calls.append("IModelDocExtension.SetUserPreference"+gate.IMAGE_QUALITY_FIELDS[field]["kind"])
                self.getters(); self.getters()
            result=dict(base,field=field,before=before,quality=deepcopy(quality),changed=changed,
                mutation=dict(attempted=changed,may_have_changed=changed),linked_changes=linked_changes(before,quality,field),
                document=self.descriptor(document,args.session))
            if changed: result.update(native_return=True,observed_quality=deepcopy(quality))
            return result
        if action == "document" and sub in ("save-as","export"):
            document=self.documents[args.document_id]
            target=self.directory/PureWindowsPath(args.output).name
            target.write_bytes(mesh_fixture("GLB") if sub=="export" else bytes(1024))
            if sub=="export":
                return dict(ok=True,api_saved=True,save_errors=0,save_warnings=0,artifact=dict(size_bytes=target.stat().st_size,format="GLB",path=args.output))
            document.update(path=args.output,modified=False); self.saved[args.output]=deepcopy(document)
            return dict(ok=True,api_saved=True,save_errors=0,save_warnings=0,document=self.descriptor(document,args.session),
                artifact=dict(format="SLDPRT",path=args.output,size_bytes=target.stat().st_size))
        result=super().dispatch(args)
        if action == "daemon":
            result["result"].update(server_version=__version__)
            result["result"]["host"].update(owned_by_daemon=True,visible=False,shared_interactive=False)
        if action == "document" and sub in ("create","open"):
            document=self.documents[result["document"]["document_id"]]
            document.setdefault("quality",snapshot())
            if sub=="open" and args.read_only and self.quality_defect=="reopen-lost-value":
                document["quality"]=snapshot()
        if action == "feature" and sub=="extrude":
            document=self.documents[args.document_id]
            profile=document["profiles"][args.sketch_id]
            if profile["radius"]: document.update(volume=1000*math.pi,area=400*math.pi)
            else: document.update(volume=12000,area=3800)
        return result


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.directory=Path(temporary.name)/"evidence"; self.directory.mkdir()
        self.trace=Path(temporary.name)/"trace.log"; self.trace.write_text("")
        self.swconst=Path(temporary.name)/"swconst.tlb"; self.swconst.write_bytes(b"static")
        self.fake=QualityCLI(self.directory,self.trace)

    def run_gate(self, *, document_properties=False, public_acceptance=False):
        def sdk(**kwargs):
            def read(**context):
                quality=deepcopy(self.fake.documents[context["document_id"]]["quality"])
                result=dict(quality=quality,document=self.fake.descriptor(self.fake.documents[context["document_id"]],kwargs["session_id"]))
                return SimpleNamespace(ok=True,raw=dict(result=result),require_result=lambda:result)
            return SimpleNamespace(document=SimpleNamespace(image_quality=read))
        with mock.patch.object(gate.modeling.subprocess,"run",side_effect=self.fake.run), \
                mock.patch.object(gate,"constants",return_value={}), mock.patch.object(gate,"Client",side_effect=sdk), \
                mock.patch.object(gate.importlib.metadata,"version",return_value="portable-fake"), \
                mock.patch.object(gate,"public_mcp_observation",return_value={"scope":"portable gate fixture"}), \
                mock.patch.dict(gate.os.environ, SWCLI_IMAGE_QUALITY_CALIBRATION="", SWCLI_GLB_PLAIN_STAGING_CALIBRATION=""), \
                mock.patch("sys.stdout",new=io.StringIO()):
            return gate.main(["--output-dir",str(self.directory),"--swconst",str(self.swconst),"--native-trace",str(self.trace),"--inside-watchdog", *(["--document-properties"] if document_properties else []), *(["--public-acceptance"] if public_acceptance else [])])

    def record(self): return json.loads((self.directory/"image-quality.json").read_text())

    def test_both_fixtures_three_levels_persist_full_raw_and_never_claim_glb_control(self):
        self.run_gate(); record=self.record()
        self.assertTrue(record["success"],record)
        self.assertFalse(record["full_acceptance_eligible"] or record["glb_control_proven"] or record["image_quality_writes_accepted"])
        self.assertEqual([case["shape"] for case in record["cases"]],["cylinder","box"])
        for case in record["cases"]:
            self.assertEqual(case["triangle_counts"],dict(coarse=1,fine=1,custom=1))
            self.assertFalse(case["quality_associated_triangle_difference_observed"])
            self.assertTrue(case["baseline_readonly_open"]["read_only"])
            self.assertEqual(case["baseline_reopened_quality"]["quality"],case["initial"]["quality"])
            self.assertTrue(Path(case["baseline_save"]["path"]).is_file())
            self.assertTrue(all(row["success"] and row["reopen"]["read_only"] for row in case["levels"]))
            self.assertEqual([len(row["noops"]) for row in case["levels"]],[3,3,2])
        self.assertEqual(self.fake.documents,{})
        self.assertTrue(all(event["request_timeout_seconds"]==600 for event in record["events"]))

    def test_custom_target_is_observed_native_value_not_an_arbitrary_range_interpolation(self):
        self.fake.quality_defect="quantize-unobserved-deviation"
        self.run_gate(document_properties=True)
        for case in self.record()["cases"]:
            row=case["levels"][-1]
            self.assertEqual(row["deviation_write"]["quality"]["shaded_deviation_mm"],case["initial"]["quality"]["shaded_deviation_mm"])
            self.assertEqual(row["deviation_target_evidence"]["source"],"initial native custom snapshot")
            self.assertNotEqual(row["deviation_write"]["before"]["shaded_deviation_mm"],row["deviation_target_evidence"]["requested_mm"])
        self.assertIn("arbitrary in-range values unsupported",self.record()["deviation_write_scope"])

    def test_document_properties_is_a_separate_complete_group_without_glb_claims(self):
        self.run_gate(document_properties=True);record=self.record()
        self.assertTrue(record["success"])
        self.assertEqual(record["profile"],"document-image-quality-calibration")
        self.assertFalse(record["covers_glb_mesh"] or record["glb_control_proven"] or record["image_quality_writes_accepted"])
        self.assertEqual(record["optimize_edge_length_verified_values"],[True,False])
        for case in record["cases"]:
            self.assertEqual(case["levels"][-1]["reopened_quality"]["quality"]["optimize_edge_length"],False)
            self.assertTrue(case["levels"][0]["reopened_quality"]["quality"]["optimize_edge_length"])
            self.assertTrue(case["levels"][1]["reopened_quality"]["quality"]["optimize_edge_length"])
            self.assertNotIn("mesh",case["levels"][-1])
        self.assertFalse(any(call.command=="document" and call.document_command=="export" for call in self.fake.calls))
        self.assertEqual(self.fake.documents,{})

    def test_public_entry_is_distinct_and_cannot_use_calibration_switches(self):
        self.run_gate(document_properties=True,public_acceptance=True)
        record=self.record()
        self.assertEqual(record["profile"],"document-image-quality-public")
        self.assertTrue(record["public_acceptance_passed"] and record["image_quality_writes_accepted"])
        self.assertFalse(record["image_quality_calibration_passed"] or record["covers_glb_mesh"] or record["glb_control_proven"] or record["full_acceptance_eligible"])
        for name in ("SWCLI_IMAGE_QUALITY_CALIBRATION","SWCLI_GLB_PLAIN_STAGING_CALIBRATION"):
            with mock.patch.dict(gate.os.environ,{name:"1"}), mock.patch.object(gate.subprocess,"run") as native, mock.patch("sys.stderr",new=io.StringIO()):
                with self.assertRaises(SystemExit):
                    gate.main(["--public-acceptance","--document-properties","--output-dir",str(self.directory),"--swconst",str(self.swconst),"--native-trace",str(self.trace)])
                native.assert_not_called()

    def test_public_mcp_observation_discovers_contract_and_reads_once_without_host_start(self):
        from tests.test_sdk import document
        core=dict(ok=True,action="document.image-quality",session_id="quality-mcp",document=document(),quality=snapshot())
        core["document"].update(active=False,current=False)
        native_trace=mock.Mock(); native_trace.verify.return_value={"setter_count":0}
        host=SimpleNamespace(endpoint="127.0.0.1:19812",session="quality")
        contract=gate.OPERATION_CATALOG["document.image-quality-set"]
        schemas=dict(success=True,result=dict(operation_schemas={"document.image-quality-set":contract.parameters},
            operation_result_schemas={"document.image-quality-set":contract.result}))
        for defect in (None,"identity","quality","schema"):
            with self.subTest(defect=defect):
                capabilities=deepcopy(schemas); reply=dict(success=True,request_id="mcp-read-once",result=deepcopy(core))
                if defect=="identity": reply["result"]["document"]["active"]=True
                if defect=="quality": reply["result"]["quality"]["save_tessellation"]=False
                if defect=="schema": capabilities["result"]["operation_schemas"]={}
                with mock.patch.object(gate,"DaemonBridge") as factory:
                    bridge=factory.return_value;bridge.call.side_effect=[capabilities,reply]
                    if defect:
                        with self.assertRaises((RuntimeError,ValueError,KeyError)):
                            gate.public_mcp_observation(host,core["document"]["document_id"],core,native_trace)
                    else:
                        result=gate.public_mcp_observation(host,core["document"]["document_id"],core,native_trace)
                        self.assertEqual(result["read"],reply)
                        self.assertEqual(bridge.call.call_count,2)
                        self.assertEqual(bridge.call.call_args.args,("execute",dict(operation="document.image-quality",parameters={},
                            document_id=core["document"]["document_id"],expected_update_stamp=core["document"]["update_stamp"])))
                    bridge.manager.start.assert_not_called();bridge.manager.stop.assert_not_called()
                    factory.assert_called_once_with(endpoint=host.endpoint,session_id="quality-mcp",timeout_seconds=600)
        native_trace.verify.assert_called_once()

    def test_first_failure_trace_and_lost_persistence_stop_without_retry_and_clean_once(self):
        for defect in ("native-first-failure","missing-trace","missing-native-getter","reopen-lost-value","global-setter","reordered-preferences"):
            with self.subTest(defect=defect):
                self.setUp(); self.fake.quality_defect=defect
                with self.assertRaises((RuntimeError, ValueError)): self.run_gate()
                self.assertFalse(self.record()["success"])
                self.assertEqual(self.fake.documents,{})
                if defect=="native-first-failure":
                    self.assertEqual(self.fake.setters,1)
                    self.assertTrue(Path(self.record()["cases"][0]["baseline_save"]["path"]).is_file())
                self.assertEqual(len(self.record()["cases"]),1)

    def test_cleanup_failure_cannot_retain_public_acceptance_flags(self):
        original=gate.QualitySmoke.cleanup
        def fail_cleanup(smoke):
            original(smoke)
            smoke.record["cleanup_errors"].append("injected cleanup failure")
        with mock.patch.object(gate.QualitySmoke,"cleanup",fail_cleanup):
            with self.assertRaisesRegex(RuntimeError,"cleanup failed"):
                self.run_gate(document_properties=True,public_acceptance=True)
        record=self.record()
        self.assertFalse(record["success"] or record["public_acceptance_passed"] or record["image_quality_writes_accepted"] or record["image_quality_calibration_passed"])

    def test_external_watchdog_bounds_whole_group_without_retry(self):
        with mock.patch.object(gate.subprocess,"run",side_effect=subprocess.TimeoutExpired("gate",1800)) as child:
            result=gate.main(["--output-dir",str(self.directory),"--swconst",str(self.swconst),"--native-trace",str(self.trace)])
        self.assertEqual(result,1); child.assert_called_once()
        self.assertEqual(child.call_args.kwargs["timeout"],1800)
        self.assertFalse(json.loads((self.directory/"group-timeout.json").read_text())["success"])

    def test_ci_target_is_default_off_exclusive_branch_only_and_skips_full_fixtures(self):
        workflow=(ROOT/".github/workflows/ci.yml").read_text()
        setting=workflow.split("      image_quality_calibration:",1)[1].split("permissions:",1)[0]
        self.assertIn("default: false",setting)
        guard=workflow.split("  solidworks-e2e:",1)[1].split("runs-on:",1)[0]
        self.assertIn("needs.native-profile.result == 'success'",guard)
        policy=(ROOT/"scripts/ci/validate-native-profile.py").read_text()
        self.assertIn('"image_quality_calibration": "refs/heads/codex/docprops-export-options"',policy)
        self.assertIn('"image_quality_public_acceptance": "refs/heads/codex/docprops-export-options"',policy)
        self.assertIn("needs.native-profile.outputs.profile == 'image_quality_calibration'",guard)
        self.assertNotIn("pull_request:",workflow)
        concurrency=workflow.split("  solidworks-e2e:",1)[1].split("    env:",1)[0]
        self.assertIn("inputs.image_quality_calibration && format('swcli-image-quality-{0}', github.ref)",concurrency)
        self.assertIn("|| 'swcli-hosted-windows-solidworks'",concurrency)
        self.assertIn("cancel-in-progress: false",concurrency)
        self.assertIn("format('swcli-image-quality-public-{0}', github.ref)",concurrency)
        public_setting=workflow.split("      image_quality_public_acceptance:",1)[1].split("permissions:",1)[0]
        self.assertIn("default: false",public_setting)
        self.assertIn("needs.native-profile.outputs.profile == 'image_quality_public_acceptance'",guard)
        for name in ("Prepare property fixtures","Prepare annotation fixtures","Run real SOLIDWORKS modeling"):
            block=workflow.split("      - name: "+name,1)[1].split("      - name:",1)[0]
            self.assertIn("needs.native-profile.outputs.profile == 'full'",block)
        wrapper=(ROOT/"scripts/ci/windows/smoke-solidworks.ps1").read_text()
        block=wrapper.split('    if ($ImageQualityCalibration -or $ImageQualityPublicAcceptance) {\n        # Independent property',1)[1].split('    if ($VisibleSmoke)',1)[0]
        self.assertIn('return',block)
        self.assertLess(block.index('--document-properties'),block.index('Image-quality document-properties group failed'))
        self.assertLess(block.index('Image-quality document-properties group failed'),block.index('--output-dir (Join-Path $Workspace \"calibration\")'))
        self.assertIn('if ($LASTEXITCODE -ne 0)',block)
        self.assertNotIn('restart',block)
        public_stop=block.split('        if ($ImageQualityPublicAcceptance) {',2)[-1].split('        & python',1)[0]
        self.assertIn('return',public_stop)
        self.assertLess(block.index('quality-public-stop'),block.index('--output-dir (Join-Path $Workspace \"calibration\")'))
