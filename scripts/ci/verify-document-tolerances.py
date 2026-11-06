"""Installed public CLI/daemon tolerance gate; SDK and MCP bridge use the same daemon.

No direct COM, host restart, failed API retry or automatic rollback.
"""
import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import threading
import time

from swcli import __version__
from swcli.document_tolerances import TOLERANCE_FIELDS
from swcli.result_schemas import validate_operation_result
from swcli.sdk import Client
from swcli.mcp import DaemonBridge

spec=importlib.util.spec_from_file_location("_tolerance_public_helpers",Path(__file__).with_name("verify-document-annotations.py"))
helpers=importlib.util.module_from_spec(spec);spec.loader.exec_module(helpers)
require=helpers.require
GET="IModelDocExtension.GetUserPreferenceInteger"
SET="IModelDocExtension.SetUserPreferenceInteger"
DIRTY="IModelDoc2.SetSaveFlag"


class NativeTrace:
    def __init__(self,path):
        self.path=path;self.requests=set();self.worker=None

    def verify(self,gate,*,setters,getters,raw=None):
        raw=raw or gate.record["events"][-1]["result"]
        request=raw.get("request_id")
        require(isinstance(request,str) and request and request not in self.requests,"missing/reused public request id")
        records=[]
        for line in self.path.read_text(encoding="utf-8-sig").splitlines():
            try:record=json.loads(line)
            except json.JSONDecodeError:
                require('"swcli.native-call"' not in line,"malformed native trace");continue
            if record.get("event")=="swcli.native-call" and record.get("request_id")==request:records.append(record)
        require(records and records[0]["phase"]=="begin" and records[-1]["phase"] in (("end",) if raw.get("ok") is not False else ("end","error"))
                and records[0]["sequence"]==records[-1]["sequence"]==0,"public request trace is incomplete")
        worker=records[0].get("worker_pid")
        require(type(worker) is int and worker>0,"native worker identity missing")
        self.worker=worker if self.worker is None else self.worker
        require(worker==self.worker and all(r.get("worker_pid")==worker for r in records),"native worker changed")
        operation=records[0]["operation"]
        require(operation in ("document.tolerances","document.tolerance-set")
                and records[-1]["call"]==records[0]["call"]==operation
                and all(r.get("operation")==operation for r in records),"native operation mismatch")
        calls=records[1:-1]
        require(len(calls)%2==0,"incomplete native call")
        for sequence,(begin,end) in enumerate(zip(calls[::2],calls[1::2]),1):
            require(begin["sequence"]==end["sequence"]==sequence and begin["call"]==end["call"]
                    and begin["phase"]=="begin" and end["phase"]=="end","native call order/error mismatch")
        all_names=[r["call"] for r in calls[::2]]
        require(not any("SetUserPreference" in name and name!=SET for name in all_names),
                "public tolerance request changed global preferences")
        names=[name for name in all_names if "UserPreference" in name or name==DIRTY]
        dirty=names.count(DIRTY)
        expected=([GET]*2+[SET]+[GET]*2+[DIRTY]*dirty+[GET]*2) if setters else [GET]*getters
        require(names==expected and names.count(SET)==setters and names.count(GET)==getters
                and dirty<=1,"native call count/order does not match exact write/noop/refusal")
        self.requests.add(request)
        proof=dict(request_id=request,operation=operation,worker_pid=worker,setters=setters,getters=getters,dirty=dirty)
        gate.record.setdefault("native_proofs",[]).append(proof)
        return proof

    def snapshot(self):
        content=self.path.read_bytes()
        return dict(prefix_size_bytes=len(content),prefix_sha256=hashlib.sha256(content).hexdigest(),verified_requests=len(self.requests))


def read(gate,trace,document):
    result=gate.command("document","tolerances",document=document)
    validate_operation_result("document.tolerances",result)
    trace.verify(gate,setters=0,getters=2);gate.background(result,document)
    require(result["write_enabled"] is True,"accepted public tolerance scope is disabled")
    return result


def edit(gate,trace,document,before,field,value,*,expected=None,error=None,session=None,stamp=None):
    options=before["options"] if expected is None else expected
    arguments=("document","tolerance-set",field,value,"--if-options",json.dumps(options),
               "--if-update-stamp",before["document"]["update_stamp"] if stamp is None else stamp)
    if session:
        result=gate.command(*arguments,document=document,session=session,lease=gate.leases[document],expected_error=error)
    else:result=gate.write(*arguments,document=document,expected_error=error)
    if error:
        trace.verify(gate,setters=0,getters=2 if error=="ValueError" and expected is not None else 0)
        if "mutation" in result:require(result["mutation"]==dict(attempted=False,may_have_changed=False),"refusal attempted mutation")
        return result
    validate_operation_result("document.tolerance-set",result)
    changed=before["options"][field]["value"]!=value
    trace.verify(gate,setters=int(changed),getters=6 if changed else 2)
    require(result["before"]==before["options"] and result["options"][field]["value"]==value
            and result["changed"] is changed and result["mutation"]==dict(attempted=changed,may_have_changed=changed)
            and all(result["options"][other]==before["options"][other] for other in TOLERANCE_FIELDS if other!=field),
            "public tolerance write did not preserve exact isolated profile")
    gate.background(result,document)
    if not changed:require(result["document"]==before["document"],"noop changed document state")
    return result


def client_contracts(gate,trace,document,current):
    client=Client(endpoint=gate.endpoint,session_id=gate.session,timeout_seconds=600)
    sdk=client.document.tolerances(document_id=document,expected_update_stamp=current["document"]["update_stamp"])
    observed=sdk.require_result()
    require(observed["options"]==current["options"] and observed["document"]==current["document"],"SDK read differs from CLI")
    trace.verify(gate,setters=0,getters=2,raw={**observed,"request_id":sdk.request_id})
    noop=client.document.tolerance_set(field="linear.precision",value="3",expected_options=current["options"],
        document_id=document,expected_update_stamp=current["document"]["update_stamp"],lease_id=gate.leases[document])
    value=noop.require_result()
    require(value["changed"] is False and value["document"]==current["document"],"SDK noop mutated native state")
    trace.verify(gate,setters=0,getters=2,raw={**value,"request_id":noop.request_id})
    bridge=DaemonBridge(endpoint=gate.endpoint,session_id=gate.session,timeout_seconds=600)
    cap=bridge.call("capabilities",dict(operation="document.tolerance-set"))
    require(cap["success"] is True,"MCP operation discovery failed")
    mcp=bridge.call("execute",dict(operation="document.tolerances",parameters={},document_id=document,
                                 expected_update_stamp=current["document"]["update_stamp"]))
    require(mcp["success"] is True and mcp["result"]["options"]==current["options"]
            and mcp["result"]["document"]==current["document"],"MCP bridge read differs from CLI")
    trace.verify(gate,setters=0,getters=2,raw={**mcp["result"],"request_id":mcp["request_id"]})
    mcp_noop=bridge.call("execute",dict(operation="document.tolerance-set",parameters=dict(
        field="linear.precision",value="3",expected_options=current["options"]),document_id=document,
        expected_update_stamp=current["document"]["update_stamp"],lease_id=gate.leases[document]))
    require(mcp_noop["success"] is True and mcp_noop["result"]["ok"] is True
            and mcp_noop["result"]["changed"] is False and mcp_noop["result"]["document"]==current["document"],
            "MCP bridge noop changed native state or failed context forwarding")
    trace.verify(gate,setters=0,getters=2,raw={**mcp_noop["result"],"request_id":mcp_noop["request_id"]})
    gate.record.setdefault("client_contracts",[]).append(dict(sdk_read=dict(sdk.raw),sdk_noop=dict(noop.raw),
        mcp_capabilities=cap,mcp_execute=mcp,mcp_noop=mcp_noop))


def run(gate,fixtures,trace):
    gate.record.update(profile="document-tolerances-public",acceptance_scope="linear.type=none/basic;linear.precision=0/3/8",
                       full_acceptance_eligible=False,success=False,tolerance_cases=[])
    host=gate.record["host"]=gate.health()["host"]
    require(host["owned_by_daemon"] is True and host["visible"] is False
            and host["shared_interactive"] is False,"public tolerance gate needs independent hidden host")
    gate.require_empty()
    for suffix,kind in (("SLDPRT",1),("SLDASM",2),("SLDDRW",3)):
        source=fixtures/("annotations."+suffix)
        source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
        opened,document,foreground=helpers.open_background(gate,str(source),kind)
        case=dict(kind=kind,source_sha256=source_hash,open=opened,writes=[],success=False)
        gate.record["tolerance_cases"].append(case)
        gate.command("document","lease","acquire","--ttl-seconds",1800,document=document)
        current=case["initial"]=read(gate,trace,document)
        if kind==1:case["geometry_initial"]=helpers.geometry(gate,document)
        case["lease_refusal"]=edit(gate,trace,document,current,"linear.type","basic",session=gate.session+"-contender",error="DocumentLeaseConflict")
        case["stamp_refusal"]=edit(gate,trace,document,current,"linear.type","basic",stamp=current["document"]["update_stamp"]+1,error="DocumentUpdateConflict")
        stale=deepcopy(current["options"]);stale["linear.precision"]["native_value"]+=100
        case["cas_refusal"]=edit(gate,trace,document,current,"linear.type","basic",expected=stale,error="ValueError")
        after=read(gate,trace,document)
        require(after==current,"guard refusals changed public document state")
        for field,value in (("linear.type","basic"),("linear.type","none"),("linear.precision","0"),
                            ("linear.precision","8"),("linear.precision","3")):
            current=edit(gate,trace,document,current,field,value)
            case["writes"].append(current)
        if kind==1:helpers.same_geometry(case["geometry_initial"],helpers.geometry(gate,document))
        saved=case["save"]=helpers.save_copy(gate,document,"public-tolerances."+suffix,suffix)
        clean=read(gate,trace,document)
        for field in TOLERANCE_FIELDS:
            case.setdefault("clean_noops",[]).append(edit(gate,trace,document,clean,field,clean["options"][field]["value"]))
        client_contracts(gate,trace,document,clean)
        gate.close(document);gate.close(foreground)
        reopened,fresh,foreground=helpers.open_background(gate,saved["host_path"],kind,read_only=True)
        case["reopen"]=reopened
        require(fresh!=document,"readonly reopen reused retired document identity")
        observed=case["reopened_options"]=read(gate,trace,fresh)
        require(observed["options"]==current["options"] and observed["document"]["modified"] is False,"saved defaults did not persist cleanly")
        gate.command("document","lease","acquire","--ttl-seconds",1800,document=fresh)
        case["readonly_refusal"]=edit(gate,trace,fresh,observed,"linear.type","basic",error="ValueError")
        final=read(gate,trace,fresh)
        require(final==observed,"readonly refusal changed native state")
        if kind==1:helpers.same_geometry(case["geometry_initial"],helpers.geometry(gate,fresh))
        gate.close(fresh);gate.close(foreground);gate.require_empty(after_case="tolerances-"+suffix)
        require(hashlib.sha256(source.read_bytes()).hexdigest()==source_hash
                and hashlib.sha256(Path(saved["path"]).read_bytes()).hexdigest()==saved["sha256"],"source or saved bytes changed")
        case["success"]=True;gate.checkpoint("tolerances-"+suffix+"-verified")
    require(gate.health()["host"]==host,"public gate changed its owned host")
    gate.record.update(state="completed",success=True,elapsed_seconds=time.monotonic()-gate.group_started)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir",type=Path,required=True)
    parser.add_argument("--fixture-dir",type=Path,required=True)
    parser.add_argument("--native-trace",type=Path,required=True)
    parser.add_argument("--host-output-dir",type=helpers.modeling.host_directory)
    args=parser.parse_args(argv)
    directory=args.output_dir.resolve();directory.mkdir(parents=True,exist_ok=False)
    gate=helpers.AnnotationSmoke(directory=directory,host_directory=args.host_output_dir or str(directory),endpoint=helpers.modeling.DEFAULT_ENDPOINT)
    gate.record_path=directory/"document-tolerances.json"
    gate.record.update(client_version=__version__,source_commit=os.environ.get("GITHUB_SHA"))
    gate.record_path.write_text(json.dumps(gate.record))
    trace=NativeTrace(args.native_trace)
    def timeout():
        (directory/"timeout.json").write_text(json.dumps(dict(group_timeout_seconds=1800,full_acceptance_eligible=False)))
        os._exit(124)
    timer=threading.Timer(1800,timeout);timer.daemon=True;timer.start()
    try:run(gate,args.fixture_dir,trace)
    except BaseException as exc:
        gate.record.update(state="failed",success=False,error=dict(type=type(exc).__name__,message=str(exc)));raise
    finally:
        try:
            gate.cleanup()
            if gate.record["cleanup_errors"] or gate.checkpoint_error is not None:gate.record.update(state="failed",success=False)
            gate.record["native_trace_snapshot"]=trace.snapshot()
            gate.checkpoint("document-tolerances-final")
        finally:timer.cancel()
    require(gate.record["success"] and not gate.record["cleanup_errors"] and gate.checkpoint_error is None,"public tolerance gate or cleanup failed")


if __name__=="__main__":main()
