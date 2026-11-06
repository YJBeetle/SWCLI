"""Portable public-gate fault injection; not native calibration evidence."""
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from swcli.cli import _typed_operation
from tests.test_document_annotations_smoke import AnnotationsCLI

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("_public_tolerance_gate_test",ROOT/"scripts/ci/verify-document-tolerances.py")
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)


def option(field,value):
    from swcli.document_tolerances import TOLERANCE_FIELDS
    return dict(value=value,native_value=TOLERANCE_FIELDS[field]["values"][value])


class ToleranceCLI(AnnotationsCLI):
    def __init__(self,*args):
        super().__init__(*args)
        self.tolerance_defect=None

    def run(self,command,**kwargs):
        completed=super().run(command,**kwargs)
        args=self.calls[-1]
        if args.command=="document" and args.document_command in ("tolerances","tolerance-set"):
            raw=json.loads(completed.stdout);request=raw["request_id"];operation="document."+args.document_command
            records=[dict(event="swcli.native-call",request_id=request,operation=operation,worker_pid=4242,
                          sequence=0,call=operation,phase="begin")]
            native_calls=["GetDocuments","GetUpdateStamp"]+self.last_native_calls+["GetSaveFlag"]
            for seq,name in enumerate(native_calls,1):
                for phase in ("begin","end"):records.append(dict(records[0],sequence=seq,call=name,phase=phase))
            records.append(dict(records[0],phase="end"))
            if self.tolerance_defect=="missing-trace-end":records=records[:-1]
            with self.trace.open("a") as stream:
                for row in records:stream.write(json.dumps(row)+"\n")
        return completed

    def dispatch(self,args):
        if args.command=="document" and args.document_command in ("tolerances","tolerance-set"):
            document=self.documents[args.document_id];options=document["tolerances"]
            result=dict(ok=True,action="document."+args.document_command,session_id=args.session,
                        document=self.descriptor(document,args.session),scope="document_defaults_linear")
            if args.document_command=="tolerances":
                self.last_native_calls.extend([gate.GET]*2)
                return dict(result,options=deepcopy(options),write_enabled=True)
            _,values,*_=_typed_operation(args)
            if args.expected_update_stamp!=document["stamp"]:return self.failure("DocumentUpdateConflict")
            if document["lease"]["session"]!=args.session:return self.failure("DocumentLeaseConflict")
            mutation=dict(attempted=False,may_have_changed=False)
            if document["read_only"]:return self.failure("ValueError",mutation=mutation)
            self.last_native_calls.extend([gate.GET]*2)
            if values["expected_options"]!=options:return self.failure("ValueError",mutation=mutation)
            field,value=values["field"],values["value"]
            before=deepcopy(options);changed=options[field]["value"]!=value
            if changed:
                self.last_native_calls.append(gate.SET)
                if self.tolerance_defect=="native-failure":
                    return self.failure("NativeToleranceFailure",mutation=dict(attempted=True,may_have_changed=True))
                options[field]=option(field,value);self.native_sets+=1
                self.last_native_calls.extend([gate.GET]*2)
                if not document["modified"]:self.last_native_calls.append(gate.DIRTY)
                document["modified"]=True
                self.last_native_calls.extend([gate.GET]*2)
            elif self.tolerance_defect=="noop-setter":self.last_native_calls.append(gate.SET)
            elif self.tolerance_defect=="noop-dirty":document["modified"]=True
            return dict(result,field=field,before=before,options=deepcopy(options),changed=changed,
                        mutation=dict(attempted=changed,may_have_changed=changed),document=self.descriptor(document,args.session))
        result=super().dispatch(args)
        if args.command=="document" and args.document_command=="measure":
            result["metrics"]["centroid_mm"]=dict(x=0.,y=0.,z=5.)
        if args.command=="document" and args.document_command in ("create","open"):
            document=self.documents[result["document"]["document_id"]]
            document.setdefault("tolerances",{"linear.type":option("linear.type","none"),
                                               "linear.precision":option("linear.precision","follow_nominal")})
            if args.document_command=="open" and args.read_only and self.tolerance_defect=="reopen-lost-value":
                document["tolerances"]["linear.precision"]=option("linear.precision","0")
        return result


class PublicToleranceGateTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.directory=Path(temporary.name)/"evidence"
        self.fixtures=Path(temporary.name)/"fixtures";self.fixtures.mkdir()
        for suffix in ("SLDPRT","SLDASM","SLDDRW"):(self.fixtures/("annotations."+suffix)).write_bytes(b"owned native fixture"*100)
        self.trace=Path(temporary.name)/"trace.log";self.trace.write_text("")
        self.fake=ToleranceCLI(self.directory,self.fixtures,self.trace)

    def execute(self):
        with mock.patch.object(gate.helpers.modeling.subprocess,"run",side_effect=self.fake.run), \
             mock.patch.object(gate,"client_contracts") as contracts, \
             mock.patch("sys.stdout",new=io.StringIO()):
            gate.main(["--output-dir",str(self.directory),"--fixture-dir",str(self.fixtures),"--native-trace",str(self.trace),"--host-output-dir",r"C:\proof"])
        return contracts

    def report(self):return json.loads((self.directory/"document-tolerances.json").read_text())

    def test_three_kinds_save_reopen_cas_noop_trace_and_source_ownership(self):
        contracts=self.execute();record=self.report()
        self.assertTrue(record["success"])
        self.assertEqual([c["kind"] for c in record["tolerance_cases"]],[1,2,3])
        self.assertEqual(len(contracts.call_args_list),3)
        self.assertEqual(self.fake.documents,{})
        self.assertEqual(self.fake.native_sets,30)
        self.assertFalse(record["full_acceptance_eligible"])
        self.assertEqual(record["cleanup_errors"],[])
        self.assertEqual({p["worker_pid"] for p in record["native_proofs"]},{4242})
        for case in record["tolerance_cases"]:
            self.assertTrue(case["success"])
            self.assertEqual([phase["reopened_options"]["options"]["linear.precision"]["value"] for phase in case["persistence_cases"]],["0","8","3"])
            self.assertEqual([phase["reopened_options"]["options"]["linear.type"]["value"] for phase in case["persistence_cases"]],["basic","basic","none"])
            self.assertEqual(case["reopened_options"]["options"]["linear.precision"],option("linear.precision","3"))
            self.assertFalse(case["reopened_options"]["document"]["modified"])
            self.assertNotEqual(case["open"]["document"]["document_id"],case["reopen"]["document"]["document_id"])

    def test_failed_setter_preserves_first_receipt_and_stops_without_second_case(self):
        self.fake.tolerance_defect="native-failure"
        with self.assertRaises(RuntimeError):self.execute()
        record=self.report();self.assertFalse(record["success"])
        self.assertEqual(len(record["tolerance_cases"]),1)
        self.assertEqual(self.fake.native_sets,0)
        failed=[e for e in record["events"] if e.get("result",{}).get("error",{}).get("type")=="NativeToleranceFailure"]
        self.assertEqual(len(failed),1)
        self.assertTrue(failed[0]["result"]["mutation"]["may_have_changed"])

    def test_missing_trace_noop_native_call_dirty_noop_or_lost_persistence_never_pass(self):
        for defect in ("missing-trace-end","noop-setter","noop-dirty","reopen-lost-value"):
            with self.subTest(defect=defect):
                self.setUp();self.fake.tolerance_defect=defect
                with self.assertRaises(RuntimeError):self.execute()
                record=self.report();self.assertFalse(record["success"])
                self.assertEqual(len(record["tolerance_cases"]),1)


class PublicToleranceClientContractsTests(unittest.TestCase):
    def current(self):
        return dict(ok=True,action="document.tolerances",scope="document_defaults_linear",write_enabled=True,
            session_id="contract",document=dict(title="owned",path="C:\\owned.SLDPRT",type=1,modified=False,
                update_stamp=7,document_id="d-ab12cd",active=False,current=False),
            options={"linear.type":option("linear.type","none"),"linear.precision":option("linear.precision","3")})

    def execute(self,defect=None):
        from types import SimpleNamespace
        from swcli import PROTOCOL_VERSION
        calls=[];current=self.current();proof=mock.Mock()
        self.latest_runner=None
        runner=SimpleNamespace(endpoint="127.0.0.1:3498",session="contract",leases={"d-ab12cd":"l-ab12cd34ef56"},record={},checkpoint=mock.Mock())
        self.latest_runner=runner
        def transport(operation,parameters,**context):
            calls.append((operation,deepcopy(parameters),deepcopy(context)))
            self.assertEqual(context["session_id"],"contract")
            if operation=="daemon.capabilities":
                self.assertEqual(parameters["operation"],"document.tolerance-set")
                result=dict(operation_schemas={})
            else:
                self.assertEqual(context["document_id"],"d-ab12cd")
                self.assertEqual(context["expected_update_stamp"],7)
                result=deepcopy(current)
                if operation=="document.tolerance-set":
                    self.assertEqual(context["lease_id"],"l-ab12cd34ef56")
                    self.assertEqual(parameters,dict(field="linear.precision",value="3",expected_options=current["options"]))
                    result.pop("write_enabled");result.update(action=operation,field="linear.precision",before=deepcopy(current["options"]),
                        changed=False,mutation=dict(attempted=False,may_have_changed=False))
                    if defect=="dirty-sdk-noop" and len(calls)==2:result["document"]["modified"]=True
                if defect=="mcp-read-mismatch" and len(calls)==4:
                    result["options"]["linear.precision"]=option("linear.precision","0")
            return dict(api_version=PROTOCOL_VERSION,request_id=context["request_id"],success=True,duration_ms=0,result=result)
        with mock.patch("swcli.sdk.client.call_daemon",side_effect=transport), \
             mock.patch("swcli.mcp.call_daemon",side_effect=transport):
            gate.client_contracts(runner,proof,"d-ab12cd",current)
        return runner,proof,calls

    def test_real_sdk_and_bridge_forward_required_context_and_complete_cas_without_retries(self):
        runner,proof,calls=self.execute()
        self.assertEqual([call[0] for call in calls],["document.tolerances","document.tolerance-set", "daemon.capabilities",
            "document.tolerances","document.tolerance-set"])
        self.assertEqual(proof.verify.call_count,4)
        self.assertEqual(len({c[2]["request_id"] for c in calls}),5)
        self.assertEqual(len(runner.record["client_contracts"]),1)

    def test_sdk_noop_state_change_and_bridge_read_mismatch_are_rejected(self):
        for defect in ("dirty-sdk-noop","mcp-read-mismatch"):
            with self.subTest(defect=defect):
                with self.assertRaises(RuntimeError):self.execute(defect)
                row=self.latest_runner.record["client_contracts"][0]
                key="sdk_noop" if defect=="dirty-sdk-noop" else "mcp_execute"
                self.assertIn("raw",row[key])
                self.assertIn("request_id",row[key]["raw"])


if __name__=="__main__":unittest.main()
