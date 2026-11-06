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
        self.assertEqual(self.fake.native_sets,15)
        self.assertFalse(record["full_acceptance_eligible"])
        self.assertEqual(record["cleanup_errors"],[])
        self.assertEqual({p["worker_pid"] for p in record["native_proofs"]},{4242})
        for case in record["tolerance_cases"]:
            self.assertTrue(case["success"])
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


if __name__=="__main__":unittest.main()
