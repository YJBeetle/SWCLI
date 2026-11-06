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
from swcli.document_image_quality import exact_snapshot, quality_snapshot
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
            for sequence, name in enumerate([operation,*self.native_calls]):
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
                if field == "shaded_mode": raw[field]={"coarse":1,"fine":2,"custom":3}[value]
                elif field == "shaded_deviation_mm": raw["shaded_deviation_m"]=value/1000
                else: raw[field]=value
                document["quality"]=quality=quality_snapshot(raw,quality["deviation_range"])
                document["modified"]=True
                self.native_calls.append("IModelDocExtension.SetUserPreference"+gate.IMAGE_QUALITY_FIELDS[field]["kind"])
                self.getters(); self.getters()
            result=dict(base,field=field,before=before,quality=deepcopy(quality),changed=changed,
                mutation=dict(attempted=changed,may_have_changed=changed),linked_changes=[],document=self.descriptor(document,args.session))
            if changed: result.update(native_return=True,observed_quality=deepcopy(quality))
            return result
        if action == "document" and sub in ("save-as","export"):
            document=self.documents[args.document_id]
            target=self.directory/PureWindowsPath(args.output).name
            target.write_bytes(mesh_fixture("GLB") if sub=="export" else bytes(1024))
            if sub=="export":
                return dict(ok=True,artifact=dict(size_bytes=target.stat().st_size,format="GLB",path=args.output))
            document.update(path=args.output,modified=False); self.saved[args.output]=deepcopy(document)
            return dict(ok=True,api_saved=True,save_errors=0,save_warnings=None,document=self.descriptor(document,args.session),
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

    def run_gate(self):
        def sdk(**kwargs):
            def read(**context):
                quality=deepcopy(self.fake.documents[context["document_id"]]["quality"])
                return SimpleNamespace(ok=True,raw=dict(result=dict(quality=quality)),require_result=lambda:dict(quality=quality))
            return SimpleNamespace(document=SimpleNamespace(image_quality=read))
        with mock.patch.object(gate.modeling.subprocess,"run",side_effect=self.fake.run), \
                mock.patch.object(gate,"constants",return_value={}), mock.patch.object(gate,"Client",side_effect=sdk), \
                mock.patch("sys.stdout",new=io.StringIO()):
            return gate.main(["--output-dir",str(self.directory),"--swconst",str(self.swconst),"--native-trace",str(self.trace),"--inside-watchdog"])

    def record(self): return json.loads((self.directory/"image-quality.json").read_text())

    def test_both_fixtures_three_levels_persist_full_raw_and_never_claim_glb_control(self):
        self.run_gate(); record=self.record()
        self.assertTrue(record["success"],record)
        self.assertFalse(record["full_acceptance_eligible"] or record["glb_control_proven"] or record["image_quality_writes_accepted"])
        self.assertEqual([case["shape"] for case in record["cases"]],["cylinder","box"])
        for case in record["cases"]:
            self.assertEqual(case["triangle_counts"],dict(coarse=1,fine=1,custom=1))
            self.assertFalse(case["quality_associated_triangle_difference_observed"])
            self.assertTrue(all(row["success"] and row["reopen"]["read_only"] for row in case["levels"]))
        self.assertEqual(self.fake.documents,{})
        self.assertTrue(all(event["request_timeout_seconds"]==600 for event in record["events"]))

    def test_first_failure_trace_and_lost_persistence_stop_without_retry_and_clean_once(self):
        for defect in ("native-first-failure","missing-trace","missing-native-getter","reopen-lost-value"):
            with self.subTest(defect=defect):
                self.setUp(); self.fake.quality_defect=defect
                with self.assertRaises((RuntimeError, ValueError)): self.run_gate()
                self.assertFalse(self.record()["success"])
                self.assertEqual(self.fake.documents,{})
                if defect=="native-first-failure": self.assertEqual(self.fake.setters,1)
                self.assertEqual(len(self.record()["cases"]),1)

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
        self.assertIn("github.ref == 'refs/heads/codex/docprops-export-options'",guard)
        self.assertIn("inputs.image_quality_calibration && !inputs.native_full",guard)
        self.assertNotIn("pull_request:",workflow)
        for name in ("Prepare property fixtures","Prepare annotation fixtures","Run real SOLIDWORKS modeling"):
            block=workflow.split("      - name: "+name,1)[1].split("      - name:",1)[0]
            self.assertIn("if: ${{ !inputs.image_quality_calibration }}",block)
        wrapper=(ROOT/"scripts/ci/windows/smoke-solidworks.ps1").read_text()
        block=wrapper.split('    if ($ImageQualityCalibration) {\n        & python',1)[1].split('    if ($VisibleSmoke)',1)[0]
        self.assertIn('return',block)
        self.assertIn('if ($LASTEXITCODE -ne 0)',block)
        self.assertNotIn('restart',block)
